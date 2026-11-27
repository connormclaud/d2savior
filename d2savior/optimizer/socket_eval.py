"""Multi-threaded evaluation and preset orchestration for Larzuk Socket Quest optimization."""

import os
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from typing import Any, cast

from d2savior.core.constants import DIFFICULTY_NAMES
from d2savior.core.d2s_struct import D2SStruct
from d2savior.core.enums import CharClass
from d2savior.core.resolver import GameDataResolver
from d2savior.core.stash import SharedStash
from d2savior.core.stats import get_current_difficulty
from d2savior.optimizer.common import normalize_target_type, parse_keep_gear
from d2savior.optimizer.extract import extract_pool_with_context
from d2savior.optimizer.native import (
    BuildConstraints,
    BuildResult,
    CharmSpec,
    ItemSpec,
    TargetTypeStr,
    optimize_builds,
    score_of_result,
)
from d2savior.optimizer.paladin import (
    build_paladin_baseline,
    build_paladin_preset_constraints,
    detect_paladin_spec,
    paladin_offense_profile,
    probe_paladin_opt1,
)
from d2savior.optimizer.presets import ConstraintOverrides, resolve_build_expr
from d2savior.optimizer.skill_tables import (
    resolve_paladin_aura_id,
    resolve_sorc_cold_armor,
    resolve_sorc_filler_skill,
)
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
from d2savior.optimizer.sorc import select_sorc_presets

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
    char_level_override: int | None = None,
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
            baseline_obj, char_level, diff_name, resolved_spec = build_paladin_baseline(
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
                char_level_override=char_level_override,
            )
            offense = paladin_offense_profile(
                resolved_spec, primary_char, left_skill=left_skill, right_skill=right_skill
            )
            extra_kwargs: dict[str, Any] = {
                k: v for k, v in preset.constraint_kwargs().items() if k != "mode"
            }
            opt1 = probe_paladin_opt1(
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
                char_level_override=char_level_override,
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
    level_override = THEORETICAL_CHAR_LEVEL if theoretical else None
    eff_char_level = THEORETICAL_CHAR_LEVEL if theoretical else char_level
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
    _, _, sorc_armor_id = (
        resolve_sorc_cold_armor(primary_char)
        if char_class == int(CharClass.SORCERESS)
        else (0, 0, None)
    )
    pal_aura_id = (
        resolve_paladin_aura_id(primary_char, pal_spec, right_skill=right_skill)
        if char_class == int(CharClass.PALADIN)
        else None
    )

    base_items, charms, set_group_ids, global_set_cache = extract_pool_with_context(
        primary_char,
        extra_chars=extra_chars,
        stashes=stashes,
        resolver=resolver,
        pal_spec=pal_spec,
        keep_equipped=keep_equipped,
        left_skill=left_skill,
        right_skill=right_skill,
        targets=targets,
        char_level_override=level_override,
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
        pal_spec=pal_spec,
        pal_offense=pal_offense,
        set_group_ids=set_group_ids,
        global_set_cache=global_set_cache,
        sorc_filler_id=sorc_filler_id,
        sorc_armor_id=sorc_armor_id,
        pal_aura_id=pal_aura_id,
        char_level_override=level_override,
        ignore_reqs=theoretical,
    )

    candidate_groups = build_candidate_groups(
        eligible,
        rune_counts=rune_counts,
        socketables=socketables,
        theoretical=theoretical,
        char_level=eff_char_level,
        char_class=char_class,
        pal_spec=pal_spec,
        pal_offense=pal_offense,
        set_group_ids=set_group_ids,
        global_set_cache=global_set_cache,
        sorc_filler_id=sorc_filler_id,
        sorc_armor_id=sorc_armor_id,
        pal_aura_id=pal_aura_id,
        ignore_reqs=theoretical,
    )

    if char_class == int(CharClass.SORCERESS):
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
            target_type=normalize_target_type(target_type),
            left_skill=left_skill,
            right_skill=right_skill,
            overrides=overrides,
            char_level_override=level_override,
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
            target_type=normalize_target_type(target_type),
            left_skill=left_skill,
            right_skill=right_skill,
            overrides=overrides,
            char_level_override=level_override,
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
