"""Sorceress build preset profiles and constraints builder."""

from collections.abc import Sequence

from d2savior.core.constants import CLASS_SKILL_BASES
from d2savior.core.d2s_struct import D2SStruct
from d2savior.core.enums import CharClass
from d2savior.core.resolver import GameDataResolver
from d2savior.core.stash import SharedStash
from d2savior.core.stats import (
    compute_anya_resist_bonus,
    get_current_difficulty,
    get_difficulty_resist_penalty,
)
from d2savior.optimizer.common import (
    CharacterBaseline,
    detect_cta_bo_bonus,
    resolve_fixed_gear,
    validate_sorceress,
)
from d2savior.optimizer.native import BuildConstraints, SearchModeStr
from d2savior.optimizer.presets import ConstraintOverrides, resolve_build_expr
from d2savior.optimizer.skill_tables import build_sorc_dps_tables

_SKILL_BLIZZARD = 59
_SKILL_COLD_MASTERY = 65
_BLIZZ_SYNERGY_SKILLS: tuple[int, ...] = (39, 45, 55)

SORCERESS_FCR_FRAMES: frozendict[int, int] = frozendict(
    {0: 13, 9: 12, 20: 11, 37: 10, 63: 9, 105: 8, 200: 7}
)
SORCERESS_FHR_FRAMES: frozendict[int, int] = frozendict(
    {0: 15, 5: 14, 9: 13, 14: 12, 20: 11, 30: 10, 42: 9, 60: 8, 86: 7, 142: 6, 280: 5}
)

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

SORC_ONLY_BUILD_CHOICES: tuple[str, ...] = ("base", "mf", "mf-speed", "mf-pure", "tz", "power")

# (title, mode, allow_mf, min_fcr, min_fhr, min_fr, min_lr, min_cr, min_pr)
_SORC_PRESET_SPECS: frozendict[
    str, tuple[str, SearchModeStr, bool, int, int, int, int, int, int]
] = frozendict(
    {
        "base": (
            "1. 0% MF Base Hunting (105% FCR, 86% FHR, 75% All Res)",
            "power",
            False,
            105,
            86,
            75,
            75,
            75,
            75,
        ),
        "mf-speed": (
            "2A. Max MF & Boss Farm — Speed (105% FCR, 60% FHR, 75% F/L/C)",
            "mf",
            True,
            105,
            60,
            75,
            75,
            75,
            0,
        ),
        "mf-pure": (
            "2B. Max MF & Boss Farm — Pure MF (63% FCR, 60% FHR, 75% F/L/C)",
            "mf",
            True,
            63,
            60,
            75,
            75,
            75,
            0,
        ),
        "tz": (
            "3. Max Power & Terror Zones (105% FCR, 86% FHR, 75% All Res)",
            "power",
            True,
            105,
            86,
            75,
            75,
            75,
            75,
        ),
        "max-res": (
            "4. Max Resist (63% FCR, 60% FHR, Max All Res)",
            "max-res",
            True,
            63,
            60,
            75,
            75,
            75,
            75,
        ),
    }
)


def _extract_blizz_base_skills(char_data: D2SStruct) -> tuple[int, int, int]:
    """Return (blizz_base_lvl, blizz_syn_pts, cm_base_lvl) from character skill points."""
    skills = char_data.skills.skill_levels if char_data.skills else ()
    sorc_base = CLASS_SKILL_BASES[int(CharClass.SORCERESS)]
    if len(skills) >= 30:
        blizz_base = skills[_SKILL_BLIZZARD - sorc_base]
        syn_pts = sum(skills[sid - sorc_base] for sid in _BLIZZ_SYNERGY_SKILLS)
        cm_base = skills[_SKILL_COLD_MASTERY - sorc_base]
        return blizz_base, syn_pts, cm_base
    return 0, 0, 0


def select_sorc_presets(
    char_data: D2SStruct,
    build: str = "all",
    max_charm_slots: int = 23,
    limit: int = 3,
    extra_chars: Sequence[D2SStruct] = (),
    stashes: Sequence[SharedStash] = (),
    resolver: GameDataResolver | None = None,
    bo_base_bonus: int | None = None,
    keep_equipped: bool | str | None = False,
    targets: int = 1,
    left_skill: int | None = None,
    right_skill: int | None = None,
    overrides: ConstraintOverrides | None = None,
) -> list[tuple[str, BuildConstraints]]:
    """Select one or more Sorceress build preset profiles by name."""
    validate_sorceress(char_data)
    # Resolve presets via TOML catalog; raises ValueError for unknown names.
    try:
        resolved_presets = resolve_build_expr(
            build, CharClass.SORCERESS, overrides=overrides, char_name=char_data.get_char_name()
        )
    except ValueError:
        # Re-raise with the legacy error message format expected by existing tests.
        valid = ", ".join((*BUILD_PRESET_ALIASES.keys(), "leveling"))
        raise ValueError(f"Unknown build preset '{build}'; expected one of: {valid}") from None
    char_level = max(1, char_data.player_stats.level or char_data.char_level)
    diff_idx = get_current_difficulty(char_data)
    base_res = get_difficulty_resist_penalty(char_data, diff_idx) + compute_anya_resist_bonus(
        char_data
    )
    if bo_base_bonus is None:
        res_obj = resolver if resolver is not None else GameDataResolver.load()
        bo_base_bonus = detect_cta_bo_bonus(
            (char_data, *extra_chars), stashes, res_obj, max_level=char_level, default=0
        )

    eff_targets = max(1, targets)
    blizz_base_lvl, blizz_syn_pts, cm_base_lvl = _extract_blizz_base_skills(char_data)
    sorc_dps = build_sorc_dps_tables(
        char_data,
        left_skill=left_skill,
        right_skill=right_skill,
        targets=eff_targets,
    )
    fixed_all, fixed_slots = resolve_fixed_gear(keep_equipped)
    baseline = CharacterBaseline(
        char_class=int(CharClass.SORCERESS),
        base_life=char_data.player_stats.max_life,
        base_mana=char_data.player_stats.max_mana,
        base_hell_res=base_res,
        base_str=char_data.player_stats.strength,
        base_dex=char_data.player_stats.dexterity,
        max_charm_slots=max_charm_slots,
        bo_base_bonus=bo_base_bonus,
        use_bo=bo_base_bonus > 0,
        fixed_gear=fixed_all,
        fixed_slots=fixed_slots,
        blizz_base_lvl=blizz_base_lvl,
        blizz_syn_pts=blizz_syn_pts,
        cm_base_lvl=cm_base_lvl,
        targets=eff_targets,
        blizz_dmg=sorc_dps.blizz_dmg,
        filler_dmg=sorc_dps.filler_dmg,
        filler_is_aoe=sorc_dps.filler_is_aoe,
    )

    out: list[tuple[str, BuildConstraints]] = []
    for preset in resolved_presets:
        title = preset.title or preset.name
        if eff_targets > 1:
            title = f"{title} [{eff_targets} targets]"
        kwargs = preset.constraint_kwargs()
        out.append(
            (
                title,
                baseline.build_constraints(
                    limit=limit,
                    **kwargs,
                ),
            )
        )
    return out
