"""Class-agnostic leveling breakpoint probe and trade-off alternative collector."""

from collections.abc import Callable, Mapping
from typing import Any

from d2savior.optimizer.common import CharacterBaseline
from d2savior.optimizer.native import (
    BuildConstraints,
    BuildResult,
    CharmSpec,
    ItemSpec,
    OffenseProfileStr,
    SearchModeStr,
    optimize_builds,
)
from d2savior.optimizer.presets import ConstraintOverrides, ResolvedPreset

type OptimizeBuildsFn = Callable[
    [list[ItemSpec], list[CharmSpec], BuildConstraints], list[BuildResult]
]

# Default elemental resist floor for the DPS-first (`mode="leveling"`) probe,
# clamped to `opt1`'s achieved resists so the floor is always feasible.
LEVELING_DPS_RES_FLOOR = 50


def _dps_probe_res_floor(opt1_res: int, floor_res: int) -> int:
    return max(floor_res, min(opt1_res, LEVELING_DPS_RES_FLOOR))


def _step_below_bp(bp: int, table: tuple[int, ...]) -> int | None:
    lower = [b for b in table if b < bp]
    return lower[-1] if lower else None


def _eff_leveling_skills(res: BuildResult, *, has_aura: bool = False) -> int:
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
        _eff_leveling_skills(res, has_aura=has_aura),
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
    fhr_frames: Mapping[int, int],
    sk_diff: int,
    res_diff: int,
) -> str:
    # Tradeoff labels compare CTH-adjusted effective DPS (`res.dps`) used by ranking/dedup,
    # whereas report lines display sheet `raw_dps` + `AR (CTH%)`.
    base_frames = fhr_frames.get(0, 9)
    frames = fhr_frames.get(res.fhr_bp, base_frames)
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


def describe_leveling_tradeoff(
    opt1: BuildResult,
    res: BuildResult,
    *,
    fhr_frames: Mapping[int, int],
    fcr_frames: Mapping[int, int] = frozendict(),
    is_caster: bool,
    is_smite: bool = False,
    has_aura: bool = False,
) -> str:
    res_diff = (res.fr + res.lr + res.cr + res.pr) - (opt1.fr + opt1.lr + opt1.cr + opt1.pr)
    sk_diff = _eff_leveling_skills(res, has_aura=has_aura) - _eff_leveling_skills(
        opt1, has_aura=has_aura
    )
    # Compare effective DPS (`res.dps`), matching ranking/dedup (see `_dps_gain_label`).
    if res.fhr_bp < opt1.fhr_bp:
        return _describe_lower_fhr_tradeoff(
            opt1, res, fhr_frames=fhr_frames, sk_diff=sk_diff, res_diff=res_diff
        )
    if is_caster and res.fcr_bp < opt1.fcr_bp:
        base_fcr_f = fcr_frames.get(0, 15)
        fcr_f = fcr_frames.get(res.fcr_bp, base_fcr_f)
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


def format_opt1_label(
    opt1: BuildResult,
    *,
    fhr_frames: Mapping[int, int],
    is_caster: bool,
) -> str:
    base_frames = fhr_frames.get(0, 9)
    frames = fhr_frames.get(opt1.fhr_bp, base_frames)
    if is_caster:
        return f"High Breakpoint ({opt1.fcr_bp}% FCR / {opt1.fhr_bp}% FHR, {frames}f)"
    return f"High Breakpoint ({opt1.fhr_bp}% FHR, {frames}f)"


def probe_leveling_opt1(
    items: list[ItemSpec],
    charms: list[CharmSpec],
    baseline: CharacterBaseline,
    *,
    offense: OffenseProfileStr,
    is_caster: bool,
    fcr_bps: tuple[int, ...],
    fhr_bps: tuple[int, ...],
    extra_kwargs: dict[str, Any] | None = None,
    optimize_fn: OptimizeBuildsFn = optimize_builds,
) -> BuildResult | None:
    ek: dict[str, Any] = dict(extra_kwargs or {})
    floor_fcr = int(ek.pop("min_fcr", 0))
    floor_fhr = int(ek.pop("min_fhr", 0))
    ek.pop("mode", None)
    best_fcr_bp = floor_fcr
    if is_caster:
        found_fcr = False
        for fcr_cand in sorted({floor_fcr, *(b for b in fcr_bps if b >= floor_fcr)}, reverse=True):
            c = baseline.build_constraints(
                mode="leveling-res",
                limit=1,
                min_fcr=fcr_cand,
                min_fhr=floor_fhr,
                offense=offense,
                **ek,
            )
            if optimize_fn(items, charms, c):
                best_fcr_bp = fcr_cand
                found_fcr = True
                break
        if not found_fcr:
            return None

    for fhr_cand in sorted({floor_fhr, *(b for b in fhr_bps if b >= floor_fhr)}, reverse=True):
        c = baseline.build_constraints(
            mode="leveling-res",
            limit=1,
            min_fcr=best_fcr_bp,
            min_fhr=fhr_cand,
            offense=offense,
            **ek,
        )
        probe = optimize_fn(items, charms, c)
        if probe:
            return probe[0]
    return None


def collect_leveling_alternatives(
    items: list[ItemSpec],
    charms: list[CharmSpec],
    baseline: CharacterBaseline,
    opt1: BuildResult,
    *,
    limit: int,
    offense: OffenseProfileStr,
    is_caster: bool,
    fcr_bps: tuple[int, ...],
    fhr_bps: tuple[int, ...],
    fhr_frames: Mapping[int, int],
    fcr_frames: Mapping[int, int] = frozendict(),
    is_smite: bool = False,
    extra_kwargs: dict[str, Any] | None = None,
    optimize_fn: OptimizeBuildsFn = optimize_builds,
) -> list[tuple[str, BuildResult]]:
    has_aura = bool(getattr(baseline.skills, "has_aura", False))
    ek: dict[str, Any] = dict(extra_kwargs or {})
    floor_fcr = int(ek.pop("min_fcr", 0))
    floor_fhr = int(ek.pop("min_fhr", 0))
    ek.pop("mode", None)
    collected: list[tuple[str, BuildResult]] = [
        (format_opt1_label(opt1, fhr_frames=fhr_frames, is_caster=is_caster), opt1)
    ]
    seen: set[tuple[object, ...]] = {
        _result_dedup_key(opt1, is_caster=is_caster, has_aura=has_aura)
    }

    def try_add(constraints: BuildConstraints) -> None:
        if len(collected) >= limit:
            return
        for res in optimize_fn(items, charms, constraints):
            if len(collected) >= limit:
                return
            key = _result_dedup_key(res, is_caster=is_caster, has_aura=has_aura)
            if key not in seen:
                seen.add(key)
                collected.append(
                    (
                        describe_leveling_tradeoff(
                            opt1,
                            res,
                            fhr_frames=fhr_frames,
                            fcr_frames=fcr_frames,
                            is_caster=is_caster,
                            is_smite=is_smite,
                            has_aura=has_aura,
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
        extra_res_floors: dict[str, int] | None = None,
    ) -> BuildConstraints:
        kw = dict(ek)
        if extra_res_floors:
            kw.update(extra_res_floors)
        return baseline.build_constraints(
            mode=mode,
            limit=res_limit,
            min_fcr=max(min_fcr, floor_fcr),
            min_fhr=max(min_fhr, floor_fhr),
            offense=offense,
            **kw,
        )

    dps_res_floors = {
        "min_fr": _dps_probe_res_floor(opt1.fr, int(ek.get("min_fr", 0))),
        "min_lr": _dps_probe_res_floor(opt1.lr, int(ek.get("min_lr", 0))),
        "min_cr": _dps_probe_res_floor(opt1.cr, int(ek.get("min_cr", 0))),
    }

    def _clamped_below(bp: int, table: tuple[int, ...], floor: int) -> int | None:
        step = _step_below_bp(bp, table)
        if step is None or step < floor:
            return floor if floor < bp else None
        return step

    fhr_below = _clamped_below(opt1.fhr_bp, fhr_bps, floor_fhr)
    fhr_below_2 = _clamped_below(fhr_below, fhr_bps, floor_fhr) if fhr_below is not None else None
    fcr_below = _clamped_below(opt1.fcr_bp, fcr_bps, floor_fcr) if is_caster else None
    caster_fcr_floor = max(opt1.fcr_bp, floor_fcr) if is_caster else floor_fcr

    if fhr_below is not None:
        try_add(build_c(mode="leveling-res", min_fcr=caster_fcr_floor, min_fhr=fhr_below))
    if is_caster and fcr_below is not None:
        try_add(build_c(mode="leveling-res", min_fcr=fcr_below, min_fhr=fhr_below or 0))
    if fhr_below_2 is not None:
        try_add(build_c(mode="leveling-res", min_fcr=caster_fcr_floor, min_fhr=fhr_below_2))
    if (fhr_below_2 is not None and fhr_below_2 > floor_fhr) or (
        is_caster and fcr_below is not None and fcr_below > floor_fcr
    ):
        try_add(build_c(mode="leveling-res"))

    try_add(build_c(mode="leveling", extra_res_floors=dps_res_floors))
    try_add(build_c(mode="max-res", min_fhr=fhr_below or 0))

    if len(collected) < limit and not baseline.fixed_gear:
        try_add(build_c(mode="leveling-res", res_limit=limit))
        try_add(build_c(mode="leveling", res_limit=limit, extra_res_floors=dps_res_floors))
    return collected


def uses_leveling_probe(preset: ResolvedPreset, overrides: ConstraintOverrides | None) -> bool:
    """Return True when a leveling preset dispatches to the two-pass breakpoint probe."""
    has_mode_override = overrides is not None and overrides.mode is not None
    return (
        preset.strategy == "leveling-probe"
        and not has_mode_override
        and preset.mode == "leveling-res"
    )
