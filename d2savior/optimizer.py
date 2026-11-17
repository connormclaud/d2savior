"""Python-to-Rust PyO3 build optimizer bridge for D2R Sorceress saves."""

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Never

from d2savior.core.constants import CLASS_SKILL_BASES
from d2savior.core.d2s_struct import D2SStruct
from d2savior.core.enums import CLASS_NAMES, EquipSlot, ItemLocation, StoredIn
from d2savior.core.item import D2Item
from d2savior.core.item_formatter import get_item_display_name
from d2savior.core.item_name import LongName
from d2savior.core.property import adjust_property_values
from d2savior.core.resolver import GameDataResolver
from d2savior.core.stash import SharedStash
from d2savior.core.stats import calculate_effective_defence, collect_item_properties

_MISSING_NATIVE_MSG = (
    "Optimization requires the optional native extension. "
    "Install with: pip install 'd2savior[optimize]' (or run 'make build-rust' from source)."
)


def _missing_native(*_args: object, **_kwargs: object) -> Never:
    raise RuntimeError(_MISSING_NATIVE_MSG)


if TYPE_CHECKING:
    from d2savior._native import (
        BuildConstraints,
        BuildResult,
        CharmSpec,
        ItemSpec,
        blizzard_damage,
        blizzard_damage_with_base,
        evaluate_build,
        optimize_builds,
    )

    HAS_NATIVE: bool = True
else:
    try:
        from d2savior._native import (
            BuildConstraints,
            BuildResult,
            CharmSpec,
            ItemSpec,
            blizzard_damage,
            blizzard_damage_with_base,
            evaluate_build,
            optimize_builds,
        )

        HAS_NATIVE = True
    except ImportError:
        HAS_NATIVE = False
        BuildConstraints = _missing_native
        BuildResult = _missing_native
        CharmSpec = _missing_native
        ItemSpec = _missing_native
        blizzard_damage = _missing_native
        blizzard_damage_with_base = _missing_native
        evaluate_build = _missing_native
        optimize_builds = _missing_native

_CHARM_SIZES: frozendict[str, int] = frozendict({"cm1": 1, "cm2": 2, "cm3": 3, "cs2": 3})

_SKILL_BLIZZARD = 59
_SKILL_COLD_MASTERY = 65
_BLIZZ_SYNERGY_SKILLS: tuple[int, ...] = (39, 45, 55)
_SKILL_BATTLE_ORDERS = 149

_EXCLUDED_CLASS_TYPES: tuple[str, ...] = (
    "pelt",
    "phlm",
    "ashd",
    "head",
    "grim",
    "abow",
    "ajav",
    "aspe",
    "h2h",
    "h2h2",
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


def _long_name_levelreq(
    long_name: LongName, resolver: GameDataResolver, *, is_crafted: bool
) -> int:
    reqs: list[int] = []
    for pid in (long_name.pref_1, long_name.pref_2, long_name.pref_3):
        if pid and (pref_info := resolver.get_magic_prefix(pid)):
            reqs.append(pref_info.levelreq)
    for sid in (long_name.suff_1, long_name.suff_2, long_name.suff_3):
        if sid and (suff_info := resolver.get_magic_suffix(sid)):
            reqs.append(suff_info.levelreq)
    if not reqs:
        return 0
    max_req = max(reqs)
    return max_req + 10 + 3 * len(reqs) if is_crafted else max_req


def _item_levelreq(item: D2Item, resolver: GameDataResolver) -> int:
    """Compute effective level requirement across base, unique/set, affixes, runewords, and sockets."""
    info = resolver.data.get_item(item.code_str.strip().lower())
    req = info.levelreq if info else 0

    ext = item.item_info.ext_info if item.item_info else None
    if ext is not None:
        if ext.unique_id is not None and (uniq_info := resolver.get_unique_item(ext.unique_id)):
            req = max(req, uniq_info.levelreq)
        if ext.set_id is not None and (set_info := resolver.get_set_item(ext.set_id)):
            req = max(req, set_info.levelreq)
        if ext.magic_prefix and (pref_info := resolver.get_magic_prefix(ext.magic_prefix)):
            req = max(req, pref_info.levelreq)
        if ext.magic_suffix and (suff_info := resolver.get_magic_suffix(ext.magic_suffix)):
            req = max(req, suff_info.levelreq)
        if ext.rare_name is not None:
            req = max(req, _long_name_levelreq(ext.rare_name, resolver, is_crafted=False))
        if ext.craft_name is not None:
            req = max(req, _long_name_levelreq(ext.craft_name, resolver, is_crafted=True))
        if (
            item.is_runeword
            and not item.gem_items
            and ext.rune_id
            and (rw_info := resolver.get_runeword(ext.rune_id))
        ):
            for code in rw_info.rune_codes:
                if rune_item := resolver.data.get_item(code.strip().lower()):
                    req = max(req, rune_item.levelreq)

    for gem in item.gem_items:
        req = max(req, _item_levelreq(gem, resolver))
    return req


def _classify_slot(item: D2Item, resolver: GameDataResolver) -> tuple[str, int, int] | None:
    info = resolver.data.get_item(item.code_str.strip().lower())
    if info is None or not info.type:
        return None

    t = info.type.lower()
    if any(resolver.is_descendant(t, cls_t) for cls_t in _EXCLUDED_CLASS_TYPES):
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
    blizz_skills: int = 0
    cm_skills: int = 0
    fcr: int = 0
    fhr: int = 0
    frw: int = 0
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
        self, name: str, slot: str, loc: str, req_str: int, req_dex: int, belt_slots: int = 0
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
        )

    def to_charm_spec(self, name: str, size: int, loc: str, unique_id: int | None) -> CharmSpec:
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
            skills=self.all_skills + self.sorc_skills,
            unique_id=unique_id,
            cold_sunder=bool(self.cold_sunder),
        )


def _extract_prop_acc(
    item: D2Item, resolver: GameDataResolver, version: int, char_level: int
) -> _PropAcc:
    acc = _PropAcc()
    props = list(collect_item_properties(item, resolver=resolver, version=version))
    for pid, val, params in props:
        pval = params[0] if params else val
        if attr := _SIMPLE_ITEM_STAT_MAP.get(pid):
            setattr(acc, attr, getattr(acc, attr) + pval)
        elif pid == 83 and len(params) >= 2 and params[0] == 1:
            acc.sorc_skills += params[1]
        elif pid == 107 and len(params) >= 2:
            if params[0] == _SKILL_BLIZZARD:
                acc.blizz_skills += params[1]
            elif params[0] == _SKILL_COLD_MASTERY:
                acc.cm_skills += params[1]
        elif pid == 188 and len(params) >= 3 and params[1] == 1:
            # Sorceress skill tab: 0=Fire, 1=Lightning, 2=Cold
            if params[0] == 1:
                acc.light_skills += params[2]
            elif params[0] == 2:
                acc.sorc_skills += params[2]
        elif per_lvl_attr := _PER_LEVEL_STAT_MAP.get(pid):
            scaled = adjust_property_values(
                pid, [pval], resolver.data.get_stat(pid), char_level=char_level
            )
            if isinstance(scaled, int):
                setattr(acc, per_lvl_attr, getattr(acc, per_lvl_attr) + scaled)
    tp = item.type_specific_info
    if tp and tp.defence is not None:
        acc.defense = calculate_effective_defence(tp.get_defence(), props)
    return acc


def _format_item_location(char_name: str, item: D2Item) -> str:
    if item.location == ItemLocation.EQUIPPED:
        if item.position in (EquipSlot.WEAPON_II, EquipSlot.SHIELD_II):
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


_USEFUL_ITEM_STATS: tuple[str, ...] = (
    "all_skills",
    "sorc_skills",
    "blizz_skills",
    "cm_skills",
    "fcr",
    "fhr",
    "frw",
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


def _item_to_spec(
    item: D2Item,
    loc: str,
    resolver: GameDataResolver,
    version: int,
    char_level: int,
) -> ItemSpec | CharmSpec | None:
    if item.location == ItemLocation.SOCKET:
        return None
    if _item_levelreq(item, resolver) > char_level:
        return None
    code = item.code_str.strip().lower()
    if code in _CHARM_SIZES:
        acc = _extract_prop_acc(item, resolver, version, char_level)
        name = get_item_display_name(item, resolver=resolver, version=version)
        ext = item.item_info.ext_info if item.item_info else None
        unique_id = ext.unique_id if ext and ext.unique_id is not None else None
        return acc.to_charm_spec(name=name, size=_CHARM_SIZES[code], loc=loc, unique_id=unique_id)

    classified = _classify_slot(item, resolver)
    if classified is None:
        return None
    slot, base_req_str, base_req_dex = classified
    acc = _extract_prop_acc(item, resolver, version, char_level)
    if all(getattr(acc, attr) == 0 for attr in _USEFUL_ITEM_STATS):
        return None

    belt_slots = resolver.get_belt_rows(code) * 4 if slot == "belt" else 0
    return acc.to_item_spec(
        name=get_item_display_name(item, resolver=resolver, version=version),
        slot=slot,
        loc=loc,
        req_str=_effective_req(base_req_str, item.is_ethereal, acc.req_pct),
        req_dex=_effective_req(base_req_dex, item.is_ethereal, acc.req_pct),
        belt_slots=belt_slots,
    )


def _compute_anya_bonus(char_data: D2SStruct) -> int:
    if not (char_data.quests and char_data.quests.magic == 0x216F6F57):
        return 0
    bonus = 0
    for qd in char_data.quests.qi_data:
        if len(qd.act_5) > 2 and (qd.act_5[2] & 1):
            bonus += 10
    return bonus


_SWAP_SLOTS = (EquipSlot.WEAPON_II, EquipSlot.SHIELD_II)


def _item_cta_bo(item: D2Item, resolver: GameDataResolver, version: int) -> int | None:
    """Return `bo_oskill + all_skills` if `item` grants Battle Orders (pid 97), else None."""
    bo_oskill: int | None = None
    all_skills = 0
    for pid, val, params in collect_item_properties(item, resolver=resolver, version=version):
        if pid == 97 and len(params) >= 2 and params[0] == _SKILL_BATTLE_ORDERS:
            bo_oskill = (bo_oskill or 0) + params[1]
        elif pid == 127:
            all_skills += params[0] if params else val
    return bo_oskill + all_skills if bo_oskill is not None else None


def _detect_cta_bo_bonus(
    chars: Sequence[D2SStruct],
    stashes: Sequence[SharedStash],
    resolver: GameDataResolver,
) -> int:
    """Return max Battle Orders bonus (`oskill + all_skills`) from any CTA in pool, else 4."""
    best: int | None = None

    def scan(item: D2Item, version: int) -> None:
        nonlocal best
        bonus = _item_cta_bo(item, resolver.for_version(version), version)
        if bonus is not None and (best is None or bonus > best):
            best = bonus

    for char in chars:
        ver = char.version or 0x63
        for it in char.item_list.items:
            scan(it, ver)
    for stash in stashes:
        for tab in stash.tabs:
            if tab.items is None:
                continue
            ver = tab.item_format or 0x63
            for it in tab.items.items:
                scan(it, ver)
    return best if best is not None else 4


def extract_pool(
    primary_char: D2SStruct,
    extra_chars: Sequence[D2SStruct] = (),
    stashes: Sequence[SharedStash] = (),
    resolver: GameDataResolver | None = None,
) -> tuple[list[ItemSpec], list[CharmSpec]]:
    """Extract Sorceress-equippable ItemSpecs and CharmSpecs across characters and shared stashes."""
    if resolver is None:
        resolver = GameDataResolver.load()

    char_level = max(1, primary_char.player_stats.level or primary_char.char_level)
    items_out: list[ItemSpec] = []
    charms_out: list[CharmSpec] = []

    def add_item(item: D2Item, loc: str, version: int) -> None:
        char_resolver = resolver.for_version(version)
        spec = _item_to_spec(item, loc, char_resolver, version, char_level)
        if isinstance(spec, ItemSpec):
            items_out.append(spec)
        elif isinstance(spec, CharmSpec):
            charms_out.append(spec)

    for char in (primary_char, *extra_chars):
        ver = char.version or 0x63
        char_resolver = resolver.for_version(ver)
        has_swap_cta = any(
            it.location == ItemLocation.EQUIPPED
            and it.position in _SWAP_SLOTS
            and _item_cta_bo(it, char_resolver, ver) is not None
            for it in char.item_list.items
        )
        char_name = char.get_char_name()
        char_charms: list[tuple[tuple[int, int, int], CharmSpec]] = []
        for it in char.item_list.items:
            if has_swap_cta and it.location == ItemLocation.EQUIPPED and it.position in _SWAP_SLOTS:
                continue
            loc = _format_item_location(char_name, it)
            spec = _item_to_spec(it, loc, char_resolver, version=ver, char_level=char_level)
            if isinstance(spec, ItemSpec):
                items_out.append(spec)
            elif isinstance(spec, CharmSpec):
                sort_key = (
                    (0, getattr(it, "column", 0), getattr(it, "row", 0))
                    if getattr(it, "stored_in", None) == StoredIn.INVENTORY
                    else (1, 0, 0)
                )
                char_charms.append((sort_key, spec))
        char_charms.sort(key=lambda pair: pair[0])
        charms_out.extend(spec for _, spec in char_charms)

    for stash in stashes:
        for idx, tab in enumerate(stash.tabs, start=1):
            if tab.items is None:
                continue
            ver = tab.item_format or 0x63
            loc = f"Stash Tab {idx}"
            for it in tab.items.items:
                add_item(it, loc, ver)

    return items_out, charms_out


BUILD_PRESET_ALIASES: frozendict[str, tuple[str, ...]] = frozendict(
    {
        "all": ("base", "mf-speed", "mf-pure", "tz", "max-res"),
        "base": ("base",),
        "mf": ("mf-speed", "mf-pure"),
        "mf-speed": ("mf-speed",),
        "mf-pure": ("mf-pure",),
        "tz": ("tz",),
        "power": ("tz",),
        "max-res": ("max-res",),
    }
)

BUILD_CHOICES: tuple[str, ...] = tuple(BUILD_PRESET_ALIASES.keys())


def _extract_blizz_base_skills(char_data: D2SStruct) -> tuple[int, int, int]:
    """Return (blizz_base_lvl, blizz_syn_pts, cm_base_lvl) or (20, 54, 20) fallback."""
    skills = char_data.skills.skill_levels if char_data.skills else ()
    sorc_base = CLASS_SKILL_BASES[1]
    if len(skills) >= 30:
        blizz_base = skills[_SKILL_BLIZZARD - sorc_base]
        if blizz_base > 0:
            syn_pts = sum(skills[sid - sorc_base] for sid in _BLIZZ_SYNERGY_SKILLS)
            cm_base = skills[_SKILL_COLD_MASTERY - sorc_base]
            return blizz_base, syn_pts, cm_base
    return 20, 54, 20


def _build_preset_map(
    char_data: D2SStruct,
    max_charm_slots: int = 23,
    limit: int = 3,
    bo_base_bonus: int = 4,
) -> dict[str, tuple[str, BuildConstraints]]:
    base_life = char_data.player_stats.max_life
    base_mana = char_data.player_stats.max_mana
    base_hell_res = -100 + _compute_anya_bonus(char_data)
    blizz_base_lvl, blizz_syn_pts, cm_base_lvl = _extract_blizz_base_skills(char_data)
    common = {
        "base_life": base_life,
        "base_mana": base_mana,
        "base_hell_res": base_hell_res,
        "base_str": char_data.player_stats.strength,
        "base_dex": char_data.player_stats.dexterity,
        "bo_base_bonus": bo_base_bonus,
        "max_charm_slots": max_charm_slots,
        "limit": limit,
        "blizz_base_lvl": blizz_base_lvl,
        "blizz_syn_pts": blizz_syn_pts,
        "cm_base_lvl": cm_base_lvl,
    }
    return {
        "base": (
            "1. 0% MF Base Hunting (105% FCR, 86% FHR, 75% All Res)",
            BuildConstraints(
                allow_mf=False,
                min_fcr=105,
                min_fhr=86,
                min_fr=75,
                min_lr=75,
                min_cr=75,
                min_pr=75,
                mode="power",
                **common,
            ),
        ),
        "mf-speed": (
            "2A. Max MF & Boss Farm — Speed (105% FCR, 60% FHR, 75% F/L/C)",
            BuildConstraints(
                allow_mf=True,
                min_fcr=105,
                min_fhr=60,
                min_fr=75,
                min_lr=75,
                min_cr=75,
                min_pr=0,
                mode="mf",
                **common,
            ),
        ),
        "mf-pure": (
            "2B. Max MF & Boss Farm — Pure MF (63% FCR, 60% FHR, 75% F/L/C)",
            BuildConstraints(
                allow_mf=True,
                min_fcr=63,
                min_fhr=60,
                min_fr=75,
                min_lr=75,
                min_cr=75,
                min_pr=0,
                mode="mf",
                **common,
            ),
        ),
        "tz": (
            "3. Max Power & Terror Zones (105% FCR, 86% FHR, 75% All Res)",
            BuildConstraints(
                allow_mf=True,
                min_fcr=105,
                min_fhr=86,
                min_fr=75,
                min_lr=75,
                min_cr=75,
                min_pr=75,
                mode="power",
                **common,
            ),
        ),
        "max-res": (
            "4. Max Resist (63% FCR, 60% FHR, Max All Res)",
            BuildConstraints(
                allow_mf=True,
                min_fcr=63,
                min_fhr=60,
                min_fr=75,
                min_lr=75,
                min_cr=75,
                min_pr=75,
                mode="max-res",
                **common,
            ),
        ),
    }


def validate_sorceress(char_data: D2SStruct) -> None:
    """Validate that a parsed character is a Sorceress."""
    if char_data.char_class != 1:
        cls_name = (
            CLASS_NAMES[char_data.char_class]
            if 0 <= char_data.char_class < len(CLASS_NAMES)
            else f"class {char_data.char_class}"
        )
        raise ValueError(
            f"Character '{char_data.get_char_name()}' is {cls_name}, expected Sorceress"
        )


def select_sorc_presets(
    char_data: D2SStruct,
    build: str = "all",
    max_charm_slots: int = 23,
    limit: int = 3,
    extra_chars: Sequence[D2SStruct] = (),
    stashes: Sequence[SharedStash] = (),
    resolver: GameDataResolver | None = None,
    bo_base_bonus: int | None = None,
) -> list[tuple[str, BuildConstraints]]:
    """Select one or more Sorceress build preset profiles by name."""
    validate_sorceress(char_data)
    keys = BUILD_PRESET_ALIASES.get(build.lower())
    if keys is None:
        valid = ", ".join(BUILD_CHOICES)
        raise ValueError(f"Unknown build preset '{build}'; expected one of: {valid}")
    if bo_base_bonus is None:
        res_obj = resolver if resolver is not None else GameDataResolver.load()
        bo_base_bonus = _detect_cta_bo_bonus((char_data, *extra_chars), stashes, res_obj)
    presets = _build_preset_map(
        char_data,
        max_charm_slots=max_charm_slots,
        limit=limit,
        bo_base_bonus=bo_base_bonus,
    )
    return [presets[k] for k in keys]


def _charm_key(c: CharmSpec) -> tuple[object, ...]:
    """Return a hashable value-equality key for CharmSpec (PyO3 class lacks __eq__)."""
    return (
        c.name,
        c.size,
        c.loc,
        c.fhr,
        c.fr,
        c.lr,
        c.cr,
        c.pr,
        c.mf,
        c.life,
        c.mana,
        c.frw,
        c.light_skills,
        c.str_bonus,
        c.dex_bonus,
        c.skills,
        c.unique_id,
        c.cold_sunder,
    )


def _is_inv_loc(loc: str) -> bool:
    """Return True when loc refers to a character's inventory."""
    return loc == "inv" or loc.endswith(" Inv")


def format_build_report(
    title: str,
    results: Sequence[BuildResult],
    charms: Sequence[CharmSpec] = (),
) -> str:
    """Format BuildResult options into a human-readable report."""
    lines = [f"=== {title} ==="]
    if not results:
        lines.append("  No loadout found matching all constraints.")
        return "\n".join(lines)

    for idx, res in enumerate(results, start=1):
        lines.append(f"Option #{idx} (evaluated {res.evaluated_candidates} pruned sets):")
        lines.append(
            f"  Skills: +{res.skills} | Blizz Avg: {res.blizz_avg:.0f} | CM: {res.cm_pierce}%"
        )
        lines.append(
            f"  FCR: {res.fcr}% (BP {res.fcr_bp}%) | FHR: {res.fhr}% (BP {res.fhr_bp}%) | FRW: {res.frw}% | MF: {res.mf}%"
        )
        lines.append(
            f"  Hell Res: F:{res.fr}%({res.fr_raw}) L:{res.lr}%({res.lr_raw}) C:{res.cr}%({res.cr_raw}) P:{res.pr}%({res.pr_raw})"
        )
        lines.append(
            f"  Life: {res.life_no_bo} (BO lvl {res.bo_lvl}: {res.life_bo}) | Mana (BO): {res.mana_bo} | Charm slots: {res.charm_slots}"
        )
        for it in res.items:
            loc_str = f" ({it.loc})" if it.loc else ""
            lines.append(f"    - {it.slot:8s}: {it.name}{loc_str}")
        inv_loc = next((c.loc for c in (*charms, *res.charms) if _is_inv_loc(c.loc)), None)
        inv_charms = [c for c in charms if c.loc == inv_loc] if inv_loc is not None else []
        if res.charms or inv_charms:
            kept_counts = Counter(
                _charm_key(c) for c in res.charms if inv_loc is not None and c.loc == inv_loc
            )
            remove: list[CharmSpec] = []
            keep: list[CharmSpec] = []
            for c in inv_charms:
                key = _charm_key(c)
                if kept_counts[key] > 0:
                    kept_counts[key] -= 1
                    keep.append(c)
                else:
                    remove.append(c)
            for c in res.charms:
                if inv_loc is not None and c.loc == inv_loc:
                    key = _charm_key(c)
                    if kept_counts[key] > 0:
                        kept_counts[key] -= 1
                        keep.append(c)
            add = [c for c in res.charms if c.loc != inv_loc]
            remove_str = ", ".join(c.name for c in remove) if remove else "none"
            keep_str = ", ".join(c.name for c in keep) if keep else "none"
            add_str = (
                ", ".join(f"{c.name} [{c.loc}]" if c.loc else c.name for c in add)
                if add
                else "none"
            )
            lines.append("    - Charms  :")
            lines.append(f"      - remove: {remove_str}")
            lines.append(f"      - keep  : {keep_str}")
            lines.append(f"      - add   : {add_str}")
    return "\n".join(lines)


__all__ = [
    "BUILD_CHOICES",
    "BUILD_PRESET_ALIASES",
    "HAS_NATIVE",
    "BuildConstraints",
    "BuildResult",
    "CharmSpec",
    "ItemSpec",
    "blizzard_damage",
    "blizzard_damage_with_base",
    "evaluate_build",
    "extract_pool",
    "format_build_report",
    "optimize_builds",
    "select_sorc_presets",
    "validate_sorceress",
]
