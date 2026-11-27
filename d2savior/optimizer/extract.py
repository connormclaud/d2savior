"""Item and charm spec extraction across characters and shared stashes."""

from collections.abc import Sequence

from d2savior.core.d2s_struct import D2SStruct
from d2savior.core.enums import CharClass, ItemLocation, StoredIn
from d2savior.core.item import D2Item
from d2savior.core.item_formatter import get_item_display_name
from d2savior.core.property import adjust_property_values
from d2savior.core.resolver import GameDataResolver
from d2savior.core.stash import SharedStash
from d2savior.core.stats import (
    calculate_effective_defence,
    collect_item_properties,
    resolve_set_group_key,
)
from d2savior.optimizer.common import (
    ALL_GEAR_SLOTS,
    item_levelreq,
    iter_pool_items,
    parse_keep_gear,
)
from d2savior.optimizer.extract_props import _USEFUL_ITEM_STATS, _apply_props_to_acc, _PropAcc
from d2savior.optimizer.native import CharmSpec, ItemSpec
from d2savior.optimizer.paladin import detect_paladin_spec, paladin_offense_profile
from d2savior.optimizer.skill_tables import (
    exploding_arrow_fire_2x,
    resolve_paladin_aura_id,
    resolve_sorc_cold_armor,
    resolve_sorc_filler_skill,
)

_CHARM_SIZES: frozendict[str, int] = frozendict({"cm1": 1, "cm2": 2, "cm3": 3, "cs2": 3})

_ETH_SAFE_PIDS: frozenset[int] = frozenset({152, 252, 253})

_CLASS_EXCLUSIVE_TYPES: tuple[tuple[str, int], ...] = (
    ("abow", int(CharClass.AMAZON)),
    ("ajav", int(CharClass.AMAZON)),
    ("aspe", int(CharClass.AMAZON)),
    ("orb", int(CharClass.SORCERESS)),
    ("head", int(CharClass.NECROMANCER)),
    ("ashd", int(CharClass.PALADIN)),
    ("phlm", int(CharClass.BARBARIAN)),
    ("pelt", int(CharClass.DRUID)),
    ("h2h", int(CharClass.ASSASSIN)),
    ("h2h2", int(CharClass.ASSASSIN)),
    ("cloa", int(CharClass.ASSASSIN)),
    ("grim", int(CharClass.WARLOCK)),
)

_SLOT_ANCESTORS: tuple[tuple[str, str], ...] = (
    ("belt", "belt"),
    ("boot", "boots"),
    ("glov", "gloves"),
    ("tors", "armor"),
    ("helm", "helm"),
    ("circ", "helm"),
    ("shld", "shield"),
)
_ARMOR_SLOTS: frozenset[str] = frozenset({"helm", "armor", "shield", "belt", "gloves", "boots"})


def classify_slot(
    item: D2Item, resolver: GameDataResolver, char_class: int = int(CharClass.SORCERESS)
) -> tuple[str, int, int] | None:
    info = resolver.data.get_item(item.code_str.strip().lower())
    if info is None or not info.type:
        return None

    t = info.type.lower()
    if any(
        owner != char_class and resolver.is_descendant(t, cls_t)
        for cls_t, owner in _CLASS_EXCLUSIVE_TYPES
    ):
        return None
    slot: str | None = None
    if t == "amul":
        slot = "amulet"
    elif t == "ring":
        slot = "ring"
    else:
        for anc, candidate in _SLOT_ANCESTORS:
            if resolver.is_descendant(t, anc):
                slot = candidate
                break
        if slot is None and info.item_type == "weapon":
            slot = "weapon2h" if (info.two_handed or info.one_or_two_handed) else "weapon"

    if slot is None:
        return None
    return slot, info.reqstr, info.reqdex


def _sum_weapon_prop_sources(
    sources: Sequence[Sequence[tuple[int, int, list[int]]]],
    resolver: GameDataResolver,
    char_level: int,
    *,
    slot: str,
) -> tuple[int, int, int, int, int]:
    """Return `(ed_min, ed_max, add_min, add_max, flat_dmg)` across weapon property sources."""
    ed_max = 0
    ed_min = 0
    add_min = 0
    add_max = 0
    flat_dmg = 0
    for src in sources:
        src_min_1h = 0
        src_max_1h = 0
        src_min_2h = 0
        src_max_2h = 0
        for pid, val, params in src:
            pval = params[0] if params else val
            if pid == 17:
                ed_max += pval
            elif pid == 18:
                ed_min += pval
            elif pid == 21:
                src_min_1h += pval
            elif pid == 22:
                src_max_1h += pval
            elif pid == 23:
                src_min_2h += pval
            elif pid == 24:
                src_max_2h += pval
            elif pid == 111:
                flat_dmg += pval
            elif pid in (218, 219):
                scaled = adjust_property_values(
                    pid, [pval], resolver.data.get_stat(pid), char_level=char_level
                )
                if isinstance(scaled, int):
                    if pid == 218:
                        add_max += scaled
                    else:
                        ed_max += scaled
                        ed_min += scaled
        add_min += src_min_2h if (slot == "weapon2h" and src_min_2h > 0) else src_min_1h
        add_max += src_max_2h if (slot == "weapon2h" and src_max_2h > 0) else src_max_1h

    if ed_min == 0 and ed_max > 0:
        ed_min = ed_max
    return ed_min, ed_max, add_min, add_max, flat_dmg


def _weapon_base_minmax(w_info: object, *, slot: str, is_ethereal: bool) -> tuple[int, int]:
    if slot == "weapon2h":
        base_min = getattr(w_info, "two_hand_mindam", 0) or getattr(w_info, "mindam", 0)
        base_max = getattr(w_info, "two_hand_maxdam", 0) or getattr(w_info, "maxdam", 0)
    else:
        base_min = getattr(w_info, "mindam", 0)
        base_max = getattr(w_info, "maxdam", 0)
    if is_ethereal:
        base_min = (base_min * 3) // 2
        base_max = (base_max * 3) // 2
    return base_min, base_max


def _compute_weapon_phys_2x(
    item: D2Item,
    props: Sequence[tuple[int, int, list[int]]],
    resolver: GameDataResolver,
    char_level: int,
    *,
    slot: str,
    code: str,
    version: int = 0x63,
    extra_props: Sequence[tuple[int, int, list[int]]] = (),
) -> tuple[int, int, int, bool]:
    """Return `(wep_phys_2x, str_pct, dex_pct, can_zeal)` for a weapon item."""
    w_info = resolver.data.get_item(code)
    if w_info is None:
        return 0, 0, 0, False

    tp = item.type_specific_info
    if tp is not None and (item.gem_items or extra_props):
        sources: list[Sequence[tuple[int, int, list[int]]]] = []
        if tp.property_list:
            sources.append(tp.property_list.get_parsed_properties(version, data=resolver.data))
        if tp.runeword_property_list:
            sources.append(
                tp.runeword_property_list.get_parsed_properties(version, data=resolver.data)
            )
        for gem in item.gem_items:
            sources.append(resolver.get_socket_properties(item, gem))
        if extra_props:
            sources.append(extra_props)
    else:
        sources = [props]

    ed_min, ed_max, add_min, add_max, flat_dmg = _sum_weapon_prop_sources(
        sources, resolver, char_level, slot=slot
    )
    base_min, base_max = _weapon_base_minmax(w_info, slot=slot, is_ethereal=item.is_ethereal)
    eff_min = (base_min * (100 + ed_min)) // 100 + add_min + flat_dmg
    eff_max = (base_max * (100 + ed_max)) // 100 + add_max + flat_dmg

    w_type = w_info.type.lower() if w_info.type else ""
    can_zeal = bool(w_type) and resolver.is_descendant(w_type, "mele")
    return max(0, eff_min + eff_max), w_info.str_bonus, w_info.dex_bonus, can_zeal


def _compute_item_defense(
    item: D2Item,
    props: Sequence[tuple[int, int, list[int]]],
    resolver: GameDataResolver,
    char_level: int,
) -> int:
    tp = item.type_specific_info
    if tp and tp.defence is not None:
        return calculate_effective_defence(
            tp.get_defence(), props, char_level=char_level, resolver=resolver
        )
    if any(pid in (31, 214) for pid, _, _ in props):
        return calculate_effective_defence(0, props, char_level=char_level, resolver=resolver)
    return 0


def _extract_prop_acc(
    item: D2Item,
    resolver: GameDataResolver,
    version: int,
    char_level: int,
    *,
    char_class: int = int(CharClass.SORCERESS),
    pal_spec: str = "leveling",
    pal_offense: str | None = None,
    is_weapon: bool = False,
    sorc_filler_id: int | None = None,
    sorc_armor_id: int | None = None,
    pal_aura_id: int | None = -1,
) -> _PropAcc:
    acc = _PropAcc()
    props = list(collect_item_properties(item, resolver=resolver, version=version))
    resolved_offense = (
        pal_offense
        if pal_offense is not None
        else (
            paladin_offense_profile(pal_spec) if char_class == int(CharClass.PALADIN) else "caster"
        )
    )
    _apply_props_to_acc(
        acc,
        props,
        resolver,
        char_level,
        char_class=char_class,
        pal_spec=pal_spec,
        pal_offense=resolved_offense,
        is_weapon=is_weapon,
        sorc_filler_id=sorc_filler_id,
        sorc_armor_id=sorc_armor_id,
        pal_aura_id=pal_aura_id,
    )
    acc.defense = _compute_item_defense(item, props, resolver, char_level)
    return acc


def _resolve_pal_offense(char_class: int, pal_spec: str, pal_offense: str | None) -> str:
    if pal_offense is not None:
        return pal_offense
    return paladin_offense_profile(pal_spec) if char_class == int(CharClass.PALADIN) else "caster"


def _extract_set_bonuses(
    item: D2Item,
    resolver: GameDataResolver,
    version: int,
    char_level: int,
    *,
    char_class: int,
    pal_spec: str,
    pal_offense: str | None = None,
    pal_aura_id: int | None = -1,
    sorc_armor_id: int | None = None,
    is_weapon: bool = False,
    slot: str = "",
    code: str = "",
) -> list[tuple[int, ItemSpec]]:
    tp = item.type_specific_info
    if not (tp and tp.set_properties):
        return []
    resolved_offense = _resolve_pal_offense(char_class, pal_spec, pal_offense)
    w_info = resolver.data.get_item(code) if is_weapon and code else None
    bonuses: list[tuple[int, ItemSpec]] = []
    for req_pieces, set_prop_list in enumerate(tp.set_properties, start=2):
        if set_prop_list is None:
            continue
        props = set_prop_list.get_parsed_properties(version, data=resolver.data)
        b_acc = _PropAcc()
        _apply_props_to_acc(
            b_acc,
            props,
            resolver,
            char_level,
            char_class=char_class,
            pal_spec=pal_spec,
            pal_offense=resolved_offense,
            is_weapon=is_weapon,
            include_defense_props=True,
            sorc_armor_id=sorc_armor_id,
            pal_aura_id=pal_aura_id,
        )
        if (
            is_weapon
            and char_class == int(CharClass.PALADIN)
            and resolved_offense in ("zeal", "melee")
        ):
            b_ed_min, b_ed_max, b_add_min, b_add_max, b_flat = _sum_weapon_prop_sources(
                [props], resolver, char_level, slot=slot
            )
            base_min, base_max = (
                _weapon_base_minmax(w_info, slot=slot, is_ethereal=item.is_ethereal)
                if w_info is not None
                else (0, 0)
            )
            b_acc.flat_phys_2x += (
                (base_min * b_ed_min) // 100
                + (base_max * b_ed_max) // 100
                + b_add_min
                + b_add_max
                + 2 * b_flat
            )
        if (
            b_acc.defense != 0
            or b_acc.block_pct != 0
            or b_acc.fbr != 0
            or b_acc.def_skill != 0
            or any(getattr(b_acc, attr) != 0 for attr in _USEFUL_ITEM_STATS)
        ):
            bonuses.append((req_pieces, b_acc.to_item_spec(f"{req_pieces}pc", "", "", 0, 0, 0)))
    return bonuses


def _extract_global_set_bonuses(
    set_name: str,
    resolver: GameDataResolver,
    char_level: int,
    *,
    char_class: int,
    pal_spec: str,
    pal_offense: str | None = None,
    pal_aura_id: int | None = -1,
    sorc_armor_id: int | None = None,
) -> list[tuple[int, ItemSpec]]:
    tiers = resolver.get_set_bonus_tiers(set_name)
    if not tiers:
        return []
    resolved_offense = _resolve_pal_offense(char_class, pal_spec, pal_offense)
    bonuses: list[tuple[int, ItemSpec]] = []
    for req_pieces, props in tiers:
        b_acc = _PropAcc()
        _apply_props_to_acc(
            b_acc,
            props,
            resolver,
            char_level,
            char_class=char_class,
            pal_spec=pal_spec,
            pal_offense=resolved_offense,
            include_defense_props=True,
            sorc_armor_id=sorc_armor_id,
            pal_aura_id=pal_aura_id,
        )
        if (
            b_acc.defense != 0
            or b_acc.block_pct != 0
            or b_acc.fbr != 0
            or b_acc.def_skill != 0
            or any(getattr(b_acc, attr) != 0 for attr in _USEFUL_ITEM_STATS)
        ):
            bonuses.append((req_pieces, b_acc.to_item_spec(f"{req_pieces}pc", "", "", 0, 0, 0)))
    return bonuses


def _effective_req(base_req: int, is_ethereal: bool, req_pct: int) -> int:
    if base_req <= 0:
        return 0
    adj = max(0, base_req - (10 if is_ethereal else 0))
    return max(0, (adj * (100 + req_pct)) // 100)


def _resolve_item_set_info(
    item: D2Item,
    resolver: GameDataResolver,
    version: int,
    char_level: int,
    *,
    char_class: int,
    pal_spec: str,
    pal_offense: str | None = None,
    set_group_ids: dict[str, int] | None,
    global_set_cache: dict[tuple[str, int], list[tuple[int, ItemSpec]]] | None = None,
    pal_aura_id: int | None = -1,
    sorc_armor_id: int | None = None,
    is_weapon: bool = False,
    slot: str = "",
    code: str = "",
) -> tuple[int, int, list[tuple[int, ItemSpec]], list[tuple[int, ItemSpec]]]:
    ext = item.ext_info
    if ext is None or ext.set_id is None:
        return 0, 0, [], []
    group_key = resolve_set_group_key(item, resolver)
    if group_key is None:
        return 0, 0, [], []
    resolved_offense = _resolve_pal_offense(char_class, pal_spec, pal_offense)
    ids = set_group_ids if set_group_ids is not None else {}
    group_id = ids.get(group_key)
    if group_id is None:
        group_id = len(ids) + 1
        ids[group_key] = group_id
    bonuses = _extract_set_bonuses(
        item,
        resolver,
        version,
        char_level,
        char_class=char_class,
        pal_spec=pal_spec,
        pal_offense=resolved_offense,
        pal_aura_id=pal_aura_id,
        sorc_armor_id=sorc_armor_id,
        is_weapon=is_weapon,
        slot=slot,
        code=code,
    )
    cache_key = (group_key, id(resolver.data))
    if global_set_cache is not None and cache_key in global_set_cache:
        global_bonuses = global_set_cache[cache_key]
    else:
        global_bonuses = _extract_global_set_bonuses(
            group_key,
            resolver,
            char_level,
            char_class=char_class,
            pal_spec=pal_spec,
            pal_offense=resolved_offense,
            pal_aura_id=pal_aura_id,
            sorc_armor_id=sorc_armor_id,
        )
        if global_set_cache is not None:
            global_set_cache[cache_key] = global_bonuses
    return group_id, ext.set_id + 1, bonuses, global_bonuses


def _is_eth_breakable(
    item: D2Item,
    item_info: object,
    props: Sequence[tuple[int, int, list[int]]],
) -> bool:
    if not item.is_ethereal:
        return False
    if getattr(item_info, "nodurability", False):
        return False
    return not any(pid in _ETH_SAFE_PIDS for pid, _, _ in props)


def _apply_shield_base_stats(
    acc: _PropAcc,
    slot: str,
    item_info: object | None,
    *,
    char_class: int,
    resolved_offense: str,
) -> None:
    if slot != "shield" or item_info is None:
        return
    acc.block_pct += getattr(item_info, "block", 0)
    if char_class == int(CharClass.PALADIN) and resolved_offense == "smite":
        acc.flat_phys_2x += getattr(item_info, "mindam", 0) + getattr(item_info, "maxdam", 0)


def item_to_spec(
    item: D2Item,
    loc: str,
    resolver: GameDataResolver,
    version: int,
    char_level: int,
    *,
    char_class: int = int(CharClass.SORCERESS),
    pal_spec: str = "leveling",
    pal_offense: str | None = None,
    set_group_ids: dict[str, int] | None = None,
    global_set_cache: dict[tuple[str, int], list[tuple[int, ItemSpec]]] | None = None,
    skip_useful_check: bool = False,
    skip_useful_slots: frozenset[str] = frozenset(),
    exclude_slots: frozenset[str] = frozenset(),
    allow_eth_melee: bool = False,
    sorc_filler_id: int | None = None,
    sorc_armor_id: int | None = None,
    pal_aura_id: int | None = -1,
    extra_props: Sequence[tuple[int, int, list[int]]] = (),
    extra_levelreq: int = 0,
    name_override: str | None = None,
    ignore_reqs: bool = False,
) -> ItemSpec | CharmSpec | None:
    if item.location == ItemLocation.SOCKET:
        return None
    if max(item_levelreq(item, resolver), extra_levelreq) > char_level:
        return None
    resolved_offense = (
        pal_offense
        if pal_offense is not None
        else (
            paladin_offense_profile(pal_spec) if char_class == int(CharClass.PALADIN) else "caster"
        )
    )
    code = item.code_str.strip().lower()
    if code in _CHARM_SIZES:
        acc = _extract_prop_acc(
            item,
            resolver,
            version,
            char_level,
            char_class=char_class,
            pal_spec=pal_spec,
            pal_offense=resolved_offense,
            pal_aura_id=pal_aura_id,
        )
        name = get_item_display_name(item, resolver=resolver, version=version)
        ext = item.ext_info
        unique_id = ext.unique_id if ext and ext.unique_id is not None else None
        return acc.to_charm_spec(
            name=name,
            size=_CHARM_SIZES[code],
            loc=loc,
            unique_id=unique_id,
            char_class=char_class,
        )

    classified = classify_slot(item, resolver, char_class=char_class)
    if classified is None:
        return None
    slot, base_req_str, base_req_dex = classified
    if slot in exclude_slots:
        return None
    is_weapon = slot in ("weapon", "weapon2h")
    props = list(collect_item_properties(item, resolver=resolver, version=version))
    if extra_props:
        props.extend(extra_props)
    acc = _PropAcc()
    _apply_props_to_acc(
        acc,
        props,
        resolver,
        char_level,
        char_class=char_class,
        pal_spec=pal_spec,
        pal_offense=resolved_offense,
        is_weapon=is_weapon,
        sorc_filler_id=sorc_filler_id,
        sorc_armor_id=sorc_armor_id,
        pal_aura_id=pal_aura_id,
    )
    acc.defense = _compute_item_defense(item, props, resolver, char_level)
    set_group, set_item_id, set_bonuses, global_set_bonuses = _resolve_item_set_info(
        item,
        resolver,
        version,
        char_level,
        char_class=char_class,
        pal_spec=pal_spec,
        pal_offense=resolved_offense,
        set_group_ids=set_group_ids,
        global_set_cache=global_set_cache,
        pal_aura_id=pal_aura_id,
        sorc_armor_id=sorc_armor_id,
        is_weapon=is_weapon,
        slot=slot,
        code=code,
    )

    keep_slot = skip_useful_check or slot in skip_useful_slots
    item_info = resolver.data.get_item(code)
    if (
        is_weapon
        and item_info is not None
        and item_info.type
        and char_class == int(CharClass.PALADIN)
        and resolved_offense in ("zeal", "melee")
        and resolver.is_descendant(item_info.type.lower(), "blun")
    ):
        acc.ed_undead += 50
    if not keep_slot and item_info is not None and _is_eth_breakable(item, item_info, props):
        if slot in _ARMOR_SLOTS:
            return None
        if is_weapon and not allow_eth_melee and resolved_offense in ("zeal", "melee", "smite"):
            return None
    _apply_shield_base_stats(
        acc,
        slot,
        item_info,
        char_class=char_class,
        resolved_offense=resolved_offense,
    )
    belt_slots = resolver.get_belt_rows(code) * 4 if slot == "belt" else 0
    wsm = 0
    wclass = ""
    wep_phys_2x = 0
    wep_str_pct = 0
    wep_dex_pct = 0
    can_zeal = False
    splash_fire = False
    splash_fire_2x = 0
    if is_weapon and item_info is not None:
        wsm = item_info.speed
        wclass = item_info.two_handed_wclass or item_info.wclass
        wep_phys_2x, wep_str_pct, wep_dex_pct, can_zeal = _compute_weapon_phys_2x(
            item,
            props,
            resolver,
            char_level,
            slot=slot,
            code=code,
            version=version,
            extra_props=extra_props,
        )
        exp_lvl = max(
            (params[0] if params else val for pid, val, params in props if pid == 158),
            default=0,
        )
        if exp_lvl > 0:
            splash_fire = True
            splash_fire_2x = exploding_arrow_fire_2x(exp_lvl)

    has_useful_stat = any(getattr(acc, attr) != 0 for attr in _USEFUL_ITEM_STATS)
    has_weapon_dps = (
        is_weapon
        and resolved_offense in ("zeal", "melee")
        and wep_phys_2x > 0
        and char_class == int(CharClass.PALADIN)
    )
    if not keep_slot and set_group == 0 and not has_useful_stat and not has_weapon_dps:
        return None

    display_name = (
        name_override
        if name_override is not None
        else get_item_display_name(item, resolver=resolver, version=version)
    )
    if item.is_ethereal and not display_name.endswith(" (eth)"):
        display_name = f"{display_name} (eth)"

    eff_req_str = 0 if ignore_reqs else _effective_req(base_req_str, item.is_ethereal, acc.req_pct)
    eff_req_dex = 0 if ignore_reqs else _effective_req(base_req_dex, item.is_ethereal, acc.req_pct)

    return acc.to_item_spec(
        name=display_name,
        slot=slot,
        loc=loc,
        req_str=eff_req_str,
        req_dex=eff_req_dex,
        belt_slots=belt_slots,
        set_group=set_group,
        set_item_id=set_item_id,
        set_bonuses=set_bonuses,
        global_set_bonuses=global_set_bonuses,
        wsm=wsm,
        wclass=wclass,
        wep_phys_2x=wep_phys_2x,
        wep_str_pct=wep_str_pct,
        wep_dex_pct=wep_dex_pct,
        can_zeal=can_zeal,
        splash_fire=splash_fire,
        splash_fire_2x=splash_fire_2x,
    )


def _resolve_pool_context(
    primary_char: D2SStruct,
    *,
    pal_spec: str | None,
    left_skill: int | None,
    right_skill: int | None,
    targets: int,
    char_level_override: int | None,
) -> tuple[int, int, str, str, int | None, int | None, int | None]:
    char_level = (
        char_level_override
        if char_level_override is not None
        else max(1, primary_char.player_stats.level or primary_char.char_level)
    )
    char_class = primary_char.char_class
    is_pal = char_class == int(CharClass.PALADIN)
    is_sorc = char_class == int(CharClass.SORCERESS)
    resolved_pal_spec = (
        pal_spec
        if pal_spec is not None
        else (
            detect_paladin_spec(primary_char, left_skill=left_skill, right_skill=right_skill)
            if is_pal
            else "leveling"
        )
    )
    resolved_pal_offense = (
        paladin_offense_profile(
            resolved_pal_spec, primary_char, left_skill=left_skill, right_skill=right_skill
        )
        if is_pal
        else "caster"
    )
    sorc_filler_id = (
        resolve_sorc_filler_skill(
            primary_char, left_skill=left_skill, right_skill=right_skill, targets=max(1, targets)
        )
        if is_sorc
        else None
    )
    _, _, sorc_armor_id = resolve_sorc_cold_armor(primary_char) if is_sorc else (0, 0, None)
    pal_aura_id = (
        resolve_paladin_aura_id(primary_char, resolved_pal_spec, right_skill=right_skill)
        if is_pal
        else None
    )
    return (
        char_level,
        char_class,
        resolved_pal_spec,
        resolved_pal_offense,
        sorc_filler_id,
        sorc_armor_id,
        pal_aura_id,
    )


def _charm_sort_key(
    item: D2Item, source_idx: int, *, is_stash: bool
) -> tuple[int, tuple[int, int, int]]:
    if not is_stash and getattr(item, "stored_in", None) == StoredIn.INVENTORY:
        return (source_idx, (0, getattr(item, "column", 0), getattr(item, "row", 0)))
    return (source_idx, (1, 0, 0))


def extract_pool_with_context(
    primary_char: D2SStruct,
    extra_chars: Sequence[D2SStruct] = (),
    stashes: Sequence[SharedStash] = (),
    resolver: GameDataResolver | None = None,
    *,
    pal_spec: str | None = None,
    keep_equipped: bool | str | None = False,
    allow_eth_melee: bool = False,
    left_skill: int | None = None,
    right_skill: int | None = None,
    targets: int = 1,
    char_level_override: int | None = None,
    ignore_reqs: bool = False,
) -> tuple[
    list[ItemSpec],
    list[CharmSpec],
    dict[str, int],
    dict[tuple[str, int], list[tuple[int, ItemSpec]]],
]:
    """Extract pool specs plus shared set-group ID and global set-bonus caches."""
    if resolver is None:
        resolver = GameDataResolver.load()

    kept_slots = parse_keep_gear(keep_equipped)
    keep_all = kept_slots == ALL_GEAR_SLOTS
    (
        char_level,
        char_class,
        resolved_pal_spec,
        resolved_pal_offense,
        sorc_filler_id,
        sorc_armor_id,
        pal_aura_id,
    ) = _resolve_pool_context(
        primary_char,
        pal_spec=pal_spec,
        left_skill=left_skill,
        right_skill=right_skill,
        targets=targets,
        char_level_override=char_level_override,
    )
    set_group_ids: dict[str, int] = {}
    global_set_cache: dict[tuple[str, int], list[tuple[int, ItemSpec]]] = {}
    items_ranked: list[tuple[tuple[int, int], ItemSpec]] = []
    charms_ranked: list[tuple[tuple[int, tuple[int, int, int]], CharmSpec]] = []

    for entry in iter_pool_items(
        primary_char,
        extra_chars=extra_chars,
        stashes=stashes,
        resolver=resolver,
        skip_swap_cta=True,
    ):
        is_charm = entry.item.code_str.strip().lower() in _CHARM_SIZES
        if keep_all and not (entry.is_active_primary or is_charm):
            continue
        exclude_slots = frozenset() if entry.is_active_primary else kept_slots
        skip_useful_slots = kept_slots if entry.is_active_primary else frozenset()
        spec = item_to_spec(
            entry.item,
            entry.loc,
            entry.resolver,
            version=entry.version,
            char_level=char_level,
            char_class=char_class,
            pal_spec=resolved_pal_spec,
            pal_offense=resolved_pal_offense,
            set_group_ids=set_group_ids,
            global_set_cache=global_set_cache,
            skip_useful_slots=skip_useful_slots,
            exclude_slots=exclude_slots,
            allow_eth_melee=allow_eth_melee,
            sorc_filler_id=sorc_filler_id,
            sorc_armor_id=sorc_armor_id,
            pal_aura_id=pal_aura_id,
            ignore_reqs=ignore_reqs,
        )
        if isinstance(spec, ItemSpec):
            items_ranked.append(((entry.source_idx, entry.locality_rank), spec))
        elif isinstance(spec, CharmSpec):
            charms_ranked.append(
                (_charm_sort_key(entry.item, entry.source_idx, is_stash=entry.is_stash), spec)
            )

    items_ranked.sort(key=lambda pair: pair[0])
    charms_ranked.sort(key=lambda pair: pair[0])
    return (
        [spec for _, spec in items_ranked],
        [spec for _, spec in charms_ranked],
        set_group_ids,
        global_set_cache,
    )


def extract_pool(
    primary_char: D2SStruct,
    extra_chars: Sequence[D2SStruct] = (),
    stashes: Sequence[SharedStash] = (),
    resolver: GameDataResolver | None = None,
    *,
    pal_spec: str | None = None,
    keep_equipped: bool | str | None = False,
    allow_eth_melee: bool = False,
    left_skill: int | None = None,
    right_skill: int | None = None,
    targets: int = 1,
    char_level_override: int | None = None,
    ignore_reqs: bool = False,
) -> tuple[list[ItemSpec], list[CharmSpec]]:
    """Extract class-equippable ItemSpecs and CharmSpecs across characters and shared stashes."""
    items_out, charms_out, _, _ = extract_pool_with_context(
        primary_char,
        extra_chars=extra_chars,
        stashes=stashes,
        resolver=resolver,
        pal_spec=pal_spec,
        keep_equipped=keep_equipped,
        allow_eth_melee=allow_eth_melee,
        left_skill=left_skill,
        right_skill=right_skill,
        targets=targets,
        char_level_override=char_level_override,
        ignore_reqs=ignore_reqs,
    )
    return items_out, charms_out
