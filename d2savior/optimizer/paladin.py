"""Paladin leveling presets, spec detection, and breakpoint trade-off search."""

from collections.abc import Sequence
from typing import Any

from d2savior.core.constants import (
    BASE_MAX_RESIST,
    CLASS_SKILL_BASES,
    DIFFICULTY_NAMES,
    HARD_MAX_RESIST,
)
from d2savior.core.d2s_struct import D2SStruct
from d2savior.core.enums import CharClass
from d2savior.core.resolver import GameDataResolver
from d2savior.core.stash import SharedStash
from d2savior.core.stats import (
    compute_anya_resist_bonus,
    compute_paladin_passive_max_res,
    get_current_difficulty,
    get_difficulty_resist_penalty,
)
from d2savior.optimizer.common import (
    CharacterBaseline,
    active_skill_bindings,
    detect_cta_bo_bonus,
    resolve_fixed_gear,
    synthesize_monster_stats,
    validate_paladin,
)
from d2savior.optimizer.common import (
    normalize_target_type as _normalize_target_type,
)
from d2savior.optimizer.native import (
    HAS_NATIVE,
    BuildConstraints,
    BuildResult,
    CharacterStats,
    CharmSpec,
    ItemSpec,
    MeleeSkillModel,
    OffenseProfileStr,
    SearchModeStr,
    TargetProfile,
    TargetTypeStr,
    class_breakpoints,
    optimize_builds,
)
from d2savior.optimizer.presets import ConstraintOverrides, ResolvedPreset
from d2savior.optimizer.skill_tables import build_paladin_dps_tables

PALADIN_BUILD_CHOICES: tuple[str, ...] = ("leveling",)

PALADIN_FHR_FRAMES: frozendict[int, int] = frozendict(
    {0: 9, 7: 8, 15: 7, 27: 6, 48: 5, 86: 4, 200: 3}
)
PALADIN_FCR_FRAMES: frozendict[int, int] = frozendict(
    {0: 15, 9: 14, 18: 13, 30: 12, 48: 11, 75: 10, 125: 9}
)

if HAS_NATIVE:
    _pal_fcr_list, _pal_fhr_list = class_breakpoints(int(CharClass.PALADIN))
    PALADIN_FCR_BPS: tuple[int, ...] = tuple(_pal_fcr_list)
    PALADIN_FHR_BPS: tuple[int, ...] = tuple(_pal_fhr_list)
else:
    PALADIN_FCR_BPS = tuple(PALADIN_FCR_FRAMES)
    PALADIN_FHR_BPS = tuple(PALADIN_FHR_FRAMES)

# Paladin skill array offsets relative to CLASS_SKILL_BASES[CharClass.PALADIN] (96, per skills.txt).
_PAL_SACRIFICE = 0
_PAL_SMITE = 1
_PAL_MIGHT = 2
_PAL_RESIST_FIRE = 4
_PAL_HOLY_BOLT = 5
_PAL_HOLY_FIRE = 6
_PAL_DEFIANCE = 8
_PAL_RESIST_COLD = 9
_PAL_ZEAL = 10
_PAL_CHARGE = 11
_PAL_BLESSED_AIM = 12
_PAL_RESIST_LIGHT = 14
_PAL_VENGEANCE = 15
_PAL_BLESSED_HAMMER = 16
_PAL_CONCENTRATION = 17
_PAL_HOLY_FREEZE = 18
_PAL_VIGOR = 19
_PAL_HOLY_SHIELD = 21
_PAL_HOLY_SHOCK = 22
_PAL_FOH = 25
_PAL_FANATICISM = 26

PALADIN_SPEC_INFO: frozendict[str, tuple[int | None, str | None, frozenset[int]]] = frozendict(
    {
        "holy-fire": (102, "Holy Fire", frozenset({1})),
        "holy-freeze": (114, "Holy Freeze", frozenset({1})),
        "holy-shock": (118, "Holy Shock", frozenset({1})),
        "hammer": (112, "Blessed Hammer", frozenset({0})),
        "foh": (121, "Fist of the Heavens", frozenset({0})),
        "holy-bolt": (101, "Holy Bolt", frozenset({0})),
        "smite": (97, "Smite", frozenset({0})),
        "zeal": (106, "Zeal", frozenset({0})),
        "vengeance": (111, "Vengeance", frozenset({0})),
        "charge": (107, "Charge", frozenset({0})),
        "sacrifice": (96, "Sacrifice", frozenset({0})),
        "leveling": (None, None, frozenset({0, 1})),
    }
)
_PALADIN_CASTER_SPECS: frozenset[str] = frozenset({"hammer", "foh", "holy-bolt"})


_SKILL_ID_SMITE = 97
_SKILL_ID_ZEAL = 106
_ELEMENTAL_AURA_SKILL_IDS: frozenset[int] = frozenset({102, 114, 118})


def paladin_offense_profile(
    spec: str,
    char_data: D2SStruct | None = None,
    *,
    left_skill: int | None = None,
    right_skill: int | None = None,
) -> OffenseProfileStr:
    """Return Rust OffenseProfile name ('smite', 'caster', 'zeal', or 'melee') for a Paladin spec.

    For aura/leveling specs, locks to the active bound skills in the save file (or CLI overrides)
    when present (e.g. normal Attack + Holy Fire -> 'melee', Zeal + Holy Fire -> 'zeal',
    Smite + Holy Fire -> 'smite'), falling back to hard skill points only when no active
    bindings are populated.
    """
    if left_skill == _SKILL_ID_SMITE:
        return "smite"
    if spec == "smite":
        return "smite"
    if spec in _PALADIN_CASTER_SPECS:
        return "caster"
    if spec == "zeal":
        return "zeal"
    if spec in ("holy-fire", "holy-freeze", "holy-shock", "leveling") and char_data is not None:
        skills = char_data.skills.skill_levels if char_data.skills else ()
        has_smite = len(skills) > _PAL_SMITE and skills[_PAL_SMITE] > 0
        has_zeal = len(skills) > _PAL_ZEAL and skills[_PAL_ZEAL] > 0
        active_left, active_right = active_skill_bindings(char_data)
        eff_left = left_skill if left_skill is not None else active_left
        eff_right = right_skill if right_skill is not None else active_right
        has_bindings = (
            left_skill is not None or right_skill is not None or eff_left != 0 or eff_right != 0
        )
        if has_bindings:
            if has_smite and _SKILL_ID_SMITE in (eff_left, eff_right):
                return "smite"
            if has_zeal and _SKILL_ID_ZEAL in (eff_left, eff_right):
                return "zeal"
            return "melee"
        if has_zeal:
            return "zeal"
    return "melee"


def detect_paladin_spec(
    char_data: D2SStruct,
    *,
    left_skill: int | None = None,
    right_skill: int | None = None,
) -> str:
    """Infer the primary Paladin leveling specialization from allocated hard skill points."""
    skills = char_data.skills.skill_levels if char_data.skills else ()
    if len(skills) < 30:
        return "leveling"
    active_left, active_right = active_skill_bindings(char_data)
    if left_skill == _SKILL_ID_SMITE and right_skill not in _ELEMENTAL_AURA_SKILL_IDS:
        return "smite"
    if right_skill == -1:
        eff_left = left_skill if left_skill is not None else active_left
        if eff_left == _SKILL_ID_SMITE:
            return "smite"
        return "zeal" if eff_left == _SKILL_ID_ZEAL else "leveling"
    if right_skill is not None and right_skill > 0:
        for spec_name in ("holy-fire", "holy-freeze", "holy-shock"):
            if PALADIN_SPEC_INFO[spec_name][0] == right_skill:
                return spec_name
    candidates: list[tuple[int, int, str]] = [
        (skills[_PAL_HOLY_FIRE], skills[_PAL_HOLY_FIRE] + skills[_PAL_RESIST_FIRE], "holy-fire"),
        (
            skills[_PAL_HOLY_FREEZE],
            skills[_PAL_HOLY_FREEZE] + skills[_PAL_RESIST_COLD],
            "holy-freeze",
        ),
        (
            skills[_PAL_HOLY_SHOCK],
            skills[_PAL_HOLY_SHOCK] + skills[_PAL_RESIST_LIGHT],
            "holy-shock",
        ),
        (
            skills[_PAL_BLESSED_HAMMER],
            skills[_PAL_BLESSED_HAMMER]
            + skills[_PAL_CONCENTRATION]
            + skills[_PAL_BLESSED_AIM]
            + skills[_PAL_VIGOR],
            "hammer",
        ),
        (skills[_PAL_FOH], skills[_PAL_FOH] + skills[_PAL_HOLY_BOLT], "foh"),
        (skills[_PAL_HOLY_BOLT], skills[_PAL_HOLY_BOLT] + skills[_PAL_FOH], "holy-bolt"),
        (
            skills[_PAL_SMITE],
            skills[_PAL_SMITE] + skills[_PAL_FANATICISM] + skills[_PAL_HOLY_SHIELD],
            "smite",
        ),
        (
            skills[_PAL_ZEAL],
            skills[_PAL_ZEAL] + skills[_PAL_SACRIFICE] + skills[_PAL_FANATICISM],
            "zeal",
        ),
        (
            skills[_PAL_VENGEANCE],
            skills[_PAL_VENGEANCE]
            + skills[_PAL_RESIST_FIRE]
            + skills[_PAL_RESIST_COLD]
            + skills[_PAL_RESIST_LIGHT],
            "vengeance",
        ),
        (
            skills[_PAL_CHARGE],
            skills[_PAL_CHARGE] + skills[_PAL_VIGOR] + skills[_PAL_MIGHT],
            "charge",
        ),
        (skills[_PAL_SACRIFICE], skills[_PAL_SACRIFICE] + skills[_PAL_FANATICISM], "sacrifice"),
    ]
    eff_left = left_skill if left_skill is not None else active_left
    eff_right = right_skill if right_skill is not None else active_right
    active_bindings = {eff_left, eff_right}
    best_pts, _, _, best_spec = max(
        (
            (
                pts,
                syn,
                1 if PALADIN_SPEC_INFO[name][0] in active_bindings else 0,
                name,
            )
            for pts, syn, name in candidates
        ),
        key=lambda c: (c[0], c[1], c[2]),
    )
    return best_spec if best_pts > 0 else "leveling"


def paladin_primary_skill_info(char_data: D2SStruct, spec: str) -> tuple[str | None, int]:
    """Return `(skill_name, allocated_hard_points)` for a Paladin spec."""
    spec_info = PALADIN_SPEC_INFO.get(spec)
    if spec_info is None:
        return None, 0
    skill_id, skill_name, _ = spec_info
    if skill_id is None or skill_name is None:
        return None, 0
    skills = char_data.skills.skill_levels if char_data.skills else ()
    pal_base = CLASS_SKILL_BASES[int(CharClass.PALADIN)]
    offset = skill_id - pal_base
    base_lvl = skills[offset] if 0 <= offset < len(skills) else 0
    return skill_name, base_lvl


def _build_paladin_baseline(
    char_data: D2SStruct,
    *,
    spec: str | None,
    max_charm_slots: int,
    extra_chars: Sequence[D2SStruct],
    stashes: Sequence[SharedStash],
    resolver: GameDataResolver | None,
    bo_base_bonus: int | None,
    keep_equipped: bool | str | None,
    targets: int = 1,
    target_type: TargetTypeStr = "champion",
    left_skill: int | None = None,
    right_skill: int | None = None,
    char_level_override: int | None = None,
) -> tuple[CharacterBaseline, int, str, str]:
    validate_paladin(char_data)
    resolved_target_type = _normalize_target_type(target_type)
    resolved_spec = (
        spec.lower()
        if spec
        else detect_paladin_spec(char_data, left_skill=left_skill, right_skill=right_skill)
    )
    if resolved_spec not in PALADIN_SPEC_INFO:
        valid = ", ".join(PALADIN_SPEC_INFO)
        raise ValueError(f"Unknown Paladin spec '{resolved_spec}'; expected one of: {valid}")
    char_level = (
        char_level_override
        if char_level_override is not None
        else max(1, char_data.player_stats.level or char_data.char_level)
    )
    diff_idx = get_current_difficulty(char_data)
    diff_name = DIFFICULTY_NAMES[diff_idx]
    base_res = get_difficulty_resist_penalty(char_data, diff_idx) + compute_anya_resist_bonus(
        char_data
    )
    base_max_fr, base_max_lr, base_max_cr = compute_paladin_passive_max_res(char_data)
    if bo_base_bonus is None:
        res_obj = resolver if resolver is not None else GameDataResolver.load()
        bo_base_bonus = detect_cta_bo_bonus(
            (char_data, *extra_chars), stashes, res_obj, max_level=char_level, default=0
        )
    offense = paladin_offense_profile(
        resolved_spec, char_data, left_skill=left_skill, right_skill=right_skill
    )
    if offense in ("zeal", "melee", "smite"):
        dps_tables = build_paladin_dps_tables(
            char_data, resolved_spec, offense, right_skill=right_skill
        )
        aura_hit_dmg = dps_tables.aura_hit_dmg
        aura_pulse_dps = dps_tables.aura_pulse_dps
        action_ed = dps_tables.action_ed
        action_hits = dps_tables.action_hits
        has_aura = dps_tables.has_aura
        aura_is_fire = dps_tables.aura_is_fire
        action_ar_pct = dps_tables.action_ar_pct
        aura_ar_pct = dps_tables.aura_ar_pct
        aura_target_def_pct = dps_tables.aura_target_def_pct
        aura_ed = dps_tables.aura_ed
        aura_ias = dps_tables.aura_ias
    else:
        aura_hit_dmg = ()
        aura_pulse_dps = ()
        action_ed = ()
        action_hits = ()
        has_aura = False
        aura_is_fire = False
        action_ar_pct = ()
        aura_ar_pct = ()
        aura_target_def_pct = ()
        aura_ed = ()
        aura_ias = ()
    target_def, target_ar, target_lvl, target_hp = synthesize_monster_stats(
        diff_idx, resolved_target_type, char_level
    )
    pal_skills = char_data.skills.skill_levels if char_data.skills else ()
    holy_shield_base_lvl = pal_skills[_PAL_HOLY_SHIELD] if len(pal_skills) > _PAL_HOLY_SHIELD else 0
    defiance_base_lvl = pal_skills[_PAL_DEFIANCE] if len(pal_skills) > _PAL_DEFIANCE else 0
    fixed_all, fixed_slots = resolve_fixed_gear(keep_equipped)
    baseline = CharacterBaseline(
        character=CharacterStats(
            char_class=int(CharClass.PALADIN),
            char_level=char_level,
            base_life=char_data.player_stats.max_life,
            base_mana=char_data.player_stats.max_mana,
            base_str=char_data.player_stats.strength,
            base_dex=char_data.player_stats.dexterity,
            base_hell_res=base_res,
            base_max_fr=base_max_fr,
            base_max_lr=base_max_lr,
            base_max_cr=base_max_cr,
            bo_base_bonus=bo_base_bonus,
            use_bo=bo_base_bonus > 0,
        ),
        target=TargetProfile(
            targets=max(1, targets),
            target_type=resolved_target_type,
            target_def=target_def,
            target_ar=target_ar,
            target_lvl=target_lvl,
            target_hp=target_hp,
        ),
        skills=MeleeSkillModel(
            aura_hit_dmg=aura_hit_dmg,
            aura_pulse_dps=aura_pulse_dps,
            action_ed=action_ed,
            action_hits=action_hits,
            has_aura=has_aura,
            aura_is_fire=aura_is_fire,
            action_ar_pct=action_ar_pct,
            aura_ar_pct=aura_ar_pct,
            aura_target_def_pct=aura_target_def_pct,
            holy_shield_base_lvl=holy_shield_base_lvl,
            defiance_base_lvl=defiance_base_lvl,
            aura_ed=aura_ed,
            aura_ias=aura_ias,
        ),
        max_charm_slots=max_charm_slots,
        fixed_gear=fixed_all,
        fixed_slots=fixed_slots,
    )
    return baseline, char_level, diff_name, resolved_spec


def select_paladin_max_res_preset(
    char_data: D2SStruct,
    max_charm_slots: int = 23,
    limit: int = 3,
    extra_chars: Sequence[D2SStruct] = (),
    stashes: Sequence[SharedStash] = (),
    resolver: GameDataResolver | None = None,
    bo_base_bonus: int | None = None,
    spec: str | None = None,
    keep_equipped: bool | str | None = False,
    targets: int = 1,
    target_type: TargetTypeStr = "champion",
    left_skill: int | None = None,
    right_skill: int | None = None,
    overrides: ConstraintOverrides | None = None,
) -> tuple[str, BuildConstraints, str]:
    """Build a Max Resist constraint profile for a Paladin at its current difficulty."""
    preset = ResolvedPreset(
        name="max-res",
        title=None,
        char_class="paladin",
        strategy=None,
        mode="max-res",
    ).apply_overrides(overrides)
    title, constraints, resolved_spec, _ = build_paladin_preset_constraints(
        char_data,
        preset,
        max_charm_slots=max_charm_slots,
        limit=limit,
        extra_chars=extra_chars,
        stashes=stashes,
        resolver=resolver,
        bo_base_bonus=bo_base_bonus,
        spec=spec,
        keep_equipped=keep_equipped,
        targets=targets,
        target_type=target_type,
        left_skill=left_skill,
        right_skill=right_skill,
    )
    return title, constraints, resolved_spec


def build_paladin_preset_constraints(
    char_data: D2SStruct,
    preset: ResolvedPreset,
    *,
    max_charm_slots: int = 23,
    limit: int = 3,
    extra_chars: Sequence[D2SStruct] = (),
    stashes: Sequence[SharedStash] = (),
    resolver: GameDataResolver | None = None,
    bo_base_bonus: int | None = None,
    spec: str | None = None,
    keep_equipped: bool | str | None = False,
    targets: int = 1,
    target_type: TargetTypeStr = "champion",
    left_skill: int | None = None,
    right_skill: int | None = None,
    char_level_override: int | None = None,
) -> tuple[str, BuildConstraints, str, str]:
    """Build a `BuildConstraints` profile from a resolved TOML preset for a Paladin."""
    eff_targets = max(1, targets)
    resolved_target_type = _normalize_target_type(target_type)
    baseline, char_level, diff_name, resolved_spec = _build_paladin_baseline(
        char_data,
        spec=spec,
        max_charm_slots=max_charm_slots,
        extra_chars=extra_chars,
        stashes=stashes,
        resolver=resolver,
        bo_base_bonus=bo_base_bonus,
        keep_equipped=keep_equipped,
        targets=eff_targets,
        target_type=resolved_target_type,
        left_skill=left_skill,
        right_skill=right_skill,
        char_level_override=char_level_override,
    )
    offense = paladin_offense_profile(
        resolved_spec, char_data, left_skill=left_skill, right_skill=right_skill
    )
    constraints = baseline.build_constraints(
        limit=limit,
        offense=offense,
        **preset.constraint_kwargs(),
    )
    target_type_part = f", {resolved_target_type}" if resolved_target_type != "champion" else ""
    if preset.title:
        extra = [
            f"{eff_targets} targets" if eff_targets > 1 else "",
            resolved_target_type if resolved_target_type != "champion" else "",
        ]
        extra_str = ", ".join(p for p in extra if p)
        title = f"{preset.title} [{extra_str}]" if extra_str else preset.title
    elif preset.mode == "max-res" and preset.name == "max-res":
        title = f"Paladin Max Resist (lvl {char_level}, {diff_name}{target_type_part})"
    else:
        mode_label = (
            "Max Resist" if preset.mode == "max-res" else preset.mode.replace("-", " ").title()
        )
        name_part = "" if preset.name in ("leveling", preset.mode) else f" — {preset.name}"
        target_suffix = f", {eff_targets} targets" if eff_targets > 1 else ""
        title = f"Paladin {mode_label}{name_part} (lvl {char_level}, {diff_name}{target_suffix}{target_type_part})"
    return title, constraints, resolved_spec, diff_name


def _step_below_bp(bp: int, table: tuple[int, ...]) -> int | None:
    lower = [b for b in table if b < bp]
    return lower[-1] if lower else None


def _eff_paladin_skills(res: BuildResult, *, has_aura: bool = False) -> int:
    extra = (
        getattr(res, "aura_skill_bonus", 0) if has_aura else getattr(res, "action_skill_bonus", 0)
    )
    return res.skills + res.primary_skill_bonus + extra


def _result_dedup_key(
    res: BuildResult, *, is_caster: bool = False, has_aura: bool = False
) -> tuple[object, ...]:
    return (
        res.fhr_bp,
        res.fcr_bp if is_caster else 0,
        _eff_paladin_skills(res, has_aura=has_aura),
        round(getattr(res, "dps", 0.0)),
        res.cb,
        res.ias_bp,
        res.cbf,
        res.fr,
        res.lr,
        res.cr,
        res.pr,
        res.life_bo,
        res.frw,
        tuple(sorted((it.slot, it.name) for it in res.items)),
        tuple(sorted(c.name for c in res.charms)),
    )


def _dps_gain_label(opt1: BuildResult, res: BuildResult) -> str | None:
    """Return DPS tradeoff label using effective `res.dps`, clarifying AR/CTH-only gains."""
    dps1 = getattr(opt1, "dps", 0.0)
    dps2 = getattr(res, "dps", 0.0)
    if not (dps1 > 0.0 and dps2 > dps1 * 1.02):
        return None
    raw1 = getattr(opt1, "raw_dps", 0.0)
    raw2 = getattr(res, "raw_dps", 0.0)
    if raw1 > 0.0 and raw2 > 0.0 and raw2 <= raw1 * 1.005:
        return "Higher Effective DPS"
    return "Higher DPS"


def _describe_lower_fhr_tradeoff(
    opt1: BuildResult,
    res: BuildResult,
    *,
    sk_diff: int,
    res_diff: int,
) -> str:
    # Tradeoff labels compare CTH-adjusted effective DPS (`res.dps`) used by ranking/dedup,
    # whereas report lines display sheet `raw_dps` + `AR (CTH%)`.
    frames = PALADIN_FHR_FRAMES.get(res.fhr_bp, 9)
    prefix = f"Lower FHR BP ({res.fhr_bp}%, {frames}f)"
    dps_label = _dps_gain_label(opt1, res)
    gained_ias = res.ias_bp > opt1.ias_bp
    if dps_label and res_diff > 0:
        return f"{prefix} — {dps_label} & Resists"
    if dps_label:
        return f"{prefix} — {dps_label}"
    if sk_diff > 0 and res_diff > 0:
        return f"{prefix} — Higher Skills & Resists"
    if gained_ias and sk_diff > 0:
        return f"{prefix} — Higher IAS & Skills"
    if gained_ias and res_diff > 0:
        return f"{prefix} — Higher IAS & Resists"
    if res_diff > 0 and res.frw > opt1.frw:
        return f"{prefix} — Better Resists & FRW"
    if res_diff > 0:
        return f"{prefix} — Better Resists"
    if gained_ias:
        return f"{prefix} — Higher IAS"
    if sk_diff > 0:
        return f"{prefix} — Higher Skills"
    if res.cb > opt1.cb:
        return f"{prefix} — Higher Crushing Blow"
    if res.cbf and not opt1.cbf:
        return f"{prefix} — Cannot Be Frozen"
    if res.life_bo > opt1.life_bo or res.frw > opt1.frw:
        return f"{prefix} — More Life / FRW"
    return prefix


def _describe_paladin_tradeoff(
    opt1: BuildResult,
    res: BuildResult,
    *,
    is_caster: bool,
    is_smite: bool,
    has_aura: bool = False,
) -> str:
    res_diff = (res.fr + res.lr + res.cr + res.pr) - (opt1.fr + opt1.lr + opt1.cr + opt1.pr)
    sk_diff = _eff_paladin_skills(res, has_aura=has_aura) - _eff_paladin_skills(
        opt1, has_aura=has_aura
    )
    # Compare effective DPS (`res.dps`), matching ranking/dedup (see `_dps_gain_label`).
    if res.fhr_bp < opt1.fhr_bp:
        return _describe_lower_fhr_tradeoff(opt1, res, sk_diff=sk_diff, res_diff=res_diff)
    if is_caster and res.fcr_bp < opt1.fcr_bp:
        fcr_f = PALADIN_FCR_FRAMES.get(res.fcr_bp, 15)
        if res_diff > 0:
            return f"Lower FCR BP ({res.fcr_bp}%, {fcr_f}f) — Better Resists"
        if sk_diff > 0:
            return f"Lower FCR BP ({res.fcr_bp}%, {fcr_f}f) — Higher Skills"
        return f"Lower FCR BP ({res.fcr_bp}%, {fcr_f}f)"
    if res_diff > 0:
        return "Max Resist Cap"
    if is_smite and res.cb > opt1.cb:
        return "Max Smite Offense (CB/IAS)"
    if dps_label := _dps_gain_label(opt1, res):
        return dps_label
    if res.ias_bp > opt1.ias_bp:
        return "Higher IAS"
    if sk_diff > 0:
        return "Max Skill Damage"
    if res.cbf and not opt1.cbf:
        return "Cannot Be Frozen"
    if res.life_bo > opt1.life_bo or res.frw > opt1.frw:
        return "More Life / FRW"
    return "Balanced Alternative"


def _format_opt1_label(opt1: BuildResult, *, is_caster: bool) -> str:
    frames = PALADIN_FHR_FRAMES.get(opt1.fhr_bp, 9)
    if is_caster:
        return f"High Breakpoint ({opt1.fcr_bp}% FCR / {opt1.fhr_bp}% FHR, {frames}f)"
    return f"High Breakpoint ({opt1.fhr_bp}% FHR, {frames}f)"


def _probe_paladin_opt1(
    items: list[ItemSpec],
    charms: list[CharmSpec],
    baseline: CharacterBaseline,
    *,
    offense: OffenseProfileStr,
    is_caster: bool,
    extra_kwargs: dict[str, Any] | None = None,
) -> BuildResult | None:
    ek: dict[str, Any] = dict(extra_kwargs or {})
    floor_fcr = int(ek.pop("min_fcr", 0))
    floor_fhr = int(ek.pop("min_fhr", 0))
    ek.pop("mode", None)
    best_fcr_bp = floor_fcr
    if is_caster:
        found_fcr = False
        for fcr_cand in sorted(
            {floor_fcr, *(b for b in PALADIN_FCR_BPS if b >= floor_fcr)}, reverse=True
        ):
            c = baseline.build_constraints(
                mode="leveling-res",
                limit=1,
                min_fcr=fcr_cand,
                min_fhr=floor_fhr,
                offense=offense,
                **ek,
            )
            if optimize_builds(items, charms, c):
                best_fcr_bp = fcr_cand
                found_fcr = True
                break
        if not found_fcr:
            return None

    for fhr_cand in sorted(
        {floor_fhr, *(b for b in PALADIN_FHR_BPS if b >= floor_fhr)}, reverse=True
    ):
        c = baseline.build_constraints(
            mode="leveling-res",
            limit=1,
            min_fcr=best_fcr_bp,
            min_fhr=fhr_cand,
            offense=offense,
            **ek,
        )
        probe = optimize_builds(items, charms, c)
        if probe:
            return probe[0]
    return None


def _collect_paladin_alternatives(
    items: list[ItemSpec],
    charms: list[CharmSpec],
    baseline: CharacterBaseline,
    opt1: BuildResult,
    *,
    limit: int,
    offense: OffenseProfileStr,
    is_caster: bool,
    is_smite: bool,
    extra_kwargs: dict[str, Any] | None = None,
) -> list[tuple[str, BuildResult]]:
    has_aura = bool(getattr(baseline.skills, "has_aura", False))
    ek: dict[str, Any] = dict(extra_kwargs or {})
    floor_fcr = int(ek.pop("min_fcr", 0))
    floor_fhr = int(ek.pop("min_fhr", 0))
    ek.pop("mode", None)
    collected: list[tuple[str, BuildResult]] = [
        (_format_opt1_label(opt1, is_caster=is_caster), opt1)
    ]
    seen: set[tuple[object, ...]] = {
        _result_dedup_key(opt1, is_caster=is_caster, has_aura=has_aura)
    }

    def try_add(constraints: BuildConstraints) -> None:
        if len(collected) >= limit:
            return
        for res in optimize_builds(items, charms, constraints):
            if len(collected) >= limit:
                return
            key = _result_dedup_key(res, is_caster=is_caster, has_aura=has_aura)
            if key not in seen:
                seen.add(key)
                collected.append(
                    (
                        _describe_paladin_tradeoff(
                            opt1, res, is_caster=is_caster, is_smite=is_smite, has_aura=has_aura
                        ),
                        res,
                    )
                )

    def build_c(
        *,
        mode: SearchModeStr,
        min_fcr: int = 0,
        min_fhr: int = 0,
        res_limit: int = 1,
    ) -> BuildConstraints:
        return baseline.build_constraints(
            mode=mode,
            limit=res_limit,
            min_fcr=max(min_fcr, floor_fcr),
            min_fhr=max(min_fhr, floor_fhr),
            offense=offense,
            **ek,
        )

    def _clamped_below(bp: int, table: tuple[int, ...], floor: int) -> int | None:
        step = _step_below_bp(bp, table)
        if step is None or step < floor:
            return floor if floor < bp else None
        return step

    fhr_below = _clamped_below(opt1.fhr_bp, PALADIN_FHR_BPS, floor_fhr)
    fcr_below = _clamped_below(opt1.fcr_bp, PALADIN_FCR_BPS, floor_fcr) if is_caster else None
    caster_fcr_floor = max(opt1.fcr_bp, floor_fcr) if is_caster else floor_fcr

    cap_fr = min(BASE_MAX_RESIST + baseline.character.base_max_fr, HARD_MAX_RESIST)
    cap_lr = min(BASE_MAX_RESIST + baseline.character.base_max_lr, HARD_MAX_RESIST)
    cap_cr = min(BASE_MAX_RESIST + baseline.character.base_max_cr, HARD_MAX_RESIST)
    cap_pr = min(BASE_MAX_RESIST + baseline.character.base_max_pr, HARD_MAX_RESIST)

    if fhr_below is not None:
        try_add(build_c(mode="leveling-res", min_fcr=caster_fcr_floor, min_fhr=fhr_below))
    if is_caster and fcr_below is not None:
        try_add(build_c(mode="leveling-res", min_fcr=fcr_below, min_fhr=fhr_below or 0))
    if (
        all(r.fr < cap_fr or r.lr < cap_lr or r.cr < cap_cr or r.pr < cap_pr for _, r in collected)
        and fhr_below is not None
        and fhr_below > floor_fhr
    ):
        try_add(build_c(mode="leveling-res"))

    try_add(build_c(mode="leveling"))
    try_add(build_c(mode="max-res", min_fhr=fhr_below or 0))
    if fhr_below is not None:
        fhr_below_2 = _clamped_below(fhr_below, PALADIN_FHR_BPS, floor_fhr)
        if fhr_below_2 is not None:
            try_add(build_c(mode="leveling-res", min_fhr=fhr_below_2))

    if len(collected) < limit and not baseline.fixed_gear:
        try_add(build_c(mode="leveling-res", res_limit=limit))
        try_add(build_c(mode="leveling", res_limit=limit))
    return collected


def optimize_paladin_leveling(
    char_data: D2SStruct,
    items: Sequence[ItemSpec],
    charms: Sequence[CharmSpec],
    *,
    spec: str | None = None,
    max_charm_slots: int = 23,
    limit: int = 3,
    extra_chars: Sequence[D2SStruct] = (),
    stashes: Sequence[SharedStash] = (),
    resolver: GameDataResolver | None = None,
    bo_base_bonus: int | None = None,
    keep_equipped: bool | str | None = False,
    targets: int = 1,
    target_type: TargetTypeStr = "champion",
    left_skill: int | None = None,
    right_skill: int | None = None,
    overrides: ConstraintOverrides | None = None,
    title: str | None = None,
) -> tuple[str, list[tuple[str, BuildResult]], str, str]:
    """Optimize Paladin leveling gear and inventory charms across breakpoint/resist trade-offs."""
    eff_targets = max(1, targets)
    resolved_target_type = _normalize_target_type(target_type)
    baseline, char_level, diff_name, resolved_spec = _build_paladin_baseline(
        char_data,
        spec=spec,
        max_charm_slots=max_charm_slots,
        extra_chars=extra_chars,
        stashes=stashes,
        resolver=resolver,
        bo_base_bonus=bo_base_bonus,
        keep_equipped=keep_equipped,
        targets=eff_targets,
        target_type=resolved_target_type,
        left_skill=left_skill,
        right_skill=right_skill,
    )
    offense = paladin_offense_profile(
        resolved_spec, char_data, left_skill=left_skill, right_skill=right_skill
    )
    is_caster = offense == "caster"
    is_smite = offense == "smite"

    skill_name, _ = paladin_primary_skill_info(char_data, resolved_spec)
    spec_label = skill_name or resolved_spec.replace("-", " ").title()
    target_suffix = f", {eff_targets} targets" if eff_targets > 1 else ""
    target_type_part = f", {resolved_target_type}" if resolved_target_type != "champion" else ""
    if title is not None:
        extra = [
            f"{eff_targets} targets" if eff_targets > 1 else "",
            resolved_target_type if resolved_target_type != "champion" else "",
        ]
        extra_str = ", ".join(p for p in extra if p)
        eff_title = f"{title} [{extra_str}]" if extra_str else title
    else:
        eff_title = f"Paladin Leveling — {spec_label} (lvl {char_level}, {diff_name}{target_suffix}{target_type_part})"
    if limit <= 0:
        return eff_title, [], resolved_spec, diff_name

    # Build extra floor kwargs from overrides (excludes mode — handled by probe itself).
    extra_kwargs: dict[str, Any] = {}
    if overrides is not None:
        for key in (
            "allow_mf",
            "require_cbf",
            "min_frw",
            "min_ias",
            "min_cb",
            "min_ll",
            "min_pdr",
            "min_mf",
            "min_fcr",
            "min_fhr",
            "min_fr",
            "min_lr",
            "min_cr",
            "min_pr",
        ):
            val = getattr(overrides, key)
            if val is not None:
                extra_kwargs[key] = val

    items_list = list(items)
    charms_list = list(charms)
    opt1 = _probe_paladin_opt1(
        items_list,
        charms_list,
        baseline,
        offense=offense,
        is_caster=is_caster,
        extra_kwargs=extra_kwargs,
    )
    if opt1 is None:
        return eff_title, [], resolved_spec, diff_name
    if limit == 1:
        return (
            eff_title,
            [(_format_opt1_label(opt1, is_caster=is_caster), opt1)],
            resolved_spec,
            diff_name,
        )

    collected = _collect_paladin_alternatives(
        items_list,
        charms_list,
        baseline,
        opt1,
        limit=limit,
        offense=offense,
        is_caster=is_caster,
        is_smite=is_smite,
        extra_kwargs=extra_kwargs,
    )
    return eff_title, collected, resolved_spec, diff_name
