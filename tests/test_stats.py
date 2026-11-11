import os

from d2s_parse import parse_file
from d2savior.core.d2data import GameDataResolver
from d2savior.core.d2s_struct import D2SStruct, ItemList
from d2savior.core.enums import ItemLocation, StoredIn
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


def test_weapon_set_switch(game_data_resolver: GameDataResolver):
    kind, char, _ = parse_file(SORK_D2S, resolver=game_data_resolver)
    assert kind == "char"
    assert char is not None

    # Switch to Weapon Set II (Bone wand + Rhyme shield)
    char.weapon_set = 1
    stats = calculate_advanced_stats(char, resolver=game_data_resolver)

    # Rhyme adds All Resistances +25
    # Bone wand removes Spirit (+55 FHR, +34 FCR)
    assert stats.resistances.fire == 125
    assert stats.resistances.cold == 71
    assert stats.resistances.lightning == 124
    assert stats.resistances.poison == 133

    assert stats.fhr == 25  # Only Stealth remains
    assert stats.fcr == 43  # 77 - 34 = 43


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
    assert "Resistances: Fire: +100%, Cold: +46%, Lightning: +99%, Poison: +108%" in summary
    assert "Faster Hit Recovery: +80% | Faster Cast Rate: +77%" in summary

    assert "=== Advanced Stats ===" in info
    assert "Resistances: Fire: +100%, Cold: +46%, Lightning: +99%, Poison: +108%" in info
    assert "Faster Hit Recovery: +80% | Faster Cast Rate: +77%" in info
