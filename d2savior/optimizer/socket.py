"""Larzuk Socket Quest optimizer across gear socketing and runeword bases."""

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, cast

from d2savior.core.constants import DIFFICULTY_NAMES
from d2savior.core.d2s_struct import D2SStruct
from d2savior.core.enums import CharClass, ItemLocation, ItemQuality
from d2savior.core.item import D2Item
from d2savior.core.item_formatter import _format_summary_properties, get_item_display_name
from d2savior.core.models import RuneWordInfo
from d2savior.core.resolver import GameDataResolver
from d2savior.core.stash import (
    GEM_CODES,
    RUNE_CODES,
    STASH_TAB_TYPE_ADVANCED,
    SharedStash,
)
from d2savior.core.stats import collect_item_properties, normalize_damage_props
from d2savior.optimizer.common import (
    ALL_GEAR_SLOTS,
    _item_cta_bo,
    _item_levelreq,
    inactive_weapon_slots,
    parse_keep_gear,
)
from d2savior.optimizer.extract import (
    _char_item_locality_rank,
    _classify_slot,
    _extract_pool_with_context,
    _format_item_location,
    _item_to_spec,
)
from d2savior.optimizer.native import (
    BuildConstraints,
    BuildResult,
    CharmSpec,
    ItemSpec,
    TargetTypeStr,
    optimize_builds,
)
from d2savior.optimizer.paladin import (
    _build_paladin_baseline,
    _probe_paladin_opt1,
    build_paladin_preset_constraints,
    detect_paladin_spec,
    paladin_offense_profile,
)
from d2savior.optimizer.presets import ConstraintOverrides, resolve_build_expr
from d2savior.optimizer.skill_tables import resolve_paladin_aura_id, resolve_sorc_filler_skill
from d2savior.optimizer.sorc import select_sorc_presets

_SOCKETABLE_SLOTS: frozenset[str] = frozenset({"helm", "armor", "shield", "weapon", "weapon2h"})
_JEWEL_CODES: frozenset[str] = frozenset({"jew", "cjw"})
_RUNE_CODES_STR: tuple[str, ...] = tuple(f"r{i:02d}" for i in range(1, 34))
_THEORETICAL_GEM_CODES: tuple[str, ...] = ("gpv", "gpb", "gpg", "gpr", "gpw", "gpy", "skz")

_COMPARE_POS_STATS: tuple[str, ...] = (
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
    "flat_fire_2x",
    "flat_elem_2x",
    "cold_dmg_pct",
    "ds",
    "cs_oskill",
    "ow",
    "ed_demon",
    "ed_undead",
    "psn_dps_2x",
    "pierce",
    "ctc_static_pct",
    "ctc_venom_dps_2x",
    "ctc_decrep_pct",
    "ctc_lifetap_pct",
    "ctc_orb_dmg_2x",
    "ar",
    "ar_pct",
    "itd",
    "target_def_pct",
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
    "mana",
    "life_per_lvl",
    "mana_per_lvl",
    "vit",
    "ene",
    "pct_life",
    "pct_mana",
    "mdr",
    "dr_flat",
    "fire_abs_pct",
    "str_bonus",
    "dex_bonus",
    "defense",
    "belt_slots",
    "wep_phys_2x",
)


def get_socket_quest_status(char_data: D2SStruct) -> list[tuple[str, str]]:
    """Return `(difficulty_name, status)` for Larzuk's 'Siege on Harrogath' quest."""
    quests = char_data.quests
    has_quests = bool(quests and quests.magic == 0x216F6F57)
    out: list[tuple[str, str]] = []
    for diff_idx, diff_name in enumerate(DIFFICULTY_NAMES):
        status = "Locked"
        if has_quests and quests is not None and diff_idx < len(quests.qi_data):
            qd = quests.qi_data[diff_idx]
            w = qd.act_5[0] if qd.act_5 else 0
            if w & 1:
                status = "Used"
            elif w & 2:
                status = "Unclaimed"
        out.append((diff_name, status))
    return out


def find_unclaimed_socket_quests(chars: Sequence[D2SStruct]) -> list[tuple[str, str]]:
    """Return `(char_name, difficulty_name)` for characters with an unclaimed socket quest."""
    unclaimed: list[tuple[str, str]] = []
    for ch in chars:
        name = ch.get_char_name()
        for diff_name, status in get_socket_quest_status(ch):
            if status == "Unclaimed":
                unclaimed.append((name, diff_name))
    return unclaimed


def get_larzuk_socket_range(item: D2Item, resolver: GameDataResolver) -> tuple[int, int]:
    """Return `(min_sockets, max_sockets)` Larzuk can add to `item`, or `(0, 0)` if ineligible."""
    if (
        item.is_socketed
        or item.is_simple
        or item.is_ear
        or item.is_runeword
        or item.is_disabled
        or item.location == ItemLocation.SOCKET
    ):
        return (0, 0)

    ilvl = item.ext_info.drop_level if item.ext_info else 99
    max_sock = resolver.get_max_sockets(item.code_str, ilvl)
    if max_sock <= 0:
        return (0, 0)

    quality = item.quality()
    if quality in (ItemQuality.LOW, ItemQuality.NORMAL, ItemQuality.HIGH):
        return (max_sock, max_sock)
    if quality == ItemQuality.MAGIC:
        return (1, min(2, max_sock))
    if quality in (ItemQuality.SET, ItemQuality.RARE, ItemQuality.UNIQUE, ItemQuality.CRAFTED):
        return (1, 1)
    return (0, 0)


@dataclass(frozen=True, slots=True)
class SocketableOption:
    """A gem, rune, or jewel candidate that can be placed into a single socket."""

    label: str
    code: str
    loc: str
    levelreq: int
    owned: bool
    is_jewel: bool
    jewel_props: tuple[tuple[int, int, tuple[int, ...]], ...] = ()

    def props_for_item(
        self, parent_item: D2Item, resolver: GameDataResolver
    ) -> list[tuple[int, int, list[int]]]:
        """Return `(prop_id, val, params)` granted by this socketable inside `parent_item`."""
        if self.is_jewel:
            return [(pid, val, list(params)) for pid, val, params in self.jewel_props]
        return resolver.get_socket_properties_for_code(parent_item, self.code)


@dataclass(frozen=True, slots=True)
class _CandidateItem:
    """An eligible unsocketed item discovered in the character/stash pool."""

    item: D2Item
    base_name: str
    loc: str
    slot: str
    version: int
    resolver: GameDataResolver
    sockets_range: tuple[int, int]
    locality_rank: int
    base_spec: ItemSpec | None


@dataclass(frozen=True, slots=True)
class SocketCandidateVariant:
    """A concrete post-Larzuk item + socket filler or runeword `ItemSpec`."""

    item_name: str
    item_loc: str
    slot: str
    kind: str  # "socket" or "runeword"
    action_label: str
    sockets_range: tuple[int, int]
    owned: bool
    missing_runes: tuple[str, ...]
    spec: ItemSpec


@dataclass(frozen=True, slots=True)
class SocketUpgradeResult:
    """Evaluated socket-quest candidate for one preset."""

    variant: SocketCandidateVariant
    baseline: BuildResult | None
    result: BuildResult
    unlocked_feasibility: bool
    score_key: tuple[int, ...]
    extra_key: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class PresetSocketReport:
    """Socket quest evaluation results for a single build preset."""

    title: str
    mode: str
    offense: str
    has_aura: bool
    diff_name: str
    baseline: BuildResult | None
    candidates: list[SocketUpgradeResult]


@dataclass(frozen=True, slots=True)
class SocketQuestReport:
    """Full socket quest optimization report across all evaluated presets."""

    char_name: str
    char_class_name: str
    char_level: int
    diff_name: str
    quest_status: list[tuple[str, str]]
    other_unclaimed: list[tuple[str, str]]
    owned_rune_types: int
    owned_gem_types: int
    owned_jewel_count: int
    theoretical: bool
    eligible_item_count: int
    presets: list[PresetSocketReport]


def _item_props_key(
    props: Sequence[tuple[int, int, list[int]]],
) -> tuple[tuple[int, int, tuple[int, ...]], ...]:
    return tuple((pid, val, tuple(params)) for pid, val, params in props)


def _format_jewel_label(item: D2Item, resolver: GameDataResolver, version: int) -> str:
    base_title = get_item_display_name(item, resolver=resolver, version=version)
    props = collect_item_properties(
        item, resolver=resolver, version=version, normalize_source=normalize_damage_props
    )
    prop_strs = _format_summary_properties(props, resolver=resolver, version=version)
    if prop_strs:
        return f"{base_title} ({', '.join(prop_strs)})"
    return base_title


def _record_socketable_item(
    item: D2Item,
    loc: str,
    rank: int,
    ver: int,
    ver_res: GameDataResolver,
    *,
    count: int,
    rune_counts: Counter[str],
    gem_counts: Counter[str],
    code_locs: dict[str, tuple[int, str]],
    jewel_map: dict[tuple[object, ...], tuple[int, SocketableOption]],
) -> None:
    if item.location == ItemLocation.SOCKET:
        return
    tn = item.type_name
    code = item.code_str.strip().lower()
    if tn in RUNE_CODES or code in _RUNE_CODES_STR:
        rune_counts[code] += count
        prev = code_locs.get(code)
        if prev is None or rank < prev[0]:
            code_locs[code] = (rank, loc)
    elif tn in GEM_CODES:
        gem_counts[code] += count
        prev = code_locs.get(code)
        if prev is None or rank < prev[0]:
            code_locs[code] = (rank, loc)
    elif code in _JEWEL_CODES:
        tp = item.type_specific_info
        raw_props = (
            tp.property_list.get_parsed_properties(ver, data=ver_res.data)
            if tp and tp.property_list
            else []
        )
        if not raw_props:
            return
        props_key = _item_props_key(raw_props)
        lvlreq = _item_levelreq(item, ver_res)
        dedup_key = (props_key, lvlreq)
        prev_j = jewel_map.get(dedup_key)
        if prev_j is None or rank < prev_j[0]:
            label = _format_jewel_label(item, ver_res, ver)
            opt = SocketableOption(
                label=label,
                code=code,
                loc=loc,
                levelreq=lvlreq,
                owned=True,
                is_jewel=True,
                jewel_props=props_key,
            )
            jewel_map[dedup_key] = (rank, opt)


def _scan_char_socketables(
    primary_char: D2SStruct,
    extra_chars: Sequence[D2SStruct],
    resolver: GameDataResolver,
    *,
    rune_counts: Counter[str],
    gem_counts: Counter[str],
    code_locs: dict[str, tuple[int, str]],
    jewel_map: dict[tuple[object, ...], tuple[int, SocketableOption]],
) -> int:
    jewel_count = 0
    for is_primary, ch in [(True, primary_char), *((False, c) for c in extra_chars)]:
        ver = ch.version or 0x63
        ver_res = resolver.for_version(ver)
        char_name = ch.get_char_name()
        swap_slots = inactive_weapon_slots(ch)
        for it in ch.item_list.items:
            if it.location in (ItemLocation.EQUIPPED, ItemLocation.SOCKET):
                continue
            if it.code_str.strip().lower() in _JEWEL_CODES:
                jewel_count += 1
            loc = _format_item_location(char_name, it, swap_slots=swap_slots)
            rank = (0 if is_primary else 20) + _char_item_locality_rank(it, swap_slots=swap_slots)
            _record_socketable_item(
                it,
                loc,
                rank,
                ver,
                ver_res,
                count=1,
                rune_counts=rune_counts,
                gem_counts=gem_counts,
                code_locs=code_locs,
                jewel_map=jewel_map,
            )
    return jewel_count


def _scan_stash_socketables(
    stashes: Sequence[SharedStash],
    resolver: GameDataResolver,
    *,
    rune_counts: Counter[str],
    gem_counts: Counter[str],
    code_locs: dict[str, tuple[int, str]],
    jewel_map: dict[tuple[object, ...], tuple[int, SocketableOption]],
) -> int:
    jewel_count = 0
    for stash in stashes:
        for idx, tab in enumerate(stash.tabs, start=1):
            if tab.items is None:
                continue
            ver = tab.item_format or 0x63
            ver_res = resolver.for_version(ver)
            loc = f"Stash Tab {idx}"
            is_adv = tab.tab_type == STASH_TAB_TYPE_ADVANCED
            for it in tab.items.items:
                cnt = it.stash_stack_size if is_adv else 1
                if is_adv and cnt <= 0:
                    continue
                if it.code_str.strip().lower() in _JEWEL_CODES:
                    jewel_count += 1
                _record_socketable_item(
                    it,
                    loc,
                    10 + idx,
                    ver,
                    ver_res,
                    count=cnt,
                    rune_counts=rune_counts,
                    gem_counts=gem_counts,
                    code_locs=code_locs,
                    jewel_map=jewel_map,
                )
    return jewel_count


def extract_socketables(
    primary_char: D2SStruct,
    extra_chars: Sequence[D2SStruct] = (),
    stashes: Sequence[SharedStash] = (),
    resolver: GameDataResolver | None = None,
    *,
    theoretical: bool = False,
) -> tuple[list[SocketableOption], Counter[str], int, int]:
    """Collect owned (and optionally theoretical) gems, runes, and jewels."""
    if resolver is None:
        resolver = GameDataResolver.load()

    rune_counts: Counter[str] = Counter()
    gem_counts: Counter[str] = Counter()
    code_locs: dict[str, tuple[int, str]] = {}
    jewel_map: dict[tuple[object, ...], tuple[int, SocketableOption]] = {}

    jewel_count = _scan_char_socketables(
        primary_char,
        extra_chars,
        resolver,
        rune_counts=rune_counts,
        gem_counts=gem_counts,
        code_locs=code_locs,
        jewel_map=jewel_map,
    )
    jewel_count += _scan_stash_socketables(
        stashes,
        resolver,
        rune_counts=rune_counts,
        gem_counts=gem_counts,
        code_locs=code_locs,
        jewel_map=jewel_map,
    )

    options: list[SocketableOption] = []
    for code, count in sorted({**rune_counts, **gem_counts}.items()):
        if count <= 0:
            continue
        info = resolver.get_item(code)
        label = resolver.get_localized_item_name(code, fallback=info.name if info else code)
        options.append(
            SocketableOption(
                label=label,
                code=code,
                loc=code_locs[code][1],
                levelreq=info.levelreq if info else 0,
                owned=True,
                is_jewel=False,
            )
        )

    options.extend(opt for _, opt in sorted(jewel_map.values(), key=lambda p: (p[0], p[1].label)))

    if theoretical:
        owned_codes = set(rune_counts) | set(gem_counts)
        for code in (*_THEORETICAL_GEM_CODES, *_RUNE_CODES_STR):
            if code in owned_codes or (info := resolver.get_item(code)) is None:
                continue
            label = resolver.get_localized_item_name(code, fallback=info.name)
            options.append(
                SocketableOption(
                    label=label,
                    code=code,
                    loc="Theoretical",
                    levelreq=info.levelreq,
                    owned=False,
                    is_jewel=False,
                )
            )

    return options, rune_counts, len(gem_counts), jewel_count


def _candidate_dedup_key(
    it: D2Item,
    display_name: str,
    sock_range: tuple[int, int],
    ver_res: GameDataResolver,
    ver: int,
) -> tuple[object, ...]:
    base_props = collect_item_properties(it, resolver=ver_res, version=ver)
    tp = it.type_specific_info
    defence = tp.get_defence() if tp and tp.defence is not None else 0
    quality = it.quality()
    code = it.code_str.strip().lower()
    if quality in (ItemQuality.LOW, ItemQuality.NORMAL, ItemQuality.HIGH):
        return ("base", code, it.is_ethereal, sock_range, defence, _item_props_key(base_props))
    return (
        "magic+",
        display_name,
        code,
        it.is_ethereal,
        quality,
        sock_range,
        defence,
        _item_props_key(base_props),
    )


def _consider_candidate_item(
    it: D2Item,
    loc: str,
    rank: int,
    ver: int,
    ver_res: GameDataResolver,
    *,
    is_active_primary: bool,
    keep_all: bool,
    kept_slots: frozenset[str],
    char_level: int,
    char_class: int,
    pal_spec: str,
    pal_offense: str,
    set_group_ids: dict[str, int],
    global_set_cache: dict[tuple[str, int], list[tuple[int, ItemSpec]]],
    sorc_filler_id: int | None,
    pal_aura_id: int | None,
    dedup: dict[tuple[object, ...], _CandidateItem],
) -> None:
    if it.location == ItemLocation.SOCKET or (keep_all and not is_active_primary):
        return
    if _item_levelreq(it, ver_res) > char_level:
        return
    sock_range = get_larzuk_socket_range(it, ver_res)
    if sock_range[1] <= 0:
        return
    classified = _classify_slot(it, ver_res, char_class=char_class)
    if classified is None:
        return
    slot, _, _ = classified
    if slot not in _SOCKETABLE_SLOTS or (not is_active_primary and slot in kept_slots):
        return

    display_name = get_item_display_name(it, resolver=ver_res, version=ver)
    d_key = _candidate_dedup_key(it, display_name, sock_range, ver_res, ver)
    prev = dedup.get(d_key)
    if prev is not None and rank >= prev.locality_rank:
        return

    base_spec_raw = _item_to_spec(
        it,
        loc,
        ver_res,
        ver,
        char_level,
        char_class=char_class,
        pal_spec=pal_spec,
        pal_offense=pal_offense,
        set_group_ids=set_group_ids,
        global_set_cache=global_set_cache,
        skip_useful_check=True,
        sorc_filler_id=sorc_filler_id,
        pal_aura_id=pal_aura_id,
    )
    dedup[d_key] = _CandidateItem(
        item=it,
        base_name=display_name,
        loc=loc,
        slot=slot,
        version=ver,
        resolver=ver_res,
        sockets_range=sock_range,
        locality_rank=rank,
        base_spec=base_spec_raw if isinstance(base_spec_raw, ItemSpec) else None,
    )


def _collect_eligible_items(
    primary_char: D2SStruct,
    extra_chars: Sequence[D2SStruct],
    stashes: Sequence[SharedStash],
    resolver: GameDataResolver,
    *,
    kept_slots: frozenset[str],
    pal_spec: str,
    pal_offense: str,
    set_group_ids: dict[str, int],
    global_set_cache: dict[tuple[str, int], list[tuple[int, ItemSpec]]],
    sorc_filler_id: int | None,
    pal_aura_id: int | None,
) -> list[_CandidateItem]:
    """Find deduplicated, class-equippable, unsocketed items eligible for Larzuk."""
    char_level = max(1, primary_char.player_stats.level or primary_char.char_level)
    char_class = primary_char.char_class
    keep_all = kept_slots == ALL_GEAR_SLOTS
    primary_inactive = inactive_weapon_slots(primary_char)
    dedup: dict[tuple[object, ...], _CandidateItem] = {}

    common_kwargs = {
        "keep_all": keep_all,
        "kept_slots": kept_slots,
        "char_level": char_level,
        "char_class": char_class,
        "pal_spec": pal_spec,
        "pal_offense": pal_offense,
        "set_group_ids": set_group_ids,
        "global_set_cache": global_set_cache,
        "sorc_filler_id": sorc_filler_id,
        "pal_aura_id": pal_aura_id,
        "dedup": dedup,
    }

    for is_primary, ch in [(True, primary_char), *((False, c) for c in extra_chars)]:
        ver = ch.version or 0x63
        ver_res = resolver.for_version(ver)
        char_name = ch.get_char_name()
        swap_slots = inactive_weapon_slots(ch)
        has_swap_cta = any(
            it.location == ItemLocation.EQUIPPED
            and it.position in swap_slots
            and _item_cta_bo(it, ver_res, ver) is not None
            for it in ch.item_list.items
        )
        for it in ch.item_list.items:
            if has_swap_cta and it.location == ItemLocation.EQUIPPED and it.position in swap_slots:
                continue
            is_active_primary = (
                is_primary
                and it.location == ItemLocation.EQUIPPED
                and it.position not in primary_inactive
            )
            loc = _format_item_location(char_name, it, swap_slots=swap_slots)
            rank = (0 if is_primary else 20) + _char_item_locality_rank(it, swap_slots=swap_slots)
            _consider_candidate_item(
                it, loc, rank, ver, ver_res, is_active_primary=is_active_primary, **common_kwargs
            )

    for stash in stashes:
        for idx, tab in enumerate(stash.tabs, start=1):
            if tab.items is None:
                continue
            ver = tab.item_format or 0x63
            ver_res = resolver.for_version(ver)
            loc = f"Stash Tab {idx}"
            for it in tab.items.items:
                _consider_candidate_item(
                    it, loc, 10 + idx, ver, ver_res, is_active_primary=False, **common_kwargs
                )

    return sorted(dedup.values(), key=lambda c: (c.locality_rank, c.base_name))


def _spec_stat_vec(spec: ItemSpec) -> tuple[int, ...]:
    return tuple(int(getattr(spec, attr)) for attr in _COMPARE_POS_STATS)


def _spec_dominates(a: ItemSpec, b: ItemSpec) -> bool:
    """Return True if `a` strictly dominates `b` within the same MF-presence bucket."""
    if (a.mf > 0) != (b.mf > 0):
        return False
    if a.req_str > b.req_str or a.req_dex > b.req_dex:
        return False
    va = _spec_stat_vec(a)
    vb = _spec_stat_vec(b)
    if va == vb and a.req_str == b.req_str and a.req_dex == b.req_dex:
        return False
    return all(x >= y for x, y in zip(va, vb, strict=True))


def _pareto_prune_variants(variants: list[SocketCandidateVariant]) -> list[SocketCandidateVariant]:
    """Prune strictly dominated variants, keeping owned options ahead of theoretical ties."""
    ordered = sorted(variants, key=lambda v: (not v.owned, v.spec.req_str, v.spec.req_dex))
    kept: list[SocketCandidateVariant] = []
    seen_identical: set[tuple[bool, tuple[int, ...], int, int]] = set()
    for v in ordered:
        sig = (v.spec.mf > 0, _spec_stat_vec(v.spec), v.spec.req_str, v.spec.req_dex)
        if sig in seen_identical:
            continue
        seen_identical.add(sig)
        if any(_spec_dominates(k.spec, v.spec) and (k.owned or not v.owned) for k in kept):
            continue
        kept = [
            k for k in kept if not (_spec_dominates(v.spec, k.spec) and (v.owned or not k.owned))
        ]
        kept.append(v)
    return kept


def _runeword_matches_item(
    rw: RuneWordInfo, item_type: str, target_sockets: int, resolver: GameDataResolver
) -> bool:
    if len(rw.rune_codes) != target_sockets or not rw.itypes:
        return False
    if not any(resolver.is_descendant(item_type, it_code) for it_code in rw.itypes):
        return False
    return not any(resolver.is_descendant(item_type, et_code) for et_code in rw.etypes)


def _build_runeword_variants(
    cand: _CandidateItem,
    *,
    rune_counts: Counter[str],
    theoretical: bool,
    char_level: int,
    char_class: int,
    pal_spec: str,
    pal_offense: str,
    set_group_ids: dict[str, int],
    global_set_cache: dict[tuple[str, int], list[tuple[int, ItemSpec]]],
    sorc_filler_id: int | None,
    pal_aura_id: int | None,
) -> list[SocketCandidateVariant]:
    ver_res = cand.resolver
    item_info = ver_res.get_item(cand.item.code_str.strip().lower())
    if item_info is None or not item_info.type:
        return []
    item_type = item_info.type.lower().strip()
    target_sockets = cand.sockets_range[1]
    variants: list[SocketCandidateVariant] = []

    for rw in ver_res.data.active_runewords:
        if not _runeword_matches_item(rw, item_type, target_sockets, ver_res):
            continue
        reqs = Counter(rw.rune_codes)
        missing = tuple(
            ver_res.get_localized_rune_short_name(rc)
            for rc, needed in reqs.items()
            if rune_counts[rc] < needed
        )
        has_runes = len(missing) == 0
        if not has_runes and not theoretical:
            continue

        rw_lvlreq = max(
            (r_info.levelreq if (r_info := ver_res.get_item(rc)) else 0) for rc in rw.rune_codes
        )
        if rw_lvlreq > char_level:
            continue

        extra_props: list[tuple[int, int, list[int]]] = []
        for mod in rw.mods:
            extra_props.extend(ver_res._set_mod_to_properties(mod))
        for rc in rw.rune_codes:
            extra_props.extend(ver_res.get_socket_properties_for_code(cand.item, rc))

        rw_name = ver_res.get_localized_runeword_name(rw.runeword_id) or rw.name
        rune_short = "+".join(ver_res.get_localized_rune_short_name(rc) for rc in rw.rune_codes)
        variant_name = f"{rw_name} ({cand.base_name}) [{rune_short}]"
        spec = _item_to_spec(
            cand.item,
            cand.loc,
            ver_res,
            cand.version,
            char_level,
            char_class=char_class,
            pal_spec=pal_spec,
            pal_offense=pal_offense,
            set_group_ids=set_group_ids,
            global_set_cache=global_set_cache,
            skip_useful_check=True,
            sorc_filler_id=sorc_filler_id,
            pal_aura_id=pal_aura_id,
            extra_props=extra_props,
            extra_levelreq=rw_lvlreq,
            name_override=variant_name,
        )
        if not isinstance(spec, ItemSpec):
            continue
        variants.append(
            SocketCandidateVariant(
                item_name=cand.base_name,
                item_loc=cand.loc,
                slot=cand.slot,
                kind="runeword",
                action_label=f"{rw_name} ({rune_short})",
                sockets_range=cand.sockets_range,
                owned=has_runes,
                missing_runes=missing,
                spec=spec,
            )
        )
    return _pareto_prune_variants(variants)


def _build_gear_socket_variants(
    cand: _CandidateItem,
    *,
    socketables: Sequence[SocketableOption],
    char_level: int,
    char_class: int,
    pal_spec: str,
    pal_offense: str,
    set_group_ids: dict[str, int],
    global_set_cache: dict[tuple[str, int], list[tuple[int, ItemSpec]]],
    sorc_filler_id: int | None,
    pal_aura_id: int | None,
) -> list[SocketCandidateVariant]:
    ver_res = cand.resolver
    base_vec = _spec_stat_vec(cand.base_spec) if cand.base_spec is not None else None
    base_reqs = (
        (cand.base_spec.req_str, cand.base_spec.req_dex) if cand.base_spec is not None else None
    )
    variants: list[SocketCandidateVariant] = []

    for sock in socketables:
        if sock.levelreq > char_level:
            continue
        s_props = sock.props_for_item(cand.item, ver_res)
        if not s_props:
            continue
        variant_name = f"{cand.base_name} [+{sock.label}]"
        spec = _item_to_spec(
            cand.item,
            cand.loc,
            ver_res,
            cand.version,
            char_level,
            char_class=char_class,
            pal_spec=pal_spec,
            pal_offense=pal_offense,
            set_group_ids=set_group_ids,
            global_set_cache=global_set_cache,
            skip_useful_check=True,
            sorc_filler_id=sorc_filler_id,
            pal_aura_id=pal_aura_id,
            extra_props=s_props,
            extra_levelreq=sock.levelreq,
            name_override=variant_name,
        )
        if not isinstance(spec, ItemSpec):
            continue
        # Skip socketables that add zero optimizer-relevant stats or req reductions.
        if (
            base_vec is not None
            and base_reqs is not None
            and _spec_stat_vec(spec) == base_vec
            and (spec.req_str, spec.req_dex) == base_reqs
        ):
            continue
        loc_tag = f" [{sock.loc}]" if sock.loc else ""
        variants.append(
            SocketCandidateVariant(
                item_name=cand.base_name,
                item_loc=cand.loc,
                slot=cand.slot,
                kind="socket",
                action_label=f"{sock.label}{loc_tag}",
                sockets_range=cand.sockets_range,
                owned=sock.owned,
                missing_runes=(),
                spec=spec,
            )
        )
    return _pareto_prune_variants(variants)


def _dps_bucket(dps: float) -> int:
    if dps <= 0.0:
        return 0
    return round(dps / 100.0)


def _offense_score(res: BuildResult, offense: str, *, has_aura: bool) -> int:
    if res.dps > 0.0:
        return _dps_bucket(res.dps)
    if offense in ("melee", "zeal") and (
        has_aura or res.action_skill_bonus != 0 or res.aura_skill_bonus != 0
    ):
        bonus = (
            res.aura_skill_bonus if has_aura else max(res.action_skill_bonus, res.aura_skill_bonus)
        )
        eff_primary = res.skills + res.primary_skill_bonus + bonus
    else:
        eff_primary = res.skills + res.primary_skill_bonus
    if offense == "smite":
        return eff_primary * 5 + res.cb * 4 + res.ias_bp
    if offense in ("melee", "zeal"):
        return eff_primary * 8 + res.ias_bp + res.cb
    return eff_primary


def _build_score_key(
    res: BuildResult, mode: str, offense: str, *, has_aura: bool, uses_caster_dps: bool
) -> tuple[int, ...]:
    """Compute a comparable score tuple matching Rust's `score_eval_summary` (without locality)."""
    eff_primary = res.skills + res.primary_skill_bonus
    if offense in ("melee", "zeal") and (
        has_aura or res.action_skill_bonus != 0 or res.aura_skill_bonus != 0
    ):
        bonus = (
            res.aura_skill_bonus if has_aura else max(res.action_skill_bonus, res.aura_skill_bonus)
        )
        eff_primary += bonus
    res_sum = res.fr + res.lr + res.cr + res.pr
    res_base = min(res.fr, 75) + min(res.lr, 75) + min(res.cr, 75) + min(res.pr, 75)
    eff_fcr_bp = res.fcr_bp if offense == "caster" else 0
    belt_slots = sum(it.belt_slots for it in res.items)
    defense = sum(it.defense for it in res.items)

    if mode == "mf":
        return (
            res.mf,
            eff_primary,
            eff_fcr_bp,
            res.fhr_bp,
            res.pr,
            res.life_bo,
            belt_slots,
            defense,
        )
    if mode == "power":
        primary = int(res.dps) if uses_caster_dps else eff_primary
        return (
            primary,
            res.skills,
            int(res.pr >= 75),
            res.pr,
            res.life_bo,
            res.mana_bo,
            belt_slots,
            defense,
        )
    if mode == "max-res":
        raw_sum = res.fr_raw + res.lr_raw + res.cr_raw + res.pr_raw
        return (
            res_sum,
            eff_primary,
            eff_fcr_bp,
            res.fhr_bp,
            res.life_bo,
            raw_sum,
            belt_slots,
            defense,
        )
    off = _offense_score(res, offense, has_aura=has_aura)
    if mode == "leveling":
        tie = (
            (res.life_bo, res.pdr_pct, res.frw, res.fhr_bp, res_sum, belt_slots, defense)
            if offense == "smite"
            else (res.life_bo, res.frw, res_sum, res.fhr_bp, eff_fcr_bp, belt_slots, defense)
        )
        return (off, res_base, int(res.cbf), *tie)
    return (
        res_base,
        off,
        int(res.cbf),
        res.life_bo,
        res.frw,
        res.fhr_bp,
        eff_fcr_bp,
        res_sum,
        belt_slots,
        defense,
    )


def _extra_improvement_key(res: BuildResult) -> tuple[int, ...]:
    return (
        round(res.dps),
        res.mf,
        res.fr_raw + res.lr_raw + res.cr_raw + res.pr_raw,
        res.life_bo,
        res.mana_bo,
        res.fhr,
        res.fcr,
        res.ias,
        sum(it.defense for it in res.items),
    )


def _clone_constraints_limit1(c: BuildConstraints) -> BuildConstraints:
    return BuildConstraints(
        allow_mf=c.allow_mf,
        min_fcr=c.min_fcr,
        min_fhr=c.min_fhr,
        min_fr=c.min_fr,
        min_lr=c.min_lr,
        min_cr=c.min_cr,
        min_pr=c.min_pr,
        max_charm_slots=c.max_charm_slots,
        mode=c.mode,
        base_life=c.base_life,
        base_mana=c.base_mana,
        base_hell_res=c.base_hell_res,
        base_str=c.base_str,
        base_dex=c.base_dex,
        bo_base_bonus=c.bo_base_bonus,
        limit=1,
        blizz_base_lvl=c.blizz_base_lvl,
        blizz_syn_pts=c.blizz_syn_pts,
        cm_base_lvl=c.cm_base_lvl,
        char_class=c.char_class,
        base_max_fr=c.base_max_fr,
        base_max_lr=c.base_max_lr,
        base_max_cr=c.base_max_cr,
        base_max_pr=c.base_max_pr,
        use_bo=c.use_bo,
        fixed_gear=c.fixed_gear,
        offense=c.offense,
        aura_hit_dmg=c.aura_hit_dmg,
        aura_pulse_dps=c.aura_pulse_dps,
        action_ed=c.action_ed,
        action_hits=c.action_hits,
        has_aura=c.has_aura,
        aura_is_fire=c.aura_is_fire,
        targets=c.targets,
        blizz_dmg=c.blizz_dmg,
        filler_dmg=c.filler_dmg,
        filler_is_aoe=c.filler_is_aoe,
        require_cbf=c.require_cbf,
        min_frw=c.min_frw,
        min_ias=c.min_ias,
        min_cb=c.min_cb,
        min_ll=c.min_ll,
        min_pdr=c.min_pdr,
        min_mf=c.min_mf,
        fixed_slots=c.fixed_slots,
        action_ar_pct=c.action_ar_pct,
        aura_ar_pct=c.aura_ar_pct,
        aura_target_def_pct=c.aura_target_def_pct,
        target_def=c.target_def,
        target_type=cast(TargetTypeStr, c.target_type),
        char_level=c.char_level,
        target_hp=c.target_hp,
    )


def evaluate_socket_candidates_for_preset(
    title: str,
    constraints: BuildConstraints,
    base_items: Sequence[ItemSpec],
    charms: Sequence[CharmSpec],
    candidate_groups: Sequence[tuple[_CandidateItem, list[SocketCandidateVariant]]],
    *,
    diff_name: str,
    limit: int = 5,
) -> PresetSocketReport:
    """Evaluate every candidate item's socketed variants for a single build preset."""
    c1 = _clone_constraints_limit1(constraints)
    base_res_list = optimize_builds(list(base_items), list(charms), c1)
    baseline = base_res_list[0] if base_res_list else None

    mode = c1.mode
    offense = c1.offense
    has_aura = c1.has_aura
    uses_caster_dps = offense == "caster" and bool(c1.blizz_dmg)

    base_score = (
        _build_score_key(
            baseline, mode, offense, has_aura=has_aura, uses_caster_dps=uses_caster_dps
        )
        if baseline is not None
        else ()
    )
    base_extra = _extra_improvement_key(baseline) if baseline is not None else ()

    wins: list[
        tuple[tuple[int, tuple[int, ...], tuple[int, ...], int, int], SocketUpgradeResult]
    ] = []
    for cand, variants in candidate_groups:
        if not variants:
            continue
        trial_items = [*base_items, *(v.spec for v in variants)]
        res_list = optimize_builds(trial_items, list(charms), c1)
        if not res_list:
            continue
        res = res_list[0]

        by_key = {(v.spec.name, v.spec.loc): v for v in variants}
        chosen_variant = next(
            (by_key[(it.name, it.loc)] for it in res.items if (it.name, it.loc) in by_key),
            None,
        )
        if chosen_variant is None:
            continue

        cand_score = _build_score_key(
            res, mode, offense, has_aura=has_aura, uses_caster_dps=uses_caster_dps
        )
        cand_extra = _extra_improvement_key(res)
        if baseline is not None and (cand_score, cand_extra) <= (base_score, base_extra):
            continue

        unlocked = baseline is None
        rank_key = (
            1 if unlocked else 0,
            cand_score,
            cand_extra,
            1 if chosen_variant.owned else 0,
            -cand.locality_rank,
        )
        wins.append(
            (
                rank_key,
                SocketUpgradeResult(
                    variant=chosen_variant,
                    baseline=baseline,
                    result=res,
                    unlocked_feasibility=unlocked,
                    score_key=cand_score,
                    extra_key=cand_extra,
                ),
            )
        )

    wins.sort(key=lambda pair: pair[0], reverse=True)
    top_wins = [res for _, res in wins[: max(0, limit)]]
    return PresetSocketReport(
        title=title,
        mode=mode,
        offense=offense,
        has_aura=has_aura,
        diff_name=diff_name,
        baseline=baseline,
        candidates=top_wins,
    )


def _resolve_paladin_socket_presets(
    primary_char: D2SStruct,
    base_items: Sequence[ItemSpec],
    charms: Sequence[CharmSpec],
    *,
    build: str,
    max_charm_slots: int,
    extra_chars: Sequence[D2SStruct],
    stashes: Sequence[SharedStash],
    resolver: GameDataResolver,
    keep_equipped: bool | str | None,
    targets: int,
    target_type: str,
    left_skill: int | None,
    right_skill: int | None,
    overrides: ConstraintOverrides | None,
) -> list[tuple[str, BuildConstraints, str]]:
    resolved = resolve_build_expr(
        build,
        CharClass.PALADIN,
        overrides=overrides,
        char_name=primary_char.get_char_name(),
    )
    has_mode_override = overrides is not None and overrides.mode is not None
    presets_out: list[tuple[str, BuildConstraints, str]] = []
    for preset in resolved:
        use_probe = (
            preset.strategy == "leveling-probe"
            and not has_mode_override
            and preset.mode == "leveling-res"
        )
        if use_probe:
            eff_targets = max(1, targets)
            baseline_obj, char_level, diff_name, resolved_spec = _build_paladin_baseline(
                primary_char,
                spec=None,
                max_charm_slots=max_charm_slots,
                extra_chars=extra_chars,
                stashes=stashes,
                resolver=resolver,
                bo_base_bonus=None,
                keep_equipped=keep_equipped,
                targets=eff_targets,
                target_type=cast(TargetTypeStr, target_type),
                left_skill=left_skill,
                right_skill=right_skill,
            )
            offense = paladin_offense_profile(
                resolved_spec, primary_char, left_skill=left_skill, right_skill=right_skill
            )
            extra_kwargs: dict[str, Any] = {
                k: v for k, v in preset.constraint_kwargs().items() if k != "mode"
            }
            opt1 = _probe_paladin_opt1(
                list(base_items),
                list(charms),
                baseline_obj,
                offense=offense,
                is_caster=(offense == "caster"),
                extra_kwargs=extra_kwargs,
            )
            eff_kwargs = dict(extra_kwargs)
            if opt1 is not None:
                eff_kwargs["min_fcr"] = max(int(eff_kwargs.get("min_fcr", 0)), opt1.fcr_bp)
                eff_kwargs["min_fhr"] = max(int(eff_kwargs.get("min_fhr", 0)), opt1.fhr_bp)
            constraints = baseline_obj.build_constraints(
                mode="leveling-res",
                limit=1,
                offense=offense,
                **eff_kwargs,
            )
            title = preset.title or f"Paladin Leveling (lvl {char_level}, {diff_name})"
            presets_out.append((title, constraints, diff_name))
        else:
            title, constraints, _, diff_name = build_paladin_preset_constraints(
                primary_char,
                preset,
                max_charm_slots=max_charm_slots,
                limit=1,
                extra_chars=extra_chars,
                stashes=stashes,
                resolver=resolver,
                keep_equipped=keep_equipped,
                targets=targets,
                target_type=cast(TargetTypeStr, target_type),
                left_skill=left_skill,
                right_skill=right_skill,
            )
            presets_out.append((title, constraints, diff_name))
    return presets_out


def optimize_socket_quests(
    primary_char: D2SStruct,
    extra_chars: Sequence[D2SStruct] = (),
    stashes: Sequence[SharedStash] = (),
    resolver: GameDataResolver | None = None,
    *,
    build: str = "all",
    max_charm_slots: int = 23,
    limit: int = 5,
    keep_equipped: bool | str | None = False,
    targets: int = 1,
    target_type: str = "champion",
    left_skill: int | None = None,
    right_skill: int | None = None,
    overrides: ConstraintOverrides | None = None,
    theoretical: bool = False,
) -> SocketQuestReport:
    """Evaluate all socket-quest-eligible items across saves/stashes for the target character."""
    if resolver is None:
        resolver = GameDataResolver.load()

    char_level = max(1, primary_char.player_stats.level or primary_char.char_level)
    char_class = primary_char.char_class
    if char_class not in (CharClass.SORCERESS, CharClass.PALADIN):
        actual = CharClass(char_class).display_name
        raise ValueError(
            f"Character '{primary_char.get_char_name()}' is {actual}, expected Sorceress or Paladin"
        )

    kept_slots = parse_keep_gear(keep_equipped)
    pal_spec = (
        detect_paladin_spec(primary_char, left_skill=left_skill, right_skill=right_skill)
        if char_class == int(CharClass.PALADIN)
        else "leveling"
    )
    pal_offense = (
        paladin_offense_profile(
            pal_spec, primary_char, left_skill=left_skill, right_skill=right_skill
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
    pal_aura_id = (
        resolve_paladin_aura_id(primary_char, pal_spec, right_skill=right_skill)
        if char_class == int(CharClass.PALADIN)
        else None
    )

    base_items, charms, set_group_ids, global_set_cache = _extract_pool_with_context(
        primary_char,
        extra_chars=extra_chars,
        stashes=stashes,
        resolver=resolver,
        pal_spec=pal_spec,
        keep_equipped=keep_equipped,
        left_skill=left_skill,
        right_skill=right_skill,
        targets=targets,
    )

    socketables, rune_counts, gem_type_count, jewel_count = extract_socketables(
        primary_char,
        extra_chars=extra_chars,
        stashes=stashes,
        resolver=resolver,
        theoretical=theoretical,
    )

    eligible = _collect_eligible_items(
        primary_char,
        extra_chars=extra_chars,
        stashes=stashes,
        resolver=resolver,
        kept_slots=kept_slots,
        pal_spec=pal_spec,
        pal_offense=pal_offense,
        set_group_ids=set_group_ids,
        global_set_cache=global_set_cache,
        sorc_filler_id=sorc_filler_id,
        pal_aura_id=pal_aura_id,
    )

    candidate_groups: list[tuple[_CandidateItem, list[SocketCandidateVariant]]] = []
    for cand in eligible:
        q = cand.item.quality()
        if q in (ItemQuality.LOW, ItemQuality.NORMAL, ItemQuality.HIGH):
            variants = _build_runeword_variants(
                cand,
                rune_counts=rune_counts,
                theoretical=theoretical,
                char_level=char_level,
                char_class=char_class,
                pal_spec=pal_spec,
                pal_offense=pal_offense,
                set_group_ids=set_group_ids,
                global_set_cache=global_set_cache,
                sorc_filler_id=sorc_filler_id,
                pal_aura_id=pal_aura_id,
            )
        else:
            variants = _build_gear_socket_variants(
                cand,
                socketables=socketables,
                char_level=char_level,
                char_class=char_class,
                pal_spec=pal_spec,
                pal_offense=pal_offense,
                set_group_ids=set_group_ids,
                global_set_cache=global_set_cache,
                sorc_filler_id=sorc_filler_id,
                pal_aura_id=pal_aura_id,
            )
        if variants:
            candidate_groups.append((cand, variants))

    if char_class == int(CharClass.SORCERESS):
        from d2savior.core.stats import get_current_difficulty

        diff_name = DIFFICULTY_NAMES[get_current_difficulty(primary_char)]
        sorc_presets = select_sorc_presets(
            primary_char,
            build=build,
            max_charm_slots=max_charm_slots,
            limit=1,
            extra_chars=extra_chars,
            stashes=stashes,
            resolver=resolver,
            keep_equipped=keep_equipped,
            targets=targets,
            left_skill=left_skill,
            right_skill=right_skill,
            overrides=overrides,
        )
        preset_specs = [(title, c, diff_name) for title, c in sorc_presets]
    else:
        preset_specs = _resolve_paladin_socket_presets(
            primary_char,
            base_items,
            charms,
            build=build,
            max_charm_slots=max_charm_slots,
            extra_chars=extra_chars,
            stashes=stashes,
            resolver=resolver,
            keep_equipped=keep_equipped,
            targets=targets,
            target_type=target_type,
            left_skill=left_skill,
            right_skill=right_skill,
            overrides=overrides,
        )
        diff_name = preset_specs[0][2] if preset_specs else "Normal"

    preset_reports = [
        evaluate_socket_candidates_for_preset(
            title,
            constraints,
            base_items,
            charms,
            candidate_groups,
            diff_name=p_diff,
            limit=limit,
        )
        for title, constraints, p_diff in preset_specs
    ]

    return SocketQuestReport(
        char_name=primary_char.get_char_name(),
        char_class_name=CharClass(char_class).display_name,
        char_level=char_level,
        diff_name=diff_name,
        quest_status=get_socket_quest_status(primary_char),
        other_unclaimed=find_unclaimed_socket_quests(extra_chars),
        owned_rune_types=sum(1 for c in rune_counts.values() if c > 0),
        owned_gem_types=gem_type_count,
        owned_jewel_count=jewel_count,
        theoretical=theoretical,
        eligible_item_count=len(eligible),
        presets=preset_reports,
    )


def _format_build_brief(res: BuildResult, *, diff_name: str, offense: str) -> str:
    parts: list[str] = []
    if res.dps > 0.0:
        parts.append(f"DPS: {res.dps:.0f}")
    parts.append(f"Skills: +{res.skills}")
    if offense == "caster":
        parts.append(f"FCR: {res.fcr}% (BP {res.fcr_bp}%)")
    if offense != "caster" and (res.ias or res.cb):
        parts.append(f"IAS: {res.ias}% (BP {res.ias_bp}%) | CB: {res.cb}%")
    parts.append(f"FHR: {res.fhr}% (BP {res.fhr_bp}%)")
    if res.mf:
        parts.append(f"MF: {res.mf}%")
    parts.append(f"{diff_name} Res: F:{res.fr} L:{res.lr} C:{res.cr} P:{res.pr}")
    parts.append(f"Life: {res.life_bo}")
    return " | ".join(parts)


def _format_delta_summary(cand: SocketUpgradeResult, *, diff_name: str, offense: str) -> str:
    if cand.unlocked_feasibility or cand.baseline is None:
        return "Unlocks feasible build!"
    b = cand.baseline
    r = cand.result
    deltas: list[str] = []
    if r.skills != b.skills:
        deltas.append(f"Skills {b.skills:+d}->{r.skills:+d}")
    if r.dps > 0.0 and abs(r.dps - b.dps) >= 1.0:
        deltas.append(f"DPS {b.dps:.0f}->{r.dps:.0f}")
    if offense == "caster" and r.fcr_bp != b.fcr_bp:
        deltas.append(f"FCR BP {b.fcr_bp}%->{r.fcr_bp}%")
    if r.fhr_bp != b.fhr_bp:
        deltas.append(f"FHR BP {b.fhr_bp}%->{r.fhr_bp}%")
    if offense != "caster" and r.ias_bp != b.ias_bp:
        deltas.append(f"IAS BP {b.ias_bp}%->{r.ias_bp}%")
    if r.cbf != b.cbf:
        deltas.append("CBF gained" if r.cbf else "CBF lost")
    if r.mf != b.mf:
        deltas.append(f"MF {b.mf}%->{r.mf}%")
    res_changes = [
        f"{lbl}:{bv}->{rv}"
        for lbl, bv, rv in (
            ("F", b.fr, r.fr),
            ("L", b.lr, r.lr),
            ("C", b.cr, r.cr),
            ("P", b.pr, r.pr),
        )
        if bv != rv
    ]
    if res_changes:
        deltas.append(f"{diff_name} Res {' '.join(res_changes)}")
    if r.life_bo != b.life_bo:
        deltas.append(f"Life {b.life_bo}->{r.life_bo}")
    if not deltas:
        raw_res_b = b.fr_raw + b.lr_raw + b.cr_raw + b.pr_raw
        raw_res_r = r.fr_raw + r.lr_raw + r.cr_raw + r.pr_raw
        if raw_res_r != raw_res_b:
            deltas.append(f"Overcap Res {raw_res_r - raw_res_b:+d}%")
        if r.fhr != b.fhr:
            deltas.append(f"FHR {b.fhr}%->{r.fhr}%")
        if r.mana_bo != b.mana_bo:
            deltas.append(f"Mana {b.mana_bo}->{r.mana_bo}")
    return ", ".join(deltas) if deltas else "Tiebreak improvement"


def _format_gear_diff_note(cand: SocketUpgradeResult) -> str | None:
    if cand.baseline is None:
        return None
    b_map = {it.slot: it.name for it in cand.baseline.items}
    r_map = {it.slot: it.name for it in cand.result.items}
    if cand.variant.slot not in r_map:
        return None
    swaps: list[str] = []
    for it in cand.result.items:
        if it.slot == "ring":
            continue
        is_target = it.name == cand.variant.spec.name and it.loc == cand.variant.spec.loc
        if is_target:
            if it.slot == "weapon2h" and "weapon2h" not in b_map:
                replaced = [b_map[s] for s in ("weapon", "shield") if s in b_map]
                prev_desc = " + ".join(replaced) if replaced else "(empty)"
                swaps.append(f"weapon2h: replaces {prev_desc}")
            else:
                prev_name = b_map.get(it.slot, "(empty)")
                if prev_name != cand.variant.item_name:
                    swaps.append(f"{it.slot}: replaces {prev_name}")
            continue
        prev_name = b_map.get(it.slot)
        if prev_name != it.name:
            swaps.append(f"{it.slot}: {prev_name or '(empty)'} -> {it.name}")
    return f"Gear changes: {'; '.join(swaps)}" if swaps else None


def format_socket_report(report: SocketQuestReport) -> str:
    """Format a `SocketQuestReport` into a concise, actionable human-readable report."""
    lines: list[str] = [
        f"=== Socket Quest Optimizer: {report.char_name} "
        f"({report.char_class_name} lvl {report.char_level}, {report.diff_name}) ==="
    ]
    quest_parts = [f"{d}: {s}" for d, s in report.quest_status]
    lines.append(f"Socket Quests ({report.char_name}): {' | '.join(quest_parts)}")
    if report.other_unclaimed:
        other_str = ", ".join(f"{name} ({diff})" for name, diff in report.other_unclaimed)
        lines.append(f"Other unclaimed Socket Quests: {other_str}")
    mode_tag = "owned + theoretical" if report.theoretical else "owned only"
    lines.append(
        f"Socketables ({mode_tag}): {report.owned_rune_types} runes, "
        f"{report.owned_gem_types} gem types, {report.owned_jewel_count} jewels | "
        f"Eligible items: {report.eligible_item_count}"
    )

    for p in report.presets:
        lines.append("")
        lines.append(f"--- {p.title} ---")
        if p.baseline is None:
            lines.append("Baseline: No loadout found matching all constraints.")
        else:
            lines.append(
                f"Baseline: {_format_build_brief(p.baseline, diff_name=p.diff_name, offense=p.offense)}"
            )
        if not p.candidates:
            lines.append("  No socket quest candidate improves this build.")
            continue

        for idx, cand in enumerate(p.candidates, start=1):
            v = cand.variant
            min_s, max_s = v.sockets_range
            sock_tag = (
                f"{min_s} socket"
                if min_s == max_s == 1
                else (f"Magic: {min_s}-{max_s} sockets" if min_s != max_s else f"{max_s} sockets")
            )
            arrow = "->" if v.kind == "runeword" else "+"
            missing_note = (
                f" [need: {', '.join(v.missing_runes)}]"
                if v.missing_runes
                else (" [theoretical]" if not v.owned else "")
            )
            lines.append(
                f"  #{idx} {v.item_name} [{v.item_loc}] ({v.slot}, {sock_tag}) "
                f"{arrow} {v.action_label}{missing_note}"
            )
            delta_str = _format_delta_summary(cand, diff_name=p.diff_name, offense=p.offense)
            lines.append(f"     Gain  : {delta_str}")
            lines.append(
                f"     Result: {_format_build_brief(cand.result, diff_name=p.diff_name, offense=p.offense)}"
            )
            if diff_note := _format_gear_diff_note(cand):
                lines.append(f"     {diff_note}")

    if len(report.presets) > 1:
        summary_counts: Counter[tuple[str, str, str]] = Counter()
        best_action: dict[tuple[str, str, str], tuple[int, str]] = {}
        for p in report.presets:
            for rank, cand in enumerate(p.candidates, start=1):
                v = cand.variant
                key = (v.item_name, v.item_loc, v.slot)
                summary_counts[key] += 1
                prev = best_action.get(key)
                if prev is None or rank < prev[0]:
                    best_action[key] = (rank, v.action_label)
        if summary_counts:
            lines.append("")
            lines.append("=== Overall Best Socket Quest Targets ===")
            ranked_targets = sorted(
                summary_counts.items(),
                key=lambda kv: (-kv[1], best_action[kv[0]][0], kv[0][0]),
            )
            for (item_name, item_loc, slot), count in ranked_targets[:5]:
                best_rank, action_lbl = best_action[(item_name, item_loc, slot)]
                lines.append(
                    f"  - {item_name} [{item_loc}] ({slot}): top-{len(p.candidates)} in "
                    f"{count}/{len(report.presets)} presets (best #{best_rank} with {action_lbl})"
                )

    return "\n".join(lines)
