import os

from d2s_parse import parse_file
from d2savior.core.d2data import GameDataResolver
from d2savior.core.d2s_struct import D2SStruct, ItemList
from d2savior.core.enums import EquipSlot, ItemLocation, StoredIn
from d2savior.core.formatters import format_char_info, format_char_summary
from d2savior.core.item import D2Item, ExtItemInfo, ItemInfo, TypeSpecificInfo
from d2savior.core.property_list import PropertyList
from d2savior.core.stats import AdvancedStats, calculate_advanced_stats

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
    assert "Faster Hit Recovery: +80% | Faster Cast Rate: +77%" in summary

    assert "=== Advanced Stats ===" in info
    assert "Resistances: Fire: +120%, Cold: +66%, Lightning: +119%, Poison: +128%" in info
    assert "Faster Hit Recovery: +80% | Faster Cast Rate: +77%" in info
