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
    # Resistances:
    # Fire: 18 (amulet) + 17 (ring) + 17 (boots) + 16 (gloves) + 12 (grand charm) + 20 (grand charm) = 100
    assert stats.resistances.fire == 100
    # Cold: 18 (amulet) + 20 (boots) + 8 (grand charm) = 46
    assert stats.resistances.cold == 46
    # Lightning: 30 (Lore) + 18 (amulet) + 16 (ring) + 14 (grand charm) + 6 (small charm) + 7 (small charm) + 8 (large charm) = 99
    assert stats.resistances.lightning == 99
    # Poison: 30 (Stealth) + 18 (amulet) + 9 (ring) + 18 (belt) + 25 (gloves) + 8 (small charm) = 108
    assert stats.resistances.poison == 108

    # FHR: 25 (Stealth) + 55 (Spirit) = 80
    assert stats.fhr == 80

    # FCR: 25 (Stealth) + 34 (Spirit) + 10 (Manald) + 8 (Demon Clasp) = 77
    assert stats.fcr == 77

    # Damage: Broad sword (7-14) base physical
    assert stats.damage.physical_min == 7
    assert stats.damage.physical_max == 14
    # Elemental damage from Spirit socketed runes:
    # Ort: 1-50 lightning
    assert stats.damage.lightning.min_damage == 1
    assert stats.damage.lightning.max_damage == 50
    # Thul: 3-14 cold (75 frames = 3.0s)
    assert stats.damage.cold.min_damage == 3
    assert stats.damage.cold.max_damage == 14
    assert stats.damage.cold.duration == 75
    assert stats.damage.cold.duration_seconds == 3.0
    # Tal: 154 poison (125 frames = 5.0s)
    assert stats.damage.poison.min_damage == 154
    assert stats.damage.poison.max_damage == 154
    assert stats.damage.poison.duration == 125
    assert stats.damage.poison.duration_seconds == 5.0


def test_d2s_0x69_sorc_advanced_stats(game_data_resolver: GameDataResolver):
    """Test advanced stats calculation on 0x69 save file (Sorc.d2s)."""
    kind, char, _ = parse_file(SORC_D2S, resolver=game_data_resolver)
    assert kind == "char"
    assert char is not None
    assert char.version == 0x69

    stats = calculate_advanced_stats(char, resolver=game_data_resolver)
    assert isinstance(stats, AdvancedStats)
    # Check that stats calculation executes safely and returns populated or zero values
    assert isinstance(stats.resistances.fire, int)
    assert isinstance(stats.fhr, int)
    assert isinstance(stats.fcr, int)
    assert isinstance(stats.damage.physical_min, int)


def test_weapon_set_switch(game_data_resolver: GameDataResolver):
    kind, char, _ = parse_file(SORK_D2S, resolver=game_data_resolver)
    assert kind == "char"
    assert char is not None

    # Switch to Weapon Set II (Bone wand + Rhyme shield)
    char.weapon_set = 1
    stats = calculate_advanced_stats(char, resolver=game_data_resolver)

    # Rhyme adds All Resistances +25
    # Bone wand removes Spirit (+55 FHR, +34 FCR, and runes)
    assert stats.resistances.fire == 125
    assert stats.resistances.cold == 71
    assert stats.resistances.lightning == 124
    assert stats.resistances.poison == 133

    assert stats.fhr == 25  # Only Stealth remains
    assert stats.fcr == 43  # 77 - 34 = 43

    # Bone wand base damage is 3-7
    assert stats.damage.physical_min == 3
    assert stats.damage.physical_max == 7
    # Spirit socketables are unequipped in weapon set II
    assert stats.damage.lightning.max_damage == 0
    assert stats.damage.cold.max_damage == 0
    assert stats.damage.poison.max_damage == 0


def test_advanced_stats_weapon_and_offweapon_ed(game_data_resolver: GameDataResolver):
    """Test damage formula: D = (Base * (1 + Weapon_ED) + Flat) * (1 + OffWeapon_ED)."""
    char = D2SStruct()
    char.version = 0x63
    char.weapon_set = 0
    char.item_list = ItemList()

    # Weapon: Broad Sword (base 7-14) with +100% Weapon ED (stat 25)
    sword = D2Item()
    sword.location = ItemLocation.EQUIPPED.value
    sword.position = EquipSlot.WEAPON_I.value
    sword.type_name = b"bsd "
    sword.item_info = ItemInfo()
    tp_s = TypeSpecificInfo()
    pl_s = PropertyList()
    pl_s.properties = [(25, 0, 100)]  # 100% weapon ED -> 14-28
    tp_s.property_list = pl_s
    sword.item_info.type_specific_info = tp_s
    char.item_list.items.append(sword)

    # Ring: +10 min and +10 max flat damage (stats 21, 22)
    ring = D2Item()
    ring.location = ItemLocation.EQUIPPED.value
    ring.position = EquipSlot.RING_RIGHT.value
    ring.type_name = b"rin "
    ring.item_info = ItemInfo()
    tp_r = TypeSpecificInfo()
    pl_r = PropertyList()
    pl_r.properties = [(21, 0, 10), (22, 0, 10)]
    tp_r.property_list = pl_r
    ring.item_info.type_specific_info = tp_r
    char.item_list.items.append(ring)

    # Armor: Lionheart (+20% off-weapon ED on stat 25)
    armor = D2Item()
    armor.location = ItemLocation.EQUIPPED.value
    armor.position = EquipSlot.ARMOR.value
    armor.type_name = b"stu "
    armor.item_info = ItemInfo()
    tp_a = TypeSpecificInfo()
    pl_a = PropertyList()
    pl_a.properties = [(25, 0, 20)]
    tp_a.property_list = pl_a
    armor.item_info.type_specific_info = tp_a
    char.item_list.items.append(armor)

    # Formula check:
    # Min: (7 * (1 + 1.0) + 10) * (1 + 0.20) = (14 + 10) * 1.2 = 24 * 1.2 = 28
    # Max: (14 * (1 + 1.0) + 10) * (1 + 0.20) = (28 + 10) * 1.2 = 38 * 1.2 = 45
    stats = calculate_advanced_stats(char, resolver=game_data_resolver)
    assert stats.damage.physical_min == 28
    assert stats.damage.physical_max == 45


def test_advanced_stats_bow_and_ethereal(game_data_resolver: GameDataResolver):
    """Test ranged bow base damage and ethereal bonus (+50%)."""
    char = D2SStruct()
    char.version = 0x63
    char.weapon_set = 0
    char.item_list = ItemList()

    # Short Bow: 2handmindam=1, 2handmaxdam=4
    bow = D2Item()
    bow.location = ItemLocation.EQUIPPED.value
    bow.position = EquipSlot.WEAPON_I.value
    bow.type_name = b"sbw "
    bow.is_ethereal = True
    char.item_list.items.append(bow)

    # Ethereal bonus (+50%): 1 * 1.5 = 1, 4 * 1.5 = 6
    stats = calculate_advanced_stats(char, resolver=game_data_resolver)
    assert stats.damage.physical_min == 1
    assert stats.damage.physical_max == 6


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


def test_format_char_advanced_stats_section(game_data_resolver: GameDataResolver):
    _kind, char, _ = parse_file(SORK_D2S, resolver=game_data_resolver)
    summary = format_char_summary(char, resolver=game_data_resolver)
    info = format_char_info(char, resolver=game_data_resolver)

    assert "=== Advanced Stats ===" in summary
    assert "Gear Resistances: Fire: +100%, Cold: +46%, Lightning: +99%, Poison: +108%" in summary
    assert "Faster Hit Recovery: +80% | Faster Cast Rate: +77%" in summary
    assert (
        "Damage: Physical: 7-14, Lightning: 1-50, Cold: 3-14 (3.0s), Poison: 154 over 5.0s"
        in summary
    )

    assert "=== Advanced Stats ===" in info
    assert "Gear Resistances: Fire: +100%, Cold: +46%, Lightning: +99%, Poison: +108%" in info
    assert "Faster Hit Recovery: +80% | Faster Cast Rate: +77%" in info
    assert (
        "Damage: Physical: 7-14, Lightning: 1-50, Cold: 3-14 (3.0s), Poison: 154 over 5.0s" in info
    )
