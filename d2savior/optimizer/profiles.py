"""Per-class orchestration profiles for optimizer CLI execution and socket evaluation."""

import argparse
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from d2savior.core.constants import DIFFICULTY_NAMES
from d2savior.core.d2s_struct import D2SStruct
from d2savior.core.enums import CharClass
from d2savior.core.resolver import GameDataResolver
from d2savior.core.stash import SharedStash
from d2savior.core.stats import get_current_difficulty, get_difficulty_resist_penalty
from d2savior.optimizer.common import (
    SUPPORTED_OPTIMIZER_CLASSES,
    normalize_target_type,
    supported_classes_label,
)
from d2savior.optimizer.native import (
    BuildConstraints,
    CharmSpec,
    ItemSpec,
    optimize_builds,
)
from d2savior.optimizer.paladin import (
    build_paladin_baseline,
    build_paladin_preset_constraints,
    optimize_paladin_leveling,
    paladin_offense_profile,
    paladin_primary_skill_info,
    probe_paladin_opt1,
    uses_paladin_leveling_probe,
)
from d2savior.optimizer.presets import ConstraintOverrides, resolve_build_expr
from d2savior.optimizer.report import format_build_report, format_paladin_leveling_report
from d2savior.optimizer.skill_tables import build_sorc_dps_tables
from d2savior.optimizer.sorc import select_sorc_presets


def _run_sorc_cli_optimize(
    primary: D2SStruct,
    extras: list[D2SStruct],
    stashes: list[SharedStash],
    items: list[ItemSpec],
    charms: list[CharmSpec],
    resolver: GameDataResolver,
    args: argparse.Namespace,
    primary_inv_loc: str,
    *,
    left_skill: int | None = None,
    right_skill: int | None = None,
    overrides: ConstraintOverrides | None = None,
) -> None:
    filler_name = build_sorc_dps_tables(
        primary, left_skill=left_skill, right_skill=right_skill, targets=args.targets
    ).filler_skill_name
    diff_idx = get_current_difficulty(primary)
    diff_name = DIFFICULTY_NAMES[diff_idx]
    resist_penalty = get_difficulty_resist_penalty(primary, diff_idx)
    for title, constraints in select_sorc_presets(
        primary,
        build=args.build,
        max_charm_slots=args.charm_slots,
        limit=args.limit,
        extra_chars=extras,
        stashes=stashes,
        resolver=resolver,
        keep_equipped=args.keep_gear,
        targets=args.targets,
        target_type=args.target_type,
        left_skill=left_skill,
        right_skill=right_skill,
        overrides=overrides,
    ):
        results = optimize_builds(items, charms, constraints)
        print(
            format_build_report(
                title,
                results,
                charms,
                diff_name=diff_name,
                resist_penalty=resist_penalty,
                primary_inv_loc=primary_inv_loc,
                filler_skill_name=filler_name,
            )
        )
        print()


def _run_paladin_cli_optimize(
    primary: D2SStruct,
    extras: list[D2SStruct],
    stashes: list[SharedStash],
    items: list[ItemSpec],
    charms: list[CharmSpec],
    resolver: GameDataResolver,
    args: argparse.Namespace,
    primary_inv_loc: str,
    *,
    left_skill: int | None = None,
    right_skill: int | None = None,
    overrides: ConstraintOverrides | None = None,
) -> None:
    resolved_presets = resolve_build_expr(
        args.build,
        CharClass.PALADIN,
        overrides=overrides,
        char_name=primary.get_char_name(),
    )
    resist_penalty = get_difficulty_resist_penalty(primary)
    for preset in resolved_presets:
        if uses_paladin_leveling_probe(preset, overrides):
            title, options, resolved_spec, diff_name = optimize_paladin_leveling(
                primary,
                items,
                charms,
                max_charm_slots=args.charm_slots,
                limit=args.limit,
                extra_chars=extras,
                stashes=stashes,
                resolver=resolver,
                keep_equipped=args.keep_gear,
                targets=args.targets,
                target_type=args.target_type,
                left_skill=left_skill,
                right_skill=right_skill,
                overrides=preset.to_overrides(),
                title=preset.title,
            )
            skill_name, base_skill_lvl = paladin_primary_skill_info(primary, resolved_spec)
            report = format_paladin_leveling_report(
                title,
                options,
                charms,
                diff_name=diff_name,
                resist_penalty=resist_penalty,
                primary_skill_name=skill_name,
                primary_skill_base=base_skill_lvl,
                primary_inv_loc=primary_inv_loc,
            )
        else:
            title, constraints, resolved_spec, diff_name = build_paladin_preset_constraints(
                primary,
                preset,
                max_charm_slots=args.charm_slots,
                limit=args.limit,
                extra_chars=extras,
                stashes=stashes,
                resolver=resolver,
                keep_equipped=args.keep_gear,
                targets=args.targets,
                target_type=args.target_type,
                left_skill=left_skill,
                right_skill=right_skill,
            )
            skill_name, base_skill_lvl = paladin_primary_skill_info(primary, resolved_spec)
            report = format_build_report(
                title,
                optimize_builds(items, charms, constraints),
                charms,
                char_class=primary.char_class,
                diff_name=diff_name,
                resist_penalty=resist_penalty,
                primary_skill_name=skill_name,
                primary_skill_base=base_skill_lvl,
                primary_inv_loc=primary_inv_loc,
            )
        print(report)
        print()


def _resolve_sorc_socket_presets(
    primary_char: D2SStruct,
    _base_items: Sequence[ItemSpec],
    _charms: Sequence[CharmSpec],
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
        char_level_override=char_level_override,
    )
    return [(title, c, diff_name) for title, c in sorc_presets]


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
    norm_target_type = normalize_target_type(target_type)
    presets_out: list[tuple[str, BuildConstraints, str]] = []
    for preset in resolved:
        if uses_paladin_leveling_probe(preset, overrides):
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
                target_type=norm_target_type,
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
                target_type=norm_target_type,
                left_skill=left_skill,
                right_skill=right_skill,
                char_level_override=char_level_override,
            )
            presets_out.append((title, constraints, diff_name))
    return presets_out


class CliOptimizeRunner(Protocol):
    def __call__(
        self,
        primary: D2SStruct,
        extras: list[D2SStruct],
        stashes: list[SharedStash],
        items: list[ItemSpec],
        charms: list[CharmSpec],
        resolver: GameDataResolver,
        args: argparse.Namespace,
        primary_inv_loc: str,
        *,
        left_skill: int | None = None,
        right_skill: int | None = None,
        overrides: ConstraintOverrides | None = None,
    ) -> None: ...


class SocketPresetResolver(Protocol):
    def __call__(
        self,
        primary_char: D2SStruct,
        base_items: Sequence[ItemSpec],
        charms: Sequence[CharmSpec],
        /,
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
    ) -> list[tuple[str, BuildConstraints, str]]: ...


@dataclass(frozen=True, slots=True)
class ClassProfile:
    """Thin per-class orchestration adapter for optimizer CLI and socket evaluation."""

    char_class: CharClass
    run_cli_optimize: CliOptimizeRunner
    resolve_socket_presets: SocketPresetResolver


CLASS_PROFILES: frozendict[CharClass, ClassProfile] = frozendict(
    {
        CharClass.SORCERESS: ClassProfile(
            char_class=CharClass.SORCERESS,
            run_cli_optimize=_run_sorc_cli_optimize,
            resolve_socket_presets=_resolve_sorc_socket_presets,
        ),
        CharClass.PALADIN: ClassProfile(
            char_class=CharClass.PALADIN,
            run_cli_optimize=_run_paladin_cli_optimize,
            resolve_socket_presets=_resolve_paladin_socket_presets,
        ),
    }
)


def get_class_profile(char_class: int | CharClass) -> ClassProfile:
    """Look up the optimizer orchestration profile for a character class."""
    cls_enum = CharClass(char_class)
    profile = CLASS_PROFILES.get(cls_enum)
    if profile is None:
        raise ValueError(
            f"Unsupported optimizer class '{cls_enum.display_name}'; "
            f"expected {supported_classes_label(SUPPORTED_OPTIMIZER_CLASSES)}"
        )
    return profile
