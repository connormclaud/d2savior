"""Larzuk Socket Quest eligibility, socketable scanning, and variant synthesis."""

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from operator import attrgetter
from typing import cast

from d2savior.core.constants import DIFFICULTY_NAMES
from d2savior.core.d2s_struct import D2SStruct
from d2savior.core.enums import ItemLocation, ItemQuality
from d2savior.core.item import D2Item
from d2savior.core.item_formatter import format_summary_properties, get_item_display_name
from d2savior.core.models import RuneWordInfo
from d2savior.core.resolver import GameDataResolver
from d2savior.core.stash import GEM_CODES, RUNE_CODES, SharedStash
from d2savior.core.stats import collect_item_properties, normalize_damage_props
from d2savior.optimizer.common import ALL_GEAR_SLOTS, item_levelreq, iter_pool_items
from d2savior.optimizer.extract import classify_slot, item_to_spec
from d2savior.optimizer.native import ItemSpec

_SOCKETABLE_SLOTS: frozenset[str] = frozenset({"helm", "armor", "shield", "weapon", "weapon2h"})
_JEWEL_CODES: frozenset[str] = frozenset({"jew", "cjw"})
_RUNE_CODES_STR: tuple[str, ...] = tuple(f"r{i:02d}" for i in range(1, 34))
_THEORETICAL_GEM_CODES: tuple[str, ...] = ("gpv", "gpb", "gpg", "gpr", "gpw", "gpy", "skz")
THEORETICAL_CHAR_LEVEL = 99

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

_SPEC_STAT_GETTER = attrgetter(*_COMPARE_POS_STATS)


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
class CandidateItem:
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


def _item_props_key(
    props: Sequence[tuple[int, int, list[int]]],
) -> tuple[tuple[int, int, tuple[int, ...]], ...]:
    return tuple((pid, val, tuple(params)) for pid, val, params in props)


def _format_jewel_label(item: D2Item, resolver: GameDataResolver, version: int) -> str:
    base_title = get_item_display_name(item, resolver=resolver, version=version)
    props = collect_item_properties(
        item, resolver=resolver, version=version, normalize_source=normalize_damage_props
    )
    prop_strs = format_summary_properties(props, resolver=resolver, version=version)
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
        lvlreq = item_levelreq(item, ver_res)
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
    jewel_count = 0

    for entry in iter_pool_items(
        primary_char,
        extra_chars=extra_chars,
        stashes=stashes,
        resolver=resolver,
        skip_swap_cta=False,
    ):
        if entry.item.location in (ItemLocation.EQUIPPED, ItemLocation.SOCKET):
            continue
        if entry.item.code_str.strip().lower() in _JEWEL_CODES:
            jewel_count += 1
        _record_socketable_item(
            entry.item,
            entry.loc,
            entry.locality_rank,
            entry.version,
            entry.resolver,
            count=entry.stack_count,
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
    sorc_armor_id: int | None,
    pal_aura_id: int | None,
    dedup: dict[tuple[object, ...], CandidateItem],
    ignore_reqs: bool = False,
) -> None:
    if it.location == ItemLocation.SOCKET or (keep_all and not is_active_primary):
        return
    if item_levelreq(it, ver_res) > char_level:
        return
    sock_range = get_larzuk_socket_range(it, ver_res)
    if sock_range[1] <= 0:
        return
    classified = classify_slot(it, ver_res, char_class=char_class)
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

    base_spec_raw = item_to_spec(
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
        sorc_armor_id=sorc_armor_id,
        pal_aura_id=pal_aura_id,
        ignore_reqs=ignore_reqs,
    )
    dedup[d_key] = CandidateItem(
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


def collect_eligible_items(
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
    sorc_armor_id: int | None = None,
    char_level_override: int | None = None,
    ignore_reqs: bool = False,
) -> list[CandidateItem]:
    """Find deduplicated, class-equippable, unsocketed items eligible for Larzuk."""
    char_level = (
        char_level_override
        if char_level_override is not None
        else max(1, primary_char.player_stats.level or primary_char.char_level)
    )
    char_class = primary_char.char_class
    keep_all = kept_slots == ALL_GEAR_SLOTS
    dedup: dict[tuple[object, ...], CandidateItem] = {}

    for entry in iter_pool_items(
        primary_char,
        extra_chars=extra_chars,
        stashes=stashes,
        resolver=resolver,
        skip_swap_cta=True,
    ):
        _consider_candidate_item(
            entry.item,
            entry.loc,
            entry.locality_rank,
            entry.version,
            entry.resolver,
            is_active_primary=entry.is_active_primary,
            keep_all=keep_all,
            kept_slots=kept_slots,
            char_level=char_level,
            char_class=char_class,
            pal_spec=pal_spec,
            pal_offense=pal_offense,
            set_group_ids=set_group_ids,
            global_set_cache=global_set_cache,
            sorc_filler_id=sorc_filler_id,
            sorc_armor_id=sorc_armor_id,
            pal_aura_id=pal_aura_id,
            dedup=dedup,
            ignore_reqs=ignore_reqs,
        )

    return sorted(dedup.values(), key=lambda c: (c.locality_rank, c.base_name))


def _spec_stat_vec(spec: ItemSpec) -> tuple[int, ...]:
    return cast(tuple[int, ...], _SPEC_STAT_GETTER(spec))


def _vec_dominates(
    mf_a: bool,
    va: tuple[int, ...],
    req_a: tuple[int, int],
    mf_b: bool,
    vb: tuple[int, ...],
    req_b: tuple[int, int],
) -> bool:
    if mf_a != mf_b or req_a[0] > req_b[0] or req_a[1] > req_b[1]:
        return False
    if va == vb and req_a == req_b:
        return False
    return all(x >= y for x, y in zip(va, vb, strict=True))


def pareto_prune_variants(variants: list[SocketCandidateVariant]) -> list[SocketCandidateVariant]:
    """Prune strictly dominated variants, keeping owned options ahead of theoretical ties."""
    ordered = sorted(variants, key=lambda v: (not v.owned, v.spec.req_str, v.spec.req_dex))
    kept: list[tuple[SocketCandidateVariant, bool, tuple[int, ...], tuple[int, int]]] = []
    seen_identical: set[tuple[bool, tuple[int, ...], int, int]] = set()
    for v in ordered:
        mf_flag = v.spec.mf > 0
        vec = _spec_stat_vec(v.spec)
        reqs = (v.spec.req_str, v.spec.req_dex)
        sig = (mf_flag, vec, reqs[0], reqs[1])
        if sig in seen_identical:
            continue
        seen_identical.add(sig)
        if any(
            _vec_dominates(kmf, kvec, kreqs, mf_flag, vec, reqs) and (kv.owned or not v.owned)
            for kv, kmf, kvec, kreqs in kept
        ):
            continue
        kept = [
            entry
            for entry in kept
            if not (
                _vec_dominates(mf_flag, vec, reqs, entry[1], entry[2], entry[3])
                and (v.owned or not entry[0].owned)
            )
        ]
        kept.append((v, mf_flag, vec, reqs))
    return [kv for kv, _, _, _ in kept]


def _runeword_matches_item(
    rw: RuneWordInfo, item_type: str, target_sockets: int, resolver: GameDataResolver
) -> bool:
    if len(rw.rune_codes) != target_sockets or not rw.itypes:
        return False
    if not any(resolver.is_descendant(item_type, it_code) for it_code in rw.itypes):
        return False
    return not any(resolver.is_descendant(item_type, et_code) for et_code in rw.etypes)


def build_runeword_variants(
    cand: CandidateItem,
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
    sorc_armor_id: int | None = None,
    ignore_reqs: bool = False,
) -> list[SocketCandidateVariant]:
    """Synthesize and Pareto-prune runeword variants for an unsocketed base item."""
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
            extra_props.extend(ver_res.set_mod_to_properties(mod))
        for rc in rw.rune_codes:
            extra_props.extend(ver_res.get_socket_properties_for_code(cand.item, rc))

        rw_name = ver_res.get_localized_runeword_name(rw.runeword_id) or rw.name
        rune_short = "+".join(ver_res.get_localized_rune_short_name(rc) for rc in rw.rune_codes)
        variant_name = f"{rw_name} ({cand.base_name}) [{rune_short}]"
        spec = item_to_spec(
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
            sorc_armor_id=sorc_armor_id,
            pal_aura_id=pal_aura_id,
            extra_props=extra_props,
            extra_levelreq=rw_lvlreq,
            name_override=variant_name,
            ignore_reqs=ignore_reqs,
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
    return pareto_prune_variants(variants)


def build_gear_socket_variants(
    cand: CandidateItem,
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
    sorc_armor_id: int | None = None,
    ignore_reqs: bool = False,
) -> list[SocketCandidateVariant]:
    """Synthesize and Pareto-prune single-socket gem/rune/jewel variants for gear."""
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
        spec = item_to_spec(
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
            sorc_armor_id=sorc_armor_id,
            pal_aura_id=pal_aura_id,
            extra_props=s_props,
            extra_levelreq=sock.levelreq,
            name_override=variant_name,
            ignore_reqs=ignore_reqs,
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
    return pareto_prune_variants(variants)


def build_candidate_groups(
    eligible: Sequence[CandidateItem],
    *,
    rune_counts: Counter[str],
    socketables: Sequence[SocketableOption],
    theoretical: bool,
    char_level: int,
    char_class: int,
    pal_spec: str,
    pal_offense: str,
    set_group_ids: dict[str, int],
    global_set_cache: dict[tuple[str, int], list[tuple[int, ItemSpec]]],
    sorc_filler_id: int | None,
    pal_aura_id: int | None,
    sorc_armor_id: int | None = None,
    ignore_reqs: bool = False,
) -> list[tuple[CandidateItem, list[SocketCandidateVariant]]]:
    """Synthesize and Pareto-prune runeword and socket variants for all eligible candidates."""
    candidate_groups: list[tuple[CandidateItem, list[SocketCandidateVariant]]] = []
    for cand in eligible:
        q = cand.item.quality()
        if q in (ItemQuality.LOW, ItemQuality.NORMAL, ItemQuality.HIGH):
            variants = build_runeword_variants(
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
                sorc_armor_id=sorc_armor_id,
                pal_aura_id=pal_aura_id,
                ignore_reqs=ignore_reqs,
            )
        else:
            variants = build_gear_socket_variants(
                cand,
                socketables=socketables,
                char_level=char_level,
                char_class=char_class,
                pal_spec=pal_spec,
                pal_offense=pal_offense,
                set_group_ids=set_group_ids,
                global_set_cache=global_set_cache,
                sorc_filler_id=sorc_filler_id,
                sorc_armor_id=sorc_armor_id,
                pal_aura_id=pal_aura_id,
                ignore_reqs=ignore_reqs,
            )
        if variants:
            candidate_groups.append((cand, variants))
    return candidate_groups
