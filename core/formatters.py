"""Full and summary text formatting for Diablo II saves, stashes, and items."""

import os
import datetime
from typing import Optional, List, Tuple

from core.d2s_struct import D2SStruct
from core.ibitstream import IBitStream
from core.property import (
    format_property,
    init_item_modifiers,
    get_skill_name,
)
from core.d2data import init_d2data, get_d2data, get_d2data_manager, GameDataResolver
from core.item import ITEM_FLAG_LABELS
from core.localized_data import init_localized_data, get_localized_data, set_language
from core.enums import StoredIn, ItemLocation, ItemQuality, EquipSlot
from core.stash import (
    SharedStash,
    STASH_TAB_TYPE_ADVANCED,
    STASH_TAB_TYPE_NORMAL,
    STASH_TAB_TYPE_CHRONICLE,
)
from core.constants import (
    TAB_TYPE_NAMES,
    GEM_TYPE_NAMES,
    GEM_CODE_MAP,
    RUNE_CODES_STRIPPED,
    GEM_CODES_STRIPPED,
    MATERIAL_CODES_STRIPPED,
    COMBINED_SLOT_ORDER_STRIPPED,
    CLASS_SKILL_BASES,
    DIFFICULTY_NAMES,
    WAYPOINTS_BY_ACT,
    QUESTS_BY_ACT,
)


def ensure_data_loaded(lang_key: Optional[str] = None, data_dir: Optional[str] = None, force: bool = False):
    """Ensure game and localization data are loaded into core managers."""
    mgr = get_d2data_manager()
    loc = get_localized_data()

    if not force and mgr is not None:
        if lang_key is not None and loc.current_lang != lang_key:
            set_language(lang_key)
        return

    actual_lang = lang_key if lang_key else (loc.current_lang or "enUS")

    if data_dir is None:
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        data_dir = os.path.join(script_dir, "data")

    if os.path.exists(data_dir):
        init_d2data(data_dir)

        local_data_dir = os.path.join(data_dir, "local")
        if os.path.exists(local_data_dir):
            init_localized_data(local_data_dir, lang_key=actual_lang)

        item_modifiers_file = os.path.join(data_dir, "local", "item-modifiers.json")
        if os.path.exists(item_modifiers_file):
            init_item_modifiers(item_modifiers_file, lang_key=actual_lang)


def get_char_type_name(char_type: int) -> str:
    flags = []
    if char_type & 0x40:
        flags.append("Ladder")
    if char_type & 0x20:
        flags.append("Expansion")
    if char_type & 0x8:
        flags.append("Died")
    if char_type & 0x4:
        flags.append("Hardcore")
    return " | ".join(flags) if flags else "Normal"


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
        dt = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
        return dt.strftime('%Y-%m-%d %H:%M:%S UTC')
    except (OSError, OverflowError, ValueError):
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


def get_item_display_name(item, version=0x63, resolver=None) -> str:
    type_name = item.sTypeName.decode('ascii', errors='replace').strip() if item.sTypeName else 'Unknown'
    if resolver is None:
        ensure_data_loaded()
        resolver = GameDataResolver(version)

    type_info = resolver.get_item(type_name)
    raw_name = type_info.name if type_info else type_name
    base_item_name = resolver.get_localized_item_name(type_name, fallback=raw_name)

    ext = getattr(getattr(item, 'item_info', None), 'ext_info', None)
    if ext:
        if ext.rune_id is not None:
            rw_name = resolver.get_localized_runeword_name(ext.rune_word_id())
            if rw_name:
                return f"{rw_name} ({base_item_name})"
        if ext.unique_id is not None:
            u_name = resolver.get_localized_unique_name(ext.unique_id)
            if u_name:
                return f"{u_name} ({base_item_name})"
        if ext.set_id is not None:
            s_name = resolver.get_localized_set_name(ext.set_id)
            if s_name:
                return f"{s_name} ({base_item_name})"
        quality = item.quality()
        if quality == ItemQuality.MAGIC:
            prefix_name = ""
            suffix_name = ""
            if ext.magic_prefix:
                prefix_name = resolver.get_localized_magic_prefix(ext.magic_prefix)
            if ext.magic_suffix:
                suffix_name = resolver.get_localized_magic_suffix(ext.magic_suffix)
            parts = [p for p in [prefix_name, base_item_name, suffix_name] if p]
            if parts:
                return " ".join(parts)
        elif quality == ItemQuality.RARE:
            rare_pfx = resolver.get_localized_quality_name("Rare")
            return f"{rare_pfx} {base_item_name}"
        elif quality == ItemQuality.CRAFTED:
            crafted_pfx = resolver.get_localized_quality_name("Crafted")
            return f"{crafted_pfx} {base_item_name}"
        elif quality == ItemQuality.HIGH:
            sup_pfx = resolver.get_localized_quality_name("Superior")
            return f"{sup_pfx} {base_item_name}"
        elif quality == ItemQuality.LOW:
            low_pfx = resolver.get_localized_quality_name("Low Quality")
            return f"{low_pfx} {base_item_name}"

    return base_item_name


def _format_parsed_properties(prop_list, version: int = 0x63, property_formatter=None) -> List[str]:
    """Format a property list into human-readable strings, falling back to raw IDs."""
    if not prop_list or not getattr(prop_list, 'mProperty', None):
        return []
    format_func = property_formatter or format_property
    result = []
    for prop_id, value, params in prop_list.get_parsed_properties(version):
        formatted = format_func(prop_id, params, version)
        if formatted:
            result.append(formatted)
        elif params:
            result.append(f"ID {prop_id}: raw={value}, params={params}")
        else:
            result.append(f"ID {prop_id}: {value}")
    return result


def format_item_summary(
    item,
    version=0x63,
    include_properties=True,
    resolver=None,
    property_formatter=None,
) -> str:
    if resolver is None:
        ensure_data_loaded()
        resolver = GameDataResolver(version)
    info = getattr(item, 'item_info', None)
    if info and info.gold:
        return f"Gold: {info.gold.quantity}"

    title = get_item_display_name(item, version=version, resolver=resolver)

    meta_tags = []
    tp = getattr(info, 'type_specific_info', None)
    if tp:
        if tp.defence is not None:
            meta_tags.append(f"Def: {tp.get_defence()}")
        sockets = tp.total_sockets()
        if sockets > 0:
            meta_tags.append(f"Sockets: {sockets}")

    if getattr(item, 'is_ethereal', False):
        meta_tags.append("Eth")
    if getattr(item, 'bDisabled', False):
        meta_tags.append("Broken")

    stack_size = getattr(info, 'stash_stack_size', 0)
    if stack_size > 1:
        meta_tags.append(f"x{stack_size}")
    elif tp and tp.quantity is not None and tp.quantity > 1:
        meta_tags.append(f"Qty: {tp.quantity}")

    if getattr(item, 'gem_items', None):
        socketed = []
        for gem in item.gem_items:
            g_name = get_item_display_name(gem, version=version, resolver=resolver)
            socketed.append(g_name)
        if socketed:
            meta_tags.append(f"Socketed: {'+'.join(socketed)}")

    props = []
    if include_properties and tp:
        props.extend(_format_parsed_properties(getattr(tp, 'property_list', None), version, property_formatter=property_formatter))
        props.extend(_format_parsed_properties(getattr(tp, 'runeword_property_list', None), version, property_formatter=property_formatter))

    meta_str = f" [{', '.join(meta_tags)}]" if meta_tags else ""
    props_str = f" ({', '.join(props)})" if props else ""
    return f"{title}{meta_str}{props_str}"


def _format_item_lines(item, indent="  ", version=None, resolver=None) -> List[str]:
    result = []
    type_name = item.sTypeName.decode('ascii', errors='replace') if item.sTypeName else 'Unknown'

    if version is None:
        version = item.dwVersion if item.dwVersion else 0x63
    if resolver is None:
        ensure_data_loaded()
        resolver = GameDataResolver(version)

    item_full_name = ""
    req_level = 0
    type_info = resolver.get_item(type_name.strip())
    if type_info:
        item_full_name = type_info.name
        req_level = type_info.levelreq

    if item_full_name:
        result.append(f"{indent}Type: {type_name} ({item_full_name})")
    else:
        result.append(f"{indent}Type: {type_name}")

    if req_level > 0:
        result.append(f"{indent}Required Level: {req_level}")

    location = ItemLocation(item.iLocation)
    if location == ItemLocation.EQUIPPED and item.iPosition in EquipSlot._value2member_map_:
        result.append(f"{indent}Location: {location}, Position: {item.iPosition} ({EquipSlot(item.iPosition)})")
    else:
        result.append(f"{indent}Location: {location}, Position: {item.iPosition}")
    storedin = StoredIn(item.iStoredIn)
    result.append(f"{indent}Column: {item.iColumn}, Row: {item.iRow}, StoredIn: {storedin}")
    quality = ItemQuality(item.quality())
    result.append(f"{indent}Quality: {quality}")

    flags = item.get_flag_names() if hasattr(item, 'get_flag_names') else [
        label for attr, label in ITEM_FLAG_LABELS if getattr(item, attr, False)
    ]
    if flags:
        result.append(f"{indent}Flags: {', '.join(flags)}")

    if item.item_info:
        info = item.item_info
        if info.ext_info:
            ext = info.ext_info
            if ext.guid:
                result.append(f"{indent}GUID: 0x{ext.guid:08X}")
            if ext.drop_level:
                result.append(f"{indent}Drop Level: {ext.drop_level}")
            if ext.magic_prefix:
                prefix_id = ext.magic_prefix
                prefix_info = resolver.get_magic_prefix(prefix_id)
                prefix_name = f" ({prefix_info.name})" if prefix_info else ""
                result.append(f"{indent}Prefix: {prefix_id}{prefix_name}")
            if ext.magic_suffix:
                suffix_id = ext.magic_suffix
                suffix_info = resolver.get_magic_suffix(suffix_id)
                suffix_name = f" ({suffix_info.name})" if suffix_info else ""
                result.append(f"{indent}Suffix: {suffix_id}{suffix_name}")
            if ext.set_id is not None:
                set_id = ext.set_id
                set_info = resolver.get_set_item(set_id)
                set_name = f" ({set_info.name})" if set_info else ""
                result.append(f"{indent}Set ID: {set_id}{set_name}")
            if ext.unique_id is not None:
                unique_id = ext.unique_id
                unique_info = resolver.get_unique_item(unique_id)
                unique_name = f" ({unique_info.index})" if unique_info else ""
                result.append(f"{indent}Unique ID: {unique_id}{unique_name}")
            if ext.rune_id is not None:
                runeword_id = ext.rune_word_id()
                runeword_info = resolver.get_runeword(runeword_id)
                runeword_name = f" ({runeword_info.name})" if runeword_info else ""
                result.append(f"{indent}Rune Word ID: {runeword_id}{runeword_name}")
                if item.gem_items:
                    rune_names = []
                    for gem in item.gem_items:
                        gem_type = gem.sTypeName.decode('ascii', errors='replace').strip() if gem.sTypeName else ''
                        if gem_type.startswith('r'):
                            try:
                                rune_num = int(gem_type[1:])
                                rune_info = resolver.get_item(gem_type)
                                rune_name = rune_info.name if rune_info else ""
                                rune_names.append(f"{rune_name}({rune_num})")
                            except ValueError:
                                pass
                    if rune_names:
                        result.append(f"{indent}Runes: {'+'.join(rune_names)}")
            if ext.rare_name:
                result.append(f"{indent}Rare Name: {ext.rare_name.name_1}-{ext.rare_name.name_2}")
            if ext.craft_name:
                result.append(f"{indent}Craft Name: {ext.craft_name.name_1}-{ext.craft_name.name_2}")

        if info.type_specific_info:
            tp = info.type_specific_info
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
            sockets = tp.total_sockets()
            if sockets > 0:
                result.append(f"{indent}Sockets: {sockets}")

            props = _format_parsed_properties(getattr(tp, 'property_list', None), version)
            if props:
                result.append(f"{indent}Properties:")
                for p in props:
                    result.append(f"{indent}  - {p}")

            rw_props = _format_parsed_properties(getattr(tp, 'runeword_property_list', None), version)
            if rw_props:
                result.append(f"{indent}Rune Word Properties:")
                for p in rw_props:
                    result.append(f"{indent}  - {p}")

            if getattr(tp, 'set_properties', None):
                for idx, set_prop_list in enumerate(tp.set_properties):
                    set_props = _format_parsed_properties(set_prop_list, version)
                    if set_props:
                        piece_count = idx + 2
                        result.append(f"{indent}Set Properties ({piece_count} Items):")
                        for p in set_props:
                            result.append(f"{indent}  - {p}")

        if getattr(info, 'iAdvancedStashStackSize', 0) > 0:
            result.append(f"{indent}Stack Size: {info.iAdvancedStashStackSize}")
        if info.gold:
            result.append(f"{indent}Gold: {info.gold.quantity}")

    if item.aGemItems:
        for j, gem in enumerate(item.aGemItems):
            result.append(f"{indent}Socketed Item [{j}]:")
            result.extend(_format_item_lines(gem, indent + "  ", version=version, resolver=resolver))

    return result


def format_item_info(item, indent="  ", version=None, resolver=None) -> str:
    return "\n".join(_format_item_lines(item, indent=indent, version=version, resolver=resolver))


def _format_waypoints_lines(char_data: D2SStruct) -> List[str]:
    ensure_data_loaded()
    loc = get_localized_data()
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
                    b = wp_data.Waypoints[global_idx // 8]
                    if b & (1 << (global_idx % 8)):
                        total_unlocked += 1
                        unlocked_in_act += 1
                    else:
                        loc_wp = loc.get_level_name(name) if loc else name
                        missing.append(loc_wp)
                    global_idx += 1
                act_stats.append((act_name, len(wp_names), unlocked_in_act, missing))

            # Check if this difficulty has been started (has waypoints beyond starter town or has quest activity)
            has_wp_progress = (wp_data.Waypoints[0] & ~1) != 0 or any(b != 0 for b in wp_data.Waypoints[1:])
            has_quest_progress = False
            if char_data.quests.magic == 0x216F6F57 and diff_idx < len(char_data.quests.qi_data):
                qd = char_data.quests.qi_data[diff_idx]
                has_quest_progress = any(w != 0 for words in [qd.wActI, qd.wActII, qd.wActIII, qd.wActIV, qd.wActV] for w in words)

            if not has_wp_progress and not has_quest_progress:
                result.append(f"{diff_name}: Not started")
                continue

            total_missing = 39 - total_unlocked
            if total_unlocked == 39:
                result.append(f"{diff_name} (39/39 unlocked): All unlocked")
            else:
                result.append(f"{diff_name} ({total_unlocked}/39 unlocked, {total_missing} missing):")
                for act_name, total_act, unlocked_act, missing in act_stats:
                    if unlocked_act == total_act:
                        result.append(f"  {act_name} ({total_act}/{total_act}): All unlocked")
                    elif unlocked_act == 0:
                        result.append(f"  {act_name} (0/{total_act}): None unlocked")
                    else:
                        result.append(f"  {act_name} ({unlocked_act}/{total_act}): Missing {', '.join(missing)}")
    return result


def format_waypoints_info(char_data: D2SStruct) -> str:
    return "\n".join(_format_waypoints_lines(char_data))


def _format_quests_lines(char_data: D2SStruct) -> List[str]:
    ensure_data_loaded()
    loc = get_localized_data()
    result = []
    result.append("=== Quests ===")
    if char_data.quests.magic == 0x216F6F57:
        for diff_idx, diff_name in enumerate(DIFFICULTY_NAMES):
            if diff_idx >= len(char_data.quests.qi_data):
                break
            qd = char_data.quests.qi_data[diff_idx]
            act_words = [qd.wActI, qd.wActII, qd.wActIII, qd.wActIV, qd.wActV]
            has_quest_progress = any(w != 0 for words in act_words for w in words)
            if not has_quest_progress and qd.bResetStats == 0:
                result.append(f"{diff_name}: Not started")
                continue

            reset_status = "Available" if qd.bResetStats == 2 else ("Used" if qd.bResetStats == 1 else "Locked")
            total_completed = sum(1 for words in act_words for w in words if (w & 1) or (w & 2))
            rewards_unclaimed = sum(1 for words in act_words for w in words if (w & 2) and not (w & 1))
            reward_str = f", {rewards_unclaimed} reward{'s' if rewards_unclaimed > 1 else ''} unclaimed" if rewards_unclaimed else ""

            result.append(f"{diff_name} ({total_completed}/27 completed{reward_str}) — Akara Reset: {reset_status}")
            for (act_name, quest_defs), words in zip(QUESTS_BY_ACT, act_words):
                words_ordered = [words[idx] for _, idx in quest_defs]
                if all(w & 1 for w in words_ordered):
                    result.append(f"  {act_name}: {' '.join('[x]' for _ in quest_defs)}")
                elif all(not (w & 1) and not (w & 2) for w in words_ordered):
                    result.append(f"  {act_name}: {' '.join('[ ]' for _ in quest_defs)}")
                else:
                    parts = []
                    for (name, idx), w in zip(quest_defs, words_ordered):
                        loc_qname = loc.get_quest_name(name) if loc else name
                        if w & 1:
                            parts.append("[x]")
                        elif w & 2:
                            parts.append(f"[!] {loc_qname} (reward unclaimed)")
                        else:
                            parts.append(f"[ ] {loc_qname}")
                    result.append(f"  {act_name}: {' '.join(parts)}")
    return result


def format_quests_info(char_data: D2SStruct) -> str:
    return "\n".join(_format_quests_lines(char_data))


def _get_character_skills(char_data: D2SStruct, resolver: Optional[GameDataResolver] = None) -> List[Tuple[int, str, int]]:
    """Return invested skills as a list of (skill_index, skill_name, level) tuples."""
    if not getattr(char_data, 'Skills', None) or char_data.Skills.wMagic != 0x6669:
        return []
    if resolver is None:
        ensure_data_loaded()
        version = char_data.dwVersion if char_data.dwVersion else 0x63
        resolver = GameDataResolver(version)
    skills = []
    for i, level in enumerate(char_data.Skills.bSkillLevel):
        if level > 0:
            skill_name = ""
            if 0 <= char_data.charClass < len(CLASS_SKILL_BASES):
                skill_id = CLASS_SKILL_BASES[char_data.charClass] + i
                skill_name = resolver.get_skill_name(skill_id)
            skills.append((i, skill_name, level))
    return skills


def format_char_info(char_data: D2SStruct, resolver=None):
    ensure_data_loaded()
    result = []
    result.append("=== Diablo II Character Info ===")
    char_name = char_data.get_char_name()
    result.append(f"Name: {char_name}")
    if resolver is None:
        resolver = GameDataResolver(char_data.dwVersion)
    result.append(f"Class: {resolver.get_localized_class_name(char_data.charClass)}")
    result.append(f"Level: {char_data.charLevel}")
    result.append(f"Version: 0x{char_data.dwVersion:X}")
    result.append(f"Hardcore: {'Yes' if char_data.is_hardcore() else 'No'}")
    result.append(f"Ladder: {'Yes' if char_data.is_ladder() else 'No'}")
    result.append(f"Expansion: {'Yes' if char_data.is_expansion() else 'No'}")
    result.append(f"Died before: {'Yes' if char_data.is_died_before() else 'No'}")

    char_type_name = get_char_type_name(char_data.charFlags)
    result.append(f"Character Flags: 0x{char_data.charFlags:X} ({char_type_name})")

    char_title = getattr(char_data, 'charTitle', 0)
    char_title_name = get_char_title_name(char_title, char_data.charClass)
    result.append(f"Character Title: 0x{char_title:X} ({char_title_name})")

    result.append(f"Weapon Set: {'I' if char_data.dwWeaponSet == 0 else 'II'}")

    create_time = getattr(char_data, 'createTime', 0)
    last_save_time = getattr(char_data, 'lastSaveTime', 0) or getattr(char_data, 'dwTime', 0)
    play_time = getattr(char_data, 'playTime', 0)

    result.append(f"Create Time: {format_timestamp(create_time)}")
    result.append(f"Last Save Time: {format_timestamp(last_save_time)}")
    result.append(f"Play Time: {format_duration(play_time)}")

    if char_data.dwVersion >= 0x69:
        result.append(f"Game Version: {getattr(char_data, 'gameVersion', 0)}")
    else:
        result.append(f"NumStats/NumSkills: 0x{getattr(char_data, 'numStatsNumSkills', 0):04X}")
        result.append(f"Merc Dead: {'Yes' if getattr(char_data, 'bMercDead', 0) else 'No'}")
        result.append(f"Merc Flags: 0x{getattr(char_data, 'mercFlagsLow', 0):04X}{getattr(char_data, 'mercFlagsHigh', 0):02X}")

    result.append("")
    result.append("=== Player Stats ===")
    stats = char_data.PlayerStats
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
    resolver = GameDataResolver(char_data.dwVersion)
    skills = _get_character_skills(char_data, resolver)
    if skills:
        result.append("Skill levels:")
        for i, skill_name, level in skills:
            if skill_name:
                result.append(f"Skill {i} ({skill_name}): {level}")
            else:
                result.append(f"Skill {i}: {level}")
    result.append("")
    result.extend(_format_waypoints_lines(char_data))
    result.append("")
    result.extend(_format_quests_lines(char_data))
    result.append("")
    result.append("=== Items ===")
    item_list = getattr(char_data, 'item_list', None) or getattr(char_data, 'ItemList', None)
    if item_list and (getattr(item_list, 'magic', getattr(item_list, 'wMajic', None)) == 0x4D4A):
        items = getattr(item_list, 'items', getattr(item_list, 'vItems', []))
        result.append(f"Total items: {len(items)}")
        for i, item in enumerate(items):
            result.append(f"--- Item {i} ---")
            result.extend(_format_item_lines(item, version=char_data.version, resolver=resolver))
    result.append("")
    result.append("=== Corpse ===")
    if char_data.stCorpse.has_corpse():
        result.append("Has corpse")
        if char_data.stCorpse.pCorpseData and char_data.stCorpse.pCorpseData.stItems:
            result.append(f"Corpse items: {char_data.stCorpse.pCorpseData.stItems.nItems}")
    else:
        result.append("No corpse")
    result.append("")
    result.append("=== Mercenary ===")
    if char_data.is_expansion():
        if char_data.has_mercenary():
            result.append(f"Has mercenary (Name: {char_data.merc_name_id}, Type: {char_data.merc_type_id})")
            if char_data.dwVersion >= 0x69:
                merc_seed = getattr(char_data, 'mercSeed', 0)
                merc_flags = getattr(char_data, 'mercFlags', 0)
                result.append(f"Mercenary Seed: 0x{merc_seed:08X}")
                result.append(f"Mercenary Exp: {char_data.merc_experience}")
                result.append(f"Mercenary Flags: 0x{merc_flags:08X}")
            else:
                result.append(f"Mercenary Exp: {char_data.merc_experience}")
                result.append(f"Merc Dead: {'Yes' if char_data.merc_is_dead else 'No'}")
            if char_data.stMercenary.stItems:
                result.append(f"Mercenary items: {char_data.stMercenary.stItems.nItems}")
                for i, item in enumerate(char_data.stMercenary.stItems.vItems):
                    result.append(f"--- Mercenary Item {i} ---")
                    result.extend(_format_item_lines(item, version=char_data.dwVersion, resolver=resolver))
        else:
            result.append("No mercenary")
    else:
        result.append("Not expansion character")
    result.append("")
    result.append("=== Golem ===")
    if char_data.is_expansion():
        if char_data.stGolem.bHasGolem:
            result.append("Has golem")
        else:
            result.append("No golem")
    else:
        result.append("Not expansion character")
    result.append("")
    result.append("=== Demon ===")
    if char_data.stDemon.hasDemon:
        result.append(f"Has demon (Magic: 0x{char_data.stDemon.wMagic:X})")
    else:
        result.append("No demon")
    return '\n'.join(result)


def format_char_summary(char_data: D2SStruct, resolver=None) -> str:
    ensure_data_loaded()
    result = []
    result.append("=== Diablo II Character Summary ===")
    char_name = char_data.get_char_name()
    version = char_data.dwVersion if char_data.dwVersion else 0x63
    if resolver is None:
        resolver = GameDataResolver(version)
    char_class = resolver.get_localized_class_name(char_data.charClass)
    flags_str = get_char_type_name(char_data.charFlags)
    char_title = getattr(char_data, 'charTitle', 0)
    title_str = get_char_title_name(char_title, char_data.charClass)
    weapon_set = 'I' if char_data.dwWeaponSet == 0 else 'II'

    result.append(f"Name: {char_name} | Class: {char_class} | Level: {char_data.charLevel} | Title: {title_str}")
    result.append(f"Status: {flags_str} | Weapon Set: {weapon_set}")

    last_save_time = getattr(char_data, 'lastSaveTime', 0) or getattr(char_data, 'dwTime', 0)
    play_time = getattr(char_data, 'playTime', 0)
    time_parts = []
    if last_save_time:
        time_parts.append(f"Last Saved: {format_timestamp(last_save_time)}")
    if play_time:
        time_parts.append(f"Play Time: {format_duration(play_time)}")
    if time_parts:
        result.append(" | ".join(time_parts))

    stats = char_data.PlayerStats
    if stats.is_valid:
        result.append(f"Attributes: Str: {stats.strength}, Dex: {stats.dexterity}, Vit: {stats.vitality}, Ene: {stats.energy}")
        result.append(f"Life: {stats.current_life}/{stats.max_life} | Mana: {stats.current_mana}/{stats.max_mana} | Gold: {stats.gold} (Person), {stats.gold_stash} (Stash)")
        if stats.stat_points_remaining > 0 or stats.skill_points_remaining > 0:
            result.append(f"Remaining Points: {stats.stat_points_remaining} Stat, {stats.skill_points_remaining} Skill")

    result.append("")
    result.append("=== Skills ===")
    skills = _get_character_skills(char_data, resolver)
    if skills:
        active_skills = [
            f"{skill_name if skill_name else f'Skill {i}'}: {level}"
            for i, skill_name, level in skills
        ]
        result.append(", ".join(active_skills))
    else:
        result.append("None")

    result.append("")
    result.extend(_format_waypoints_lines(char_data))
    result.append("")
    result.extend(_format_quests_lines(char_data))
    result.append("")

    result.append("=== Equipped Gear ===")
    equipped_items = {}
    inventory_items = []
    stash_items = []
    cube_items = []
    belt_items = []
    cursor_items = []

    item_list = getattr(char_data, 'item_list', None) or getattr(char_data, 'ItemList', None)
    if item_list and (getattr(item_list, 'magic', getattr(item_list, 'wMajic', None)) == 0x4D4A):
        items = getattr(item_list, 'items', getattr(item_list, 'vItems', []))
        for item in items:
            loc = ItemLocation(item.iLocation)
            if loc == ItemLocation.EQUIPPED:
                equipped_items[item.iPosition] = item
            elif loc == ItemLocation.BELT:
                belt_items.append(item)
            elif loc == ItemLocation.STORED:
                if item.iStoredIn == StoredIn.INVENTORY:
                    inventory_items.append(item)
                elif item.iStoredIn == StoredIn.STASH:
                    stash_items.append(item)
                elif item.iStoredIn == StoredIn.CUBE:
                    cube_items.append(item)
                else:
                    inventory_items.append(item)
            elif loc == ItemLocation.CURSOR:
                cursor_items.append(item)

    has_equipped = False
    for slot in EquipSlot:
        if slot.value in equipped_items:
            has_equipped = True
            it = equipped_items[slot.value]
            result.append(f"- {slot.display_name}: {format_item_summary(it, version, resolver=resolver)}")
    if not has_equipped:
        result.append("None")

    result.append("")
    result.append("=== Mercenary ===")
    if char_data.is_expansion() and char_data.has_mercenary():
        dead_str = " (Dead)" if char_data.merc_is_dead else ""
        result.append(f"Mercenary: Name Index {char_data.merc_name_id}, Type {char_data.merc_type_id}{dead_str}")
        if char_data.stMercenary.stItems and char_data.stMercenary.stItems.vItems:
            result.append("Equipped:")
            for m_item in char_data.stMercenary.stItems.vItems:
                loc = ItemLocation(m_item.iLocation)
                slot_str = ""
                if loc == ItemLocation.EQUIPPED and m_item.iPosition in EquipSlot._value2member_map_:
                    slot_str = f"{EquipSlot(m_item.iPosition).display_name}: "
                result.append(f"  - {slot_str}{format_item_summary(m_item, version, resolver=resolver)}")
        else:
            result.append("Equipped: None")
    else:
        result.append("No mercenary")

    result.append("")
    result.append("=== Inventory & Stash ===")
    stored_lines = []
    for it in inventory_items:
        stored_lines.append(f"- [Inventory] {format_item_summary(it, version, resolver=resolver)}")
    for it in stash_items:
        stored_lines.append(f"- [Stash] {format_item_summary(it, version, resolver=resolver)}")
    for it in cube_items:
        stored_lines.append(f"- [Cube] {format_item_summary(it, version, resolver=resolver)}")

    if belt_items:
        belt_counts = {}
        for it in belt_items:
            summary = format_item_summary(it, version, resolver=resolver)
            belt_counts[summary] = belt_counts.get(summary, 0) + 1
        for summary, count in belt_counts.items():
            count_str = f" (x{count})" if count > 1 else ""
            stored_lines.append(f"- [Belt] {summary}{count_str}")

    for it in cursor_items:
        stored_lines.append(f"- [Cursor] {format_item_summary(it, version, resolver=resolver)}")

    if stored_lines:
        result.extend(stored_lines)
    else:
        result.append("No stored items")

    return '\n'.join(result).rstrip()


def format_stash_info(stash: SharedStash, resolver=None) -> str:
    ensure_data_loaded()
    result = []
    result.append("=== Diablo II Shared Stash ===")
    result.append(f"Total Tabs: {stash.get_tab_count()}")
    result.append("")

    for tab_idx, tab in enumerate(stash.tabs):
        tab_type_name = TAB_TYPE_NAMES.get(tab.TabType, f"Unknown({tab.TabType})")
        result.append(f"=== Tab {tab_idx + 1} ({tab_type_name}) ===")
        if tab.Gold:
            result.append(f"Gold: {tab.Gold}")

        items = tab.Items.vItems if tab.Items else []
        version = tab.ItemFormat if tab.ItemFormat else 0x63
        tab_resolver = resolver if resolver is not None else GameDataResolver(version)
        if tab.TabType == STASH_TAB_TYPE_ADVANCED:
            active_items = [
                item for item in items
                if getattr(getattr(item, 'item_info', None), 'stash_stack_size', 0) > 0
            ]
            result.append(f"Total items: {len(active_items)}")
            for item_idx, item in enumerate(active_items):
                result.append(f"--- Item {item_idx} ---")
                result.extend(_format_item_lines(item, version=version, resolver=tab_resolver))
        else:
            result.append(f"Total items: {len(items)}")
            for item_idx, item in enumerate(items):
                result.append(f"--- Item {item_idx} ---")
                result.extend(_format_item_lines(item, version=version, resolver=tab_resolver))
        result.append("")

    return '\n'.join(result).rstrip()


def format_stash_summary(stash: SharedStash, resolver=None) -> str:
    ensure_data_loaded()
    result = []
    result.append("=== Diablo II Shared Stash Summary ===")
    tab_count = stash.get_tab_count()
    result.append(f"Total Tabs: {tab_count}")

    tab_summaries = []
    for tab_idx, tab in enumerate(stash.tabs):
        tname = TAB_TYPE_NAMES.get(tab.TabType, f"Unknown({tab.TabType})")
        tab_summaries.append(f"Tab {tab_idx + 1}: {tname}")
    result.append(f"Tabs: {', '.join(tab_summaries)}")
    result.append("")

    slot_order_map = {code: idx for idx, code in enumerate(COMBINED_SLOT_ORDER_STRIPPED)}

    for tab_idx, tab in enumerate(stash.tabs):
        tname = TAB_TYPE_NAMES.get(tab.TabType, f"Unknown({tab.TabType})")
        result.append(f"=== Tab {tab_idx + 1} ({tname}) ===")
        if tab.Gold:
            result.append(f"Gold: {tab.Gold}")

        items = tab.Items.vItems if tab.Items else []
        version = tab.ItemFormat if tab.ItemFormat else 0x63
        cur_resolver = resolver if resolver is not None else GameDataResolver(version)

        if tab.TabType == STASH_TAB_TYPE_ADVANCED:
            active_items = [
                it for it in items
                if getattr(getattr(it, 'item_info', None), 'stash_stack_size', 0) > 0
            ]
            if not active_items:
                result.append("  (empty)")
            else:
                runes_list = []
                materials_list = []
                other_list = []
                gem_stats = {g: {'p': 0, 'f': 0, 'o': 0} for g in GEM_TYPE_NAMES}

                sorted_active = sorted(
                    active_items,
                    key=lambda it: slot_order_map.get(getattr(it, 'sTypeName', b'').strip(), 9999)
                )

                for it in sorted_active:
                    code_b = getattr(it, 'sTypeName', b'').strip()
                    code_str = code_b.decode('ascii', errors='replace')
                    stack_size = getattr(getattr(it, 'item_info', None), 'stash_stack_size', 0)

                    if code_b in GEM_CODE_MAP:
                        g_type, tier = GEM_CODE_MAP[code_b]
                        gem_stats[g_type][tier] += stack_size
                    elif code_b in RUNE_CODES_STRIPPED:
                        display_name = cur_resolver.get_localized_rune_short_name(code_str)
                        runes_list.append(f"{display_name}: {stack_size}")
                    elif code_b in MATERIAL_CODES_STRIPPED:
                        type_info = cur_resolver.get_item(code_str)
                        raw_name = type_info.name if type_info else code_str
                        item_name = cur_resolver.get_localized_item_name(code_str, fallback=raw_name)
                        materials_list.append(f"{item_name}: {stack_size}")
                    else:
                        type_info = cur_resolver.get_item(code_str)
                        raw_name = type_info.name if type_info else code_str
                        item_name = cur_resolver.get_localized_item_name(code_str, fallback=raw_name)
                        other_list.append(f"{item_name}: {stack_size}")

                gems_list = []
                for g_type in GEM_TYPE_NAMES:
                    p = gem_stats[g_type]['p']
                    f = gem_stats[g_type]['f']
                    o = gem_stats[g_type]['o']
                    if p > 0 or f > 0 or o > 0:
                        loc_g_type = cur_resolver.get_localized_gem_type_name(g_type)
                        gems_list.append(f"{loc_g_type}: p {p}, f {f}, o {o}")

                if runes_list:
                    result.append(f"  Runes: {', '.join(runes_list)}")
                if gems_list:
                    result.append(f"  Gems (p=perfect, f=flawless, o=other): {', '.join(gems_list)}")
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
                    summary = format_item_summary(it, version=version, include_properties=False, resolver=cur_resolver)
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

    return '\n'.join(result).rstrip()
