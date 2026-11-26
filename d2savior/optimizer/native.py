"""Optional PyO3 native optimizer bindings and graceful fallback stubs."""

from typing import TYPE_CHECKING, Literal, Never

type SearchModeStr = Literal["power", "mf", "max-res", "leveling", "leveling-res"]
type OffenseProfileStr = Literal["caster", "melee", "zeal", "smite"]
type TargetTypeStr = Literal["trash", "champion", "boss"]

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
        CasterSkillModel,
        CharacterStats,
        CharmSpec,
        ItemSpec,
        MeleeSkillModel,
        SkillModel,
        TargetProfile,
        blizzard_damage,
        blizzard_damage_with_base,
        class_breakpoints,
        evaluate_build,
        optimize_builds,
        score_of_result,
    )

    HAS_NATIVE: bool = True
else:
    try:
        from d2savior._native import (
            BuildConstraints,
            BuildResult,
            CasterSkillModel,
            CharacterStats,
            CharmSpec,
            ItemSpec,
            MeleeSkillModel,
            TargetProfile,
            blizzard_damage,
            blizzard_damage_with_base,
            class_breakpoints,
            evaluate_build,
            optimize_builds,
            score_of_result,
        )

        type SkillModel = CasterSkillModel | MeleeSkillModel
        HAS_NATIVE = True
    except ImportError:
        HAS_NATIVE = False
        BuildConstraints = _missing_native
        BuildResult = _missing_native
        CasterSkillModel = _missing_native
        CharacterStats = _missing_native
        CharmSpec = _missing_native
        ItemSpec = _missing_native
        MeleeSkillModel = _missing_native
        TargetProfile = _missing_native
        type SkillModel = object
        blizzard_damage = _missing_native
        blizzard_damage_with_base = _missing_native
        class_breakpoints = _missing_native
        evaluate_build = _missing_native
        optimize_builds = _missing_native
        score_of_result = _missing_native
