"""Text formatting and pattern matching for Diablo II items and item properties."""

from collections.abc import Callable
from typing import NamedTuple

from d2savior.core.enums import EquipSlot, ItemLocation, ItemQuality, StoredIn
from d2savior.core.item import D2Item
from d2savior.core.property_list import PropertyList
from d2savior.core.resolver import GameDataResolver
from d2savior.core.stats import (
    SummaryPropKey,
    aggregate_summary_properties,
    calculate_effective_defence,
    collect_item_properties,
    extract_grouped_damage_values,
    normalize_damage_props,
)

type FormattedLines = list[str]


class _ElementalTemplate(NamedTuple):
    single_key: str
    single_fallback: str
    range_key: str
    range_fallback: str


_ELEMENTAL_TEMPLATES: frozendict[int, _ElementalTemplate] = frozendict(
    {
        48: _ElementalTemplate(
            "strModFireDamage",
            "%+d fire damage",
            "strModFireDamageRange",
            "Adds %d-%d fire damage",
        ),
        50: _ElementalTemplate(
            "strModLightningDamage",
            "%+d lightning damage",
            "strModLightningDamageRange",
            "Adds %d-%d lightning damage",
        ),
        52: _ElementalTemplate(
            "strModMagicDamage",
            "%+d magic damage",
            "strModMagicDamageRange",
            "Adds %d-%d magic damage",
        ),
        54: _ElementalTemplate(
            "strModColdDamage",
            "%+d cold damage",
            "strModColdDamageRange",
            "Adds %d-%d cold damage",
        ),
        57: _ElementalTemplate(
            "strModPoisonDamage",
            "%+d poison damage over %d seconds",
            "strModPoisonDamageRange",
            "Adds %d-%d poison damage over %d seconds",
        ),
    }
)


def get_item_display_name(item: D2Item, resolver: GameDataResolver, version: int = 0x63) -> str:
    type_name = item.code_str or "Unknown"

    raw_name = type_info.name if (type_info := resolver.get_item(type_name)) else type_name
    base_item_name = resolver.get_localized_item_name(type_name, fallback=raw_name)

    if ext := item.ext_info:
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
    item: D2Item, pattern: str, resolver: GameDataResolver, version: int = 0x63
) -> bool:
    """Return True if the item or any of its socketed items match the search pattern."""
    norm = pattern.strip().lower()
    if not norm:
        return False

    title = get_item_display_name(item, resolver=resolver, version=version)
    if norm in title.lower():
        return True

    for gem in item.gem_items:
        gem_title = get_item_display_name(gem, resolver=resolver, version=version)
        if norm in gem_title.lower():
            return True

    return False


def _format_modifier_template(
    resolver: GameDataResolver,
    key: str,
    fallback: str,
    *values: int,
    signed_first: bool = False,
) -> str:
    """Resolve and format a localized item-modifier template with integer arguments."""
    tpl = resolver.get_item_modifier(key)
    if not tpl or tpl == key:
        tpl = fallback
    result = tpl
    for i, val in enumerate(values):
        if i == 0 and signed_first and "%+d" in result:
            result = result.replace("%+d", f"{val:+d}", 1)
        elif "%d" in result:
            result = result.replace("%d", str(val), 1)
    return result.replace("%%", "%")


def _extract_grouped_replacements(
    parsed_props: list[tuple[int, int, list[int]]],
    resolver: GameDataResolver,
) -> dict[int, tuple[int, str]]:
    """Map grouped elemental and enhanced-damage stat IDs to (group_id, combined_text)."""
    grouped = extract_grouped_damage_values(parsed_props)
    replacements: dict[int, tuple[int, str]] = {}

    for entry in grouped.elemental:
        tpl = _ELEMENTAL_TEMPLATES[entry.min_id]
        extra = (entry.seconds,) if entry.seconds is not None else ()
        if entry.d_min == entry.d_max:
            formatted = _format_modifier_template(
                resolver,
                tpl.single_key,
                tpl.single_fallback,
                entry.d_min,
                *extra,
                signed_first=True,
            )
        else:
            formatted = _format_modifier_template(
                resolver,
                tpl.range_key,
                tpl.range_fallback,
                entry.d_min,
                entry.d_max,
                *extra,
            )
        for sid in entry.present_ids:
            replacements[sid] = (entry.min_id, formatted)

    if grouped.equal_enhanced_damage is not None:
        ed_str = _format_modifier_template(
            resolver,
            "strModEnhancedDamage",
            "%+d%% Enhanced Damage",
            grouped.equal_enhanced_damage,
            signed_first=True,
        )
        for sid in grouped.ed_present_ids:
            replacements[sid] = (17, ed_str)

    return replacements


def _format_property_entries(
    parsed_props: list[tuple[int, int, list[int]]],
    resolver: GameDataResolver,
    version: int = 0x63,
    property_formatter: Callable[..., str | None] | None = None,
) -> FormattedLines:
    """Format parsed property tuples into strings, grouping paired elemental/ED stats."""
    format_func = property_formatter or resolver.format_property
    elem_replacements = (
        _extract_grouped_replacements(parsed_props, resolver) if property_formatter is None else {}
    )
    emitted_elem_groups: set[int] = set()
    result = []

    for prop_id, value, params in parsed_props:
        if prop_id in elem_replacements:
            group_id, formatted_elem = elem_replacements[prop_id]
            if group_id not in emitted_elem_groups:
                emitted_elem_groups.add(group_id)
                result.append(formatted_elem)
            continue
        formatted = format_func(prop_id, params, version)
        if formatted:
            result.append(formatted)
        elif params:
            result.append(f"ID {prop_id}: raw={value}, params={params}")
        else:
            result.append(f"ID {prop_id}: {value}")
    return result


def _format_parsed_properties(
    prop_list: PropertyList | None,
    resolver: GameDataResolver,
    version: int = 0x63,
    property_formatter: Callable[..., str | None] | None = None,
) -> FormattedLines:
    """Format a property list into human-readable strings, falling back to raw IDs."""
    if not prop_list or not prop_list.properties:
        return []
    parsed_props = prop_list.get_parsed_properties(version, data=resolver.data)
    return _format_property_entries(
        parsed_props,
        resolver=resolver,
        version=version,
        property_formatter=property_formatter,
    )


def _format_summary_properties(
    parsed_props: list[tuple[int, int, list[int]]],
    resolver: GameDataResolver,
    version: int = 0x63,
    property_formatter: Callable[..., str | None] | None = None,
) -> FormattedLines:
    """Format summary properties with numeric stat stacking and resistance/damage collapsing."""
    if not parsed_props:
        return []

    format_func = property_formatter or resolver.format_property
    agg = aggregate_summary_properties(parsed_props, resolver)
    elem_replacements = (
        _extract_grouped_replacements(parsed_props, resolver) if property_formatter is None else {}
    )

    result: list[str] = []
    all_res_inserted = False
    emitted_dmg_pairs: set[SummaryPropKey] = set()
    emitted_elem_groups: set[int] = set()

    for key in agg.ordered_keys:
        if key not in agg.aggregated:
            continue

        prop_id = agg.prop_id_map[key]
        params = agg.aggregated[key]

        if prop_id in elem_replacements:
            group_id, formatted_elem = elem_replacements[prop_id]
            if group_id not in emitted_elem_groups:
                emitted_elem_groups.add(group_id)
                result.append(formatted_elem)
            continue

        if key in agg.dmg_pair_map:
            if key not in emitted_dmg_pairs:
                partner_key, d_min, d_max = agg.dmg_pair_map[key]
                emitted_dmg_pairs.add(key)
                emitted_dmg_pairs.add(partner_key)
                result.append(
                    _format_modifier_template(
                        resolver, "strModMinDamageRange", "Adds %d-%d damage", d_min, d_max
                    )
                )
            continue

        if agg.min_all_res > 0 and key in agg.res_keys:
            if not all_res_inserted:
                all_res_inserted = True
                tpl = resolver.get_item_modifier("strModAllResistances") or "All Resistances %+d"
                all_res_str = tpl.replace("%+d", f"{agg.min_all_res:+d}").replace(
                    "%d", str(agg.min_all_res)
                )
                result.append(all_res_str)

            val = params[0]
            if val > agg.min_all_res:
                excess = val - agg.min_all_res
                formatted_excess = format_func(prop_id, [excess], version)
                if formatted_excess:
                    result.append(formatted_excess)
            continue

        formatted = format_func(prop_id, params, version)
        if formatted:
            result.append(formatted)
        elif len(params) > 1:
            raw_val = agg.raw_val_map.get(key, params[0])
            result.append(f"ID {prop_id}: raw={raw_val}, params={params}")
        elif params:
            result.append(f"ID {prop_id}: {params[0]}")
        else:
            raw_val = agg.raw_val_map.get(key, 0)
            result.append(f"ID {prop_id}: {raw_val}")

    return result


def format_item_summary(
    item: D2Item,
    resolver: GameDataResolver,
    version: int = 0x63,
    include_properties: bool = True,
    property_formatter: Callable[..., str | None] | None = None,
) -> str:
    info = item.item_info
    if info and info.gold:
        return f"Gold: {info.gold.quantity}"

    title = get_item_display_name(item, resolver=resolver, version=version)

    meta_tags = []
    tp = item.type_specific_info
    need_parsed = tp is not None and (include_properties or tp.defence is not None)
    all_parsed = (
        collect_item_properties(item, resolver, version, normalize_source=normalize_damage_props)
        if need_parsed
        else []
    )

    if tp:
        if tp.defence is not None:
            effective_def = calculate_effective_defence(tp.get_defence(), all_parsed)
            meta_tags.append(f"Def: {effective_def}")
        sockets = tp.total_sockets()
        if sockets > 0:
            meta_tags.append(f"Sockets: {sockets}")

    if item.is_ethereal:
        meta_tags.append("Eth")
    if item.is_disabled:
        meta_tags.append("Broken")

    stack_size = item.stash_stack_size
    if stack_size > 1:
        meta_tags.append(f"x{stack_size}")
    elif tp and tp.quantity is not None and tp.quantity > 1:
        meta_tags.append(f"Qty: {tp.quantity}")

    if item.gem_items:
        socketed = []
        for gem in item.gem_items:
            g_name = get_item_display_name(gem, version=version, resolver=resolver)
            socketed.append(g_name)
        if socketed:
            meta_tags.append(f"Socketed: {'+'.join(socketed)}")

    props = []
    if include_properties and tp:
        props = _format_summary_properties(
            all_parsed,
            resolver=resolver,
            version=version,
            property_formatter=property_formatter,
        )

    return f"{title}{f' [{", ".join(meta_tags)}]' if meta_tags else ''}{f' ({", ".join(props)})' if props else ''}"


def _format_item_lines(
    item: D2Item,
    resolver: GameDataResolver,
    indent: str = "  ",
    version: int | None = None,
    parent_item: D2Item | None = None,
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

    flags = item.get_flag_names()
    if flags:
        result.append(f"{indent}Flags: {', '.join(flags)}")

    tp = None
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
                        gem_type = gem.code_str
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
                base_def = tp.get_defence()
                eff_def = calculate_effective_defence(
                    base_def,
                    collect_item_properties(
                        item, item_resolver, version, normalize_source=normalize_damage_props
                    ),
                )
                def_suffix = f" (effective: {eff_def})" if eff_def != base_def else ""
                result.append(f"{indent}Defence: {base_def}{def_suffix}")
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
                tp.property_list, resolver=item_resolver, version=version
            ):
                result.append(f"{indent}Properties:")
                for p in props:
                    result.append(f"{indent}  - {p}")

            if rw_props := _format_parsed_properties(
                tp.runeword_property_list, resolver=item_resolver, version=version
            ):
                result.append(f"{indent}Rune Word Properties:")
                for p in rw_props:
                    result.append(f"{indent}  - {p}")

            if tp.set_properties:
                for idx, set_prop_list in enumerate(tp.set_properties):
                    if set_props := _format_parsed_properties(
                        set_prop_list, resolver=item_resolver, version=version
                    ):
                        piece_count = idx + 2
                        result.append(f"{indent}Set Properties ({piece_count} Items):")
                        for p in set_props:
                            result.append(f"{indent}  - {p}")

        if info.stash_stack_size > 0:
            result.append(f"{indent}Stack Size: {info.stash_stack_size}")
        if info.gold:
            result.append(f"{indent}Gold: {info.gold.quantity}")

    if parent_item and not (tp and tp.property_list):
        socket_props = item_resolver.get_socket_properties(parent_item, item)
        if socket_props:
            result.append(f"{indent}Properties:")
            for formatted in _format_property_entries(
                socket_props, resolver=item_resolver, version=version
            ):
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
    item: D2Item,
    resolver: GameDataResolver,
    indent: str = "  ",
    version: int | None = None,
) -> str:
    return "\n".join(_format_item_lines(item, resolver=resolver, indent=indent, version=version))


def format_item_find(
    item: D2Item,
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
