"""Human-readable optimizer report formatters."""

from collections import Counter
from collections.abc import Sequence

from d2savior.core.constants import DIFFICULTY_NAMES, DIFFICULTY_RESIST_PENALTIES_EXPANSION
from d2savior.core.enums import CharClass
from d2savior.optimizer.native import BuildResult, CharmSpec
from d2savior.optimizer.paladin import PALADIN_FCR_FRAMES, PALADIN_FHR_FRAMES
from d2savior.optimizer.sorc import SORCERESS_FCR_FRAMES, SORCERESS_FHR_FRAMES

_DEFAULT_DIFFICULTY_PENALTIES: frozendict[str, int] = frozendict(
    zip(DIFFICULTY_NAMES, DIFFICULTY_RESIST_PENALTIES_EXPANSION, strict=True)
)


def _format_res_line(diff_name: str, res: BuildResult, resist_penalty: int | None) -> str:
    """Format effective (capped) and pre-penalty total resistances for a build option."""
    penalty = (
        resist_penalty
        if resist_penalty is not None
        else _DEFAULT_DIFFICULTY_PENALTIES.get(diff_name, 0)
    )
    return (
        f"  {diff_name} Res: "
        f"F:{res.fr}%({res.fr_raw - penalty}) "
        f"L:{res.lr}%({res.lr_raw - penalty}) "
        f"C:{res.cr}%({res.cr_raw - penalty}) "
        f"P:{res.pr}%({res.pr_raw - penalty})"
    )


def _format_def_line(res: BuildResult) -> str | None:
    """Format post-skill defense, monster hit %, and passive block / FBR frames."""
    defense = getattr(res, "defense", 0)
    enemy_cth = getattr(res, "enemy_cth", 0)
    has_shield = bool(getattr(res, "has_shield", False))
    if defense <= 0 and enemy_cth <= 0 and not has_shield:
        return None
    def_part = f"Def: {defense} ({enemy_cth}% hit)" if enemy_cth > 0 else f"Def: {defense}"
    if not has_shield:
        return f"  {def_part}"
    block_pct = getattr(res, "block_pct", 0)
    fbr = getattr(res, "fbr", 0)
    fbr_frames = getattr(res, "fbr_frames", 0)
    return f"  {def_part} | Block: {block_pct}% (FBR {fbr}%, {fbr_frames}f)"


def _is_inv_loc(loc: str) -> bool:
    """Return True when loc refers to a character's inventory."""
    return loc == "inv" or loc.endswith(" Inv")


def _format_charm_diff_lines(
    res_charms: Sequence[CharmSpec],
    pool_charms: Sequence[CharmSpec],
    primary_inv_loc: str | None = None,
) -> list[str]:
    inv_loc = (
        primary_inv_loc
        if primary_inv_loc is not None
        else next((c.loc for c in (*pool_charms, *res_charms) if _is_inv_loc(c.loc)), None)
    )
    inv_charms = [c for c in pool_charms if c.loc == inv_loc] if inv_loc is not None else []
    if not res_charms and not inv_charms:
        return []

    kept_counts = Counter(c for c in res_charms if inv_loc is not None and c.loc == inv_loc)
    remove: list[CharmSpec] = []
    keep: list[CharmSpec] = []
    for c in inv_charms:
        if kept_counts[c] > 0:
            kept_counts[c] -= 1
            keep.append(c)
        else:
            remove.append(c)
    for c in res_charms:
        if inv_loc is not None and c.loc == inv_loc and kept_counts[c] > 0:
            kept_counts[c] -= 1
            keep.append(c)
    add = [c for c in res_charms if c.loc != inv_loc]
    remove_str = ", ".join(c.name for c in remove) if remove else "none"
    keep_str = ", ".join(c.name for c in keep) if keep else "none"
    add_str = ", ".join(f"{c.name} [{c.loc}]" if c.loc else c.name for c in add) if add else "none"
    return [
        "    - Charms  :",
        f"      - remove: {remove_str}",
        f"      - keep  : {keep_str}",
        f"      - add   : {add_str}",
    ]


_AURA_PRIMARY_NAMES: frozenset[str] = frozenset({"Holy Fire", "Holy Freeze", "Holy Shock"})


def _format_paladin_option_lines(
    header: str,
    res: BuildResult,
    charms: Sequence[CharmSpec],
    *,
    diff_name: str,
    resist_penalty: int | None = None,
    primary_skill_name: str | None,
    primary_skill_base: int,
    primary_inv_loc: str | None,
    has_aura: bool | None = None,
) -> list[str]:
    lines = [header]
    if primary_skill_name:
        is_aura = has_aura if has_aura is not None else (primary_skill_name in _AURA_PRIMARY_NAMES)
        extra_skill = (
            getattr(res, "aura_skill_bonus", 0)
            if is_aura
            else getattr(res, "action_skill_bonus", 0)
        )
        total_lvl = primary_skill_base + res.skills + res.primary_skill_bonus + extra_skill
        skill_str = f"Skills: +{res.skills} ({primary_skill_name} lvl {total_lvl})"
    else:
        skill_str = f"Skills: +{res.skills}"
    dps_val = getattr(res, "dps", 0.0)
    if dps_val > 0.0:
        # Intentionally display unadjusted sheet `raw_dps` alongside AR/CTH while ranking and
        # tradeoff comparisons use CTH-adjusted `res.dps`.
        shown_dps = getattr(res, "raw_dps", 0.0) or dps_val
        atk_label = (
            "Zeal"
            if getattr(res, "used_zeal", False)
            else (
                primary_skill_name
                if primary_skill_name in ("Sacrifice", "Charge", "Vengeance")
                else "Attack"
            )
        )
        cth_val = getattr(res, "cth", 0)
        ar_val = getattr(res, "ar", 0)
        ar_part = f"AR: {ar_val} ({cth_val}%) | " if cth_val > 0 else ""
        dps_prefix = f"DPS: {shown_dps:.0f} ({atk_label}) | {ar_part}"
    else:
        dps_prefix = ""
    extra_combat = (
        f" | DR: {res.pdr_pct}% | LL: {res.life_leech}%" if (res.pdr_pct or res.life_leech) else ""
    )
    ias_last = getattr(res, "ias_last_frames", 0)
    ias_frames_str = f"{res.ias_frames}/{ias_last}f" if ias_last > 0 else f"{res.ias_frames}f"
    lines.append(
        f"  {dps_prefix}{skill_str} | CBF: {'Yes' if res.cbf else 'No'} | IAS: {res.ias}% (BP {res.ias_bp}%, {ias_frames_str}) | CB: {res.cb}%{extra_combat}"
    )
    fhr_f = PALADIN_FHR_FRAMES.get(res.fhr_bp, 9)
    fcr_f = PALADIN_FCR_FRAMES.get(res.fcr_bp, 15)
    lines.append(
        f"  FHR: {res.fhr}% (BP {res.fhr_bp}%, {fhr_f}f) | FCR: {res.fcr}% (BP {res.fcr_bp}%, {fcr_f}f) | FRW: {res.frw}% | MF: {res.mf}%"
    )
    lines.append(_format_res_line(diff_name, res, resist_penalty))
    if def_line := _format_def_line(res):
        lines.append(def_line)
    if res.bo_lvl > 0:
        lines.append(
            f"  Life: {res.life_no_bo} (BO lvl {res.bo_lvl}: {res.life_bo}) | Mana (BO): {res.mana_bo} | Charm slots: {res.charm_slots}"
        )
    else:
        lines.append(
            f"  Life: {res.life_no_bo} | Mana: {res.mana_bo} | Charm slots: {res.charm_slots}"
        )
    for it in res.items:
        loc_str = f" ({it.loc})" if it.loc else ""
        lines.append(f"    - {it.slot:8s}: {it.name}{loc_str}")
    lines.extend(_format_charm_diff_lines(res.charms, charms, primary_inv_loc=primary_inv_loc))
    return lines


def format_build_report(
    title: str,
    results: Sequence[BuildResult],
    charms: Sequence[CharmSpec] = (),
    *,
    char_class: int = int(CharClass.SORCERESS),
    diff_name: str = "Hell",
    resist_penalty: int | None = None,
    primary_skill_name: str | None = None,
    primary_skill_base: int = 0,
    primary_inv_loc: str | None = None,
    filler_skill_name: str | None = None,
) -> str:
    """Format BuildResult options into a human-readable report."""
    lines = [f"=== {title} ==="]
    if not results:
        lines.append("  No loadout found matching all constraints.")
        return "\n".join(lines)

    for idx, res in enumerate(results, start=1):
        header = f"Option #{idx} (evaluated {res.evaluated_candidates} pruned sets):"
        if char_class == int(CharClass.PALADIN):
            lines.extend(
                _format_paladin_option_lines(
                    header,
                    res,
                    charms,
                    diff_name=diff_name,
                    resist_penalty=resist_penalty,
                    primary_skill_name=primary_skill_name,
                    primary_skill_base=primary_skill_base,
                    primary_inv_loc=primary_inv_loc,
                )
            )
            continue
        lines.append(header)
        dps_val = getattr(res, "dps", 0.0)
        if dps_val > 0.0:
            dps_label = f"Blizz + {filler_skill_name}" if filler_skill_name else "Blizz"
            dps_prefix = f"DPS: {dps_val:.0f} ({dps_label}) | "
        else:
            dps_prefix = ""
        blizz_suffix = (
            f" | Blizz Avg: {res.blizz_avg:.0f} | CM: {res.cm_pierce}%"
            if (res.blizz_avg > 0.0 or res.cm_pierce != 0)
            else ""
        )
        lines.append(f"  {dps_prefix}Skills: +{res.skills}{blizz_suffix}")
        fcr_f = SORCERESS_FCR_FRAMES.get(res.fcr_bp, 13)
        fhr_f = SORCERESS_FHR_FRAMES.get(res.fhr_bp, 15)
        lines.append(
            f"  FCR: {res.fcr}% (BP {res.fcr_bp}%, {fcr_f}f) | FHR: {res.fhr}% (BP {res.fhr_bp}%, {fhr_f}f) | FRW: {res.frw}% | MF: {res.mf}%"
        )
        lines.append(_format_res_line(diff_name, res, resist_penalty))
        if def_line := _format_def_line(res):
            lines.append(def_line)
        if res.bo_lvl > 0:
            lines.append(
                f"  Life: {res.life_no_bo} (BO lvl {res.bo_lvl}: {res.life_bo}) | Mana (BO): {res.mana_bo} | Charm slots: {res.charm_slots}"
            )
        else:
            lines.append(
                f"  Life: {res.life_no_bo} | Mana: {res.mana_bo} | Charm slots: {res.charm_slots}"
            )
        for it in res.items:
            loc_str = f" ({it.loc})" if it.loc else ""
            lines.append(f"    - {it.slot:8s}: {it.name}{loc_str}")
        lines.extend(_format_charm_diff_lines(res.charms, charms, primary_inv_loc=primary_inv_loc))
    return "\n".join(lines)


def format_paladin_leveling_report(
    title: str,
    options: Sequence[tuple[str, BuildResult]],
    charms: Sequence[CharmSpec] = (),
    *,
    diff_name: str = "Normal",
    resist_penalty: int | None = None,
    primary_skill_name: str | None = None,
    primary_skill_base: int = 0,
    primary_inv_loc: str | None = None,
) -> str:
    """Format Paladin leveling trade-off options into a human-readable report."""
    lines = [f"=== {title} ==="]
    if not options:
        lines.append("  No loadout found matching all constraints.")
        return "\n".join(lines)

    for idx, (label, res) in enumerate(options, start=1):
        header = f"Option #{idx}: {label} (evaluated {res.evaluated_candidates} pruned sets):"
        lines.extend(
            _format_paladin_option_lines(
                header,
                res,
                charms,
                diff_name=diff_name,
                resist_penalty=resist_penalty,
                primary_skill_name=primary_skill_name,
                primary_skill_base=primary_skill_base,
                primary_inv_loc=primary_inv_loc,
            )
        )
    return "\n".join(lines)
