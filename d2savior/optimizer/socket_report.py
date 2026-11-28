"""Socket Quest report models and human-readable text formatting."""

from collections import Counter
from dataclasses import dataclass

from d2savior.optimizer.native import BuildResult
from d2savior.optimizer.socket_candidates import THEORETICAL_CHAR_LEVEL
from d2savior.optimizer.socket_variants import SocketCandidateVariant


@dataclass(frozen=True, slots=True)
class SocketUpgradeResult:
    """Evaluated socket-quest candidate for one preset."""

    variant: SocketCandidateVariant
    baseline: BuildResult | None
    result: BuildResult
    unlocked_feasibility: bool
    score_key: tuple[int, ...]
    extra_key: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class PresetSocketReport:
    """Socket quest evaluation results for a single build preset."""

    title: str
    mode: str
    offense: str
    has_aura: bool
    diff_name: str
    baseline: BuildResult | None
    candidates: list[SocketUpgradeResult]


@dataclass(frozen=True, slots=True)
class SocketQuestReport:
    """Full socket quest optimization report across all evaluated presets."""

    char_name: str
    char_class_name: str
    char_level: int
    diff_name: str
    quest_status: list[tuple[str, str]]
    other_unclaimed: list[tuple[str, str]]
    owned_rune_types: int
    owned_gem_types: int
    owned_jewel_count: int
    theoretical: bool
    eligible_item_count: int
    presets: list[PresetSocketReport]
    no_quest: bool = False


def _format_build_brief(res: BuildResult, *, diff_name: str, offense: str) -> str:
    parts: list[str] = []
    if res.dps > 0.0:
        parts.append(f"DPS: {res.dps:.0f}")
    parts.append(f"Skills: +{res.skills}")
    if offense == "caster":
        parts.append(f"FCR: {res.fcr}% (BP {res.fcr_bp}%)")
    if offense != "caster" and (res.ias or res.cb):
        parts.append(f"IAS: {res.ias}% (BP {res.ias_bp}%) | CB: {res.cb}%")
    parts.append(f"FHR: {res.fhr}% (BP {res.fhr_bp}%)")
    if res.mf:
        parts.append(f"MF: {res.mf}%")
    parts.append(f"{diff_name} Res: F:{res.fr} L:{res.lr} C:{res.cr} P:{res.pr}")
    parts.append(f"Life: {res.life_bo}")
    return " | ".join(parts)


def _format_delta_summary(cand: SocketUpgradeResult, *, diff_name: str, offense: str) -> str:
    if cand.unlocked_feasibility or cand.baseline is None:
        return "Unlocks feasible build!"
    b = cand.baseline
    r = cand.result
    deltas: list[str] = []
    if r.skills != b.skills:
        deltas.append(f"Skills {b.skills:+d}->{r.skills:+d}")
    if r.dps > 0.0 and abs(r.dps - b.dps) >= 1.0:
        deltas.append(f"DPS {b.dps:.0f}->{r.dps:.0f}")
    if offense == "caster" and r.fcr_bp != b.fcr_bp:
        deltas.append(f"FCR BP {b.fcr_bp}%->{r.fcr_bp}%")
    if r.fhr_bp != b.fhr_bp:
        deltas.append(f"FHR BP {b.fhr_bp}%->{r.fhr_bp}%")
    if offense != "caster" and r.ias_bp != b.ias_bp:
        deltas.append(f"IAS BP {b.ias_bp}%->{r.ias_bp}%")
    if r.cbf != b.cbf:
        deltas.append("CBF gained" if r.cbf else "CBF lost")
    if r.mf != b.mf:
        deltas.append(f"MF {b.mf}%->{r.mf}%")
    res_changes = [
        f"{lbl}:{bv}->{rv}"
        for lbl, bv, rv in (
            ("F", b.fr, r.fr),
            ("L", b.lr, r.lr),
            ("C", b.cr, r.cr),
            ("P", b.pr, r.pr),
        )
        if bv != rv
    ]
    if res_changes:
        deltas.append(f"{diff_name} Res {' '.join(res_changes)}")
    if r.life_bo != b.life_bo:
        deltas.append(f"Life {b.life_bo}->{r.life_bo}")
    if not deltas:
        raw_res_b = b.fr_raw + b.lr_raw + b.cr_raw + b.pr_raw
        raw_res_r = r.fr_raw + r.lr_raw + r.cr_raw + r.pr_raw
        if raw_res_r != raw_res_b:
            deltas.append(f"Overcap Res {raw_res_r - raw_res_b:+d}%")
        if r.fhr != b.fhr:
            deltas.append(f"FHR {b.fhr}%->{r.fhr}%")
        if r.mana_bo != b.mana_bo:
            deltas.append(f"Mana {b.mana_bo}->{r.mana_bo}")
    return ", ".join(deltas) if deltas else "Tiebreak improvement"


def _format_gear_diff_note(cand: SocketUpgradeResult) -> str | None:
    if cand.baseline is None:
        return None
    b_map = {it.slot: it.name for it in cand.baseline.items}
    r_map = {it.slot: it.name for it in cand.result.items}
    if cand.variant.slot not in r_map:
        return None
    swaps: list[str] = []
    for it in cand.result.items:
        if it.slot == "ring":
            continue
        is_target = it.name == cand.variant.spec.name and it.loc == cand.variant.spec.loc
        if is_target:
            if it.slot == "weapon2h" and "weapon2h" not in b_map:
                replaced = [b_map[s] for s in ("weapon", "shield") if s in b_map]
                prev_desc = " + ".join(replaced) if replaced else "(empty)"
                swaps.append(f"weapon2h: replaces {prev_desc}")
            else:
                prev_name = b_map.get(it.slot, "(empty)")
                if prev_name != cand.variant.item_name:
                    swaps.append(f"{it.slot}: replaces {prev_name}")
            continue
        prev_name = b_map.get(it.slot)
        if prev_name != it.name:
            swaps.append(f"{it.slot}: {prev_name or '(empty)'} -> {it.name}")
    return f"Gear changes: {'; '.join(swaps)}" if swaps else None


def _format_socket_tag(v: SocketCandidateVariant, *, no_quest: bool) -> str:
    min_s, max_s = v.sockets_range
    if no_quest:
        if v.total_sockets > min_s:
            return f"{min_s}/{v.total_sockets} open"
        return "1 open socket" if min_s == 1 else f"{min_s} open sockets"
    if min_s == max_s == 1:
        return "1 socket"
    if min_s != max_s:
        return f"Magic: {min_s}-{max_s} sockets"
    return f"{max_s} sockets"


def format_socket_report(report: SocketQuestReport) -> str:
    """Format a `SocketQuestReport` into a concise, actionable human-readable report."""
    header_title = "Socket Filler Optimizer" if report.no_quest else "Socket Quest Optimizer"
    lines: list[str] = [
        f"=== {header_title}: {report.char_name} "
        f"({report.char_class_name} lvl {report.char_level}, {report.diff_name}) ==="
    ]
    if not report.no_quest:
        quest_parts = [f"{d}: {s}" for d, s in report.quest_status]
        lines.append(f"Socket Quests ({report.char_name}): {' | '.join(quest_parts)}")
        if report.other_unclaimed:
            other_str = ", ".join(f"{name} ({diff})" for name, diff in report.other_unclaimed)
            lines.append(f"Other unclaimed Socket Quests: {other_str}")
    mode_tag = (
        f"owned + theoretical, lvl {THEORETICAL_CHAR_LEVEL} unbound Str/Dex"
        if report.theoretical
        else "owned only"
    )
    lines.append(
        f"Socketables ({mode_tag}): {report.owned_rune_types} runes, "
        f"{report.owned_gem_types} gem types, {report.owned_jewel_count} jewels | "
        f"Eligible items: {report.eligible_item_count}"
    )

    for p in report.presets:
        lines.append("")
        lines.append(f"--- {p.title} ---")
        if p.baseline is None:
            lines.append("Baseline: No loadout found matching all constraints.")
        else:
            lines.append(
                f"Baseline: {_format_build_brief(p.baseline, diff_name=p.diff_name, offense=p.offense)}"
            )
        if not p.candidates:
            empty_msg = (
                "  No open-socket fill improves this build."
                if report.no_quest
                else "  No socket quest candidate improves this build."
            )
            lines.append(empty_msg)
            continue

        for idx, cand in enumerate(p.candidates, start=1):
            v = cand.variant
            sock_tag = _format_socket_tag(v, no_quest=report.no_quest)
            arrow = "->" if v.kind == "runeword" else "+"
            missing_note = (
                f" [need: {', '.join(v.missing_runes)}]"
                if v.missing_runes
                else (" [theoretical]" if not v.owned else "")
            )
            lines.append(
                f"  #{idx} {v.item_name} [{v.item_loc}] ({v.slot}, {sock_tag}) "
                f"{arrow} {v.action_label}{missing_note}"
            )
            delta_str = _format_delta_summary(cand, diff_name=p.diff_name, offense=p.offense)
            lines.append(f"     Gain  : {delta_str}")
            lines.append(
                f"     Result: {_format_build_brief(cand.result, diff_name=p.diff_name, offense=p.offense)}"
            )
            if diff_note := _format_gear_diff_note(cand):
                lines.append(f"     {diff_note}")

    if len(report.presets) > 1:
        summary_counts: Counter[tuple[str, str, str]] = Counter()
        best_action: dict[tuple[str, str, str], tuple[int, str]] = {}
        for p in report.presets:
            for rank, cand in enumerate(p.candidates, start=1):
                v = cand.variant
                key = (v.item_name, v.item_loc, v.slot)
                summary_counts[key] += 1
                prev = best_action.get(key)
                if prev is None or rank < prev[0]:
                    best_action[key] = (rank, v.action_label)
        if summary_counts:
            lines.append("")
            summary_title = (
                "=== Overall Best Open-Socket Targets ==="
                if report.no_quest
                else "=== Overall Best Socket Quest Targets ==="
            )
            lines.append(summary_title)
            ranked_targets = sorted(
                summary_counts.items(),
                key=lambda kv: (-kv[1], best_action[kv[0]][0], kv[0][0]),
            )
            for (item_name, item_loc, slot), count in ranked_targets[:5]:
                best_rank, action_lbl = best_action[(item_name, item_loc, slot)]
                lines.append(
                    f"  - {item_name} [{item_loc}] ({slot}): top-{len(p.candidates)} in "
                    f"{count}/{len(report.presets)} presets (best #{best_rank} with {action_lbl})"
                )

    return "\n".join(lines)
