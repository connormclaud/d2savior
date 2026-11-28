"""Multi-threaded evaluation and preset orchestration for Larzuk Socket Quest optimization."""

import os
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor

from d2savior.core.constants import DIFFICULTY_NAMES
from d2savior.core.d2s_struct import D2SStruct
from d2savior.core.enums import CharClass
from d2savior.core.resolver import GameDataResolver
from d2savior.core.stash import SharedStash
from d2savior.core.stats import get_current_difficulty
from d2savior.optimizer.common import (
    parse_keep_gear,
    validate_supported_class,
)
from d2savior.optimizer.extract import extract_pool_with_context, resolve_extraction_context
from d2savior.optimizer.native import (
    BuildConstraints,
    BuildResult,
    CharmSpec,
    ItemSpec,
    optimize_builds,
    score_of_result,
)
from d2savior.optimizer.presets import ConstraintOverrides
from d2savior.optimizer.profiles import get_class_profile
from d2savior.optimizer.socket_candidates import (
    THEORETICAL_CHAR_LEVEL,
    CandidateItem,
    SocketCandidateVariant,
    build_candidate_groups,
    collect_eligible_items,
    extract_socketables,
    find_unclaimed_socket_quests,
    get_socket_quest_status,
)
from d2savior.optimizer.socket_report import (
    PresetSocketReport,
    SocketQuestReport,
    SocketUpgradeResult,
)

_EXCLUDED_SLOTS_FOR_CAND: dict[str, frozenset[str]] = {
    "weapon": frozenset({"weapon", "weapon2h"}),
    "shield": frozenset({"shield", "weapon2h"}),
    "weapon2h": frozenset({"weapon", "shield", "weapon2h"}),
}


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
        res.gear_defense,
    )


def _evaluate_candidate_groups(
    base_items: Sequence[ItemSpec],
    charms: list[CharmSpec],
    c1: BuildConstraints,
    baseline: BuildResult | None,
    active_groups: Sequence[tuple[CandidateItem, list[SocketCandidateVariant]]],
) -> list[list[BuildResult]]:
    """Run Rust optimization per candidate group, restricting the candidate's slot and sharing threads."""
    filtered_base_by_slot: dict[str, list[ItemSpec]] = {}
    for cand, _ in active_groups:
        if cand.slot not in filtered_base_by_slot:
            drop = _EXCLUDED_SLOTS_FOR_CAND.get(cand.slot, frozenset({cand.slot}))
            filtered_base_by_slot[cand.slot] = [it for it in base_items if it.slot not in drop]

    def _eval_group(
        group: tuple[CandidateItem, list[SocketCandidateVariant]],
    ) -> list[BuildResult]:
        cand_item, group_vars = group
        trial_items = [
            *filtered_base_by_slot[cand_item.slot],
            *(v.spec for v in group_vars),
        ]
        return optimize_builds(trial_items, charms, c1, baseline)

    if len(active_groups) <= 1:
        return [_eval_group(group) for group in active_groups]
    max_workers = min(len(active_groups), os.cpu_count() or 4)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        return list(executor.map(_eval_group, active_groups))


def evaluate_socket_candidates_for_preset(
    title: str,
    constraints: BuildConstraints,
    base_items: Sequence[ItemSpec],
    charms: Sequence[CharmSpec],
    candidate_groups: Sequence[tuple[CandidateItem, list[SocketCandidateVariant]]],
    *,
    diff_name: str,
    limit: int = 5,
) -> PresetSocketReport:
    """Evaluate every candidate item's socketed variants for a single build preset."""
    c1 = constraints.with_limit(1)
    charms_list = list(charms)
    base_res_list = optimize_builds(list(base_items), charms_list, c1)
    baseline = base_res_list[0] if base_res_list else None

    mode = c1.mode
    offense = c1.offense
    has_aura = bool(getattr(c1.skills, "has_aura", False))

    base_score = score_of_result(baseline, c1) if baseline is not None else ()
    base_extra = _extra_improvement_key(baseline) if baseline is not None else ()

    active_groups = [(cand, variants) for cand, variants in candidate_groups if variants]
    group_results = _evaluate_candidate_groups(base_items, charms_list, c1, baseline, active_groups)

    wins: list[
        tuple[tuple[int, tuple[int, ...], tuple[int, ...], int, int], SocketUpgradeResult]
    ] = []
    for (cand, variants), res_list in zip(active_groups, group_results, strict=True):
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

        cand_score = score_of_result(res, c1)
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

    validate_supported_class(primary_char)
    profile = get_class_profile(primary_char.char_class)

    char_level = max(1, primary_char.player_stats.level or primary_char.char_level)
    level_override = THEORETICAL_CHAR_LEVEL if theoretical else None
    kept_slots = parse_keep_gear(keep_equipped)
    ctx = resolve_extraction_context(
        primary_char,
        left_skill=left_skill,
        right_skill=right_skill,
        targets=targets,
        char_level_override=level_override,
    )

    base_items, charms, set_group_ids, global_set_cache = extract_pool_with_context(
        primary_char,
        extra_chars=extra_chars,
        stashes=stashes,
        resolver=resolver,
        ctx=ctx,
        keep_equipped=keep_equipped,
        ignore_reqs=theoretical,
    )

    socketables, rune_counts, gem_type_count, jewel_count = extract_socketables(
        primary_char,
        extra_chars=extra_chars,
        stashes=stashes,
        resolver=resolver,
        theoretical=theoretical,
    )

    eligible = collect_eligible_items(
        primary_char,
        extra_chars=extra_chars,
        stashes=stashes,
        resolver=resolver,
        kept_slots=kept_slots,
        ctx=ctx,
        set_group_ids=set_group_ids,
        global_set_cache=global_set_cache,
        ignore_reqs=theoretical,
    )

    candidate_groups = build_candidate_groups(
        eligible,
        rune_counts=rune_counts,
        socketables=socketables,
        theoretical=theoretical,
        ctx=ctx,
        set_group_ids=set_group_ids,
        global_set_cache=global_set_cache,
        ignore_reqs=theoretical,
    )

    preset_specs = profile.resolve_socket_presets(
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
        char_level_override=level_override,
    )
    diff_name = (
        preset_specs[0][2]
        if preset_specs
        else DIFFICULTY_NAMES[get_current_difficulty(primary_char)]
    )

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
        char_class_name=CharClass(ctx.char_class).display_name,
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
