"""Paladin leveling presets, spec detection, and breakpoint trade-off search."""

from collections.abc import Sequence

from d2savior.core.constants import CLASS_SKILL_BASES, DIFFICULTY_NAMES
from d2savior.core.d2s_struct import D2SStruct
from d2savior.core.enums import CharClass
from d2savior.core.resolver import GameDataResolver
from d2savior.core.stash import SharedStash
from d2savior.core.stats import get_current_difficulty, get_difficulty_resist_penalty
from d2savior.optimizer.common import (
    CharacterBaseline,
    _compute_anya_bonus,
    detect_cta_bo_bonus,
    validate_paladin,
)
from d2savior.optimizer.native import (
    HAS_NATIVE,
    BuildConstraints,
    BuildResult,
    CharmSpec,
    ItemSpec,
    OffenseProfileStr,
    SearchModeStr,
    class_breakpoints,
    optimize_builds,
)

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


def paladin_offense_profile(spec: str) -> OffenseProfileStr:
    """Return Rust OffenseProfile name ('smite', 'caster', or 'melee') for a Paladin spec."""
    if spec == "smite":
        return "smite"
    if spec in _PALADIN_CASTER_SPECS:
        return "caster"
    return "melee"


def detect_paladin_spec(char_data: D2SStruct) -> str:
    """Infer the primary Paladin leveling specialization from allocated hard skill points."""
    skills = char_data.skills.skill_levels if char_data.skills else ()
    if len(skills) < 30:
        return "leveling"
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
    best_pts, _, best_spec = max(candidates, key=lambda c: (c[0], c[1]))
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


def _paladin_passive_max_res(char_data: D2SStruct) -> tuple[int, int, int]:
    """Return passive Paladin (+1 max res per 2 hard points) bonuses for (FR, LR, CR).

    Per D2R `skills.txt` (IDs 100, 105, 110: Resist Fire/Cold/Lightning),
    `passivestat1 = max*resist` with `passivecalc1 = skill('<Aura>'.blvl)/2`
    scales strictly with hard base points (`.blvl`); `+skills` do not apply.
    """
    skills = char_data.skills.skill_levels if char_data.skills else ()
    if len(skills) <= _PAL_RESIST_LIGHT:
        return 0, 0, 0
    return (
        skills[_PAL_RESIST_FIRE] // 2,
        skills[_PAL_RESIST_LIGHT] // 2,
        skills[_PAL_RESIST_COLD] // 2,
    )


def _build_paladin_baseline(
    char_data: D2SStruct,
    *,
    spec: str | None,
    max_charm_slots: int,
    extra_chars: Sequence[D2SStruct],
    stashes: Sequence[SharedStash],
    resolver: GameDataResolver | None,
    bo_base_bonus: int | None,
    keep_equipped: bool,
) -> tuple[CharacterBaseline, int, str, str]:
    validate_paladin(char_data)
    resolved_spec = spec.lower() if spec else detect_paladin_spec(char_data)
    if resolved_spec not in PALADIN_SPEC_INFO:
        valid = ", ".join(PALADIN_SPEC_INFO)
        raise ValueError(f"Unknown Paladin spec '{resolved_spec}'; expected one of: {valid}")
    char_level = max(1, char_data.player_stats.level or char_data.char_level)
    diff_idx = get_current_difficulty(char_data)
    diff_name = DIFFICULTY_NAMES[diff_idx]
    base_res = get_difficulty_resist_penalty(char_data, diff_idx) + _compute_anya_bonus(char_data)
    base_max_fr, base_max_lr, base_max_cr = _paladin_passive_max_res(char_data)
    if bo_base_bonus is None:
        res_obj = resolver if resolver is not None else GameDataResolver.load()
        bo_base_bonus = detect_cta_bo_bonus(
            (char_data, *extra_chars), stashes, res_obj, max_level=char_level, default=0
        )
    baseline = CharacterBaseline(
        char_class=int(CharClass.PALADIN),
        base_life=char_data.player_stats.max_life,
        base_mana=char_data.player_stats.max_mana,
        base_hell_res=base_res,
        base_str=char_data.player_stats.strength,
        base_dex=char_data.player_stats.dexterity,
        max_charm_slots=max_charm_slots,
        bo_base_bonus=bo_base_bonus,
        use_bo=bo_base_bonus > 0,
        fixed_gear=keep_equipped,
        base_max_fr=base_max_fr,
        base_max_lr=base_max_lr,
        base_max_cr=base_max_cr,
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
    keep_equipped: bool = False,
) -> tuple[str, BuildConstraints, str]:
    """Build a Max Resist constraint profile for a Paladin at its current difficulty."""
    baseline, char_level, diff_name, resolved_spec = _build_paladin_baseline(
        char_data,
        spec=spec,
        max_charm_slots=max_charm_slots,
        extra_chars=extra_chars,
        stashes=stashes,
        resolver=resolver,
        bo_base_bonus=bo_base_bonus,
        keep_equipped=keep_equipped,
    )
    constraints = baseline.build_constraints(
        mode="max-res",
        limit=limit,
        offense=paladin_offense_profile(resolved_spec),
    )
    title = f"Paladin Max Resist (lvl {char_level}, {diff_name})"
    return title, constraints, resolved_spec


def _step_below_bp(bp: int, table: tuple[int, ...]) -> int | None:
    lower = [b for b in table if b < bp]
    return lower[-1] if lower else None


def _result_dedup_key(res: BuildResult) -> tuple[object, ...]:
    return (
        res.fhr_bp,
        res.fcr_bp,
        res.skills + res.primary_skill_bonus,
        res.cb,
        res.ias,
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


def _describe_lower_fhr_tradeoff(
    opt1: BuildResult,
    res: BuildResult,
    *,
    sk_diff: int,
    res_diff: int,
) -> str:
    prefix = f"Lower FHR BP ({res.fhr_bp}%)"
    gained_ias = res.ias > opt1.ias
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
    opt1: BuildResult, res: BuildResult, *, is_caster: bool, is_smite: bool
) -> str:
    res_diff = (res.fr + res.lr + res.cr + res.pr) - (opt1.fr + opt1.lr + opt1.cr + opt1.pr)
    sk_diff = (res.skills + res.primary_skill_bonus) - (opt1.skills + opt1.primary_skill_bonus)
    if res.fhr_bp < opt1.fhr_bp:
        return _describe_lower_fhr_tradeoff(opt1, res, sk_diff=sk_diff, res_diff=res_diff)
    if is_caster and res.fcr_bp < opt1.fcr_bp:
        if res_diff > 0:
            return f"Lower FCR BP ({res.fcr_bp}%) — Better Resists"
        if sk_diff > 0:
            return f"Lower FCR BP ({res.fcr_bp}%) — Higher Skills"
        return f"Lower FCR BP ({res.fcr_bp}%)"
    if res_diff > 0:
        return "Max Resist Cap"
    if is_smite and res.cb > opt1.cb:
        return "Max Smite Offense (CB/IAS)"
    if res.ias > opt1.ias:
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
) -> BuildResult | None:
    best_fcr_bp = 0
    if is_caster:
        for fcr_cand in reversed(PALADIN_FCR_BPS):
            c = baseline.build_constraints(
                mode="leveling-res", limit=1, min_fcr=fcr_cand, offense=offense
            )
            if optimize_builds(items, charms, c):
                best_fcr_bp = fcr_cand
                break

    for fhr_cand in reversed(PALADIN_FHR_BPS):
        c = baseline.build_constraints(
            mode="leveling-res",
            limit=1,
            min_fcr=best_fcr_bp,
            min_fhr=fhr_cand,
            offense=offense,
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
) -> list[tuple[str, BuildResult]]:
    collected: list[tuple[str, BuildResult]] = [
        (_format_opt1_label(opt1, is_caster=is_caster), opt1)
    ]
    seen: set[tuple[object, ...]] = {_result_dedup_key(opt1)}

    def try_add(constraints: BuildConstraints) -> None:
        if len(collected) >= limit:
            return
        for res in optimize_builds(items, charms, constraints):
            if len(collected) >= limit:
                return
            key = _result_dedup_key(res)
            if key not in seen:
                seen.add(key)
                collected.append(
                    (
                        _describe_paladin_tradeoff(
                            opt1, res, is_caster=is_caster, is_smite=is_smite
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
            min_fcr=min_fcr,
            min_fhr=min_fhr,
            offense=offense,
        )

    fhr_below = _step_below_bp(opt1.fhr_bp, PALADIN_FHR_BPS)
    fcr_below = _step_below_bp(opt1.fcr_bp, PALADIN_FCR_BPS) if is_caster else None
    caster_fcr_floor = opt1.fcr_bp if is_caster else 0

    if fhr_below is not None:
        try_add(build_c(mode="leveling-res", min_fcr=caster_fcr_floor, min_fhr=fhr_below))
    if is_caster and fcr_below is not None:
        try_add(build_c(mode="leveling-res", min_fcr=fcr_below, min_fhr=fhr_below or 0))
    if (
        all(min(r.fr, r.lr, r.cr, r.pr) < 75 for _, r in collected)
        and fhr_below is not None
        and fhr_below > 0
    ):
        try_add(build_c(mode="leveling-res"))

    try_add(build_c(mode="leveling"))
    try_add(build_c(mode="max-res", min_fhr=fhr_below or 0))
    if fhr_below is not None:
        fhr_below_2 = _step_below_bp(fhr_below, PALADIN_FHR_BPS)
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
    keep_equipped: bool = False,
) -> tuple[str, list[tuple[str, BuildResult]], str, str]:
    """Optimize Paladin leveling gear and inventory charms across breakpoint/resist trade-offs."""
    baseline, char_level, diff_name, resolved_spec = _build_paladin_baseline(
        char_data,
        spec=spec,
        max_charm_slots=max_charm_slots,
        extra_chars=extra_chars,
        stashes=stashes,
        resolver=resolver,
        bo_base_bonus=bo_base_bonus,
        keep_equipped=keep_equipped,
    )
    offense = paladin_offense_profile(resolved_spec)
    is_caster = offense == "caster"
    is_smite = offense == "smite"

    skill_name, _ = paladin_primary_skill_info(char_data, resolved_spec)
    spec_label = skill_name or resolved_spec.replace("-", " ").title()
    title = f"Paladin Leveling — {spec_label} (lvl {char_level}, {diff_name})"
    if limit <= 0:
        return title, [], resolved_spec, diff_name

    items_list = list(items)
    charms_list = list(charms)
    opt1 = _probe_paladin_opt1(
        items_list, charms_list, baseline, offense=offense, is_caster=is_caster
    )
    if opt1 is None:
        return title, [], resolved_spec, diff_name
    if limit == 1:
        return (
            title,
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
    )
    return title, collected, resolved_spec, diff_name
