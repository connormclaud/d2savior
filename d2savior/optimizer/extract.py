"""Item and charm spec extraction across characters and shared stashes."""

from collections.abc import Sequence
from dataclasses import dataclass

from d2savior.core.d2s_struct import D2SStruct
from d2savior.core.enums import CharClass, EquipSlot, ItemLocation, StoredIn
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
    _SWAP_SLOTS,
    ALL_GEAR_SLOTS,
    _item_cta_bo,
    _item_levelreq,
    inactive_weapon_slots,
    parse_keep_gear,
)
from d2savior.optimizer.native import CharmSpec, ItemSpec
from d2savior.optimizer.paladin import (
    PALADIN_SPEC_INFO,
    detect_paladin_spec,
    paladin_offense_profile,
)
from d2savior.optimizer.skill_tables import exploding_arrow_fire_2x, resolve_sorc_filler_skill

_CHARM_SIZES: frozendict[str, int] = frozendict({"cm1": 1, "cm2": 2, "cm3": 3, "cs2": 3})

_SKILL_BLIZZARD = 59
_SKILL_COLD_MASTERY = 65
_SKILL_ZEAL = 106
_FLAT_ELEM_PIDS: frozenset[int] = frozenset({48, 49, 50, 51, 52, 53, 54, 55})
_ETH_SAFE_PIDS: frozenset[int] = frozenset({152, 252, 253})
_ELEMENTAL_AURA_SPECS: frozenset[str] = frozenset({"holy-fire", "holy-freeze", "holy-shock"})

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

_SIMPLE_ITEM_STAT_MAP: frozendict[int, str] = frozendict(
    {
        0: "str_bonus",
        1: "ene",
        2: "dex_bonus",
        3: "vit",
        7: "life",
        9: "mana",
        34: "dr_flat",
        35: "mdr",
        36: "pdr_pct",
        39: "fr",
        40: "max_fr",
        41: "lr",
        42: "max_lr",
        43: "cr",
        44: "max_cr",
        45: "pr",
        46: "max_pr",
        77: "pct_mana",
        80: "mf",
        91: "req_pct",
        96: "frw",
        99: "fhr",
        105: "fcr",
        127: "all_skills",
        142: "fire_abs_pct",
        187: "cold_sunder",
    }
)

_PER_LEVEL_STAT_MAP: frozendict[int, str] = frozendict(
    {216: "life_per_lvl", 217: "mana_per_lvl", 240: "mf"}
)

_PAL_SIMPLE_STAT_MAP: frozendict[int, str] = frozendict({93: "ias", 136: "cb", 60: "life_leech"})

_USEFUL_ITEM_STATS: tuple[str, ...] = (
    "all_skills",
    "sorc_skills",
    "pal_skills",
    "blizz_skills",
    "cm_skills",
    "primary_skill",
    "action_skill_bonus",
    "aura_skill_bonus",
    "off_ed",
    "flat_phys_2x",
    "flat_elem_2x",
    "cold_dmg_pct",
    "fcr",
    "fhr",
    "frw",
    "ias",
    "cb",
    "cbf",
    "pdr_pct",
    "life_leech",
    "fr",
    "lr",
    "cr",
    "pr",
    "max_fr",
    "max_lr",
    "max_cr",
    "max_pr",
    "mf",
    "life",
    "life_per_lvl",
    "mana",
    "mana_per_lvl",
    "vit",
    "ene",
    "pct_mana",
    "mdr",
    "dr_flat",
    "fire_abs_pct",
    "str_bonus",
    "dex_bonus",
)


def _classify_slot(
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


@dataclass
class _PropAcc:
    all_skills: int = 0
    sorc_skills: int = 0
    pal_skills: int = 0
    blizz_skills: int = 0
    cm_skills: int = 0
    primary_skill: int = 0
    action_skill_bonus: int = 0
    aura_skill_bonus: int = 0
    off_ed: int = 0
    flat_phys_2x: int = 0
    flat_elem_2x: int = 0
    cold_dmg_pct: int = 0
    fcr: int = 0
    fhr: int = 0
    frw: int = 0
    ias: int = 0
    cb: int = 0
    cbf: int = 0
    pdr_pct: int = 0
    life_leech: int = 0
    fr: int = 0
    lr: int = 0
    cr: int = 0
    pr: int = 0
    max_fr: int = 0
    max_lr: int = 0
    max_cr: int = 0
    max_pr: int = 0
    mf: int = 0
    life: int = 0
    life_per_lvl: int = 0
    mana: int = 0
    mana_per_lvl: int = 0
    vit: int = 0
    ene: int = 0
    pct_mana: int = 0
    mdr: int = 0
    dr_flat: int = 0
    fire_abs_pct: int = 0
    light_skills: int = 0
    str_bonus: int = 0
    dex_bonus: int = 0
    req_pct: int = 0
    defense: int = 0
    cold_sunder: int = 0

    def to_item_spec(
        self,
        name: str,
        slot: str,
        loc: str,
        req_str: int,
        req_dex: int,
        belt_slots: int = 0,
        *,
        set_group: int = 0,
        set_item_id: int = 0,
        set_bonuses: Sequence[tuple[int, ItemSpec]] = (),
        global_set_bonuses: Sequence[tuple[int, ItemSpec]] = (),
        wsm: int = 0,
        wclass: str = "",
        wep_phys_2x: int = 0,
        wep_str_pct: int = 0,
        wep_dex_pct: int = 0,
        can_zeal: bool = False,
        splash_fire: bool = False,
        splash_fire_2x: int = 0,
    ) -> ItemSpec:
        return ItemSpec(
            name=name,
            slot=slot,
            loc=loc,
            all_skills=self.all_skills,
            sorc_skills=self.sorc_skills,
            fcr=self.fcr,
            fhr=self.fhr,
            frw=self.frw,
            fr=self.fr,
            lr=self.lr,
            cr=self.cr,
            pr=self.pr,
            mf=self.mf,
            life=self.life,
            mana=self.mana,
            vit=self.vit,
            ene=self.ene,
            pct_mana=self.pct_mana,
            mdr=self.mdr,
            dr_flat=self.dr_flat,
            fire_abs_pct=self.fire_abs_pct,
            str_bonus=self.str_bonus,
            dex_bonus=self.dex_bonus,
            req_str=req_str,
            req_dex=req_dex,
            max_fr=self.max_fr,
            max_lr=self.max_lr,
            max_cr=self.max_cr,
            max_pr=self.max_pr,
            life_per_lvl=self.life_per_lvl,
            mana_per_lvl=self.mana_per_lvl,
            blizz_skills=self.blizz_skills,
            cm_skills=self.cm_skills,
            defense=self.defense,
            belt_slots=belt_slots,
            pal_skills=self.pal_skills,
            primary_skill=self.primary_skill,
            ias=self.ias,
            cb=self.cb,
            cbf=self.cbf,
            pdr_pct=self.pdr_pct,
            life_leech=self.life_leech,
            set_group=set_group,
            set_item_id=set_item_id,
            set_bonuses=list(set_bonuses),
            wsm=wsm,
            wclass=wclass,
            action_skill_bonus=self.action_skill_bonus,
            aura_skill_bonus=self.aura_skill_bonus,
            off_ed=self.off_ed,
            flat_phys_2x=self.flat_phys_2x,
            flat_elem_2x=self.flat_elem_2x,
            wep_phys_2x=wep_phys_2x,
            wep_str_pct=wep_str_pct,
            wep_dex_pct=wep_dex_pct,
            can_zeal=can_zeal,
            splash_fire=splash_fire,
            splash_fire_2x=splash_fire_2x,
            cold_dmg_pct=self.cold_dmg_pct,
            global_set_bonuses=list(global_set_bonuses),
        )

    def to_charm_spec(
        self,
        name: str,
        size: int,
        loc: str,
        unique_id: int | None,
        char_class: int = int(CharClass.SORCERESS),
    ) -> CharmSpec:
        cls_skills = self.pal_skills if char_class == int(CharClass.PALADIN) else self.sorc_skills
        return CharmSpec(
            name=name,
            size=size,
            loc=loc,
            fhr=self.fhr,
            fr=self.fr,
            lr=self.lr,
            cr=self.cr,
            pr=self.pr,
            mf=self.mf,
            life=self.life,
            mana=self.mana,
            frw=self.frw,
            light_skills=self.light_skills,
            str_bonus=self.str_bonus,
            dex_bonus=self.dex_bonus,
            skills=self.all_skills + cls_skills,
            unique_id=unique_id,
            cold_sunder=bool(self.cold_sunder) and char_class == int(CharClass.SORCERESS),
            action_skills=self.action_skill_bonus,
            aura_skills=self.aura_skill_bonus,
        )


def _apply_per_lvl_prop(
    acc: _PropAcc, pid: int, pval: int, resolver: GameDataResolver, char_level: int
) -> None:
    per_lvl_attr = _PER_LEVEL_STAT_MAP[pid]
    scaled = adjust_property_values(pid, [pval], resolver.data.get_stat(pid), char_level=char_level)
    if isinstance(scaled, int):
        setattr(acc, per_lvl_attr, getattr(acc, per_lvl_attr) + scaled)


def _apply_sorc_prop(
    acc: _PropAcc,
    pid: int,
    params: list[int],
    *,
    pval: int | None = None,
    sorc_filler_id: int | None = None,
) -> None:
    sorc_id = int(CharClass.SORCERESS)
    if pid == 83 and len(params) >= 2 and params[0] == sorc_id:
        acc.sorc_skills += params[1]
    elif pid == 331:
        acc.cold_dmg_pct += pval if pval is not None else (params[0] if params else 0)
    elif pid == 107 and len(params) >= 2:
        if params[0] == _SKILL_BLIZZARD:
            acc.blizz_skills += params[1]
        elif params[0] == _SKILL_COLD_MASTERY:
            acc.cm_skills += params[1]
        elif sorc_filler_id is not None and params[0] == sorc_filler_id:
            acc.action_skill_bonus += params[1]
    elif pid == 188 and len(params) >= 3 and params[1] == sorc_id:
        # Sorceress skill tab: 0=Fire, 1=Lightning, 2=Cold
        if params[0] == 1:
            acc.light_skills += params[2]
        elif params[0] == 2:
            acc.sorc_skills += params[2]


def _apply_paladin_skill_prop(
    acc: _PropAcc,
    pid: int,
    params: list[int],
    pal_spec: str,
    pal_primary_id: int | None,
    pal_tabs: frozenset[int],
    pal_offense: str,
) -> bool:
    pal_id = int(CharClass.PALADIN)
    split_skills = pal_offense in ("zeal", "melee")
    if pid == 83 and len(params) >= 2 and params[0] == pal_id:
        acc.pal_skills += params[1]
        return True
    if pid == 188 and len(params) >= 3 and params[1] == pal_id:
        if split_skills:
            if params[0] == 0:
                acc.action_skill_bonus += params[2]
            elif params[0] == 1:
                acc.aura_skill_bonus += params[2]
        elif params[0] in pal_tabs:
            acc.pal_skills += params[2]
        return True
    if pid == 126 and len(params) >= 2 and params[0] == 1 and pal_spec == "holy-fire":
        if split_skills:
            acc.aura_skill_bonus += params[1]
        else:
            acc.pal_skills += params[1]
        return True
    if pid == 107 and len(params) >= 2:
        if split_skills:
            if params[0] == _SKILL_ZEAL and pal_offense == "zeal":
                acc.action_skill_bonus += params[1]
            if (
                pal_spec in _ELEMENTAL_AURA_SPECS
                and pal_primary_id is not None
                and params[0] == pal_primary_id
            ):
                acc.aura_skill_bonus += params[1]
        elif pal_primary_id is not None and params[0] == pal_primary_id:
            acc.primary_skill += params[1]
        return True
    return False


def _apply_paladin_prop(
    acc: _PropAcc,
    pid: int,
    pval: int,
    params: list[int],
    resolver: GameDataResolver,
    char_level: int,
    pal_spec: str,
    pal_primary_id: int | None,
    pal_tabs: frozenset[int],
    *,
    pal_offense: str = "caster",
    is_weapon: bool = False,
) -> None:
    if pal_attr := _PAL_SIMPLE_STAT_MAP.get(pid):
        setattr(acc, pal_attr, getattr(acc, pal_attr) + pval)
    elif _apply_paladin_skill_prop(
        acc, pid, params, pal_spec, pal_primary_id, pal_tabs, pal_offense
    ):
        return
    elif pid in _FLAT_ELEM_PIDS and pal_offense in ("zeal", "melee"):
        acc.flat_elem_2x += pval
    elif pal_offense in ("zeal", "melee") and not is_weapon and pid in (17, 25):
        acc.off_ed += pval
    elif pal_offense in ("zeal", "melee") and not is_weapon and pid in (21, 22):
        acc.flat_phys_2x += pval
    elif pal_offense in ("zeal", "melee") and not is_weapon and pid in (218, 219):
        scaled = adjust_property_values(
            pid, [pval], resolver.data.get_stat(pid), char_level=char_level
        )
        if isinstance(scaled, int):
            if pid == 218:
                acc.flat_phys_2x += scaled
            else:
                acc.off_ed += scaled
    elif pid == 247:
        scaled = adjust_property_values(
            pid, [pval], resolver.data.get_stat(pid), char_level=char_level
        )
        if isinstance(scaled, int):
            acc.cb += scaled


def _compute_weapon_phys_2x(
    item: D2Item,
    props: Sequence[tuple[int, int, list[int]]],
    resolver: GameDataResolver,
    char_level: int,
    *,
    slot: str,
    code: str,
) -> tuple[int, int, int, bool]:
    """Return `(wep_phys_2x, str_pct, dex_pct, can_zeal)` for a weapon item."""
    w_info = resolver.data.get_item(code)
    if w_info is None:
        return 0, 0, 0, False

    if slot == "weapon2h":
        base_min = w_info.two_hand_mindam or w_info.mindam
        base_max = w_info.two_hand_maxdam or w_info.maxdam
    else:
        base_min = w_info.mindam
        base_max = w_info.maxdam

    ed_max = 0
    ed_min = 0
    add_min_1h = 0
    add_max_1h = 0
    add_min_2h = 0
    add_max_2h = 0
    flat_dmg = 0
    for pid, val, params in props:
        pval = params[0] if params else val
        if pid == 17:
            ed_max += pval
        elif pid == 18:
            ed_min += pval
        elif pid == 21:
            add_min_1h += pval
        elif pid == 22:
            add_max_1h += pval
        elif pid == 23:
            add_min_2h += pval
        elif pid == 24:
            add_max_2h += pval
        elif pid == 111:
            flat_dmg += pval
        elif pid in (218, 219):
            scaled = adjust_property_values(
                pid, [pval], resolver.data.get_stat(pid), char_level=char_level
            )
            if isinstance(scaled, int):
                if pid == 218:
                    add_max_1h += scaled
                    add_max_2h += scaled
                else:
                    ed_max += scaled
                    ed_min += scaled

    if ed_min == 0 and ed_max > 0:
        ed_min = ed_max

    if item.is_ethereal:
        base_min = (base_min * 3) // 2
        base_max = (base_max * 3) // 2

    add_min = add_min_2h if (slot == "weapon2h" and add_min_2h > 0) else add_min_1h
    add_max = add_max_2h if (slot == "weapon2h" and add_max_2h > 0) else add_max_1h
    eff_min = (base_min * (100 + ed_min)) // 100 + add_min + flat_dmg
    eff_max = (base_max * (100 + ed_max)) // 100 + add_max + flat_dmg

    w_type = w_info.type.lower() if w_info.type else ""
    can_zeal = bool(w_type) and resolver.is_descendant(w_type, "mele")
    return max(0, eff_min + eff_max), w_info.str_bonus, w_info.dex_bonus, can_zeal


def _apply_props_to_acc(
    acc: _PropAcc,
    props: Sequence[tuple[int, int, list[int]]],
    resolver: GameDataResolver,
    char_level: int,
    *,
    char_class: int,
    pal_spec: str,
    pal_offense: str = "caster",
    is_weapon: bool = False,
    include_defense_props: bool = False,
    sorc_filler_id: int | None = None,
) -> None:
    pal_primary_id, _, pal_tabs = PALADIN_SPEC_INFO.get(pal_spec, (None, None, frozenset({0, 1})))
    for pid, val, params in props:
        pval = params[0] if params else val
        if attr := _SIMPLE_ITEM_STAT_MAP.get(pid):
            setattr(acc, attr, getattr(acc, attr) + pval)
        elif pid in _PER_LEVEL_STAT_MAP:
            _apply_per_lvl_prop(acc, pid, pval, resolver, char_level)
        elif pid == 153 and pval > 0:
            acc.cbf = 1
        elif include_defense_props and pid == 31:
            acc.defense += pval
        elif include_defense_props and pid == 214:
            scaled = adjust_property_values(
                pid, [pval], resolver.data.get_stat(pid), char_level=char_level
            )
            if isinstance(scaled, int):
                acc.defense += scaled
        elif char_class == int(CharClass.SORCERESS):
            _apply_sorc_prop(acc, pid, params, pval=pval, sorc_filler_id=sorc_filler_id)
        elif char_class == int(CharClass.PALADIN):
            _apply_paladin_prop(
                acc,
                pid,
                pval,
                params,
                resolver,
                char_level,
                pal_spec,
                pal_primary_id,
                pal_tabs,
                pal_offense=pal_offense,
                is_weapon=is_weapon,
            )


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
    )
    tp = item.type_specific_info
    if tp and tp.defence is not None:
        acc.defense = calculate_effective_defence(tp.get_defence(), props)
    return acc


def _extract_set_bonuses(
    item: D2Item,
    resolver: GameDataResolver,
    version: int,
    char_level: int,
    *,
    char_class: int,
    pal_spec: str,
    pal_offense: str = "caster",
) -> list[tuple[int, ItemSpec]]:
    tp = item.type_specific_info
    if not (tp and tp.set_properties):
        return []
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
            pal_offense=pal_offense,
            include_defense_props=True,
        )
        if b_acc.defense != 0 or any(getattr(b_acc, attr) != 0 for attr in _USEFUL_ITEM_STATS):
            bonuses.append((req_pieces, b_acc.to_item_spec(f"{req_pieces}pc", "", "", 0, 0, 0)))
    return bonuses


def _extract_global_set_bonuses(
    set_name: str,
    resolver: GameDataResolver,
    char_level: int,
    *,
    char_class: int,
    pal_spec: str,
    pal_offense: str = "caster",
) -> list[tuple[int, ItemSpec]]:
    tiers = resolver.get_set_bonus_tiers(set_name)
    if not tiers:
        return []
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
            pal_offense=pal_offense,
            include_defense_props=True,
        )
        if b_acc.defense != 0 or any(getattr(b_acc, attr) != 0 for attr in _USEFUL_ITEM_STATS):
            bonuses.append((req_pieces, b_acc.to_item_spec(f"{req_pieces}pc", "", "", 0, 0, 0)))
    return bonuses


def _format_item_location(
    char_name: str,
    item: D2Item,
    swap_slots: tuple[EquipSlot, EquipSlot] = _SWAP_SLOTS,
) -> str:
    if item.location == ItemLocation.EQUIPPED:
        if item.position in swap_slots:
            return f"{char_name} Swap"
        return f"{char_name} Equipped"
    if item.stored_in == StoredIn.STASH:
        return f"{char_name} Stash"
    if item.stored_in == StoredIn.INVENTORY:
        return f"{char_name} Inv"
    return char_name


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
    pal_offense: str = "caster",
    set_group_ids: dict[str, int] | None,
    global_set_cache: dict[tuple[str, int], list[tuple[int, ItemSpec]]] | None = None,
) -> tuple[int, int, list[tuple[int, ItemSpec]], list[tuple[int, ItemSpec]]]:
    ext = item.ext_info
    if ext is None or ext.set_id is None:
        return 0, 0, [], []
    group_key = resolve_set_group_key(item, resolver)
    if group_key is None:
        return 0, 0, [], []
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
        pal_offense=pal_offense,
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
            pal_offense=pal_offense,
        )
        if global_set_cache is not None:
            global_set_cache[cache_key] = global_bonuses
    return group_id, ext.set_id + 1, bonuses, global_bonuses


def _is_eth_weapon_breakable(
    item: D2Item,
    w_info: object,
    props: Sequence[tuple[int, int, list[int]]],
) -> bool:
    if not item.is_ethereal:
        return False
    if getattr(w_info, "nodurability", False):
        return False
    return not any(pid in _ETH_SAFE_PIDS for pid, _, _ in props)


def _item_to_spec(
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
) -> ItemSpec | CharmSpec | None:
    if item.location == ItemLocation.SOCKET:
        return None
    if _item_levelreq(item, resolver) > char_level:
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

    classified = _classify_slot(item, resolver, char_class=char_class)
    if classified is None:
        return None
    slot, base_req_str, base_req_dex = classified
    if slot in exclude_slots:
        return None
    is_weapon = slot in ("weapon", "weapon2h")
    props = list(collect_item_properties(item, resolver=resolver, version=version))
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
    )
    tp = item.type_specific_info
    if tp and tp.defence is not None:
        acc.defense = calculate_effective_defence(tp.get_defence(), props)
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
    )

    keep_slot = skip_useful_check or slot in skip_useful_slots
    belt_slots = resolver.get_belt_rows(code) * 4 if slot == "belt" else 0
    wsm = 0
    wclass = ""
    wep_phys_2x = 0
    wep_str_pct = 0
    wep_dex_pct = 0
    can_zeal = False
    splash_fire = False
    splash_fire_2x = 0
    if is_weapon and (w_info := resolver.data.get_item(code)) is not None:
        if (
            not keep_slot
            and not allow_eth_melee
            and char_class == int(CharClass.PALADIN)
            and resolved_offense in ("zeal", "melee")
            and _is_eth_weapon_breakable(item, w_info, props)
        ):
            return None
        wsm = w_info.speed
        wclass = w_info.two_handed_wclass or w_info.wclass
        wep_phys_2x, wep_str_pct, wep_dex_pct, can_zeal = _compute_weapon_phys_2x(
            item,
            props,
            resolver,
            char_level,
            slot=slot,
            code=code,
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

    display_name = get_item_display_name(item, resolver=resolver, version=version)
    if is_weapon and item.is_ethereal and not display_name.endswith(" (eth)"):
        display_name = f"{display_name} (eth)"

    return acc.to_item_spec(
        name=display_name,
        slot=slot,
        loc=loc,
        req_str=_effective_req(base_req_str, item.is_ethereal, acc.req_pct),
        req_dex=_effective_req(base_req_dex, item.is_ethereal, acc.req_pct),
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


def _char_item_locality_rank(
    item: D2Item,
    swap_slots: tuple[EquipSlot, EquipSlot] = _SWAP_SLOTS,
) -> int:
    if item.location == ItemLocation.EQUIPPED:
        return 1 if item.position in swap_slots else 0
    if item.stored_in == StoredIn.INVENTORY:
        return 2
    if item.stored_in == StoredIn.STASH:
        return 3
    return 4


def _extract_char_specs(
    char: D2SStruct,
    *,
    is_primary: bool,
    kept_slots: frozenset[str],
    primary_inactive_slots: tuple[EquipSlot, EquipSlot],
    char_level: int,
    char_class: int,
    pal_spec: str,
    pal_offense: str,
    resolver: GameDataResolver,
    set_group_ids: dict[str, int],
    global_set_cache: dict[tuple[str, int], list[tuple[int, ItemSpec]]],
    allow_eth_melee: bool = False,
    sorc_filler_id: int | None = None,
) -> tuple[list[ItemSpec], list[CharmSpec]]:
    ver = char.version or 0x63
    char_resolver = resolver.for_version(ver)
    keep_all = kept_slots == ALL_GEAR_SLOTS
    char_swap_slots = inactive_weapon_slots(char)
    has_swap_cta = any(
        it.location == ItemLocation.EQUIPPED
        and it.position in char_swap_slots
        and _item_cta_bo(it, char_resolver, ver) is not None
        for it in char.item_list.items
    )
    char_name = char.get_char_name()
    char_items: list[tuple[int, ItemSpec]] = []
    char_charms: list[tuple[tuple[int, int, int], CharmSpec]] = []

    for it in char.item_list.items:
        is_charm = it.code_str.strip().lower() in _CHARM_SIZES
        is_active_primary_eq = (
            is_primary
            and it.location == ItemLocation.EQUIPPED
            and it.position not in primary_inactive_slots
        )
        if keep_all:
            if not (is_active_primary_eq or is_charm):
                continue
        elif (
            has_swap_cta and it.location == ItemLocation.EQUIPPED and it.position in char_swap_slots
        ):
            continue

        loc = _format_item_location(char_name, it, swap_slots=char_swap_slots)
        exclude_slots = frozenset() if is_active_primary_eq else kept_slots
        skip_useful_slots = kept_slots if is_active_primary_eq else frozenset()
        spec = _item_to_spec(
            it,
            loc,
            char_resolver,
            version=ver,
            char_level=char_level,
            char_class=char_class,
            pal_spec=pal_spec,
            pal_offense=pal_offense,
            set_group_ids=set_group_ids,
            global_set_cache=global_set_cache,
            skip_useful_slots=skip_useful_slots,
            exclude_slots=exclude_slots,
            allow_eth_melee=allow_eth_melee,
            sorc_filler_id=sorc_filler_id,
        )
        if isinstance(spec, ItemSpec):
            char_items.append((_char_item_locality_rank(it, swap_slots=char_swap_slots), spec))
        elif isinstance(spec, CharmSpec):
            sort_key = (
                (0, getattr(it, "column", 0), getattr(it, "row", 0))
                if getattr(it, "stored_in", None) == StoredIn.INVENTORY
                else (1, 0, 0)
            )
            char_charms.append((sort_key, spec))

    char_items.sort(key=lambda pair: pair[0])
    char_charms.sort(key=lambda pair: pair[0])
    return [spec for _, spec in char_items], [spec for _, spec in char_charms]


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
) -> tuple[list[ItemSpec], list[CharmSpec]]:
    """Extract class-equippable ItemSpecs and CharmSpecs across characters and shared stashes."""
    if resolver is None:
        resolver = GameDataResolver.load()

    kept_slots = parse_keep_gear(keep_equipped)
    keep_all = kept_slots == ALL_GEAR_SLOTS
    char_level = max(1, primary_char.player_stats.level or primary_char.char_level)
    char_class = primary_char.char_class
    resolved_pal_spec = (
        pal_spec
        if pal_spec is not None
        else (
            detect_paladin_spec(primary_char, left_skill=left_skill, right_skill=right_skill)
            if char_class == int(CharClass.PALADIN)
            else "leveling"
        )
    )
    resolved_pal_offense = (
        paladin_offense_profile(
            resolved_pal_spec, primary_char, left_skill=left_skill, right_skill=right_skill
        )
        if char_class == int(CharClass.PALADIN)
        else "caster"
    )
    sorc_filler_id = (
        resolve_sorc_filler_skill(
            primary_char, left_skill=left_skill, right_skill=right_skill, targets=max(1, targets)
        )
        if char_class == int(CharClass.SORCERESS)
        else None
    )
    items_out: list[ItemSpec] = []
    charms_out: list[CharmSpec] = []
    set_group_ids: dict[str, int] = {}
    global_set_cache: dict[tuple[str, int], list[tuple[int, ItemSpec]]] = {}

    primary_inactive_slots = inactive_weapon_slots(primary_char)

    ch_items, ch_charms = _extract_char_specs(
        primary_char,
        is_primary=True,
        kept_slots=kept_slots,
        primary_inactive_slots=primary_inactive_slots,
        char_level=char_level,
        char_class=char_class,
        pal_spec=resolved_pal_spec,
        pal_offense=resolved_pal_offense,
        resolver=resolver,
        set_group_ids=set_group_ids,
        global_set_cache=global_set_cache,
        allow_eth_melee=allow_eth_melee,
        sorc_filler_id=sorc_filler_id,
    )
    items_out.extend(ch_items)
    charms_out.extend(ch_charms)

    for stash in stashes:
        for idx, tab in enumerate(stash.tabs, start=1):
            if tab.items is None:
                continue
            ver = tab.item_format or 0x63
            char_resolver = resolver.for_version(ver)
            loc = f"Stash Tab {idx}"
            for it in tab.items.items:
                if keep_all and it.code_str.strip().lower() not in _CHARM_SIZES:
                    continue
                spec = _item_to_spec(
                    it,
                    loc,
                    char_resolver,
                    ver,
                    char_level,
                    char_class=char_class,
                    pal_spec=resolved_pal_spec,
                    pal_offense=resolved_pal_offense,
                    set_group_ids=set_group_ids,
                    global_set_cache=global_set_cache,
                    exclude_slots=kept_slots,
                    allow_eth_melee=allow_eth_melee,
                    sorc_filler_id=sorc_filler_id,
                )
                if isinstance(spec, ItemSpec):
                    items_out.append(spec)
                elif isinstance(spec, CharmSpec):
                    charms_out.append(spec)

    for char in extra_chars:
        ch_items, ch_charms = _extract_char_specs(
            char,
            is_primary=False,
            kept_slots=kept_slots,
            primary_inactive_slots=primary_inactive_slots,
            char_level=char_level,
            char_class=char_class,
            pal_spec=resolved_pal_spec,
            pal_offense=resolved_pal_offense,
            resolver=resolver,
            set_group_ids=set_group_ids,
            global_set_cache=global_set_cache,
            allow_eth_melee=allow_eth_melee,
            sorc_filler_id=sorc_filler_id,
        )
        items_out.extend(ch_items)
        charms_out.extend(ch_charms)

    return items_out, charms_out
