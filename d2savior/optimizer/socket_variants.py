"""Socket variant synthesis (runewords, gem/rune/jewel fillers) and Pareto pruning."""

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from operator import attrgetter
from typing import cast

from d2savior.core.enums import ItemQuality
from d2savior.core.models import RuneWordInfo
from d2savior.core.resolver import GameDataResolver
from d2savior.optimizer.extract import item_to_spec
from d2savior.optimizer.extract_props import ExtractionContext
from d2savior.optimizer.native import ItemSpec
from d2savior.optimizer.socket_candidates import CandidateItem, SocketableOption

_COMPARE_POS_STATS: tuple[str, ...] = (
    "all_skills",
    "class_skills",
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
    ctx: ExtractionContext,
    set_group_ids: dict[str, int],
    global_set_cache: dict[tuple[str, int], list[tuple[int, ItemSpec]]],
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
        if rw_lvlreq > ctx.char_level:
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
            ctx=ctx,
            set_group_ids=set_group_ids,
            global_set_cache=global_set_cache,
            skip_useful_check=True,
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
    ctx: ExtractionContext,
    set_group_ids: dict[str, int],
    global_set_cache: dict[tuple[str, int], list[tuple[int, ItemSpec]]],
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
        if sock.levelreq > ctx.char_level:
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
            ctx=ctx,
            set_group_ids=set_group_ids,
            global_set_cache=global_set_cache,
            skip_useful_check=True,
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
    ctx: ExtractionContext,
    set_group_ids: dict[str, int],
    global_set_cache: dict[tuple[str, int], list[tuple[int, ItemSpec]]],
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
                ctx=ctx,
                set_group_ids=set_group_ids,
                global_set_cache=global_set_cache,
                ignore_reqs=ignore_reqs,
            )
        else:
            variants = build_gear_socket_variants(
                cand,
                socketables=socketables,
                ctx=ctx,
                set_group_ids=set_group_ids,
                global_set_cache=global_set_cache,
                ignore_reqs=ignore_reqs,
            )
        if variants:
            candidate_groups.append((cand, variants))
    return candidate_groups
