"""Python-to-Rust PyO3 build optimizer bridge for D2R Sorceress and Paladin saves."""

from d2savior.optimizer.common import (
    KEEP_GEAR_GROUPS,
    SUPPORTED_OPTIMIZER_CLASSES,
    detect_cta_bo_bonus,
    parse_keep_gear,
    validate_paladin,
    validate_sorceress,
    validate_supported_class,
)
from d2savior.optimizer.extract import extract_pool
from d2savior.optimizer.native import (
    HAS_NATIVE,
    BuildConstraints,
    BuildResult,
    CharmSpec,
    ItemSpec,
    blizzard_damage,
    blizzard_damage_with_base,
    class_breakpoints,
    evaluate_build,
    optimize_builds,
)
from d2savior.optimizer.paladin import (
    PALADIN_BUILD_CHOICES,
    PALADIN_FCR_BPS,
    PALADIN_FCR_FRAMES,
    PALADIN_FHR_BPS,
    PALADIN_FHR_FRAMES,
    PALADIN_SPEC_INFO,
    build_paladin_preset_constraints,
    detect_paladin_spec,
    optimize_paladin_leveling,
    paladin_offense_profile,
    paladin_primary_skill_info,
    select_paladin_max_res_preset,
)
from d2savior.optimizer.presets import ConstraintOverrides, list_presets, resolve_build_expr
from d2savior.optimizer.report import format_build_report, format_paladin_leveling_report
from d2savior.optimizer.sorc import (
    BUILD_PRESET_ALIASES,
    SORC_ONLY_BUILD_CHOICES,
    select_sorc_presets,
)

BUILD_CHOICES: tuple[str, ...] = (*BUILD_PRESET_ALIASES.keys(), *PALADIN_BUILD_CHOICES)

__all__ = [
    "BUILD_CHOICES",
    "BUILD_PRESET_ALIASES",
    "HAS_NATIVE",
    "KEEP_GEAR_GROUPS",
    "PALADIN_BUILD_CHOICES",
    "PALADIN_FCR_BPS",
    "PALADIN_FCR_FRAMES",
    "PALADIN_FHR_BPS",
    "PALADIN_FHR_FRAMES",
    "PALADIN_SPEC_INFO",
    "SORC_ONLY_BUILD_CHOICES",
    "SUPPORTED_OPTIMIZER_CLASSES",
    "BuildConstraints",
    "BuildResult",
    "CharmSpec",
    "ConstraintOverrides",
    "ItemSpec",
    "blizzard_damage",
    "blizzard_damage_with_base",
    "build_paladin_preset_constraints",
    "class_breakpoints",
    "detect_cta_bo_bonus",
    "detect_paladin_spec",
    "evaluate_build",
    "extract_pool",
    "format_build_report",
    "format_paladin_leveling_report",
    "list_presets",
    "optimize_builds",
    "optimize_paladin_leveling",
    "paladin_offense_profile",
    "paladin_primary_skill_info",
    "parse_keep_gear",
    "resolve_build_expr",
    "select_paladin_max_res_preset",
    "select_sorc_presets",
    "validate_paladin",
    "validate_sorceress",
    "validate_supported_class",
]
