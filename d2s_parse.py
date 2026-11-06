#!/usr/bin/env python3
import sys
import os
import argparse
from core.d2s_struct import D2SStruct
from core.ibitstream import IBitStream
from core.property import format_property, init_item_modifiers, get_skill_name
from core.d2data import init_d2data, get_d2data, get_d2data_manager
from core.localized_data import init_localized_data
from core.enums import StoredIn, ItemLocation, ItemQuality, EquipSlot
from core.stash import SharedStash, STASH_TAB_TYPE_ADVANCED, STASH_TAB_TYPE_NORMAL, STASH_TAB_TYPE_CHRONICLE

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
    
    if char_data.dwVersion >= 0x69:
        result.append(f"Create Time: {getattr(char_data, 'createTime', 0)}")
        result.append(f"Last Save Time: {getattr(char_data, 'lastSaveTime', 0)}")
        result.append(f"Play Time: {getattr(char_data, 'playTime', 0)}")
        result.append(f"Game Version: {getattr(char_data, 'gameVersion', 0)}")
    else:
        result.append(f"Create Time: {getattr(char_data, 'createTime', 0)}")
        result.append(f"Play Time: {getattr(char_data, 'playTime', 0)}")
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
    result.append("=== Waypoints ===")
    if char_data.Waypoints.wMajic == 0x5357:
        for i, wp_data in enumerate(char_data.Waypoints.wp):
            result.append(f"Waypoint set {i}:")
            result.append(f"  Unknown: 0x{wp_data.unknown:X}")
            result.append(f"  Waypoints: {wp_data.Waypoints}")
    result.append("")
    result.append("=== Quest Info ===")
    if char_data.QuestInfo.dwMajic == 0x216F6F57:
        result.append(f"Magic: 0x{char_data.QuestInfo.dwMajic:X}")
        result.append(f"Acts: {char_data.QuestInfo.dwActs}")
        result.append(f"Size: 0x{char_data.QuestInfo.wSize:X}")
        for i, qi_data in enumerate(char_data.QuestInfo.QIData):
            result.append(f"Quest Info {i}:")
            result.append(f"  Act I: {[hex(w) for w in qi_data.wActI]}")
            result.append(f"  Act II: {[hex(w) for w in qi_data.wActII]}")
            result.append(f"  Act III: {[hex(w) for w in qi_data.wActIII]}")
            result.append(f"  Act IV: {[hex(w) for w in qi_data.wActIV]}")
            result.append(f"  Act V: {[hex(w) for w in qi_data.wActV]}")
            if qi_data.bResetStats:
                result.append(f"  Reset Stats: 0x{qi_data.bResetStats:X}")
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

def main():
    parser = argparse.ArgumentParser(
        description='Diablo II Save and Shared Stash File Parser',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  %(prog)s character.d2s
  %(prog)s ModernSharedStashSoftCoreV2.d2i
  %(prog)s --debug character.d2s
  %(prog)s --lang zhCN character.d2s
  %(prog)s --search 10110011 character.d2s
  %(prog)s --search-bytes 4a4d character.d2s
        '''
    )
    
    parser.add_argument('file_path', help='Path to the .d2s save file or .d2i stash/item file')
    parser.add_argument('-d', '--debug', action='store_true', help='Show debug info')
    parser.add_argument('-s', '--search', metavar='PATTERN', 
                        help='Search bit pattern (e.g. "10110011")')
    parser.add_argument('-sb', '--search-bytes', metavar='HEX', 
                        help='Search byte pattern (e.g. "4a4d")')
    parser.add_argument('--lang', metavar='LANG_KEY', 
                        help='Set language (e.g. enUS, zhCN, zhTW)')
    
    args = parser.parse_args()
    
    file_path = args.file_path
    
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
                print(format_stash_info(stash_or_item))
            elif kind == "item":
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
        
        print(format_char_info(char_data))

if __name__ == "__main__":
    main()
