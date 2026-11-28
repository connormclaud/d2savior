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

_MAX_MIXED_SOCKETS = 3
_MAX_COMBO_FRONTIER = 64

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
    """A concrete post-Larzuk or filled-socket item + socket filler or runeword `ItemSpec`."""

    item_name: str
    item_loc: str
    slot: str
    kind: str  # "socket" or "runeword"
    action_label: str
    sockets_range: tuple[int, int]
    owned: bool
    missing_runes: tuple[str, ...]
    spec: ItemSpec
    total_sockets: int = 0


@dataclass(frozen=True, slots=True)
class _SocketBasis:
    """A single-socketable basis option with its resolved properties and usable capacity."""

    option: SocketableOption
    props: list[tuple[int, int, list[int]]]
    usable: int


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


def _pareto_prune_entries[T](
    entries: Sequence[tuple[T, SocketCandidateVariant, int]],
) -> list[tuple[T, SocketCandidateVariant]]:
    """Prune strictly dominated `(payload, variant, capacity)` entries, preferring owned & higher capacity."""
    ordered = sorted(
        entries,
        key=lambda e: (not e[1].owned, -e[2], e[1].spec.req_str, e[1].spec.req_dex),
    )
    kept: list[tuple[T, SocketCandidateVariant, int, bool, tuple[int, ...], tuple[int, int]]] = []
    seen_identical: set[tuple[bool, tuple[int, ...], int, int, int]] = set()
    for payload, v, cap in ordered:
        mf_flag = v.spec.mf > 0
        vec = _spec_stat_vec(v.spec)
        reqs = (v.spec.req_str, v.spec.req_dex)
        sig = (mf_flag, vec, reqs[0], reqs[1], cap)
        if sig in seen_identical:
            continue
        seen_identical.add(sig)
        if any(
            (
                _vec_dominates(kmf, kvec, kreqs, mf_flag, vec, reqs)
                or (kmf == mf_flag and kvec == vec and kreqs == reqs)
            )
            and (kv.owned or not v.owned)
            and kcap >= cap
            for _, kv, kcap, kmf, kvec, kreqs in kept
        ):
            continue
        kept = [
            entry
            for entry in kept
            if not (
                _vec_dominates(mf_flag, vec, reqs, entry[3], entry[4], entry[5])
                and (v.owned or not entry[1].owned)
                and cap >= entry[2]
            )
        ]
        kept.append((payload, v, cap, mf_flag, vec, reqs))
    return [(payload, v) for payload, v, _, _, _, _ in kept]


def pareto_prune_variants(variants: list[SocketCandidateVariant]) -> list[SocketCandidateVariant]:
    """Prune strictly dominated variants, keeping owned options ahead of theoretical ties."""
    return [v for _, v in _pareto_prune_entries([(None, v, 0) for v in variants])]


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
                total_sockets=cand.total_sockets,
            )
        )
    return pareto_prune_variants(variants)


def _format_combo_labels(parts: Sequence[tuple[SocketableOption, int]]) -> tuple[str, str]:
    short_parts: list[str] = []
    action_parts: list[str] = []
    for opt, qty in parts:
        prefix = f"{qty}x " if qty > 1 else ""
        loc_tag = f" [{opt.loc}]" if opt.loc else ""
        short_parts.append(f"{prefix}{opt.label}")
        action_parts.append(f"{prefix}{opt.label}{loc_tag}")
    return " + ".join(short_parts), " + ".join(action_parts)


def _synthesize_combo_variant(
    cand: CandidateItem,
    combo_parts: Sequence[tuple[_SocketBasis, int]],
    *,
    ctx: ExtractionContext,
    set_group_ids: dict[str, int],
    global_set_cache: dict[tuple[str, int], list[tuple[int, ItemSpec]]],
    ignore_reqs: bool,
    base_vec: tuple[int, ...] | None,
    base_reqs: tuple[int, int] | None,
) -> SocketCandidateVariant | None:
    extra_props = [p for basis, qty in combo_parts for _ in range(qty) for p in basis.props]
    extra_levelreq = max(basis.option.levelreq for basis, _ in combo_parts)
    short_lbl, action_lbl = _format_combo_labels(
        [(basis.option, qty) for basis, qty in combo_parts]
    )
    variant_name = f"{cand.base_name} [+{short_lbl}]"
    spec = item_to_spec(
        cand.item,
        cand.loc,
        cand.resolver,
        cand.version,
        ctx=ctx,
        set_group_ids=set_group_ids,
        global_set_cache=global_set_cache,
        skip_useful_check=True,
        extra_props=extra_props,
        extra_levelreq=extra_levelreq,
        name_override=variant_name,
        ignore_reqs=ignore_reqs,
    )
    if not isinstance(spec, ItemSpec):
        return None
    if (
        base_vec is not None
        and base_reqs is not None
        and _spec_stat_vec(spec) == base_vec
        and (spec.req_str, spec.req_dex) == base_reqs
    ):
        return None
    owned = all(qty <= basis.option.count for basis, qty in combo_parts)
    return SocketCandidateVariant(
        item_name=cand.base_name,
        item_loc=cand.loc,
        slot=cand.slot,
        kind="socket",
        action_label=action_lbl,
        sockets_range=cand.sockets_range,
        owned=owned,
        missing_runes=(),
        spec=spec,
        total_sockets=cand.total_sockets,
    )


def _expand_mixed_socket_combos(
    cand: CandidateItem,
    basis_list: Sequence[_SocketBasis],
    *,
    max_sockets: int,
    ctx: ExtractionContext,
    set_group_ids: dict[str, int],
    global_set_cache: dict[tuple[str, int], list[tuple[int, ItemSpec]]],
    ignore_reqs: bool,
    base_vec: tuple[int, ...] | None,
    base_reqs: tuple[int, int] | None,
) -> list[SocketCandidateVariant]:
    """Iteratively build Pareto-pruned mixed socket combos for 2..max_sockets."""
    out: list[SocketCandidateVariant] = []
    prev_combos: list[tuple[tuple[int, int], ...]] = [((i, 1),) for i in range(len(basis_list))]
    for _size in range(2, max_sockets + 1):
        seen: set[tuple[tuple[int, int], ...]] = set()
        step_entries: list[tuple[tuple[tuple[int, int], ...], SocketCandidateVariant, int]] = []
        for combo in prev_combos:
            counts = dict(combo)
            for idx, basis in enumerate(basis_list):
                new_qty = counts.get(idx, 0) + 1
                if new_qty > basis.usable:
                    continue
                new_counts = dict(counts)
                new_counts[idx] = new_qty
                new_combo = tuple(sorted(new_counts.items()))
                if new_combo in seen:
                    continue
                seen.add(new_combo)
                variant = _synthesize_combo_variant(
                    cand,
                    [(basis_list[i], q) for i, q in new_combo],
                    ctx=ctx,
                    set_group_ids=set_group_ids,
                    global_set_cache=global_set_cache,
                    ignore_reqs=ignore_reqs,
                    base_vec=base_vec,
                    base_reqs=base_reqs,
                )
                if variant is not None:
                    step_entries.append((new_combo, variant, 0))
        if not step_entries:
            break
        pruned = _pareto_prune_entries(step_entries)
        if len(pruned) > _MAX_COMBO_FRONTIER:
            pruned.sort(key=lambda e: (not e[1].owned, e[1].spec.req_str, e[1].spec.req_dex))
            pruned = pruned[:_MAX_COMBO_FRONTIER]
        out.extend(v for _, v in pruned)
        prev_combos = [c for c, _ in pruned]
    return out


def _expand_homogeneous_socket_combos(
    cand: CandidateItem,
    basis_list: Sequence[_SocketBasis],
    *,
    theoretical: bool,
    ctx: ExtractionContext,
    set_group_ids: dict[str, int],
    global_set_cache: dict[tuple[str, int], list[tuple[int, ItemSpec]]],
    ignore_reqs: bool,
    base_vec: tuple[int, ...] | None,
    base_reqs: tuple[int, int] | None,
) -> list[SocketCandidateVariant]:
    """Synthesize homogeneous multi-socket fills (kx same socketable) for 4+ open sockets."""
    out: list[SocketCandidateVariant] = []
    for basis in basis_list:
        qtys: set[int] = set()
        if basis.usable >= 2:
            qtys.add(basis.usable)
        if theoretical and 1 < basis.option.count < basis.usable:
            qtys.add(basis.option.count)
        for qty in sorted(qtys):
            variant = _synthesize_combo_variant(
                cand,
                [(basis, qty)],
                ctx=ctx,
                set_group_ids=set_group_ids,
                global_set_cache=global_set_cache,
                ignore_reqs=ignore_reqs,
                base_vec=base_vec,
                base_reqs=base_reqs,
            )
            if variant is not None:
                out.append(variant)
    return out


def build_gear_socket_variants(
    cand: CandidateItem,
    *,
    socketables: Sequence[SocketableOption],
    ctx: ExtractionContext,
    set_group_ids: dict[str, int],
    global_set_cache: dict[tuple[str, int], list[tuple[int, ItemSpec]]],
    ignore_reqs: bool = False,
    max_sockets: int = 1,
    theoretical: bool = False,
) -> list[SocketCandidateVariant]:
    """Synthesize and Pareto-prune gem/rune/jewel socket variants (1..max_sockets)."""
    ver_res = cand.resolver
    base_vec = _spec_stat_vec(cand.base_spec) if cand.base_spec is not None else None
    base_reqs = (
        (cand.base_spec.req_str, cand.base_spec.req_dex) if cand.base_spec is not None else None
    )
    single_entries: list[tuple[_SocketBasis, SocketCandidateVariant, int]] = []

    for sock in socketables:
        if sock.levelreq > ctx.char_level:
            continue
        usable = (
            max_sockets
            if (theoretical and not sock.is_jewel) or not sock.owned
            else min(max_sockets, sock.count)
        )
        if usable <= 0:
            continue
        s_props = sock.props_for_item(cand.item, ver_res)
        if not s_props:
            continue
        basis = _SocketBasis(option=sock, props=s_props, usable=usable)
        variant = _synthesize_combo_variant(
            cand,
            [(basis, 1)],
            ctx=ctx,
            set_group_ids=set_group_ids,
            global_set_cache=global_set_cache,
            ignore_reqs=ignore_reqs,
            base_vec=base_vec,
            base_reqs=base_reqs,
        )
        if variant is not None:
            single_entries.append((basis, variant, usable))

    if max_sockets <= 1:
        return pareto_prune_variants([v for _, v, _ in single_entries])

    frontier_1 = _pareto_prune_entries(single_entries)
    if not frontier_1:
        return []

    basis_list = [b for b, _ in frontier_1]
    all_variants: list[SocketCandidateVariant] = [v for _, v in frontier_1]
    if max_sockets <= _MAX_MIXED_SOCKETS:
        all_variants.extend(
            _expand_mixed_socket_combos(
                cand,
                basis_list,
                max_sockets=max_sockets,
                ctx=ctx,
                set_group_ids=set_group_ids,
                global_set_cache=global_set_cache,
                ignore_reqs=ignore_reqs,
                base_vec=base_vec,
                base_reqs=base_reqs,
            )
        )
    else:
        all_variants.extend(
            _expand_homogeneous_socket_combos(
                cand,
                basis_list,
                theoretical=theoretical,
                ctx=ctx,
                set_group_ids=set_group_ids,
                global_set_cache=global_set_cache,
                ignore_reqs=ignore_reqs,
                base_vec=base_vec,
                base_reqs=base_reqs,
            )
        )
    return pareto_prune_variants(all_variants)


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
    no_quest: bool = False,
) -> list[tuple[CandidateItem, list[SocketCandidateVariant]]]:
    """Synthesize and Pareto-prune runeword and socket variants for all eligible candidates."""
    candidate_groups: list[tuple[CandidateItem, list[SocketCandidateVariant]]] = []
    for cand in eligible:
        q = cand.item.quality()
        if no_quest:
            variants: list[SocketCandidateVariant] = []
            if (
                q in (ItemQuality.LOW, ItemQuality.NORMAL, ItemQuality.HIGH)
                and cand.open_sockets == cand.total_sockets
                and cand.total_sockets >= 2
            ):
                variants.extend(
                    build_runeword_variants(
                        cand,
                        rune_counts=rune_counts,
                        theoretical=theoretical,
                        ctx=ctx,
                        set_group_ids=set_group_ids,
                        global_set_cache=global_set_cache,
                        ignore_reqs=ignore_reqs,
                    )
                )
            variants.extend(
                build_gear_socket_variants(
                    cand,
                    socketables=socketables,
                    ctx=ctx,
                    set_group_ids=set_group_ids,
                    global_set_cache=global_set_cache,
                    ignore_reqs=ignore_reqs,
                    max_sockets=max(1, cand.open_sockets),
                    theoretical=theoretical,
                )
            )
            if variants:
                variants = pareto_prune_variants(variants)
        elif q in (ItemQuality.LOW, ItemQuality.NORMAL, ItemQuality.HIGH):
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
                theoretical=theoretical,
            )
        if variants:
            candidate_groups.append((cand, variants))
    return candidate_groups
