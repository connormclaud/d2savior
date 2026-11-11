"""Full and summary text formatting for Diablo II saves, stashes, and items."""

import datetime
from collections.abc import Callable
from typing import Any

from d2savior.core.constants import (
    CLASS_SKILL_BASES,
    COMBINED_SLOT_ORDER_STRIPPED,
    DIFFICULTY_NAMES,
    GEM_CODE_MAP,
    GEM_TYPE_NAMES,
    MATERIAL_CODES_STRIPPED,
    QUESTS_BY_ACT,
    RUNE_CODES_STRIPPED,
    TAB_TYPE_NAMES,
    WAYPOINTS_BY_ACT,
)
from d2savior.core.d2data import GameDataResolver
from d2savior.core.d2s_struct import CharStatus, D2SStruct
from d2savior.core.enums import EquipSlot, ItemLocation, ItemQuality, StoredIn
from d2savior.core.item import ITEM_FLAG_LABELS
from d2savior.core.stash import (
    STASH_TAB_TYPE_ADVANCED,
    SharedStash,
)
from d2savior.core.stats import calculate_advanced_stats

type SkillInfo = tuple[int, str, int]
type FormattedLines = list[str]


def get_char_type_name(char_type: int) -> str:
    status = CharStatus(char_type)
    flags = [f.name.capitalize() for f in status]
    return " | ".join(flags) if flags else "Normal"


def get_char_status_summary(char_data: D2SStruct) -> str:
    status_parts = []
    is_lad = (
        char_data.is_ladder()
        if hasattr(char_data, "is_ladder")
        else bool(getattr(char_data, "char_flags", 0) & 0x40)
    )
    if is_lad:
        status_parts.append("Ladder")

    is_hc = (
        char_data.is_hardcore()
        if hasattr(char_data, "is_hardcore")
        else bool(getattr(char_data, "char_flags", 0) & 0x04)
    )
    status_parts.append("Hardcore" if is_hc else "Softcore")

    is_died = (
        char_data.is_died_before()
        if hasattr(char_data, "is_died_before")
        else bool(getattr(char_data, "char_flags", 0) & 0x08)
    )
    if is_died:
        status_parts.append("Died before")

    return " | ".join(status_parts)


def get_char_title_name(char_title: int, char_class: int) -> str:
    if char_title == 0:
        return "None"
    elif char_title >= 0xF:
        if char_class in [0, 1]:
            return "Matriarch"
        else:
            return "Patriarch"
    elif char_title >= 0xA:
        return "Champion"
    elif char_title >= 5:
        return "Slayer"
    else:
        return f"Unknown({char_title})"


def format_timestamp(ts: int) -> str:
    if not ts or ts == 0xFFFFFFFF or ts < 0:
        return "N/A"
    try:
        dt = datetime.datetime.fromtimestamp(ts, tz=datetime.UTC)
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except OSError, OverflowError, ValueError:
        return f"Unknown({ts})"


def format_duration(seconds: int) -> str:
    if seconds == 0xFFFFFFFF or seconds < 0:
        return "N/A"
    if seconds == 0:
        return "0s"
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if secs > 0 or not parts:
        parts.append(f"{secs}s")
    return " ".join(parts)


def get_item_display_name(item: Any, resolver: GameDataResolver, version: int = 0x63) -> str:
    type_name = (
        item.type_name.decode("ascii", errors="replace").strip() if item.type_name else "Unknown"
    )

    raw_name = type_info.name if (type_info := resolver.get_item(type_name)) else type_name
    base_item_name = resolver.get_localized_item_name(type_name, fallback=raw_name)

    if ext := getattr(getattr(item, "item_info", None), "ext_info", None):
        if ext.rune_id is not None and (
            rw_name := resolver.get_localized_runeword_name(ext.rune_word_id())
        ):
            return f"{rw_name} ({base_item_name})"
        if ext.unique_id is not None and (
            u_name := resolver.get_localized_unique_name(ext.unique_id)
        ):
            return f"{u_name} ({base_item_name})"
        if ext.set_id is not None and (s_name := resolver.get_localized_set_name(ext.set_id)):
            return f"{s_name} ({base_item_name})"
        match item.quality():
            case ItemQuality.MAGIC:
                prefix_name = (
                    resolver.get_localized_magic_prefix(ext.magic_prefix)
                    if ext.magic_prefix
                    else ""
                )
                suffix_name = (
                    resolver.get_localized_magic_suffix(ext.magic_suffix)
                    if ext.magic_suffix
                    else ""
                )
                if parts := [p for p in [prefix_name, base_item_name, suffix_name] if p]:
                    return " ".join(parts)
            case ItemQuality.RARE:
                rare_pfx = resolver.get_localized_quality_name("Rare")
                if ext.rare_name and (
                    rare_name := resolver.get_localized_rare_name(
                        ext.rare_name.name_1, ext.rare_name.name_2
                    )
                ):
                    return f"{rare_name} ({rare_pfx} {base_item_name})"
                return f"{rare_pfx} {base_item_name}"
            case ItemQuality.CRAFTED:
                crafted_pfx = resolver.get_localized_quality_name("Crafted")
                if ext.craft_name and (
                    craft_name := resolver.get_localized_rare_name(
                        ext.craft_name.name_1, ext.craft_name.name_2
                    )
                ):
                    return f"{craft_name} ({crafted_pfx} {base_item_name})"
                return f"{crafted_pfx} {base_item_name}"
            case ItemQuality.HIGH:
                sup_pfx = resolver.get_localized_quality_name("Superior")
                return f"{sup_pfx} {base_item_name}"
            case ItemQuality.LOW:
                low_pfx = resolver.get_localized_quality_name("Low Quality")
                return f"{low_pfx} {base_item_name}"

    return base_item_name


def item_matches_pattern(
    item: Any, pattern: str, resolver: GameDataResolver, version: int = 0x63
) -> bool:
    """Return True if the item or any of its socketed items match the search pattern."""
    norm = pattern.strip().lower()
    if not norm:
        return False

    title = get_item_display_name(item, resolver=resolver, version=version)
    if norm in title.lower():
        return True

    if getattr(item, "gem_items", None):
        for gem in item.gem_items:
            gem_title = get_item_display_name(gem, resolver=resolver, version=version)
            if norm in gem_title.lower():
                return True

    return False


def _format_parsed_properties(
    prop_list: Any,
    resolver: GameDataResolver,
    version: int = 0x63,
    property_formatter: Callable[..., str | None] | None = None,
) -> FormattedLines:
    """Format a property list into human-readable strings, falling back to raw IDs."""
    if not prop_list or not getattr(prop_list, "properties", None):
        return []
    format_func = property_formatter or resolver.format_property
    result = []
    data = resolver.data
    parsed_props = prop_list.get_parsed_properties(version, data=data)

    for prop_id, value, params in parsed_props:
        formatted = format_func(prop_id, params, version)
        if formatted:
            result.append(formatted)
        elif params:
            result.append(f"ID {prop_id}: raw={value}, params={params}")
        else:
            result.append(f"ID {prop_id}: {value}")
    return result


def _format_summary_properties(
    parsed_props: list[tuple[int, int, list[int]]],
    resolver: GameDataResolver,
    version: int = 0x63,
    property_formatter: Callable[..., str | None] | None = None,
) -> FormattedLines:
    """Format summary properties with numeric stat stacking and resistance collapsing."""
    if not parsed_props:
        return []

    format_func = property_formatter or resolver.format_property

    ordered_keys: list[Any] = []
    aggregated: dict[Any, list[int]] = {}
    prop_id_map: dict[Any, int] = {}
    raw_val_map: dict[Any, int] = {}

    for idx, (prop_id, value, params) in enumerate(parsed_props):
        p_list = list(params) if params else [value]
        stat = resolver.data.get_stat(prop_id)
        if stat is None:
            key = (prop_id, idx)
            ordered_keys.append(key)
            aggregated[key] = p_list
            prop_id_map[key] = prop_id
            raw_val_map[key] = value
        elif prop_id in (83, 97, 107):
            key = (prop_id, p_list[0])
            if key not in aggregated:
                ordered_keys.append(key)
                aggregated[key] = p_list
                prop_id_map[key] = prop_id
                raw_val_map[key] = value
            else:
                aggregated[key][1] += p_list[1]
        elif prop_id == 188:
            key = (prop_id, p_list[0], p_list[1])
            if key not in aggregated:
                ordered_keys.append(key)
                aggregated[key] = p_list
                prop_id_map[key] = prop_id
                raw_val_map[key] = value
            else:
                aggregated[key][2] += p_list[2]
        elif prop_id in (179, 180):
            key = (prop_id, p_list[0])
            if key not in aggregated:
                ordered_keys.append(key)
                aggregated[key] = p_list
                prop_id_map[key] = prop_id
                raw_val_map[key] = value
            else:
                aggregated[key][1] += p_list[1]
        elif prop_id in (98, 151, 155, 195, 196, 197, 198, 199, 201, 204):
            key = (prop_id, idx)
            ordered_keys.append(key)
            aggregated[key] = p_list
            prop_id_map[key] = prop_id
            raw_val_map[key] = value
        else:
            val = p_list[0]
            key = (prop_id,)
            if key not in aggregated:
                ordered_keys.append(key)
                aggregated[key] = [val]
                prop_id_map[key] = prop_id
                raw_val_map[key] = value
            else:
                aggregated[key][0] += val

    res_keys = [(39,), (41,), (43,), (45,)]
    all_res_present = all(k in aggregated for k in res_keys)
    min_res = 0
    if all_res_present:
        res_vals = [aggregated[k][0] for k in res_keys]
        if all(v > 0 for v in res_vals):
            min_res = min(res_vals)

    result: list[str] = []
    all_res_inserted = False

    for key in ordered_keys:
        if key not in aggregated:
            continue

        prop_id = prop_id_map[key]
        params = aggregated[key]

        if min_res > 0 and key in res_keys:
            if not all_res_inserted:
                all_res_inserted = True
                tpl = resolver.get_item_modifier("strModAllResistances") or "All Resistances %+d"
                all_res_str = tpl.replace("%+d", f"{min_res:+d}").replace("%d", str(min_res))
                result.append(all_res_str)

            val = params[0]
            if val > min_res:
                excess = val - min_res
                formatted_excess = format_func(prop_id, [excess], version)
                if formatted_excess:
                    result.append(formatted_excess)
            continue

        formatted = format_func(prop_id, params, version)
        if formatted:
            result.append(formatted)
        elif len(params) > 1:
            raw_val = raw_val_map.get(key, params[0])
            result.append(f"ID {prop_id}: raw={raw_val}, params={params}")
        elif params:
            result.append(f"ID {prop_id}: {params[0]}")
        else:
            raw_val = raw_val_map.get(key, 0)
            result.append(f"ID {prop_id}: {raw_val}")

    return result


def format_item_summary(
    item: Any,
    resolver: GameDataResolver,
    version: int = 0x63,
    include_properties: bool = True,
    property_formatter: Callable[..., str | None] | None = None,
) -> str:
    info = getattr(item, "item_info", None)
    if info and info.gold:
        return f"Gold: {info.gold.quantity}"

    title = get_item_display_name(item, resolver=resolver, version=version)

    meta_tags = []
    tp = getattr(info, "type_specific_info", None)
    if tp:
        if tp.defence is not None:
            meta_tags.append(f"Def: {tp.get_defence()}")
        sockets = tp.total_sockets()
        if sockets > 0:
            meta_tags.append(f"Sockets: {sockets}")

    if getattr(item, "is_ethereal", False):
        meta_tags.append("Eth")
    if getattr(item, "is_disabled", False):
        meta_tags.append("Broken")

    stack_size = getattr(info, "stash_stack_size", 0)
    if stack_size > 1:
        meta_tags.append(f"x{stack_size}")
    elif tp and tp.quantity is not None and tp.quantity > 1:
        meta_tags.append(f"Qty: {tp.quantity}")

    if getattr(item, "gem_items", None):
        socketed = []
        for gem in item.gem_items:
            g_name = get_item_display_name(gem, version=version, resolver=resolver)
            socketed.append(g_name)
        if socketed:
            meta_tags.append(f"Socketed: {'+'.join(socketed)}")

    props = []
    if include_properties and tp:
        all_parsed: list[tuple[int, int, list[int]]] = []
        if getattr(tp, "property_list", None):
            all_parsed.extend(tp.property_list.get_parsed_properties(version, data=resolver.data))
        if getattr(tp, "runeword_property_list", None):
            all_parsed.extend(
                tp.runeword_property_list.get_parsed_properties(version, data=resolver.data)
            )
        if getattr(item, "gem_items", None):
            for gem in item.gem_items:
                all_parsed.extend(resolver.get_socket_properties(item, gem))

        props = _format_summary_properties(
            all_parsed,
            resolver=resolver,
            version=version,
            property_formatter=property_formatter,
        )

    return f"{title}{f' [{", ".join(meta_tags)}]' if meta_tags else ''}{f' ({", ".join(props)})' if props else ''}"


def _format_item_lines(
    item: Any,
    resolver: GameDataResolver,
    indent: str = "  ",
    version: int | None = None,
    parent_item: Any | None = None,
) -> FormattedLines:
    result = []
    type_name = item.type_name.decode("ascii", errors="replace") if item.type_name else "Unknown"

    if version is None:
        version = item.version if item.version else 0x63
    item_resolver = resolver.for_version(version)

    item_full_name = ""
    req_level = 0
    if type_info := item_resolver.get_item(type_name.strip()):
        item_full_name = type_info.name
        req_level = type_info.levelreq

    result.append(f"{indent}Type: {type_name}{f' ({item_full_name})' if item_full_name else ''}")

    if req_level > 0:
        result.append(f"{indent}Required Level: {req_level}")

    location = ItemLocation(item.location)
    if location == ItemLocation.EQUIPPED and item.position in EquipSlot:
        result.append(
            f"{indent}Location: {location}, Position: {item.position} ({EquipSlot(item.position)})"
        )
    else:
        result.append(f"{indent}Location: {location}, Position: {item.position}")
    storedin = StoredIn(item.stored_in)
    result.append(f"{indent}Column: {item.column}, Row: {item.row}, StoredIn: {storedin}")
    quality = ItemQuality(item.quality())
    result.append(f"{indent}Quality: {quality}")

    flags = (
        item.get_flag_names()
        if hasattr(item, "get_flag_names")
        else [label for attr, label in ITEM_FLAG_LABELS if getattr(item, attr, False)]
    )
    if flags:
        result.append(f"{indent}Flags: {', '.join(flags)}")

    if info := item.item_info:
        if ext := info.ext_info:
            if ext.guid:
                result.append(f"{indent}GUID: 0x{ext.guid:08X}")
            if ext.drop_level:
                result.append(f"{indent}Drop Level: {ext.drop_level}")
            if ext.magic_prefix:
                prefix_id = ext.magic_prefix
                prefix_name = item_resolver.get_localized_magic_prefix(prefix_id)
                result.append(
                    f"{indent}Prefix: {prefix_id}{f' ({prefix_name})' if prefix_name else ''}"
                )
            if ext.magic_suffix:
                suffix_id = ext.magic_suffix
                suffix_name = item_resolver.get_localized_magic_suffix(suffix_id)
                result.append(
                    f"{indent}Suffix: {suffix_id}{f' ({suffix_name})' if suffix_name else ''}"
                )
            if ext.set_id is not None:
                set_id = ext.set_id
                set_name = item_resolver.get_localized_set_name(set_id)
                result.append(f"{indent}Set ID: {set_id}{f' ({set_name})' if set_name else ''}")
            if ext.unique_id is not None:
                unique_id = ext.unique_id
                unique_name = item_resolver.get_localized_unique_name(unique_id)
                result.append(
                    f"{indent}Unique ID: {unique_id}{f' ({unique_name})' if unique_name else ''}"
                )
            if ext.rune_id is not None:
                runeword_id = ext.rune_word_id()
                rw_name = item_resolver.get_localized_runeword_name(runeword_id)
                result.append(
                    f"{indent}Rune Word ID: {runeword_id}{f' ({rw_name})' if rw_name else ''}"
                )
                if item.gem_items:
                    rune_names = []
                    for gem in item.gem_items:
                        gem_type = (
                            gem.type_name.decode("ascii", errors="replace").strip()
                            if gem.type_name
                            else ""
                        )
                        if gem_type.startswith("r"):
                            try:
                                rune_num = int(gem_type[1:])
                                rune_name = (
                                    rune_info.name
                                    if (rune_info := resolver.get_item(gem_type))
                                    else ""
                                )
                                rune_names.append(f"{rune_name}({rune_num})")
                            except ValueError:
                                pass
                    if rune_names:
                        result.append(f"{indent}Runes: {'+'.join(rune_names)}")
            if ext.rare_name:
                rare_name = item_resolver.get_localized_rare_name(
                    ext.rare_name.name_1, ext.rare_name.name_2
                )
                result.append(
                    f"{indent}Rare Name: {ext.rare_name.name_1}-{ext.rare_name.name_2}{f' ({rare_name})' if rare_name else ''}"
                )
            if ext.craft_name:
                craft_name = item_resolver.get_localized_rare_name(
                    ext.craft_name.name_1, ext.craft_name.name_2
                )
                result.append(
                    f"{indent}Craft Name: {ext.craft_name.name_1}-{ext.craft_name.name_2}{f' ({craft_name})' if craft_name else ''}"
                )

        if tp := info.type_specific_info:
            if tp.defence is not None:
                result.append(f"{indent}Defence: {tp.get_defence()}")
            if tp.max_durability is not None:
                if tp.is_indestructible():
                    result.append(f"{indent}Durability: Indestructible")
                else:
                    cur = tp.current_durability if tp.current_durability is not None else 0
                    result.append(f"{indent}Durability: {cur}/{tp.max_durability}")
            if tp.quantity is not None:
                result.append(f"{indent}Quantity: {tp.quantity}")
            if (sockets := tp.total_sockets()) > 0:
                result.append(f"{indent}Sockets: {sockets}")

            if props := _format_parsed_properties(
                getattr(tp, "property_list", None), resolver=item_resolver, version=version
            ):
                result.append(f"{indent}Properties:")
                for p in props:
                    result.append(f"{indent}  - {p}")

            if rw_props := _format_parsed_properties(
                getattr(tp, "runeword_property_list", None), resolver=item_resolver, version=version
            ):
                result.append(f"{indent}Rune Word Properties:")
                for p in rw_props:
                    result.append(f"{indent}  - {p}")

            if getattr(tp, "set_properties", None):
                for idx, set_prop_list in enumerate(tp.set_properties):
                    if set_props := _format_parsed_properties(
                        set_prop_list, resolver=item_resolver, version=version
                    ):
                        piece_count = idx + 2
                        result.append(f"{indent}Set Properties ({piece_count} Items):")
                        for p in set_props:
                            result.append(f"{indent}  - {p}")

        if getattr(info, "stash_stack_size", 0) > 0:
            result.append(f"{indent}Stack Size: {info.stash_stack_size}")
        if info.gold:
            result.append(f"{indent}Gold: {info.gold.quantity}")

    if parent_item and not (tp and getattr(tp, "property_list", None)):
        socket_props = item_resolver.get_socket_properties(parent_item, item)
        if socket_props:
            result.append(f"{indent}Properties:")
            for prop_id, _val, params in socket_props:
                formatted = item_resolver.format_property(prop_id, params, version)
                if formatted:
                    result.append(f"{indent}  - {formatted}")

    if item.gem_items:
        for j, gem in enumerate(item.gem_items):
            result.append(f"{indent}Socketed Item [{j}]:")
            result.extend(
                _format_item_lines(
                    gem,
                    resolver=item_resolver,
                    indent=indent + "  ",
                    version=version,
                    parent_item=item,
                )
            )

    return result


def format_item_info(
    item: Any,
    resolver: GameDataResolver,
    indent: str = "  ",
    version: int | None = None,
) -> str:
    return "\n".join(_format_item_lines(item, resolver=resolver, indent=indent, version=version))


def _format_waypoints_lines(char_data: D2SStruct, resolver: GameDataResolver) -> FormattedLines:
    loc = resolver.loc
    result = []
    result.append("=== Waypoints ===")
    if char_data.waypoints.magic == 0x5357:
        for diff_idx, diff_name in enumerate(DIFFICULTY_NAMES):
            if diff_idx >= len(char_data.waypoints.wp):
                break
            wp_data = char_data.waypoints.wp[diff_idx]
            global_idx = 0
            total_unlocked = 0
            act_stats = []
            for act_name, wp_names in WAYPOINTS_BY_ACT:
                unlocked_in_act = 0
                missing = []
                for name in wp_names:
                    b = wp_data.waypoints[global_idx // 8]
                    if b & (1 << (global_idx % 8)):
                        total_unlocked += 1
                        unlocked_in_act += 1
                    else:
                        loc_wp = loc.get_level_name(name) if loc else name
                        missing.append(loc_wp)
                    global_idx += 1
                act_stats.append((act_name, len(wp_names), unlocked_in_act, missing))

            # Check if this difficulty has been started (has waypoints beyond starter town or has quest activity)
            has_wp_progress = (wp_data.waypoints[0] & ~1) != 0 or any(
                b != 0 for b in wp_data.waypoints[1:]
            )
            has_quest_progress = False
            if (
                char_data.quests
                and char_data.quests.magic == 0x216F6F57
                and diff_idx < len(char_data.quests.qi_data)
            ):
                qd = char_data.quests.qi_data[diff_idx]
                has_quest_progress = any(
                    w != 0
                    for words in [qd.act_1, qd.act_2, qd.act_3, qd.act_4, qd.act_5]
                    for w in words
                )

            if not has_wp_progress and not has_quest_progress:
                result.append(f"{diff_name}: Not started")
                continue

            total_missing = 39 - total_unlocked
            if total_unlocked == 39:
                result.append(f"{diff_name} (39/39 unlocked): All unlocked")
            else:
                result.append(
                    f"{diff_name} ({total_unlocked}/39 unlocked, {total_missing} missing):"
                )
                for act_name, total_act, unlocked_act, missing in act_stats:
                    if unlocked_act == total_act:
                        result.append(f"  {act_name} ({total_act}/{total_act}): All unlocked")
                    elif unlocked_act == 0:
                        result.append(f"  {act_name} (0/{total_act}): None unlocked")
                    else:
                        result.append(
                            f"  {act_name} ({unlocked_act}/{total_act}): Missing {', '.join(missing)}"
                        )
    return result


def format_waypoints_info(char_data: D2SStruct, resolver: GameDataResolver) -> str:
    return "\n".join(_format_waypoints_lines(char_data, resolver))


def _format_quests_lines(char_data: D2SStruct, resolver: GameDataResolver) -> FormattedLines:
    loc = resolver.loc
    result = []
    result.append("=== Quests ===")
    if char_data.quests and char_data.quests.magic == 0x216F6F57:
        for diff_idx, diff_name in enumerate(DIFFICULTY_NAMES):
            if diff_idx >= len(char_data.quests.qi_data):
                break
            qd = char_data.quests.qi_data[diff_idx]
            act_words = [qd.act_1, qd.act_2, qd.act_3, qd.act_4, qd.act_5]
            has_quest_progress = any(w != 0 for words in act_words for w in words)
            if not has_quest_progress and qd.reset_stats == 0:
                result.append(f"{diff_name}: Not started")
                continue

            reset_status = (
                "Available"
                if qd.reset_stats == 2
                else ("Used" if qd.reset_stats == 1 else "Locked")
            )
            total_completed = sum(1 for words in act_words for w in words if (w & 1) or (w & 2))
            rewards_unclaimed = sum(
                1 for words in act_words for w in words if (w & 2) and not (w & 1)
            )
            reward_str = (
                f", {rewards_unclaimed} reward{'s' if rewards_unclaimed > 1 else ''} unclaimed"
                if rewards_unclaimed
                else ""
            )

            result.append(
                f"{diff_name} ({total_completed}/27 completed{reward_str}) — Akara Reset: {reset_status}"
            )
            for (act_name, quest_defs), words in zip(QUESTS_BY_ACT, act_words, strict=False):
                words_ordered = [words[idx] for _, idx in quest_defs]
                if all(w & 1 for w in words_ordered):
                    result.append(f"  {act_name}: {' '.join('[x]' for _ in quest_defs)}")
                elif all(not (w & 1) and not (w & 2) for w in words_ordered):
                    result.append(f"  {act_name}: {' '.join('[ ]' for _ in quest_defs)}")
                else:
                    parts = []
                    for (name, _idx), w in zip(quest_defs, words_ordered, strict=False):
                        loc_qname = loc.get_quest_name(name) if loc else name
                        if w & 1:
                            parts.append("[x]")
                        elif w & 2:
                            parts.append(f"[!] {loc_qname} (reward unclaimed)")
                        else:
                            parts.append(f"[ ] {loc_qname}")
                    result.append(f"  {act_name}: {' '.join(parts)}")
    return result


def format_quests_info(char_data: D2SStruct, resolver: GameDataResolver) -> str:
    return "\n".join(_format_quests_lines(char_data, resolver))


def _get_character_skills(char_data: D2SStruct, resolver: GameDataResolver) -> list[SkillInfo]:
    """Return invested skills as a list of (skill_index, skill_name, level) tuples."""
    if not getattr(char_data, "skills", None) or char_data.skills.magic != 0x6669:
        return []
    skills = []
    for i, level in enumerate(char_data.skills.skill_levels):
        if level > 0:
            skill_name = ""
            if 0 <= char_data.char_class < len(CLASS_SKILL_BASES):
                skill_id = CLASS_SKILL_BASES[char_data.char_class] + i
                skill_name = resolver.get_skill_name(skill_id)
            skills.append((i, skill_name, level))
    return skills


def format_char_info(char_data: D2SStruct, resolver: GameDataResolver) -> str:
    result = []
    result.append("=== Diablo II Character Info ===")
    char_name = char_data.get_char_name()
    result.append(f"Name: {char_name}")
    char_resolver = resolver.for_version(char_data.version)
    result.append(f"Class: {char_resolver.get_localized_class_name(char_data.char_class)}")
    result.append(f"Level: {char_data.char_level}")
    result.append(f"Version: 0x{char_data.version:X}")
    result.append(f"Hardcore: {'Yes' if char_data.is_hardcore() else 'No'}")
    result.append(f"Ladder: {'Yes' if char_data.is_ladder() else 'No'}")
    result.append(f"Expansion: {'Yes' if char_data.is_expansion() else 'No'}")
    result.append(f"Died before: {'Yes' if char_data.is_died_before() else 'No'}")

    char_type_name = get_char_type_name(char_data.char_flags)
    result.append(f"Character Flags: 0x{char_data.char_flags:X} ({char_type_name})")

    char_title = getattr(char_data, "char_title", 0)
    char_title_name = get_char_title_name(char_title, char_data.char_class)
    result.append(f"Character Title: 0x{char_title:X} ({char_title_name})")

    result.append(f"Weapon Set: {'I' if char_data.weapon_set == 0 else 'II'}")

    create_time = getattr(char_data, "create_time", 0)
    last_save_time = getattr(char_data, "last_save_time", 0) or getattr(char_data, "dw_time", 0)
    play_time = getattr(char_data, "play_time", 0)

    result.append(f"Create Time: {format_timestamp(create_time)}")
    result.append(f"Last Save Time: {format_timestamp(last_save_time)}")
    result.append(f"Play Time: {format_duration(play_time)}")

    if char_data.version >= 0x69:
        result.append(f"Game Version: {getattr(char_data, 'game_version', 0)}")
    else:
        result.append(f"NumStats/NumSkills: 0x{getattr(char_data, 'num_stats_num_skills', 0):04X}")
        result.append(f"Merc Dead: {'Yes' if getattr(char_data, 'merc_dead', 0) else 'No'}")
        result.append(
            f"Merc Flags: 0x{getattr(char_data, 'merc_flags_low', 0):04X}{getattr(char_data, 'merc_flags_high', 0):02X}"
        )

    result.append("")
    result.append("=== Player Stats ===")
    stats = char_data.player_stats
    if stats.is_valid:
        result.append(f"Strength: {stats.strength}")
        result.append(f"Energy: {stats.energy}")
        result.append(f"Dexterity: {stats.dexterity}")
        result.append(f"Vitality: {stats.vitality}")
        result.append(f"Stat Points Remaining: {stats.stat_points_remaining}")
        result.append(f"Skill Points Remaining: {stats.skill_points_remaining}")
        result.append(f"Current Life: {stats.current_life}")
        result.append(f"Maximum Life: {stats.max_life}")
        result.append(f"Current Mana: {stats.current_mana}")
        result.append(f"Maximum Mana: {stats.max_mana}")
        result.append(f"Current Stamina: {stats.current_stamina}")
        result.append(f"Maximum Stamina: {stats.max_stamina}")
        result.append(f"Level: {stats.level}")
        result.append(f"Experience: {stats.experience}")
        result.append(f"Gold on Person: {stats.gold}")
        result.append(f"Gold in Stash: {stats.gold_stash}")
    result.append("")
    result.append("=== Skills ===")
    skills = _get_character_skills(char_data, char_resolver)
    if skills:
        result.append("Skill levels:")
        for i, skill_name, level in skills:
            if skill_name:
                result.append(f"Skill {i} ({skill_name}): {level}")
            else:
                result.append(f"Skill {i}: {level}")
    result.append("")
    result.extend(_format_waypoints_lines(char_data, char_resolver))
    result.append("")
    result.extend(_format_quests_lines(char_data, char_resolver))
    result.append("")
    adv_stats = calculate_advanced_stats(char_data, resolver=resolver)
    result.append("=== Advanced Stats ===")
    result.append(f"Gear Resistances: {adv_stats.resistances.format_summary()}")
    result.append(f"Faster Hit Recovery: +{adv_stats.fhr}% | Faster Cast Rate: +{adv_stats.fcr}%")
    result.append(f"Damage: {adv_stats.damage.format_summary()}")
    result.append("")
    result.append("=== Items ===")
    item_list = getattr(char_data, "item_list", None)
    if item_list and getattr(item_list, "magic", None) == 0x4D4A:
        items = getattr(item_list, "items", [])
        result.append(f"Total items: {len(items)}")
        for i, item in enumerate(items):
            result.append(f"--- Item {i} ---")
            result.extend(
                _format_item_lines(item, resolver=char_resolver, version=char_data.version)
            )
    result.append("")
    result.append("=== Corpse ===")
    if char_data.corpse.has_corpse():
        result.append("Has corpse")
        if char_data.corpse.corpse_data and char_data.corpse.corpse_data.items:
            result.append(f"Corpse items: {char_data.corpse.corpse_data.items.count}")
    else:
        result.append("No corpse")
    result.append("")
    result.append("=== Mercenary ===")
    if char_data.is_expansion():
        if char_data.has_mercenary():
            result.append(
                f"Has mercenary (Name: {char_data.merc_name_id}, Type: {char_data.merc_type_id})"
            )
            if char_data.version >= 0x69:
                merc_seed = getattr(char_data, "merc_seed", 0)
                merc_flags = getattr(char_data, "merc_flags", 0)
                result.append(f"Mercenary Seed: 0x{merc_seed:08X}")
                result.append(f"Mercenary Exp: {char_data.merc_experience}")
                result.append(f"Mercenary Flags: 0x{merc_flags:08X}")
            else:
                result.append(f"Mercenary Exp: {char_data.merc_experience}")
                result.append(f"Merc Dead: {'Yes' if char_data.merc_is_dead else 'No'}")
            if char_data.mercenary.items:
                result.append(f"Mercenary items: {char_data.mercenary.items.count}")
                for i, item in enumerate(char_data.mercenary.items.items):
                    result.append(f"--- Mercenary Item {i} ---")
                    result.extend(
                        _format_item_lines(item, resolver=char_resolver, version=char_data.version)
                    )
        else:
            result.append("No mercenary")
    else:
        result.append("Not expansion character")
    result.append("")
    result.append("=== Golem ===")
    if char_data.is_expansion():
        if char_data.golem.has_golem:
            result.append("Has golem")
        else:
            result.append("No golem")
    else:
        result.append("Not expansion character")
    result.append("")
    result.append("=== Demon ===")
    if char_data.demon.has_demon:
        result.append(f"Has demon (Magic: 0x{char_data.demon.magic:X})")
    else:
        result.append("No demon")
    return "\n".join(result)


def format_char_summary(char_data: D2SStruct, resolver: GameDataResolver) -> str:
    result = []
    result.append("=== Diablo II Character Summary ===")
    char_name = char_data.get_char_name()
    version = char_data.version if char_data.version else 0x63
    char_resolver = resolver.for_version(version)
    char_class = char_resolver.get_localized_class_name(char_data.char_class)
    flags_str = get_char_status_summary(char_data)
    char_title = getattr(char_data, "char_title", 0)
    title_str = get_char_title_name(char_title, char_data.char_class)
    weapon_set = "I" if char_data.weapon_set == 0 else "II"

    result.append(
        f"Name: {char_name} | Class: {char_class} | Level: {char_data.char_level} | Title: {title_str}"
    )
    result.append(f"Status: {flags_str} | Weapon Set: {weapon_set}")

    last_save_time = getattr(char_data, "last_save_time", 0) or getattr(char_data, "dw_time", 0)
    play_time = getattr(char_data, "play_time", 0)
    time_parts = []
    if last_save_time:
        time_parts.append(f"Last Saved: {format_timestamp(last_save_time)}")
    if play_time:
        time_parts.append(f"Play Time: {format_duration(play_time)}")
    if time_parts:
        result.append(" | ".join(time_parts))

    stats = char_data.player_stats
    if stats.is_valid:
        result.append(
            f"Attributes: Str: {stats.strength}, Dex: {stats.dexterity}, Vit: {stats.vitality}, Ene: {stats.energy}"
        )
        result.append(
            f"Life: {stats.current_life}/{stats.max_life} | Mana: {stats.current_mana}/{stats.max_mana} | Gold: {stats.gold} (Person), {stats.gold_stash} (Stash)"
        )
        if stats.stat_points_remaining > 0 or stats.skill_points_remaining > 0:
            result.append(
                f"Remaining Points: {stats.stat_points_remaining} Stat, {stats.skill_points_remaining} Skill"
            )

    result.append("")
    result.append("=== Skills ===")
    skills = _get_character_skills(char_data, char_resolver)
    if skills:
        active_skills = [
            f"{skill_name if skill_name else f'Skill {i}'}: {level}"
            for i, skill_name, level in skills
        ]
        result.append(", ".join(active_skills))
    else:
        result.append("None")

    result.append("")
    result.extend(_format_waypoints_lines(char_data, char_resolver))
    result.append("")
    result.extend(_format_quests_lines(char_data, char_resolver))
    result.append("")
    adv_stats = calculate_advanced_stats(char_data, resolver=resolver)
    result.append("=== Advanced Stats ===")
    result.append(f"Gear Resistances: {adv_stats.resistances.format_summary()}")
    result.append(f"Faster Hit Recovery: +{adv_stats.fhr}% | Faster Cast Rate: +{adv_stats.fcr}%")
    result.append(f"Damage: {adv_stats.damage.format_summary()}")
    result.append("")

    result.append("=== Equipped Gear ===")
    equipped_items = {}
    inventory_items = []
    stash_items = []
    cube_items = []
    belt_items = []
    cursor_items = []

    item_list = getattr(char_data, "item_list", None)
    if item_list and getattr(item_list, "magic", None) == 0x4D4A:
        items = getattr(item_list, "items", [])
        for item in items:
            loc = ItemLocation(item.location)
            match (loc, item.stored_in):
                case (ItemLocation.EQUIPPED, _):
                    equipped_items[item.position] = item
                case (ItemLocation.BELT, _):
                    belt_items.append(item)
                case (ItemLocation.STORED, StoredIn.INVENTORY):
                    inventory_items.append(item)
                case (ItemLocation.STORED, StoredIn.STASH):
                    stash_items.append(item)
                case (ItemLocation.STORED, StoredIn.CUBE):
                    cube_items.append(item)
                case (ItemLocation.STORED, _):
                    inventory_items.append(item)
                case (ItemLocation.CURSOR, _):
                    cursor_items.append(item)

    has_equipped = False
    for slot in EquipSlot:
        if slot.value in equipped_items:
            has_equipped = True
            it = equipped_items[slot.value]
            result.append(
                f"- {slot.display_name}: {format_item_summary(it, resolver=char_resolver, version=version)}"
            )
    if not has_equipped:
        result.append("None")

    result.append("")
    result.append("=== Mercenary ===")
    if char_data.is_expansion() and char_data.has_mercenary():
        result.append(
            f"Mercenary: Name Index {char_data.merc_name_id}, Type {char_data.merc_type_id}{' (Dead)' if char_data.merc_is_dead else ''}"
        )
        if char_data.mercenary.items and char_data.mercenary.items.items:
            result.append("Equipped:")
            for m_item in char_data.mercenary.items.items:
                loc = ItemLocation(m_item.location)
                slot_str = ""
                if loc == ItemLocation.EQUIPPED and m_item.position in EquipSlot:
                    slot_str = f"{EquipSlot(m_item.position).display_name}: "
                result.append(
                    f"  - {slot_str}{format_item_summary(m_item, resolver=char_resolver, version=version)}"
                )
        else:
            result.append("Equipped: None")
    else:
        result.append("No mercenary")

    result.append("")
    result.append("=== Inventory & Stash ===")
    stored_lines = []
    for it in inventory_items:
        stored_lines.append(
            f"- [Inventory] {format_item_summary(it, resolver=char_resolver, version=version)}"
        )
    for it in stash_items:
        stored_lines.append(
            f"- [Stash] {format_item_summary(it, resolver=char_resolver, version=version)}"
        )
    for it in cube_items:
        stored_lines.append(
            f"- [Cube] {format_item_summary(it, resolver=char_resolver, version=version)}"
        )

    if belt_items:
        belt_counts = {}
        for it in belt_items:
            summary = format_item_summary(it, resolver=char_resolver, version=version)
            belt_counts[summary] = belt_counts.get(summary, 0) + 1
        for summary, count in belt_counts.items():
            stored_lines.append(f"- [Belt] {summary}{f' (x{count})' if count > 1 else ''}")

    for it in cursor_items:
        stored_lines.append(
            f"- [Cursor] {format_item_summary(it, resolver=char_resolver, version=version)}"
        )

    if stored_lines:
        result.extend(stored_lines)
    else:
        result.append("No stored items")

    return "\n".join(result).rstrip()


def format_char_list(records: list[dict[str, Any]]) -> str:
    """Format a list of character records into a column-aligned table."""
    if not records:
        return ""
    headers = ("NAME", "CLASS", "LEVEL", "MODE", "LAST PLAYED")
    col_name = max(len(headers[0]), max((len(r["name"]) for r in records), default=0))
    col_class = max(len(headers[1]), max((len(r["class"]) for r in records), default=0))
    col_level = max(len(headers[2]), max((len(str(r["level"])) for r in records), default=0))
    col_mode = max(len(headers[3]), max((len(r["mode"]) for r in records), default=0))
    col_last_played = max(len(headers[4]), max((len(r["last_played"]) for r in records), default=0))

    header_line = (
        f"{headers[0]:<{col_name}}  "
        f"{headers[1]:<{col_class}}  "
        f"{headers[2]:>{col_level}}  "
        f"{headers[3]:<{col_mode}}  "
        f"{headers[4]:<{col_last_played}}"
    ).rstrip()

    lines = [header_line]
    for r in records:
        line = (
            f"{r['name']:<{col_name}}  "
            f"{r['class']:<{col_class}}  "
            f"{r['level']!s:>{col_level}}  "
            f"{r['mode']:<{col_mode}}  "
            f"{r['last_played']:<{col_last_played}}"
        ).rstrip()
        lines.append(line)
    return "\n".join(lines)


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
            active_items = [
                item
                for item in items
                if getattr(getattr(item, "item_info", None), "stash_stack_size", 0) > 0
            ]
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
            active_items = [
                it
                for it in items
                if getattr(getattr(it, "item_info", None), "stash_stack_size", 0) > 0
            ]
            if not active_items:
                result.append("  (empty)")
            else:
                runes_list = []
                materials_list = []
                other_list = []
                gem_stats = {g: {"p": 0, "f": 0, "o": 0} for g in GEM_TYPE_NAMES}

                sorted_active = sorted(
                    active_items,
                    key=lambda it: slot_order_map.get(getattr(it, "type_name", b"").strip(), 9999),
                )

                for it in sorted_active:
                    code_b = getattr(it, "type_name", b"").strip()
                    code_str = code_b.decode("ascii", errors="replace")
                    stack_size = getattr(getattr(it, "item_info", None), "stash_stack_size", 0)

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
                item_counts = {}
                item_order = []
                for it in items:
                    summary = format_item_summary(
                        it, resolver=cur_resolver, version=version, include_properties=False
                    )
                    if summary not in item_counts:
                        item_counts[summary] = 0
                        item_order.append(summary)
                    item_counts[summary] += 1

                for summary in item_order:
                    count = item_counts[summary]
                    if count > 1:
                        plural = "Jewels" if summary == "Jewel" else summary
                        result.append(f"  - {count}x {plural}")
                    else:
                        result.append(f"  - {summary}")
        result.append("")

    return "\n".join(result).rstrip()


def format_char_find(
    char_data: D2SStruct,
    pattern: str,
    resolver: GameDataResolver,
    summary: bool = True,
) -> str | None:
    """Format matching items found in a character save file."""
    version = char_data.version
    char_resolver = resolver.for_version(version)

    equipped_matches: list[tuple[EquipSlot, Any]] = []
    merc_matches: list[tuple[str, Any]] = []
    corpse_matches: list[Any] = []
    stored_matches: list[tuple[str, Any]] = []

    item_list = getattr(char_data, "item_list", None)
    if item_list and getattr(item_list, "magic", None) == 0x4D4A:
        for it in getattr(item_list, "items", []):
            if not item_matches_pattern(it, pattern, resolver=char_resolver, version=version):
                continue
            loc = ItemLocation(it.location)
            match (loc, it.stored_in):
                case (ItemLocation.EQUIPPED, _):
                    if it.position in EquipSlot:
                        equipped_matches.append((EquipSlot(it.position), it))
                case (ItemLocation.STORED, StoredIn.INVENTORY):
                    stored_matches.append(("[Inventory]", it))
                case (ItemLocation.STORED, StoredIn.STASH):
                    stored_matches.append(("[Stash]", it))
                case (ItemLocation.STORED, StoredIn.CUBE):
                    stored_matches.append(("[Cube]", it))
                case (ItemLocation.STORED, _):
                    stored_matches.append(("[Inventory]", it))
                case (ItemLocation.BELT, _):
                    stored_matches.append(("[Belt]", it))
                case (ItemLocation.CURSOR, _):
                    stored_matches.append(("[Cursor]", it))

    slot_order = {slot: idx for idx, slot in enumerate(EquipSlot)}
    equipped_matches.sort(key=lambda pair: slot_order.get(pair[0], 999))

    if (
        char_data.is_expansion()
        and char_data.has_mercenary()
        and char_data.mercenary.items
        and char_data.mercenary.items.items
    ):
        for m_item in char_data.mercenary.items.items:
            if item_matches_pattern(m_item, pattern, resolver=char_resolver, version=version):
                loc = ItemLocation(m_item.location)
                slot_str = ""
                if loc == ItemLocation.EQUIPPED and m_item.position in EquipSlot:
                    slot_str = f"{EquipSlot(m_item.position).display_name}: "
                merc_matches.append((slot_str, m_item))

    if (
        char_data.corpse.has_corpse()
        and char_data.corpse.corpse_data
        and char_data.corpse.corpse_data.items
    ):
        for c_item in char_data.corpse.corpse_data.items.items:
            if item_matches_pattern(c_item, pattern, resolver=char_resolver, version=version):
                corpse_matches.append(c_item)

    if not equipped_matches and not merc_matches and not corpse_matches and not stored_matches:
        return None

    char_name = char_data.get_char_name().strip() or "Unknown"
    char_class = char_resolver.get_localized_class_name(char_data.char_class)
    char_level = char_data.char_level

    result = []
    header_mode = "Summary" if summary else "Info"
    result.append(
        f"=== Diablo II Character {header_mode}: {char_name} ({char_class}, Level {char_level}) ==="
    )

    if summary:
        if equipped_matches:
            result.append("=== Equipped Gear ===")
            for slot, it in equipped_matches:
                result.append(
                    f"- {slot.display_name}: {format_item_summary(it, resolver=char_resolver, version=version)}"
                )
        if merc_matches:
            result.append("=== Mercenary ===")
            result.append("Equipped:")
            for slot_str, m_it in merc_matches:
                result.append(
                    f"  - {slot_str}{format_item_summary(m_it, resolver=char_resolver, version=version)}"
                )
        if corpse_matches:
            result.append("=== Corpse ===")
            for c_it in corpse_matches:
                result.append(
                    f"- [Corpse] {format_item_summary(c_it, resolver=char_resolver, version=version)}"
                )
        if stored_matches:
            result.append("=== Inventory & Stash ===")
            for label, it in stored_matches:
                result.append(
                    f"- {label} {format_item_summary(it, resolver=char_resolver, version=version)}"
                )
    else:
        if equipped_matches:
            result.append("=== Equipped Gear ===")
            for slot, it in equipped_matches:
                result.append(f"--- Equipped: {slot.display_name} ---")
                result.extend(_format_item_lines(it, resolver=char_resolver, version=version))
        if merc_matches:
            result.append("=== Mercenary ===")
            for slot_str, m_it in merc_matches:
                slot_label = slot_str.rstrip(": ") or "Item"
                result.append(f"--- Mercenary: {slot_label} ---")
                result.extend(_format_item_lines(m_it, resolver=char_resolver, version=version))
        if corpse_matches:
            result.append("=== Corpse ===")
            for c_it in corpse_matches:
                result.append("--- Corpse Item ---")
                result.extend(_format_item_lines(c_it, resolver=char_resolver, version=version))
        if stored_matches:
            result.append("=== Inventory & Stash ===")
            for label, it in stored_matches:
                result.append(f"--- {label} ---")
                result.extend(_format_item_lines(it, resolver=char_resolver, version=version))

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
            items = [
                it
                for it in items
                if getattr(getattr(it, "item_info", None), "stash_stack_size", 0) > 0
            ]

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
                item_counts: dict[str, int] = {}
                item_order: list[str] = []
                for it in matching:
                    s = format_item_summary(
                        it, resolver=tab_resolver, version=version, include_properties=True
                    )
                    if s not in item_counts:
                        item_counts[s] = 0
                        item_order.append(s)
                    item_counts[s] += 1
                for s in item_order:
                    count = item_counts[s]
                    if count > 1:
                        plural = "Jewels" if s == "Jewel" else s
                        lines.append(f"  - {count}x {plural}")
                    else:
                        lines.append(f"  - {s}")
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


def format_item_find(
    item: Any,
    pattern: str,
    resolver: GameDataResolver,
    summary: bool = True,
) -> str | None:
    """Format single standalone item if it matches pattern."""
    if not item_matches_pattern(item, pattern, resolver=resolver):
        return None
    if summary:
        return f"=== Item Summary ===\n- {format_item_summary(item, resolver=resolver)}"
    return f"=== Item Info ===\n{format_item_info(item, resolver=resolver)}"
