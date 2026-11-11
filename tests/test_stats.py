import os

from d2s_parse import parse_file
from d2savior.core.d2data import GameDataResolver
from d2savior.core.d2s_struct import D2SStruct, ItemList
from d2savior.core.enums import EquipSlot, ItemLocation, StoredIn
from d2savior.core.formatters import format_char_info, format_char_summary
from d2savior.core.item import D2Item, ItemInfo, TypeSpecificInfo
from d2savior.core.property_list import PropertyList
from d2savior.core.stats import AdvancedStats, calculate_advanced_stats

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
SORK_D2S = os.path.join(FIXTURES_DIR, "sork.d2s")


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
    # Thul: 3-14 cold
    assert stats.damage.cold.min_damage == 3
    assert stats.damage.cold.max_damage == 14
    # Tal: 154 poison
    assert stats.damage.poison.min_damage == 154
    assert stats.damage.poison.max_damage == 154


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


def test_advanced_stats_synthetic(game_data_resolver: GameDataResolver):
    """Test synthetic character with custom items and enhanced damage."""
    char = D2SStruct()
    char.version = 0x63
    char.weapon_set = 0
    char.item_list = ItemList()

    # Create weapon with enhanced damage and fire damage
    sword = D2Item()
    sword.location = ItemLocation.EQUIPPED.value
    sword.position = EquipSlot.WEAPON_I.value
    sword.type_name = b"bsd "  # Broad Sword: base 7-14
    sword.item_info = ItemInfo()
    tp = TypeSpecificInfo()
    pl = PropertyList()
    # Stat 25 (Enhanced Damage +100%), Stat 48 (Fire min dam +10), Stat 49 (Fire max dam +20)
    pl.properties = [(25, 0, 100), (48, 0, 10), (49, 0, 20)]
    tp.property_list = pl
    sword.item_info.type_specific_info = tp
    char.item_list.items.append(sword)

    # Create inventory charm with resistances and FHR
    charm = D2Item()
    charm.location = ItemLocation.STORED.value
    charm.stored_in = StoredIn.INVENTORY.value
    charm.type_name = b"cm1 "
    charm.item_info = ItemInfo()
    tp_c = TypeSpecificInfo()
    pl_c = PropertyList()
    # Stat 39 (Fire Resist +15, save_add=200 -> raw=215), Stat 99 (FHR +12, save_add=20 -> raw=32)
    pl_c.properties = [(39, 0, 215), (99, 0, 32)]
    tp_c.property_list = pl_c
    charm.item_info.type_specific_info = tp_c
    char.item_list.items.append(charm)

    stats = calculate_advanced_stats(char, resolver=game_data_resolver)
    assert stats.resistances.fire == 15
    assert stats.fhr == 12
    assert stats.fcr == 0

    # Base 7-14 + 100% ED = 14-28
    assert stats.damage.physical_min == 14
    assert stats.damage.physical_max == 28
    assert stats.damage.fire.min_damage == 10
    assert stats.damage.fire.max_damage == 20


def test_format_char_advanced_stats_section(game_data_resolver: GameDataResolver):
    _kind, char, _ = parse_file(SORK_D2S, resolver=game_data_resolver)
    summary = format_char_summary(char, resolver=game_data_resolver)
    info = format_char_info(char, resolver=game_data_resolver)

    assert "=== Advanced Stats ===" in summary
    assert "Resistances: Fire: +100%, Cold: +46%, Lightning: +99%, Poison: +108%" in summary
    assert "Faster Hit Recovery: +80% | Faster Cast Rate: +77%" in summary
    assert "Damage: Physical: 7-14, Lightning: 1-50, Cold: 3-14, Poison: 154" in summary

    assert "=== Advanced Stats ===" in info
    assert "Resistances: Fire: +100%, Cold: +46%, Lightning: +99%, Poison: +108%" in info
    assert "Faster Hit Recovery: +80% | Faster Cast Rate: +77%" in info
    assert "Damage: Physical: 7-14, Lightning: 1-50, Cold: 3-14, Poison: 154" in info
