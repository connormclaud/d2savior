import os

from d2s_parse import parse_file
from d2savior.core.d2data import GameDataResolver
from d2savior.core.d2s_struct import D2SStruct, ItemList
from d2savior.core.enums import EquipSlot, ItemLocation, StoredIn
from d2savior.core.formatters import format_char_info, format_char_summary
from d2savior.core.item import D2Item, ExtItemInfo, ItemInfo, TypeSpecificInfo
from d2savior.core.property_list import PropertyList
from d2savior.core.stats import (
    AdvancedStats,
    MercenaryStats,
    calculate_advanced_stats,
    calculate_mercenary_level,
    calculate_mercenary_stats,
)

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
SORK_D2S = os.path.join(FIXTURES_DIR, "sork.d2s")
SORC_D2S = os.path.join(FIXTURES_DIR, "Sorc.d2s")


def test_sork_advanced_stats(game_data_resolver: GameDataResolver):
    kind, char, _ = parse_file(SORK_D2S, resolver=game_data_resolver)
    assert kind == "char"
    assert char is not None

    stats = calculate_advanced_stats(char, resolver=game_data_resolver)
    assert isinstance(stats, AdvancedStats)

    # In sork save (weapon set I active):
    # Resistances (gear + charms + 2x Anya quest = +20 to all):
    # Fire: 18 (amulet) + 17 (ring) + 17 (boots) + 16 (gloves) + 12 (grand charm) + 20 (grand charm) + 20 (Anya) = 120
    assert stats.resistances.fire == 120
    # Cold: 18 (amulet) + 20 (boots) + 8 (grand charm) = 46
    assert stats.resistances.cold == 66
    # Lightning: 30 (Lore) + 18 (amulet) + 16 (ring) + 14 (grand charm) + 6 (small charm) + 7 (small charm) + 8 (large charm) = 99
    assert stats.resistances.lightning == 119
    # Poison: 30 (Stealth) + 18 (amulet) + 9 (ring) + 18 (belt) + 25 (gloves) + 8 (small charm) = 108
    assert stats.resistances.poison == 128

    # FHR: 25 (Stealth) + 55 (Spirit) = 80
    assert stats.fhr == 80

    # FCR: 25 (Stealth) + 34 (Spirit) + 10 (Manald) + 8 (Demon Clasp) = 77
    assert stats.fcr == 77

    # MF: 0 on Weapon Set I
    assert stats.mf == 0


def test_d2s_0x69_sorc_advanced_stats(game_data_resolver: GameDataResolver):
    """Test advanced stats calculation on 0x69 save file (Sorc.d2s)."""
    kind, char, _ = parse_file(SORC_D2S, resolver=game_data_resolver)
    assert kind == "char"
    assert char is not None
    assert char.version == 0x69

    stats = calculate_advanced_stats(char, resolver=game_data_resolver)
    assert isinstance(stats, AdvancedStats)
    assert isinstance(stats.resistances.fire, int)
    assert isinstance(stats.fhr, int)
    assert isinstance(stats.fcr, int)
    assert isinstance(stats.mf, int)


def test_weapon_set_switch(game_data_resolver: GameDataResolver):
    kind, char, _ = parse_file(SORK_D2S, resolver=game_data_resolver)
    assert kind == "char"
    assert char is not None

    # Switch to Weapon Set II (Bone wand + Rhyme shield)
    char.weapon_set = 1
    stats = calculate_advanced_stats(char, resolver=game_data_resolver)

    # Rhyme adds All Resistances +25
    # Bone wand removes Spirit (+55 FHR, +34 FCR)
    assert stats.resistances.fire == 145
    assert stats.resistances.cold == 91
    assert stats.resistances.lightning == 144
    assert stats.resistances.poison == 153

    assert stats.fhr == 25  # Only Stealth remains
    assert stats.fcr == 43  # 77 - 34 = 43
    assert stats.mf == 25  # Rhyme shield adds +25% Magic Find


def test_set_properties_activated(game_data_resolver: GameDataResolver):
    """Test that wearing 2 items of a set activates partial set properties."""
    char = D2SStruct()
    char.version = 0x63
    char.weapon_set = 0
    char.item_list = ItemList()

    # Item 1 of set: set_id=10122 (Civerb's Ward / Vestments)
    item1 = D2Item()
    item1.location = ItemLocation.EQUIPPED.value
    item1.position = EquipSlot.SHIELD_I.value
    item1.type_name = b"sml "
    item1.item_info = ItemInfo()
    item1.item_info.ext_info = ExtItemInfo()
    item1.item_info.ext_info.set_id = 10122
    tp1 = TypeSpecificInfo()
    # Base property: 10 fire resist
    pl1 = PropertyList()
    pl1.properties = [(39, 0, 210)]
    tp1.property_list = pl1
    # 2-piece set bonus (index 0, requiring 2 items): +15% FHR (stat 99)
    sp1 = PropertyList()
    sp1.properties = [(99, 0, 35)]
    tp1.set_properties = [sp1, None, None, None, None]
    item1.item_info.type_specific_info = tp1
    char.item_list.items.append(item1)

    # With only 1 piece equipped, set property is inactive
    stats1 = calculate_advanced_stats(char, resolver=game_data_resolver)
    assert stats1.resistances.fire == 10
    assert stats1.fhr == 0

    # Item 2 of same set: set_id=10122
    item2 = D2Item()
    item2.location = ItemLocation.EQUIPPED.value
    item2.position = EquipSlot.AMULET.value
    item2.type_name = b"amu "
    item2.item_info = ItemInfo()
    item2.item_info.ext_info = ExtItemInfo()
    item2.item_info.ext_info.set_id = 10122
    tp2 = TypeSpecificInfo()
    # Base property: 20 cold resist
    pl2 = PropertyList()
    pl2.properties = [(43, 0, 220)]
    tp2.property_list = pl2
    # 2-piece set bonus (index 0): +10% FCR (stat 105, save_add=20 -> 30)
    sp2 = PropertyList()
    sp2.properties = [(105, 0, 30)]
    tp2.set_properties = [sp2, None, None, None, None]
    item2.item_info.type_specific_info = tp2
    char.item_list.items.append(item2)

    # With 2 pieces equipped, both 2-piece set bonuses activate!
    stats2 = calculate_advanced_stats(char, resolver=game_data_resolver)
    assert stats2.resistances.fire == 10
    assert stats2.resistances.cold == 20
    assert stats2.fhr == 15
    assert stats2.fcr == 10


def test_inventory_charm_filtering(game_data_resolver: GameDataResolver):
    """Ensure spare equipment in inventory does not contribute to stats, but charms do."""
    char = D2SStruct()
    char.version = 0x63
    char.weapon_set = 0
    char.item_list = ItemList()

    # Non-charm in inventory (e.g. backup ring with +30 fire resist)
    spare_ring = D2Item()
    spare_ring.location = ItemLocation.STORED.value
    spare_ring.stored_in = StoredIn.INVENTORY.value
    spare_ring.type_name = b"rin "
    spare_ring.item_info = ItemInfo()
    tp_r = TypeSpecificInfo()
    pl_r = PropertyList()
    pl_r.properties = [(39, 0, 230)]  # +30 fire resist
    tp_r.property_list = pl_r
    spare_ring.item_info.type_specific_info = tp_r
    char.item_list.items.append(spare_ring)

    # Charm in inventory (small charm cm1 with +15 cold resist and +12 FHR)
    charm = D2Item()
    charm.location = ItemLocation.STORED.value
    charm.stored_in = StoredIn.INVENTORY.value
    charm.type_name = b"cm1 "
    charm.item_info = ItemInfo()
    tp_c = TypeSpecificInfo()
    pl_c = PropertyList()
    pl_c.properties = [(43, 0, 215), (99, 0, 32)]  # +15 cold resist, +12 FHR
    tp_c.property_list = pl_c
    charm.item_info.type_specific_info = tp_c
    char.item_list.items.append(charm)

    stats = calculate_advanced_stats(char, resolver=game_data_resolver)
    # Spare ring ignored
    assert stats.resistances.fire == 0
    # Charm included
    assert stats.resistances.cold == 15
    assert stats.fhr == 12
    assert stats.fcr == 0


def test_quest_resistances_anya(game_data_resolver: GameDataResolver):
    """Test that Prison of Ice (Anya) completion in Act V awards +10 to all resistances per difficulty."""
    from d2savior.core.d2s_struct import QuestInfo, QuestInfoData

    char = D2SStruct()
    char.version = 0x63
    char.weapon_set = 0
    char.quests = QuestInfo()
    char.quests.magic = 0x216F6F57

    # 3 difficulties: Normal, Nightmare, Hell
    norm_qd = QuestInfoData()
    norm_qd.act_5 = [0, 0, 0x1, 0, 0, 0]  # Quest 2 (Prison of Ice) completed
    nm_qd = QuestInfoData()
    nm_qd.act_5 = [0, 0, 0x1, 0, 0, 0]  # Quest 2 completed
    hell_qd = QuestInfoData()
    hell_qd.act_5 = [0, 0, 0x0, 0, 0, 0]  # Quest 2 not completed

    char.quests.qi_data = [norm_qd, nm_qd, hell_qd]

    stats = calculate_advanced_stats(char, resolver=game_data_resolver)
    assert stats.resistances.fire == 20
    assert stats.resistances.cold == 20
    assert stats.resistances.lightning == 20
    assert stats.resistances.poison == 20


def test_format_char_advanced_stats_section(game_data_resolver: GameDataResolver):
    _kind, char, _ = parse_file(SORK_D2S, resolver=game_data_resolver)
    summary = format_char_summary(char, resolver=game_data_resolver)
    info = format_char_info(char, resolver=game_data_resolver)

    assert "=== Advanced Stats ===" in summary
    assert "Resistances: Fire: +120%, Cold: +66%, Lightning: +119%, Poison: +128%" in summary
    assert "Faster Hit Recovery: +80% | Faster Cast Rate: +77% | Magic Find: +0%" in summary

    assert "=== Advanced Stats ===" in info
    assert "Resistances: Fire: +120%, Cold: +66%, Lightning: +119%, Poison: +128%" in info
    assert "Faster Hit Recovery: +80% | Faster Cast Rate: +77% | Magic Find: +0%" in info


def test_magic_find_flat_and_per_level(game_data_resolver: GameDataResolver):
    """Test flat Magic Find (stat 80) and per-level Magic Find (stat 240)."""
    char = D2SStruct()
    char.version = 0x63
    char.weapon_set = 0
    char.char_level = 80
    char.item_list = ItemList()

    # Equipped armor with +50% MF (stat 80, save_add=100 -> 150) and +1%/lvl MF (stat 240, 8/8 per level)
    armor = D2Item()
    armor.location = ItemLocation.EQUIPPED.value
    armor.position = EquipSlot.ARMOR.value
    armor.type_name = b"xpl "
    armor.item_info = ItemInfo()
    tp_a = TypeSpecificInfo()
    pl_a = PropertyList()
    pl_a.properties = [(80, 0, 150), (240, 0, 8)]
    tp_a.property_list = pl_a
    armor.item_info.type_specific_info = tp_a
    char.item_list.items.append(armor)

    # Small charm in inventory with +7% MF (stat 80, save_add=100 -> 107)
    charm = D2Item()
    charm.location = ItemLocation.STORED.value
    charm.stored_in = StoredIn.INVENTORY.value
    charm.type_name = b"cm1 "
    charm.item_info = ItemInfo()
    tp_c = TypeSpecificInfo()
    pl_c = PropertyList()
    pl_c.properties = [(80, 0, 107)]
    tp_c.property_list = pl_c
    charm.item_info.type_specific_info = tp_c
    char.item_list.items.append(charm)

    stats = calculate_advanced_stats(char, resolver=game_data_resolver)
    # 50 (armor flat) + (8 * 80 // 8 = 80) (armor per-level) + 7 (charm) = 137
    assert stats.mf == 137


def test_sork_mercenary_stats(game_data_resolver: GameDataResolver):
    """Test mercenary level, attributes, and resistances on sork.d2s."""
    kind, char, _ = parse_file(SORK_D2S, resolver=game_data_resolver)
    assert kind == "char"
    assert char is not None

    merc_stats = calculate_mercenary_stats(char, resolver=game_data_resolver)
    assert isinstance(merc_stats, MercenaryStats)
    # Act II Nightmare Holy Freeze (Id=10), Exp=49287024 -> Level 74 (Exp(74)=49284000)
    assert merc_stats.level == 74
    # Base Str at 74: 117 + (31 * 14) // 8 = 171; Gear: Lionheart (+25) + Insight (+5) = 201
    assert merc_stats.strength == 201
    # Base Dex at 74: 91 + (31 * 12) // 8 = 137; Gear: Lionheart (+15) + Insight (+5) = 157
    assert merc_stats.dexterity == 157
    # Base Res at 74: 86 + (31 * 7) // 4 = 140; Gear: Lionheart (+30) + Tal's Crest (+15) = +185
    assert merc_stats.resistances.fire == 185
    assert merc_stats.resistances.cold == 185
    assert merc_stats.resistances.lightning == 185
    assert merc_stats.resistances.poison == 185


def test_d2s_0x69_sorc_mercenary_stats(game_data_resolver: GameDataResolver):
    """Test mercenary stat calculation on 0x69 Sorc.d2s (Act I Cold Rogue, Exp=43792)."""
    kind, char, _ = parse_file(SORC_D2S, resolver=game_data_resolver)
    assert kind == "char"
    assert char is not None

    merc_stats = calculate_mercenary_stats(char, resolver=game_data_resolver)
    assert merc_stats is not None
    # Act I Ice Normal (Id=1), Exp/Lvl=105 -> Exp(7)=41160 <= 43792 < Exp(8)=60480
    assert merc_stats.level == 7
    assert merc_stats.strength == 40
    assert merc_stats.dexterity == 53
    assert merc_stats.resistances.fire == 8
    assert merc_stats.resistances.cold == 8
    assert merc_stats.resistances.lightning == 8
    assert merc_stats.resistances.poison == 8


def test_mercenary_level_tiered_exp_and_cap(game_data_resolver: GameDataResolver):
    """Test tiered Exp/Lvl progression across breakpoints and the level 98 cap."""
    vd = game_data_resolver.for_version(0x69).data
    rogue = vd.get_hireling(0)
    assert rogue is not None
    # Rogue Fire Normal (Version 100): Lv3 Exp/Lvl=100, Lv36 Exp/Lvl=110, Lv67 Exp/Lvl=120
    assert [entry.level for entry in rogue.levels] == [3, 36, 67]
    assert calculate_mercenary_level(0, rogue) == 1
    # Threshold to reach Lv 36 uses Lv 3 row (Exp/Lvl=100): 100 * 36 * 36 * 37 = 4,795,200
    assert calculate_mercenary_level(4_795_199, rogue) == 35
    assert calculate_mercenary_level(4_795_200, rogue) == 36
    # Threshold to reach Lv 37 uses Lv 36 row (Exp/Lvl=110): 110 * 37 * 37 * 38 = 5,722,420
    assert calculate_mercenary_level(5_722_419, rogue) == 36
    assert calculate_mercenary_level(5_722_420, rogue) == 37
    # Capped at 98
    assert calculate_mercenary_level(0xFFFFFFFF, rogue) == 98


def test_mercenary_gear_negative_res_and_per_level_stats(game_data_resolver: GameDataResolver):
    """Test negative item resistances, per-level scaling, and socketed runes on merc items."""
    char = D2SStruct()
    char.version = 0x69
    char.game_version = 3
    char.merc_seed = 0x12345678
    char.merc_name_index = 10
    char.merc_hireling_id = 34  # Act II Hell Holy Freeze (Id=34, Lv75 breakpoint, Exp/Lvl=130)
    # Level 80: 130 * 80 * 80 * 81 = 67,392,000
    char._merc_experience = 67_392_000

    # Helmet with +20 Str (base=-32 -> 52), -30 Fire Res (base=-50 -> 20), +70 Poison Res (base=-50 -> 120),
    # +4/8 Str/lvl (220), +4/8 Cold Res/lvl (230), socketed with Ko Rune (+10 Dex)
    helm = D2Item()
    helm.location = ItemLocation.EQUIPPED.value
    helm.position = EquipSlot.HELMET.value
    helm.type_name = b"usk "
    helm.item_info = ItemInfo()
    tp = TypeSpecificInfo()
    pl = PropertyList()
    pl.properties = [
        (0, 0, 52),
        (39, 0, 20),
        (45, 0, 120),
        (220, 0, 4),
        (230, 0, 4),
    ]
    tp.property_list = pl
    helm.item_info.type_specific_info = tp

    ko = D2Item()
    ko.type_name = b"r18 "
    helm.gem_items = [ko]

    char.mercenary.items = ItemList()
    char.mercenary.items.items = [helm]
    char.mercenary.items.count = 1

    merc_stats = calculate_mercenary_stats(char, resolver=game_data_resolver)
    assert merc_stats is not None
    assert merc_stats.level == 80
    # Base at 80 (from Lv75 row: level_ups=5): Str=173+(5*14)//8=181, Dex=139+(5*12)//8=146, Res=142+(5*4)//4=147
    # Gear Str: +20 flat + (4 * 80 // 8 = +40) = +60 -> 241
    assert merc_stats.strength == 241
    # Gear Dex: +10 (Ko rune) -> 156
    assert merc_stats.dexterity == 156
    # Gear Res: Fire -30 -> 117, Cold +(4 * 80 // 8 = 40) -> 187, Lightning +0 -> 147, Poison +70 -> 217
    assert merc_stats.resistances.fire == 117
    assert merc_stats.resistances.cold == 187
    assert merc_stats.resistances.lightning == 147
    assert merc_stats.resistances.poison == 217


def test_mercenary_stats_returns_none_when_unavailable(game_data_resolver: GameDataResolver):
    """Non-expansion, unhired, and unknown-type mercenaries should return None."""
    classic_char = D2SStruct()
    classic_char.version = 0x63
    classic_char.char_flags = 0
    assert calculate_mercenary_stats(classic_char, resolver=game_data_resolver) is None

    no_merc = D2SStruct()
    no_merc.version = 0x69
    no_merc.game_version = 3
    assert calculate_mercenary_stats(no_merc, resolver=game_data_resolver) is None

    unknown_merc = D2SStruct()
    unknown_merc.version = 0x69
    unknown_merc.game_version = 3
    unknown_merc.merc_seed = 0x1
    unknown_merc.merc_hireling_id = 999
    assert calculate_mercenary_stats(unknown_merc, resolver=game_data_resolver) is None
