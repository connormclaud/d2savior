"""Full, summary, and search text formatting for Diablo II shared stash files."""

from d2savior.core.constants import (
    COMBINED_SLOT_ORDER_STRIPPED,
    GEM_CODE_MAP,
    GEM_TYPE_NAMES,
    MATERIAL_CODES_STRIPPED,
    RUNE_CODES_STRIPPED,
    TAB_TYPE_NAMES,
)
from d2savior.core.item import D2Item
from d2savior.core.item_formatter import (
    _format_item_lines,
    format_item_summary,
    item_matches_pattern,
)
from d2savior.core.resolver import GameDataResolver
from d2savior.core.stash import STASH_TAB_TYPE_ADVANCED, SharedStash


def _append_counted_summaries(
    lines: list[str],
    items: list[D2Item],
    resolver: GameDataResolver,
    version: int,
    *,
    include_properties: bool,
) -> None:
    """Group identical item summaries with counts and append bullet lines."""
    item_counts: dict[str, int] = {}
    item_order: list[str] = []
    for it in items:
        summary = format_item_summary(
            it, resolver=resolver, version=version, include_properties=include_properties
        )
        if summary not in item_counts:
            item_counts[summary] = 0
            item_order.append(summary)
        item_counts[summary] += 1

    for summary in item_order:
        count = item_counts[summary]
        if count > 1:
            plural = "Jewels" if summary == "Jewel" else summary
            lines.append(f"  - {count}x {plural}")
        else:
            lines.append(f"  - {summary}")


def format_stash_info(stash: SharedStash, resolver: GameDataResolver) -> str:
    result = []
    result.append("=== Diablo II Shared Stash ===")
    result.append(f"Total Tabs: {stash.get_tab_count()}")
    result.append("")

    for tab_idx, tab in enumerate(stash.tabs):
        result.append(
            f"=== Tab {tab_idx + 1} ({TAB_TYPE_NAMES.get(tab.tab_type, f'Unknown({tab.tab_type})')}) ==="
        )
        if tab.gold:
            result.append(f"Gold: {tab.gold}")

        items = tab.items.items if tab.items else []
        version = tab.item_format if tab.item_format else 0x63
        tab_resolver = resolver.for_version(version)
        if tab.tab_type == STASH_TAB_TYPE_ADVANCED:
            active_items = [item for item in items if item.stash_stack_size > 0]
            result.append(f"Total items: {len(active_items)}")
            for item_idx, item in enumerate(active_items):
                result.append(f"--- Item {item_idx} ---")
                result.extend(_format_item_lines(item, resolver=tab_resolver, version=version))
        else:
            result.append(f"Total items: {len(items)}")
            for item_idx, item in enumerate(items):
                result.append(f"--- Item {item_idx} ---")
                result.extend(_format_item_lines(item, resolver=tab_resolver, version=version))
        result.append("")

    return "\n".join(result).rstrip()


def format_stash_summary(stash: SharedStash, resolver: GameDataResolver) -> str:
    result = []
    result.append("=== Diablo II Shared Stash Summary ===")
    tab_count = stash.get_tab_count()
    result.append(f"Total Tabs: {tab_count}")

    tab_summaries = [
        f"Tab {tab_idx + 1}: {TAB_TYPE_NAMES.get(tab.tab_type, f'Unknown({tab.tab_type})')}"
        for tab_idx, tab in enumerate(stash.tabs)
    ]
    result.append(f"Tabs: {', '.join(tab_summaries)}")
    result.append("")

    slot_order_map = {code: idx for idx, code in enumerate(COMBINED_SLOT_ORDER_STRIPPED)}

    for tab_idx, tab in enumerate(stash.tabs):
        result.append(
            f"=== Tab {tab_idx + 1} ({TAB_TYPE_NAMES.get(tab.tab_type, f'Unknown({tab.tab_type})')}) ==="
        )
        if tab.gold:
            result.append(f"Gold: {tab.gold}")

        items = tab.items.items if tab.items else []
        version = tab.item_format if tab.item_format else 0x63
        cur_resolver = resolver.for_version(version)

        if tab.tab_type == STASH_TAB_TYPE_ADVANCED:
            active_items = [it for it in items if it.stash_stack_size > 0]
            if not active_items:
                result.append("  (empty)")
            else:
                runes_list = []
                materials_list = []
                other_list = []
                gem_stats = {g: {"p": 0, "f": 0, "o": 0} for g in GEM_TYPE_NAMES}

                sorted_active = sorted(
                    active_items,
                    key=lambda it: slot_order_map.get(it.type_name.strip(), 9999),
                )

                for it in sorted_active:
                    code_b = it.type_name.strip()
                    code_str = it.code_str
                    stack_size = it.stash_stack_size

                    if code_b in GEM_CODE_MAP:
                        g_type, tier = GEM_CODE_MAP[code_b]
                        gem_stats[g_type][tier] += stack_size
                    elif code_b in RUNE_CODES_STRIPPED:
                        display_name = cur_resolver.get_localized_rune_short_name(code_str)
                        runes_list.append(f"{display_name}: {stack_size}")
                    elif code_b in MATERIAL_CODES_STRIPPED:
                        type_info = cur_resolver.get_item(code_str)
                        raw_name = type_info.name if type_info else code_str
                        item_name = cur_resolver.get_localized_item_name(
                            code_str, fallback=raw_name
                        )
                        materials_list.append(f"{item_name}: {stack_size}")
                    else:
                        type_info = cur_resolver.get_item(code_str)
                        raw_name = type_info.name if type_info else code_str
                        item_name = cur_resolver.get_localized_item_name(
                            code_str, fallback=raw_name
                        )
                        other_list.append(f"{item_name}: {stack_size}")

                gems_list = []
                for g_type in GEM_TYPE_NAMES:
                    p = gem_stats[g_type]["p"]
                    f = gem_stats[g_type]["f"]
                    o = gem_stats[g_type]["o"]
                    if p > 0 or f > 0 or o > 0:
                        loc_g_type = cur_resolver.get_localized_gem_type_name(g_type)
                        gems_list.append(f"{loc_g_type}: p {p}, f {f}, o {o}")

                if runes_list:
                    result.append(f"  Runes: {', '.join(runes_list)}")
                if gems_list:
                    result.append(
                        f"  Gems (p=perfect, f=flawless, o=other): {', '.join(gems_list)}"
                    )
                if materials_list:
                    result.append(f"  Materials: {', '.join(materials_list)}")
                if other_list:
                    result.append(f"  Other: {', '.join(other_list)}")
        else:
            if not items:
                result.append("  (empty)")
            else:
                _append_counted_summaries(
                    result, items, resolver=cur_resolver, version=version, include_properties=False
                )
        result.append("")

    return "\n".join(result).rstrip()


def format_stash_find(
    stash: SharedStash,
    pattern: str,
    resolver: GameDataResolver,
    summary: bool = True,
) -> str | None:
    """Format matching items found in a shared stash file."""
    tab_results: list[list[str]] = []

    for tab_idx, tab in enumerate(stash.tabs):
        version = tab.item_format if tab.item_format else 0x63
        tab_resolver = resolver.for_version(version)
        items = tab.items.items if tab.items else []
        is_advanced = tab.tab_type == STASH_TAB_TYPE_ADVANCED

        if is_advanced:
            items = [it for it in items if it.stash_stack_size > 0]

        matching = [
            it
            for it in items
            if item_matches_pattern(it, pattern, resolver=tab_resolver, version=version)
        ]
        if not matching:
            continue

        lines: list[str] = []
        tab_name = TAB_TYPE_NAMES.get(tab.tab_type, f"Unknown({tab.tab_type})")
        lines.append(f"=== Tab {tab_idx + 1} ({tab_name}) ===")

        if summary:
            if is_advanced:
                for it in matching:
                    lines.append(
                        f"  - {format_item_summary(it, resolver=tab_resolver, version=version, include_properties=True)}"
                    )
            else:
                _append_counted_summaries(
                    lines,
                    matching,
                    resolver=tab_resolver,
                    version=version,
                    include_properties=True,
                )
        else:
            for item_idx, it in enumerate(matching):
                lines.append(f"--- Item {item_idx} ---")
                lines.extend(_format_item_lines(it, resolver=tab_resolver, version=version))

        tab_results.append(lines)

    if not tab_results:
        return None

    result = []
    header_mode = "Summary" if summary else ""
    header = f"=== Diablo II Shared Stash {header_mode} ===".replace("  ", " ").strip()
    result.append(header)
    for t_lines in tab_results:
        result.extend(t_lines)
        result.append("")

    return "\n".join(result).rstrip()
