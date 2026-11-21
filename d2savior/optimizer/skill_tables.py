"""Precomputed D2R skill DPS lookup tables parsed from skills.txt."""

import re
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files

from d2savior.core.constants import CLASS_SKILL_BASES
from d2savior.core.d2s_struct import D2SStruct
from d2savior.core.enums import CharClass
from d2savior.core.loader import TsvReader
from d2savior.optimizer.common import active_skill_bindings

DEFAULT_MAX_SKILL_BONUS = 40

_SORC_SKILL_BASE = CLASS_SKILL_BASES[int(CharClass.SORCERESS)]
_PAL_SKILL_BASE = CLASS_SKILL_BASES[int(CharClass.PALADIN)]
_SKILL_EXPLODING_ARROW = 16
_SKILL_ICE_BLAST = 45
_SKILL_GLACIAL_SPIKE = 55
_SKILL_BLIZZARD = 59
_SKILL_SACRIFICE = 96
_SKILL_HOLY_FIRE = 102
_SKILL_ZEAL = 106
_SKILL_HOLY_FREEZE = 114
_SKILL_HOLY_SHOCK = 118

_ELEMENTAL_AURA_SPECS: frozendict[str, int] = frozendict(
    {
        "holy-fire": _SKILL_HOLY_FIRE,
        "holy-freeze": _SKILL_HOLY_FREEZE,
        "holy-shock": _SKILL_HOLY_SHOCK,
    }
)

_SYNERGY_RE = re.compile(r"skill\('([^']+)'\.blvl\)\s*\*\s*par(\d+)")
_SYNERGY_GROUP_RE = re.compile(r"\((.+)\)\s*\*\s*par(\d+)")
_SKILL_BLVL_RE = re.compile(r"skill\('([^']+)'\.blvl\)")
_SORC_FILLER_NAMES: frozendict[int, str] = frozendict(
    {_SKILL_ICE_BLAST: "Ice Blast", _SKILL_GLACIAL_SPIKE: "Glacial Spike"}
)


def _parse_synergies(syn_expr: str, params: dict[int, int]) -> tuple[tuple[str, int], ...]:
    if not syn_expr:
        return ()
    direct = tuple(
        (m.group(1), params.get(int(m.group(2)), 0)) for m in _SYNERGY_RE.finditer(syn_expr)
    )
    if direct:
        return direct
    out: list[tuple[str, int]] = []
    for grp in _SYNERGY_GROUP_RE.finditer(syn_expr):
        pct = params.get(int(grp.group(2)), 0)
        for sname in _SKILL_BLVL_RE.findall(grp.group(1)):
            out.append((sname, pct))
    return tuple(out)


@dataclass(frozen=True, slots=True)
class _SkillFormula:
    skill_id: int
    name: str
    hit_shift: int
    perdelay: int
    emin: int
    emin_lev: tuple[int, int, int, int, int]
    emax: int
    emax_lev: tuple[int, int, int, int, int]
    params: dict[int, int]
    passivecalc1: str
    passivecalc2: str
    synergies: tuple[tuple[str, int], ...]  # (skill_name, pct_per_blvl)


@dataclass(frozen=True, slots=True)
class PaladinDpsTables:
    """1D skill tables indexed by bonus skill level (0..=max_bonus)."""

    aura_hit_dmg: tuple[float, ...]
    aura_pulse_dps: tuple[float, ...]
    action_ed: tuple[int, ...]
    action_hits: tuple[int, ...]
    has_aura: bool
    aura_is_fire: bool = False


def _piecewise_linear(base: int, levs: tuple[int, int, int, int, int], slvl: int) -> int:
    """Evaluate D2's 5-tier piecewise-linear skill progression at `slvl >= 1`."""
    if slvl <= 0:
        return 0
    total = base
    rem = slvl - 1
    for tier_len, inc in zip((7, 8, 6, 6), levs[:4], strict=True):
        step = min(rem, tier_len)
        total += step * inc
        rem -= step
        if rem <= 0:
            return total
    return total + rem * levs[4]


@lru_cache(maxsize=1)
def _load_skill_formulas() -> tuple[dict[int, _SkillFormula], dict[str, int]]:
    """Parse skills.txt once and return (id -> _SkillFormula, name -> id)."""
    skills_path = files("d2savior.data") / "d2r" / "skills.txt"
    formulas: dict[int, _SkillFormula] = {}
    name_to_id: dict[str, int] = {}
    wanted = {
        _SKILL_EXPLODING_ARROW,
        _SKILL_ICE_BLAST,
        _SKILL_GLACIAL_SPIKE,
        _SKILL_BLIZZARD,
        _SKILL_HOLY_FIRE,
        _SKILL_HOLY_FREEZE,
        _SKILL_HOLY_SHOCK,
        _SKILL_ZEAL,
    }

    for row in TsvReader(skills_path):
        sid = row.get_int("*Id", -1)
        if sid < 0:
            continue
        name = row.get("skill")
        if name:
            name_to_id[name] = sid
        if sid not in wanted:
            continue

        params = {i: row.get_int(f"Param{i}") for i in range(1, 9)}
        syn_expr = row.get("EDmgSymPerCalc") or row.get("calc2")
        synergies = _parse_synergies(syn_expr, params)
        formulas[sid] = _SkillFormula(
            skill_id=sid,
            name=name,
            hit_shift=row.get_int("HitShift", 8),
            perdelay=row.get_int("perdelay", 50),
            emin=row.get_int("EMin"),
            emin_lev=(
                row.get_int("EMinLev1"),
                row.get_int("EMinLev2"),
                row.get_int("EMinLev3"),
                row.get_int("EMinLev4"),
                row.get_int("EMinLev5"),
            ),
            emax=row.get_int("EMax"),
            emax_lev=(
                row.get_int("EMaxLev1"),
                row.get_int("EMaxLev2"),
                row.get_int("EMaxLev3"),
                row.get_int("EMaxLev4"),
                row.get_int("EMaxLev5"),
            ),
            params=params,
            passivecalc1=row.get("passivecalc1"),
            passivecalc2=row.get("passivecalc2"),
            synergies=synergies,
        )
    return formulas, name_to_id


def exploding_arrow_fire_2x(slvl: int) -> int:
    """Return 2x average base fire damage of Exploding Arrow at `slvl` (from skills.txt)."""
    if slvl <= 0:
        return 0
    formulas, _ = _load_skill_formulas()
    ef = formulas.get(_SKILL_EXPLODING_ARROW)
    if ef is None:
        return 0
    scale = 2.0 ** (ef.hit_shift - 8)
    f_min = _piecewise_linear(ef.emin, ef.emin_lev, slvl) * scale
    f_max = _piecewise_linear(ef.emax, ef.emax_lev, slvl) * scale
    return round(f_min + f_max)


def _pal_hard_pts(skill_levels: tuple[int, ...] | list[int], skill_id: int) -> int:
    offset = skill_id - _PAL_SKILL_BASE
    return skill_levels[offset] if 0 <= offset < len(skill_levels) else 0


def build_paladin_dps_tables(
    char_data: D2SStruct,
    spec: str,
    offense: str,
    *,
    max_bonus: int = DEFAULT_MAX_SKILL_BONUS,
) -> PaladinDpsTables:
    """Build 1D aura/action DPS lookup tables from skills.txt for a Paladin."""
    formulas, name_to_id = _load_skill_formulas()
    skill_levels = char_data.skills.skill_levels if char_data.skills else ()

    # --- Aura tables (Holy Fire / Holy Freeze / Holy Shock) ---
    aura_id = _ELEMENTAL_AURA_SPECS.get(spec)
    base_aura = _pal_hard_pts(skill_levels, aura_id) if aura_id is not None else 0
    if aura_id is not None and base_aura > 0 and aura_id in formulas:
        af = formulas[aura_id]
        scale = 2.0 ** (af.hit_shift - 8)
        syn_pct = sum(
            _pal_hard_pts(skill_levels, name_to_id[sname]) * pct
            for sname, pct in af.synergies
            if sname in name_to_id
        )
        syn_mult = 1.0 + syn_pct / 100.0
        on_hit_mult = af.params.get(5, 1)
        flat_min_one = af.passivecalc1 == "1"
        ticks_per_sec = 25.0 / af.perdelay if af.perdelay > 0 else 0.0

        aura_hit: list[float] = []
        aura_pulse: list[float] = []
        for b in range(max_bonus + 1):
            slvl = base_aura + b
            p_min = _piecewise_linear(af.emin, af.emin_lev, slvl) * scale * syn_mult
            p_max = _piecewise_linear(af.emax, af.emax_lev, slvl) * scale * syn_mult
            aura_pulse.append(((p_min + p_max) / 2.0) * ticks_per_sec)
            h_min = 1.0 if flat_min_one else p_min * on_hit_mult
            h_max = p_max * on_hit_mult
            aura_hit.append((h_min + h_max) / 2.0)
        aura_hit_t = tuple(aura_hit)
        aura_pulse_t = tuple(aura_pulse)
        has_aura = True
    else:
        aura_hit_t = (0.0,)
        aura_pulse_t = (0.0,)
        has_aura = False

    # --- Action tables (Zeal vs normal Attack) ---
    base_zeal = _pal_hard_pts(skill_levels, _SKILL_ZEAL)
    if offense == "zeal" and base_zeal > 0 and _SKILL_ZEAL in formulas:
        zf = formulas[_SKILL_ZEAL]
        par4 = zf.params.get(4, 6)
        par5 = zf.params.get(5, 2)
        par6 = zf.params.get(6, 5)
        sac_pct = next((pct for _, pct in zf.synergies), zf.params.get(8, 12))
        sac_ed = _pal_hard_pts(skill_levels, _SKILL_SACRIFICE) * sac_pct

        action_ed_list: list[int] = []
        action_hits_list: list[int] = []
        for b in range(max_bonus + 1):
            slvl = base_zeal + b
            action_hits_list.append(min(par5 + slvl - 1, par6))
            lvl_ed = 0 if slvl < 5 else (slvl - 4) * par4
            action_ed_list.append(lvl_ed + sac_ed)
        action_ed_t = tuple(action_ed_list)
        action_hits_t = tuple(action_hits_list)
    else:
        action_ed_t = (0,)
        action_hits_t = (1,)

    return PaladinDpsTables(
        aura_hit_dmg=aura_hit_t,
        aura_pulse_dps=aura_pulse_t,
        action_ed=action_ed_t,
        action_hits=action_hits_t,
        has_aura=has_aura,
        aura_is_fire=has_aura and aura_id == _SKILL_HOLY_FIRE,
    )


@dataclass(frozen=True, slots=True)
class SorcDpsTables:
    """1D Blizzard + filler (Ice Blast / Glacial Spike) damage tables from skills.txt."""

    blizz_dmg: tuple[float, ...]
    filler_dmg: tuple[float, ...]
    filler_is_aoe: bool
    filler_skill_id: int | None
    filler_skill_name: str | None


def _norm_skill_key(name: str) -> str:
    return re.sub(r"[\s_-]+", "", name.strip().lower())


def resolve_skill_override(name: str) -> int:
    """Resolve a CLI skill override name (e.g. 'ice-blast', 'zeal', 'attack', 'none') to a skill ID."""
    key = _norm_skill_key(name)
    if key == "none":
        return -1
    if key in ("attack", "normalattack"):
        return 0
    _, name_to_id = _load_skill_formulas()
    for sname, sid in name_to_id.items():
        if _norm_skill_key(sname) == key:
            return sid
    raise ValueError(f"Unknown skill '{name}'")


def _sorc_hard_pts(skill_levels: tuple[int, ...] | list[int], skill_id: int) -> int:
    offset = skill_id - _SORC_SKILL_BASE
    return skill_levels[offset] if 0 <= offset < len(skill_levels) else 0


def resolve_sorc_filler_skill(
    char_data: D2SStruct,
    *,
    left_skill: int | None = None,
    right_skill: int | None = None,
    targets: int = 1,
) -> int | None:
    """Resolve active Blizzard Sorceress filler skill (Ice Blast or Glacial Spike)."""
    if left_skill == -1:
        return None
    skill_levels = char_data.skills.skill_levels if char_data.skills else ()
    ib_pts = _sorc_hard_pts(skill_levels, _SKILL_ICE_BLAST)
    gs_pts = _sorc_hard_pts(skill_levels, _SKILL_GLACIAL_SPIKE)

    active_left, active_right = active_skill_bindings(char_data)
    eff_left = left_skill if left_skill is not None else active_left
    eff_right = right_skill if right_skill is not None else active_right
    for sid, explicit in ((eff_left, left_skill is not None), (eff_right, right_skill is not None)):
        if sid in _SORC_FILLER_NAMES and (explicit or _sorc_hard_pts(skill_levels, sid) > 0):
            return sid

    if ib_pts <= 0 and gs_pts <= 0:
        return None
    if gs_pts > ib_pts:
        return _SKILL_GLACIAL_SPIKE
    if ib_pts > gs_pts:
        return _SKILL_ICE_BLAST
    return _SKILL_GLACIAL_SPIKE if targets > 1 else _SKILL_ICE_BLAST


def _eval_skill_dmg_table(
    sf: _SkillFormula,
    base_lvl: int,
    syn_mult: float,
    max_bonus: int,
) -> tuple[float, ...]:
    scale = 2.0 ** (sf.hit_shift - 8)
    out: list[float] = []
    for b in range(max_bonus + 1):
        slvl = base_lvl + b
        d_min = _piecewise_linear(sf.emin, sf.emin_lev, slvl) * scale * syn_mult
        d_max = _piecewise_linear(sf.emax, sf.emax_lev, slvl) * scale * syn_mult
        out.append((d_min + d_max) / 2.0)
    return tuple(out)


def build_sorc_dps_tables(
    char_data: D2SStruct,
    *,
    left_skill: int | None = None,
    right_skill: int | None = None,
    targets: int = 1,
    max_bonus: int = DEFAULT_MAX_SKILL_BONUS,
) -> SorcDpsTables:
    """Build 1D Blizzard + filler (Ice Blast / Glacial Spike) damage tables from skills.txt."""
    formulas, name_to_id = _load_skill_formulas()
    skill_levels = char_data.skills.skill_levels if char_data.skills else ()

    base_blizz = _sorc_hard_pts(skill_levels, _SKILL_BLIZZARD)
    if base_blizz <= 0 or _SKILL_BLIZZARD not in formulas:
        return SorcDpsTables((), (), False, None, None)

    bf = formulas[_SKILL_BLIZZARD]
    blizz_syn = sum(
        _sorc_hard_pts(skill_levels, name_to_id[sname]) * pct
        for sname, pct in bf.synergies
        if sname in name_to_id
    )
    blizz_tbl = _eval_skill_dmg_table(bf, base_blizz, 1.0 + blizz_syn / 100.0, max_bonus)

    filler_id = resolve_sorc_filler_skill(
        char_data, left_skill=left_skill, right_skill=right_skill, targets=targets
    )
    if filler_id is not None and filler_id in formulas:
        base_filler = max(1, _sorc_hard_pts(skill_levels, filler_id))
        ff = formulas[filler_id]
        filler_syn = sum(
            _sorc_hard_pts(skill_levels, name_to_id[sname]) * pct
            for sname, pct in ff.synergies
            if sname in name_to_id
        )
        filler_tbl = _eval_skill_dmg_table(ff, base_filler, 1.0 + filler_syn / 100.0, max_bonus)
        return SorcDpsTables(
            blizz_dmg=blizz_tbl,
            filler_dmg=filler_tbl,
            filler_is_aoe=(filler_id == _SKILL_GLACIAL_SPIKE),
            filler_skill_id=filler_id,
            filler_skill_name=_SORC_FILLER_NAMES.get(filler_id),
        )

    return SorcDpsTables(blizz_tbl, (), False, None, None)
