#!/usr/bin/env python3
import sys
import os
import argparse
import datetime
from core.d2s_struct import D2SStruct
from core.ibitstream import IBitStream
from core.property import format_property, init_item_modifiers, get_skill_name
from core.d2data import init_d2data, get_d2data, get_d2data_manager
from core.localized_data import init_localized_data
from core.enums import StoredIn, ItemLocation, ItemQuality, EquipSlot
from core.stash import (
    SharedStash,
    STASH_TAB_TYPE_ADVANCED,
    STASH_TAB_TYPE_NORMAL,
    STASH_TAB_TYPE_CHRONICLE,
    COMBINED_SLOT_ORDER,
    RUNE_CODES,
    GEM_CODES,
    MATERIAL_CODES,
)

GEM_TYPE_NAMES = ['Amethyst', 'Topaz', 'Sapphire', 'Emerald', 'Ruby', 'Diamond', 'Skull']

GEM_CODE_MAP = {
    # Amethyst
    b'gcv': ('Amethyst', False),
    b'gfv': ('Amethyst', False),
    b'gsv': ('Amethyst', False),
    b'gzv': ('Amethyst', False),
    b'gpv': ('Amethyst', True),
    # Topaz
    b'gcy': ('Topaz', False),
    b'gfy': ('Topaz', False),
    b'gsy': ('Topaz', False),
    b'gly': ('Topaz', False),
    b'gpy': ('Topaz', True),
    # Sapphire
    b'gcb': ('Sapphire', False),
    b'gfb': ('Sapphire', False),
    b'gsb': ('Sapphire', False),
    b'glb': ('Sapphire', False),
    b'gpb': ('Sapphire', True),
    # Emerald
    b'gcg': ('Emerald', False),
    b'gfg': ('Emerald', False),
    b'gsg': ('Emerald', False),
    b'glg': ('Emerald', False),
    b'gpg': ('Emerald', True),
    # Ruby
    b'gcr': ('Ruby', False),
    b'gfr': ('Ruby', False),
    b'gsr': ('Ruby', False),
    b'glr': ('Ruby', False),
    b'gpr': ('Ruby', True),
    # Diamond
    b'gcw': ('Diamond', False),
    b'gfw': ('Diamond', False),
    b'gsw': ('Diamond', False),
    b'glw': ('Diamond', False),
    b'gpw': ('Diamond', True),
    # Skull
    b'skc': ('Skull', False),
    b'skf': ('Skull', False),
    b'sku': ('Skull', False),
    b'skl': ('Skull', False),
    b'skz': ('Skull', True),
}

RUNE_CODES_STRIPPED = {c.strip() for c in RUNE_CODES}
GEM_CODES_STRIPPED = {c.strip() for c in GEM_CODES}
MATERIAL_CODES_STRIPPED = {c.strip() for c in MATERIAL_CODES}
COMBINED_SLOT_ORDER_STRIPPED = [c.strip() for c in COMBINED_SLOT_ORDER]

CLASS_SKILL_BASES = [
    6,    # Amazon (0)
    36,   # Sorceress (1)
    66,   # Necromancer (2)
    96,   # Paladin (3)
    126,  # Barbarian (4)
    221,  # Druid (5)
    251,  # Assassin (6)
    373,  # Warlock (7)
]

DIFFICULTY_NAMES = ["Normal", "Nightmare", "Hell"]

WAYPOINTS_BY_ACT = [
    ("Act I", [
        "Rogue Encampment", "Cold Plains", "Stony Field", "Dark Wood",
        "Black Marsh", "Outer Cloister", "Jail Level 1", "Inner Cloister",
        "Catacombs Level 2"
    ]),
    ("Act II", [
        "Lut Gholein", "Sewers Level 2", "Dry Hills", "Halls of the Dead Level 2",
        "Far Oasis", "Lost City", "Palace Cellar Level 1", "Arcane Sanctuary",
        "Canyon of the Magi"
    ]),
    ("Act III", [
        "Kurast Docks", "Spider Forest", "Great Marsh", "Flayer Jungle",
        "Lower Kurast", "Kurast Bazaar", "Upper Kurast", "Travincal",
        "Durance of Hate Level 2"
    ]),
    ("Act IV", [
        "The Pandemonium Fortress", "City of the Damned", "River of Flame"
    ]),
    ("Act V", [
        "Harrogath", "Frigid Highlands", "Arreat Plateau", "Crystalline Passage",
        "Glacial Trail", "Halls of Pain", "Frozen Tundra", "The Ancients' Way",
        "Worldstone Keep Level 2"
    ])
]

QUESTS_BY_ACT = [
    ("Act I", [
        ("Den of Evil", 0),
        ("Sisters' Burial Grounds", 1),
        ("The Search for Cain", 3),
        ("The Forgotten Tower", 4),
        ("Tools of the Trade", 2),
        ("Sisters to the Slaughter", 5),
    ]),
    ("Act II", [
        ("Radament's Lair", 0),
        ("The Horadric Staff", 1),
        ("Tainted Sun", 2),
        ("Arcane Sanctuary", 3),
        ("The Summoner", 4),
        ("The Seven Tombs", 5),
    ]),
    ("Act III", [
        ("The Golden Bird", 3),
        ("Blade of the Old Religion", 2),
        ("Khalim's Will", 1),
        ("Lam Esen's Tome", 0),
        ("The Blackened Temple", 4),
        ("The Guardian", 5),
    ]),
    ("Act IV", [
        ("The Fallen Angel", 0),
        ("Hell's Forge", 2),
        ("Terror's End", 1),
    ]),
    ("Act V", [
        ("Siege on Harrogath", 0),
        ("Rescue on Mount Arreat", 1),
        ("Prison of Ice", 2),
        ("Betrayal of Harrogath", 3),
        ("Rite of Passage", 4),
        ("Eve of Destruction", 5),
    ])
]

_script_dir = os.path.dirname(os.path.abspath(__file__))

# 提前解析语言参数，因为模块加载时需要
def parse_lang_arg():
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == '--lang' and i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return 'enUS'  # 默认语言

_lang_key = parse_lang_arg()

data_dir = os.path.join(_script_dir, "data")
if os.path.exists(data_dir):
    init_d2data(data_dir)
    
    local_data_dir = os.path.join(data_dir, "local")
    if os.path.exists(local_data_dir):
        init_localized_data(local_data_dir, lang_key=_lang_key)
    
    item_modifiers_file = os.path.join(data_dir, "local", "item-modifiers.json")
    if os.path.exists(item_modifiers_file):
        init_item_modifiers(item_modifiers_file, lang_key=_lang_key)

def get_char_type_name(char_type):
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

def get_char_title_name(char_title, char_class):
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

def get_item_display_name(item, version=0x63) -> str:
    type_name = item.sTypeName.decode('ascii', errors='replace').strip() if item.sTypeName else 'Unknown'
    d2data = get_d2data()
    d2data_manager = get_d2data_manager()
    
    base_item_name = ""
    if d2data_manager:
        type_info = d2data_manager.get_item(type_name, version)
        if type_info:
            base_item_name = type_info.name
    elif d2data:
        type_info = d2data.get_item(type_name)
        if type_info:
            base_item_name = type_info.name
    if not base_item_name:
        base_item_name = type_name

    ext = getattr(getattr(item, 'pItemInfo', None), 'pExtItemInfo', None)
    if ext:
        if ext.wRune.exist():
            runeword_id = ext.rune_word_id()
            rw_info = d2data_manager.get_runeword(runeword_id, version) if d2data_manager else (d2data.get_runeword(runeword_id) if d2data else None)
            if rw_info:
                return f"{rw_info.name} ({base_item_name})"
        if ext.wUniID.exist():
            unique_id = ext.wUniID.value
            u_info = d2data_manager.get_unique_item(unique_id, version) if d2data_manager else (d2data.get_unique_item(unique_id) if d2data else None)
            if u_info:
                return f"{u_info.index} ({base_item_name})"
        if ext.wSetID.exist():
            set_id = ext.wSetID.value
            s_info = d2data_manager.get_set_item(set_id, version) if d2data_manager else (d2data.get_set_item(set_id, version) if d2data else None)
            if s_info:
                return f"{s_info.name} ({base_item_name})"
        quality = item.quality()
        if quality == ItemQuality.MAGIC:
            prefix_name = ""
            suffix_name = ""
            if ext.wPrefix.exist() and ext.wPrefix.value > 0:
                p_info = d2data_manager.get_magic_prefix(ext.wPrefix.value, version) if d2data_manager else (d2data.get_magic_prefix(ext.wPrefix.value) if d2data else None)
                if p_info:
                    prefix_name = p_info.name
            if ext.wSuffix.exist() and ext.wSuffix.value > 0:
                s_info = d2data_manager.get_magic_suffix(ext.wSuffix.value, version) if d2data_manager else (d2data.get_magic_suffix(ext.wSuffix.value) if d2data else None)
                if s_info:
                    suffix_name = s_info.name
            parts = [p for p in [prefix_name, base_item_name, suffix_name] if p]
            if parts:
                return " ".join(parts)
        elif quality == ItemQuality.RARE:
            return f"Rare {base_item_name}"
        elif quality == ItemQuality.CRAFTED:
            return f"Crafted {base_item_name}"
        elif quality == ItemQuality.HIGH:
            return f"Superior {base_item_name}"
        elif quality == ItemQuality.LOW:
            return f"Low Quality {base_item_name}"

    return base_item_name

def format_item_summary(item, version=0x63, include_properties=True) -> str:
    info = getattr(item, 'pItemInfo', None)
    if info and info.pGold:
        return f"Gold: {info.pGold.wQuantity}"
        
    title = get_item_display_name(item, version)
    
    meta_tags = []
    tp = getattr(info, 'pTpSpInfo', None)
    if tp:
        if tp.iDefence.exist():
            meta_tags.append(f"Def: {tp.get_defence()}")
        sockets = tp.total_sockets()
        if sockets > 0:
            meta_tags.append(f"Sockets: {sockets}")
            
    if getattr(item, 'bEthereal', False):
        meta_tags.append("Eth")
    if getattr(item, 'bDisabled', False):
        meta_tags.append("Broken")
        
    stack_size = getattr(info, 'iAdvancedStashStackSize', 0)
    if stack_size > 1:
        meta_tags.append(f"x{stack_size}")
    elif tp and tp.iQuantity.exist() and tp.iQuantity.value > 1:
        meta_tags.append(f"Qty: {tp.iQuantity.value}")
        
    if getattr(item, 'aGemItems', None):
        socketed = []
        for gem in item.aGemItems:
            g_name = get_item_display_name(gem, version)
            socketed.append(g_name)
        if socketed:
            meta_tags.append(f"Socketed: {'+'.join(socketed)}")
            
    props = []
    if include_properties:
        if tp and tp.stPropertyList and tp.stPropertyList.mProperty:
            for prop_id, value, params in tp.stPropertyList.get_parsed_properties(version):
                formatted = format_property(prop_id, params, version)
                if formatted:
                    props.append(formatted)
                elif params:
                    props.append(f"ID {prop_id}: raw={value}, params={params}")
                else:
                    props.append(f"ID {prop_id}: {value}")
        if tp and tp.stRuneWordPropertyList and tp.stRuneWordPropertyList.mProperty:
            for prop_id, value, params in tp.stRuneWordPropertyList.get_parsed_properties(version):
                formatted = format_property(prop_id, params, version)
                if formatted:
                    props.append(formatted)
                elif params:
                    props.append(f"ID {prop_id}: raw={value}, params={params}")
                else:
                    props.append(f"ID {prop_id}: {value}")
                    
    meta_str = f" [{', '.join(meta_tags)}]" if meta_tags else ""
    props_str = f" ({', '.join(props)})" if props else ""
    return f"{title}{meta_str}{props_str}"

def format_item_info(item, indent="  "):
    result = []
    type_name = item.sTypeName.decode('ascii', errors='replace') if item.sTypeName else 'Unknown'
    
    item_full_name = ""
    req_level = 0
    
    version = item.dwVersion if item.dwVersion else 0x63
    d2data = get_d2data()
    d2data_manager = get_d2data_manager()
    
    if d2data_manager:
        type_info = d2data_manager.get_item(type_name.strip(), version)
        if type_info:
            item_full_name = type_info.name
            req_level = type_info.levelreq
    elif d2data:
        # 向后兼容
        type_info = d2data.get_item(type_name.strip())
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
    
    flags = []
    if item.bIdentified:
        flags.append("Identified")
    if item.bSocketed:
        flags.append("Socketed")
    if item.bEthereal:
        flags.append("Ethereal")
    if item.bRuneWord:
        flags.append("RuneWord")
    if item.bPersonalized:
        flags.append("Personalized")
    if item.bQuest:
        flags.append("Quest")
    if getattr(item, 'bNoSell', False):
        flags.append("NoSell")
    if getattr(item, 'bNamed', False):
        flags.append("Named")
    if getattr(item, 'bJustSaved', False):
        flags.append("JustSaved")
    if getattr(item, 'bLowQuality', False):
        flags.append("LowQuality")
    if getattr(item, 'bDisabled', False):
        flags.append("Broken")
    if getattr(item, 'bNew', False):
        flags.append("InStore")
    if getattr(item, 'bBadEquipped', False):
        flags.append("NoEquip")
    if getattr(item, 'bNewbie', False):
        flags.append("StarterItem")
    if flags:
        result.append(f"{indent}Flags: {', '.join(flags)}")
    
    if item.pItemInfo:
        info = item.pItemInfo
        if info.pExtItemInfo:
            ext = info.pExtItemInfo
            if ext.dwGUID:
                result.append(f"{indent}GUID: 0x{ext.dwGUID:08X}")
            if ext.iDropLevel:
                result.append(f"{indent}Drop Level: {ext.iDropLevel}")
            if ext.wPrefix.exist() and ext.wPrefix.value > 0:
                prefix_id = ext.wPrefix.value
                prefix_name = ""
                if d2data_manager:
                    prefix_info = d2data_manager.get_magic_prefix(prefix_id, version)
                    if prefix_info:
                        prefix_name = f" ({prefix_info.name})"
                elif d2data:
                    # 向后兼容
                    prefix_info = d2data.get_magic_prefix(prefix_id)
                    if prefix_info:
                        prefix_name = f" ({prefix_info.name})"
                result.append(f"{indent}Prefix: {prefix_id}{prefix_name}")
            if ext.wSuffix.exist() and ext.wSuffix.value > 0:
                suffix_id = ext.wSuffix.value
                suffix_name = ""
                if d2data_manager:
                    suffix_info = d2data_manager.get_magic_suffix(suffix_id, version)
                    if suffix_info:
                        suffix_name = f" ({suffix_info.name})"
                elif d2data:
                    # 向后兼容
                    suffix_info = d2data.get_magic_suffix(suffix_id)
                    if suffix_info:
                        suffix_name = f" ({suffix_info.name})"
                result.append(f"{indent}Suffix: {suffix_id}{suffix_name}")
            if ext.wSetID.exist():
                set_id = ext.wSetID.value
                set_name = ""
                if d2data_manager:
                    set_info = d2data_manager.get_set_item(set_id, version)
                    if set_info:
                        set_name = f" ({set_info.name})"
                elif d2data:
                    set_info = d2data.get_set_item(set_id, version)
                    if set_info:
                        set_name = f" ({set_info.name})"
                result.append(f"{indent}Set ID: {set_id}{set_name}")
            if ext.wUniID.exist():
                unique_id = ext.wUniID.value
                unique_name = ""
                if d2data_manager:
                    unique_info = d2data_manager.get_unique_item(unique_id, version)
                    if unique_info:
                        unique_name = f" ({unique_info.index})"
                elif d2data:
                    # 向后兼容
                    unique_info = d2data.get_unique_item(unique_id)
                    if unique_info:
                        unique_name = f" ({unique_info.index})"
                result.append(f"{indent}Unique ID: {unique_id}{unique_name}")
            if ext.wRune.exist():
                runeword_id = ext.rune_word_id()
                runeword_name = ""
                if d2data_manager:
                    runeword_info = d2data_manager.get_runeword(runeword_id, version)
                    if runeword_info:
                        runeword_name = f" ({runeword_info.name})"
                elif d2data:
                    # 向后兼容
                    runeword_info = d2data.get_runeword(runeword_id)
                    if runeword_info:
                        runeword_name = f" ({runeword_info.name})"
                result.append(f"{indent}Rune Word ID: {runeword_id}{runeword_name}")
                if item.aGemItems:
                    rune_names = []
                    for gem in item.aGemItems:
                        gem_type = gem.sTypeName.decode('ascii', errors='replace').strip() if gem.sTypeName else ''
                        if gem_type.startswith('r'):
                            try:
                                rune_num = int(gem_type[1:])
                                rune_name = ""
                                if d2data_manager:
                                    rune_info = d2data_manager.get_item(gem_type, version)
                                    if rune_info:
                                        rune_name = rune_info.name
                                elif d2data:
                                    # 向后兼容
                                    rune_info = d2data.get_item(gem_type)
                                    if rune_info:
                                        rune_name = rune_info.name
                                rune_names.append(f"{rune_name}({rune_num})")
                            except ValueError:
                                pass
                    if rune_names:
                        result.append(f"{indent}Runes: {'+'.join(rune_names)}")
            if ext.pRareName:
                result.append(f"{indent}Rare Name: {ext.pRareName.iName1}-{ext.pRareName.iName2}")
            if ext.pCraftName:
                result.append(f"{indent}Craft Name: {ext.pCraftName.iName1}-{ext.pCraftName.iName2}")
        
        if info.pTpSpInfo:
            tp = info.pTpSpInfo
            if tp.iDefence.exist():
                result.append(f"{indent}Defence: {tp.get_defence()}")
            if tp.iMaxDurability.exist():
                if tp.is_indestructible():
                    result.append(f"{indent}Durability: Indestructible")
                else:
                    cur = tp.iCurDur.value if tp.iCurDur.exist() else 0
                    result.append(f"{indent}Durability: {cur}/{tp.iMaxDurability.value}")
            if tp.iQuantity.exist():
                result.append(f"{indent}Quantity: {tp.iQuantity.value}")
            sockets = tp.total_sockets()
            if sockets > 0:
                result.append(f"{indent}Sockets: {sockets}")
            
            if tp.stPropertyList and tp.stPropertyList.mProperty:
                result.append(f"{indent}Properties:")
                version = item.dwVersion if item.dwVersion else 0x63
                for prop_id, value, params in tp.stPropertyList.get_parsed_properties(version):
                    formatted = format_property(prop_id, params, version)
                    if formatted:
                        result.append(f"{indent}  - {formatted}")
                    elif params:
                        result.append(f"{indent}  - ID {prop_id}: raw={value}, params={params}")
                    else:
                        result.append(f"{indent}  - ID {prop_id}: {value}")
            
            if tp.stRuneWordPropertyList and tp.stRuneWordPropertyList.mProperty:
                result.append(f"{indent}Rune Word Properties:")
                version = item.dwVersion if item.dwVersion else 0x63
                for prop_id, value, params in tp.stRuneWordPropertyList.get_parsed_properties(version):
                    formatted = format_property(prop_id, params, version)
                    if formatted:
                        result.append(f"{indent}  - {formatted}")
                    elif params:
                        result.append(f"{indent}  - ID {prop_id}: raw={value}, params={params}")
                    else:
                        result.append(f"{indent}  - ID {prop_id}: {value}")
            
            if getattr(tp, 'apSetProperty', None):
                for idx, set_prop_list in enumerate(tp.apSetProperty):
                    if set_prop_list and set_prop_list.mProperty:
                        piece_count = idx + 2
                        result.append(f"{indent}Set Properties ({piece_count} Items):")
                        version = item.dwVersion if item.dwVersion else 0x63
                        for prop_id, value, params in set_prop_list.get_parsed_properties(version):
                            formatted = format_property(prop_id, params, version)
                            if formatted:
                                result.append(f"{indent}  - {formatted}")
                            elif params:
                                result.append(f"{indent}  - ID {prop_id}: raw={value}, params={params}")
                            else:
                                result.append(f"{indent}  - ID {prop_id}: {value}")
        
        if getattr(info, 'iAdvancedStashStackSize', 0) > 0:
            result.append(f"{indent}Stack Size: {info.iAdvancedStashStackSize}")
        if info.pGold:
            result.append(f"{indent}Gold: {info.pGold.wQuantity}")
    
    if item.aGemItems:
        for j, gem in enumerate(item.aGemItems):
            result.append(f"{indent}Socketed Item [{j}]:")
            result.extend(format_item_info(gem, indent + "  "))
    
    return result

def format_waypoints_info(char_data: D2SStruct):
    result = []
    result.append("=== Waypoints ===")
    if char_data.Waypoints.wMajic == 0x5357:
        for diff_idx, diff_name in enumerate(DIFFICULTY_NAMES):
            if diff_idx >= len(char_data.Waypoints.wp):
                break
            wp_data = char_data.Waypoints.wp[diff_idx]
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
                        missing.append(name)
                    global_idx += 1
                act_stats.append((act_name, len(wp_names), unlocked_in_act, missing))
            
            # Check if this difficulty has been started (has waypoints beyond starter town or has quest activity)
            has_wp_progress = (wp_data.Waypoints[0] & ~1) != 0 or any(b != 0 for b in wp_data.Waypoints[1:])
            has_quest_progress = False
            if char_data.QuestInfo.dwMajic == 0x216F6F57 and diff_idx < len(char_data.QuestInfo.QIData):
                qd = char_data.QuestInfo.QIData[diff_idx]
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

def format_quests_info(char_data: D2SStruct):
    result = []
    result.append("=== Quests ===")
    if char_data.QuestInfo.dwMajic == 0x216F6F57:
        for diff_idx, diff_name in enumerate(DIFFICULTY_NAMES):
            if diff_idx >= len(char_data.QuestInfo.QIData):
                break
            qd = char_data.QuestInfo.QIData[diff_idx]
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
                        if w & 1:
                            parts.append("[x]")
                        elif w & 2:
                            parts.append(f"[!] {name} (reward unclaimed)")
                        else:
                            parts.append(f"[ ] {name}")
                    result.append(f"  {act_name}: {' '.join(parts)}")
    return result

def format_char_info(char_data: D2SStruct):
    result = []
    result.append("=== Diablo II Character Info ===")
    char_name = char_data.get_char_name()
    result.append(f"Name: {char_name}")
    result.append(f"Class: {char_data.get_char_class_name()}")
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
    if char_data.PlayerStats.wMajic == 0x6667:
        result.append(f"Strength: {char_data.PlayerStats.m_adwValue[0]}")
        result.append(f"Energy: {char_data.PlayerStats.m_adwValue[1]}")
        result.append(f"Dexterity: {char_data.PlayerStats.m_adwValue[2]}")
        result.append(f"Vitality: {char_data.PlayerStats.m_adwValue[3]}")
        result.append(f"Stat Points Remaining: {char_data.PlayerStats.m_adwValue[4]}")
        result.append(f"Skill Points Remaining: {char_data.PlayerStats.m_adwValue[5]}")
        result.append(f"Current Life: {char_data.PlayerStats.m_adwValue[6] >> 8}")
        result.append(f"Maximum Life: {char_data.PlayerStats.m_adwValue[7] >> 8}")
        result.append(f"Current Mana: {char_data.PlayerStats.m_adwValue[8] >> 8}")
        result.append(f"Maximum Mana: {char_data.PlayerStats.m_adwValue[9] >> 8}")
        result.append(f"Current Stamina: {char_data.PlayerStats.m_adwValue[0xA] >> 8}")
        result.append(f"Maximum Stamina: {char_data.PlayerStats.m_adwValue[0xB] >> 8}")
        result.append(f"Level: {char_data.PlayerStats.m_adwValue[0xC]}")
        result.append(f"Experience: {char_data.PlayerStats.m_adwValue[0xD]}")
        result.append(f"Gold on Person: {char_data.PlayerStats.m_adwValue[0xE]}")
        result.append(f"Gold in Stash: {char_data.PlayerStats.m_adwValue[0xF]}")
    result.append("")
    result.append("=== Skills ===")
    if char_data.Skills.wMagic == 0x6669:
        result.append("Skill levels:")
        d2data = get_d2data()
        d2data_manager = get_d2data_manager()
        for i, level in enumerate(char_data.Skills.bSkillLevel):
            if level > 0:
                skill_name = ""
                if 0 <= char_data.charClass < len(CLASS_SKILL_BASES):
                    skill_id = CLASS_SKILL_BASES[char_data.charClass] + i
                    loc_name, _ = get_skill_name(skill_id)
                    if loc_name:
                        skill_name = loc_name
                    elif d2data_manager:
                        skill_name = d2data_manager.get_skill_name(skill_id, char_data.dwVersion)
                    elif d2data:
                        skill_name = d2data.get_skill_name(skill_id)
                if skill_name:
                    result.append(f"Skill {i} ({skill_name}): {level}")
                else:
                    result.append(f"Skill {i}: {level}")
    result.append("")
    result.extend(format_waypoints_info(char_data))
    result.append("")
    result.extend(format_quests_info(char_data))
    result.append("")
    result.append("=== Items ===")
    if char_data.ItemList.wMajic == 0x4D4A:
        result.append(f"Total items: {char_data.ItemList.nItems}")
        for i, item in enumerate(char_data.ItemList.vItems):
            result.append(f"--- Item {i} ---")
            result.extend(format_item_info(item))
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
            if char_data.dwVersion >= 0x69:
                merc_seed = getattr(char_data, 'mercSeed', 0)
                merc_name = getattr(char_data, 'mercNameIndex', 0)
                merc_type = getattr(char_data, 'mercHirelingId', 0)
                merc_exp = getattr(char_data, 'mercExperience', 0)
                merc_flags = getattr(char_data, 'mercFlags', 0)
                result.append(f"Has mercenary (Name: {merc_name}, Type: {merc_type})")
                result.append(f"Mercenary Seed: 0x{merc_seed:08X}")
                result.append(f"Mercenary Exp: {merc_exp}")
                result.append(f"Mercenary Flags: 0x{merc_flags:08X}")
            else:
                merc_name = getattr(char_data, 'wMercName', 0)
                merc_type = getattr(char_data, 'wMercType', 0)
                merc_exp = getattr(char_data, 'dwMercExp', 0)
                result.append(f"Has mercenary (Name: {merc_name}, Type: {merc_type})")
                result.append(f"Mercenary Exp: {merc_exp}")
                result.append(f"Merc Dead: {'Yes' if getattr(char_data, 'bMercDead', 0) else 'No'}")
            if char_data.stMercenary.stItems:
                result.append(f"Mercenary items: {char_data.stMercenary.stItems.nItems}")
                for i, item in enumerate(char_data.stMercenary.stItems.vItems):
                    result.append(f"--- Mercenary Item {i} ---")
                    result.extend(format_item_info(item))
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

def format_char_summary(char_data: D2SStruct) -> str:
    result = []
    result.append("=== Diablo II Character Summary ===")
    char_name = char_data.get_char_name()
    char_class = char_data.get_char_class_name()
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
        
    if char_data.PlayerStats.wMajic == 0x6667:
        str_val = char_data.PlayerStats.m_adwValue[0]
        ene_val = char_data.PlayerStats.m_adwValue[1]
        dex_val = char_data.PlayerStats.m_adwValue[2]
        vit_val = char_data.PlayerStats.m_adwValue[3]
        stat_pts = char_data.PlayerStats.m_adwValue[4]
        skill_pts = char_data.PlayerStats.m_adwValue[5]
        cur_life = char_data.PlayerStats.m_adwValue[6] >> 8
        max_life = char_data.PlayerStats.m_adwValue[7] >> 8
        cur_mana = char_data.PlayerStats.m_adwValue[8] >> 8
        max_mana = char_data.PlayerStats.m_adwValue[9] >> 8
        gold_person = char_data.PlayerStats.m_adwValue[0xE]
        gold_stash = char_data.PlayerStats.m_adwValue[0xF]
        result.append(f"Attributes: Str: {str_val}, Dex: {dex_val}, Vit: {vit_val}, Ene: {ene_val}")
        result.append(f"Life: {cur_life}/{max_life} | Mana: {cur_mana}/{max_mana} | Gold: {gold_person} (Person), {gold_stash} (Stash)")
        if stat_pts > 0 or skill_pts > 0:
            result.append(f"Remaining Points: {stat_pts} Stat, {skill_pts} Skill")

    result.append("")
    result.append("=== Skills ===")
    if char_data.Skills.wMagic == 0x6669:
        d2data = get_d2data()
        d2data_manager = get_d2data_manager()
        active_skills = []
        for i, level in enumerate(char_data.Skills.bSkillLevel):
            if level > 0:
                skill_name = ""
                if 0 <= char_data.charClass < len(CLASS_SKILL_BASES):
                    skill_id = CLASS_SKILL_BASES[char_data.charClass] + i
                    loc_name, _ = get_skill_name(skill_id)
                    if loc_name:
                        skill_name = loc_name
                    elif d2data_manager:
                        skill_name = d2data_manager.get_skill_name(skill_id, char_data.dwVersion)
                    elif d2data:
                        skill_name = d2data.get_skill_name(skill_id)
                display = skill_name if skill_name else f"Skill {i}"
                active_skills.append(f"{display}: {level}")
        if active_skills:
            result.append(", ".join(active_skills))
        else:
            result.append("None")

    result.append("")
    result.extend(format_waypoints_info(char_data))
    result.append("")
    result.extend(format_quests_info(char_data))
    result.append("")

    result.append("=== Equipped Gear ===")
    version = char_data.dwVersion if char_data.dwVersion else 0x63
    equipped_items = {}
    inventory_items = []
    stash_items = []
    cube_items = []
    belt_items = []
    cursor_items = []

    if char_data.ItemList.wMajic == 0x4D4A:
        for item in char_data.ItemList.vItems:
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
            result.append(f"- {slot.display_name}: {format_item_summary(it, version)}")
    if not has_equipped:
        result.append("None")

    result.append("")
    result.append("=== Mercenary ===")
    if char_data.is_expansion() and char_data.has_mercenary():
        merc_name = getattr(char_data, 'mercNameIndex', 0) if char_data.dwVersion >= 0x69 else getattr(char_data, 'wMercName', 0)
        merc_type = getattr(char_data, 'mercHirelingId', 0) if char_data.dwVersion >= 0x69 else getattr(char_data, 'wMercType', 0)
        dead_str = " (Dead)" if getattr(char_data, 'bMercDead', 0) else ""
        result.append(f"Mercenary: Name Index {merc_name}, Type {merc_type}{dead_str}")
        if char_data.stMercenary.stItems and char_data.stMercenary.stItems.vItems:
            result.append("Equipped:")
            for m_item in char_data.stMercenary.stItems.vItems:
                loc = ItemLocation(m_item.iLocation)
                slot_str = ""
                if loc == ItemLocation.EQUIPPED and m_item.iPosition in EquipSlot._value2member_map_:
                    slot_str = f"{EquipSlot(m_item.iPosition).display_name}: "
                result.append(f"  - {slot_str}{format_item_summary(m_item, version)}")
        else:
            result.append("Equipped: None")
    else:
        result.append("No mercenary")

    result.append("")
    result.append("=== Inventory & Stash ===")
    stored_lines = []
    for it in inventory_items:
        stored_lines.append(f"- [Inventory] {format_item_summary(it, version)}")
    for it in stash_items:
        stored_lines.append(f"- [Stash] {format_item_summary(it, version)}")
    for it in cube_items:
        stored_lines.append(f"- [Cube] {format_item_summary(it, version)}")

    if belt_items:
        belt_counts = {}
        for it in belt_items:
            summary = format_item_summary(it, version)
            belt_counts[summary] = belt_counts.get(summary, 0) + 1
        for summary, count in belt_counts.items():
            count_str = f" (x{count})" if count > 1 else ""
            stored_lines.append(f"- [Belt] {summary}{count_str}")

    for it in cursor_items:
        stored_lines.append(f"- [Cursor] {format_item_summary(it, version)}")

    if stored_lines:
        result.extend(stored_lines)
    else:
        result.append("No stored items")

    return '\n'.join(result).rstrip()

def debug_bitstream(bs, context_bits=64, label=""):
    offset = bs.getOffset()
    bits_str = str(bs)
    
    start = max(0, offset - context_bits)
    end = min(len(bits_str), offset + context_bits)
    
    before = bits_str[start:offset]
    current = bits_str[offset:end]
    
    byte_pos = offset // 8
    bit_pos = offset % 8
    
    print(f"\n=== BitStream Debug {label} ===")
    print(f"Offset: {offset} (byte {byte_pos}, bit {bit_pos})")
    print(f"Position marker: ...{before}[HERE]{current}...")
    print(f"Byte context: {bs.data[max(0,byte_pos-4):byte_pos+8].hex()}")
    print("=" * 40)

def search_bits(bs, pattern, context=16):
    bits_str = str(bs)
    results = []
    start = 0
    while True:
        pos = bits_str.find(pattern, start)
        if pos == -1:
            break
        byte_pos = pos // 8
        bit_pos = pos % 8
        before = bits_str[max(0, pos-context):pos]
        after = bits_str[pos+len(pattern):pos+len(pattern)+context]
        results.append({
            'offset': pos,
            'byte': byte_pos,
            'bit': bit_pos,
            'context': f"...{before}[{pattern}]{after}..."
        })
        start = pos + 1
    return results

def search_bytes(bs, byte_pattern, context=4):
    data = bs.data
    results = []
    start = 0
    while True:
        pos = data.find(byte_pattern, start)
        if pos == -1:
            break
        before = data[max(0, pos-context):pos].hex()
        after = data[pos+len(byte_pattern):pos+len(byte_pattern)+context].hex()
        results.append({
            'offset': pos,
            'context': f"...{before}[{byte_pattern.hex()}]{after}..."
        })
        start = pos + 1
    return results

def format_stash_info(stash: SharedStash) -> str:
    result = []
    result.append("=== Diablo II Shared Stash ===")
    result.append(f"Total Tabs: {stash.get_tab_count()}")
    result.append("")
    
    TAB_TYPE_NAMES = {
        STASH_TAB_TYPE_NORMAL: "Normal",
        STASH_TAB_TYPE_ADVANCED: "Advanced (Currency)",
        STASH_TAB_TYPE_CHRONICLE: "Chronicle",
    }
    
    for tab_idx, tab in enumerate(stash.tabs):
        tab_type_name = TAB_TYPE_NAMES.get(tab.TabType, f"Unknown({tab.TabType})")
        result.append(f"=== Tab {tab_idx + 1} ({tab_type_name}) ===")
        if tab.Gold:
            result.append(f"Gold: {tab.Gold}")
        
        items = tab.Items.vItems if tab.Items else []
        if tab.TabType == STASH_TAB_TYPE_ADVANCED:
            active_items = [
                item for item in items
                if getattr(getattr(item, 'pItemInfo', None), 'iAdvancedStashStackSize', 0) > 0
            ]
            result.append(f"Total items: {len(active_items)}")
            for item_idx, item in enumerate(active_items):
                result.append(f"--- Item {item_idx} ---")
                result.extend(format_item_info(item))
        else:
            result.append(f"Total items: {len(items)}")
            for item_idx, item in enumerate(items):
                result.append(f"--- Item {item_idx} ---")
                result.extend(format_item_info(item))
        result.append("")
        
    return '\n'.join(result).rstrip()

def format_stash_summary(stash: SharedStash) -> str:
    result = []
    result.append("=== Diablo II Shared Stash Summary ===")
    tab_count = stash.get_tab_count()
    result.append(f"Total Tabs: {tab_count}")
    
    TAB_TYPE_NAMES = {
        STASH_TAB_TYPE_NORMAL: "Normal",
        STASH_TAB_TYPE_ADVANCED: "Advanced (Currency)",
        STASH_TAB_TYPE_CHRONICLE: "Chronicle",
    }
    
    tab_summaries = []
    for tab_idx, tab in enumerate(stash.tabs):
        tname = TAB_TYPE_NAMES.get(tab.TabType, f"Unknown({tab.TabType})")
        tab_summaries.append(f"Tab {tab_idx + 1}: {tname}")
    result.append(f"Tabs: {', '.join(tab_summaries)}")
    result.append("")
    
    d2data = get_d2data()
    d2data_manager = get_d2data_manager()
    slot_order_map = {code: idx for idx, code in enumerate(COMBINED_SLOT_ORDER_STRIPPED)}
    
    for tab_idx, tab in enumerate(stash.tabs):
        tname = TAB_TYPE_NAMES.get(tab.TabType, f"Unknown({tab.TabType})")
        result.append(f"=== Tab {tab_idx + 1} ({tname}) ===")
        if tab.Gold:
            result.append(f"Gold: {tab.Gold}")
            
        items = tab.Items.vItems if tab.Items else []
        version = tab.ItemFormat if tab.ItemFormat else 0x63
        
        if tab.TabType == STASH_TAB_TYPE_ADVANCED:
            active_items = [
                it for it in items
                if getattr(getattr(it, 'pItemInfo', None), 'iAdvancedStashStackSize', 0) > 0
            ]
            if not active_items:
                result.append("  (empty)")
            else:
                runes_list = []
                materials_list = []
                other_list = []
                gem_stats = {g: {'p': 0, 'o': 0} for g in GEM_TYPE_NAMES}
                
                sorted_active = sorted(
                    active_items,
                    key=lambda it: slot_order_map.get(getattr(it, 'sTypeName', b'').strip(), 9999)
                )
                
                for it in sorted_active:
                    code_b = getattr(it, 'sTypeName', b'').strip()
                    code_str = code_b.decode('ascii', errors='replace')
                    stack_size = getattr(getattr(it, 'pItemInfo', None), 'iAdvancedStashStackSize', 0)
                    
                    if code_b in GEM_CODE_MAP:
                        g_type, is_perf = GEM_CODE_MAP[code_b]
                        if is_perf:
                            gem_stats[g_type]['p'] += stack_size
                        else:
                            gem_stats[g_type]['o'] += stack_size
                    elif code_b in RUNE_CODES_STRIPPED:
                        type_info = d2data_manager.get_item(code_str, version) if d2data_manager else (d2data.get_item(code_str) if d2data else None)
                        item_name = type_info.name if type_info else code_str
                        display_name = item_name[:-5] if item_name.endswith(" Rune") else item_name
                        runes_list.append(f"{display_name}: {stack_size}")
                    elif code_b in MATERIAL_CODES_STRIPPED:
                        type_info = d2data_manager.get_item(code_str, version) if d2data_manager else (d2data.get_item(code_str) if d2data else None)
                        item_name = type_info.name if type_info else code_str
                        materials_list.append(f"{item_name}: {stack_size}")
                    else:
                        type_info = d2data_manager.get_item(code_str, version) if d2data_manager else (d2data.get_item(code_str) if d2data else None)
                        item_name = type_info.name if type_info else code_str
                        other_list.append(f"{item_name}: {stack_size}")

                gems_list = []
                for g_type in GEM_TYPE_NAMES:
                    p = gem_stats[g_type]['p']
                    o = gem_stats[g_type]['o']
                    if p > 0 or o > 0:
                        gems_list.append(f"{g_type}: p {p}, o {o}")
                        
                if runes_list:
                    result.append(f"  Runes: {', '.join(runes_list)}")
                if gems_list:
                    result.append(f"  Gems (p=perfect, o=other): {', '.join(gems_list)}")
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
                    summary = format_item_summary(it, version, include_properties=False)
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

def parse_d2i_file(file_path, debug=False):
    try:
        with open(file_path, 'rb') as f:
            data = f.read()
        
        bs = IBitStream(data)
        if len(data) >= 4 and data[:4] == b'\x55\xaa\x55\xaa':
            stash = SharedStash()
            stash.deserialize(bs)
            if debug:
                print(f"\n=== BitStream Final State ===")
                print(f"Total bits: {len(bs)}")
                print(f"Final offset: {bs.getOffset()}")
                print(f"Remaining: {bs.remaining()}")
            return True, stash, "stash", bs
        elif data.startswith(b'JM'):
            from core.item import D2Item
            item = D2Item()
            item.deserialize(bs)
            return True, item, "item", bs
        else:
            stash = SharedStash()
            stash.deserialize(bs)
            return True, stash, "stash", bs
    except Exception as e:
        print(f"Error parsing file: {e}")
        import traceback
        traceback.print_exc()
        return False, None, None, None

def parse_d2s_file(file_path, debug=False):
    try:
        with open(file_path, 'rb') as f:
            data = f.read()
        
        bs = IBitStream(data)
        char_data = D2SStruct()
        char_data.deserialize(bs)
        
        if debug:
            print(f"\n=== BitStream Final State ===")
            print(f"Total bits: {len(bs)}")
            print(f"Final offset: {bs.getOffset()}")
            print(f"Remaining: {bs.remaining()}")
        
        return True, char_data, bs
        
    except Exception as e:
        print(f"Error parsing file: {e}")
        import traceback
        traceback.print_exc()
        return False, None, None

def process_file(file_path, args):
    if not os.path.exists(file_path):
        print(f"Error: File '{file_path}' does not exist")
        return
    
    if not (file_path.endswith('.d2s') or file_path.endswith('.d2i')):
        print(f"Error: File '{file_path}' is not a .d2s or .d2i file")
        return
    
    if file_path.endswith('.d2i'):
        success, stash_or_item, kind, bs = parse_d2i_file(file_path, args.debug)
        if success and stash_or_item:
            if args.search:
                results = search_bits(bs, args.search)
                print(f"\n=== Search Results for '{args.search}' ===")
                for r in results:
                    print(f"Offset {r['offset']} (byte {r['byte']}, bit {r['bit']}): {r['context']}")
                if not results:
                    print("Pattern not found")
            
            if args.search_bytes:
                search_byte_pattern = bytes.fromhex(args.search_bytes)
                results = search_bytes(bs, search_byte_pattern)
                print(f"\n=== Search Results for bytes '{search_byte_pattern.hex()}' ===")
                for r in results:
                    print(f"Offset {r['offset']}: {r['context']}")
                if not results:
                    print("Pattern not found")
            
            if kind == "stash":
                if getattr(args, 'summary', False):
                    print(format_stash_summary(stash_or_item))
                else:
                    print(format_stash_info(stash_or_item))
            elif kind == "item":
                if getattr(args, 'summary', False):
                    print("=== Item Summary ===")
                    print(f"- {format_item_summary(stash_or_item)}")
                else:
                    print("=== Item Info ===")
                    print('\n'.join(format_item_info(stash_or_item)))
        return

    success, char_data, bs = parse_d2s_file(file_path, args.debug)
    
    if success and char_data:
        if args.search:
            results = search_bits(bs, args.search)
            print(f"\n=== Search Results for '{args.search}' ===")
            for r in results:
                print(f"Offset {r['offset']} (byte {r['byte']}, bit {r['bit']}): {r['context']}")
            if not results:
                print("Pattern not found")
        
        if args.search_bytes:
            search_byte_pattern = bytes.fromhex(args.search_bytes)
            results = search_bytes(bs, search_byte_pattern)
            print(f"\n=== Search Results for bytes '{search_byte_pattern.hex()}' ===")
            for r in results:
                print(f"Offset {r['offset']}: {r['context']}")
            if not results:
                print("Pattern not found")
        
        if getattr(args, 'summary', False):
            print(format_char_summary(char_data))
        else:
            print(format_char_info(char_data))

def main():
    parser = argparse.ArgumentParser(
        description='Diablo II Save and Shared Stash File Parser',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  %(prog)s character.d2s
  %(prog)s --summary character.d2s
  %(prog)s ModernSharedStashSoftCoreV2.d2i
  %(prog)s --summary *.d2s ModernSharedStashSoftCoreV2.d2i
  %(prog)s --debug character.d2s
  %(prog)s --lang zhCN character.d2s
  %(prog)s --search 10110011 character.d2s
  %(prog)s --search-bytes 4a4d character.d2s
        '''
    )
    
    parser.add_argument('file_path', nargs='+', help='Path to the .d2s save file(s) or .d2i stash/item file(s)')
    parser.add_argument('--summary', action='store_true', help='Show compact summary instead of full dump')
    parser.add_argument('-d', '--debug', action='store_true', help='Show debug info')
    parser.add_argument('-s', '--search', metavar='PATTERN', 
                        help='Search bit pattern (e.g. "10110011")')
    parser.add_argument('-sb', '--search-bytes', metavar='HEX', 
                        help='Search byte pattern (e.g. "4a4d")')
    parser.add_argument('--lang', metavar='LANG_KEY', 
                        help='Set language (e.g. enUS, zhCN, zhTW)')
    
    args = parser.parse_args()
    
    for idx, path in enumerate(args.file_path):
        if len(args.file_path) > 1:
            if idx > 0:
                print()
            print(f"=== File: {path} ===")
        process_file(path, args)


if __name__ == "__main__":
    main()
