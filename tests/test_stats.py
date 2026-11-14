import os

from d2s_parse import parse_file
from d2savior.core.char_formatter import format_char_info, format_char_summary
from d2savior.core.d2s_struct import D2SStruct, ItemList
from d2savior.core.enums import EquipSlot, ItemLocation, StoredIn
from d2savior.core.item import D2Item, ExtItemInfo, ItemInfo, TypeSpecificInfo
from d2savior.core.property_list import PropertyList
from d2savior.core.resolver import GameDataResolver
from d2savior.core.stats import (
    AdvancedStats,
    MercenaryStats,
    ResistanceStats,
    calculate_advanced_stats,
    calculate_mercenary_level,
    calculate_mercenary_stats,
    get_current_difficulty,
    get_difficulty_resist_penalty,
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

    # FRW: 25 (Stealth) + 20 (Boots) + 5 (Large Charm) = 50; IAS: 0
    assert stats.frw == 50
    assert stats.ias == 0

    # Skills: +1 (Lore) + 2 (Spirit) = +3 All; +1 (Visceratuant) Sorceress
    assert stats.all_skills == 3
    assert stats.class_skills == 1

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
    assert stats.frw == 50
    assert stats.all_skills == 1  # Lore only (Spirit swapped out)
    assert stats.class_skills == 0  # Visceratuant swapped out
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
    assert (
        "Resistances (Nightmare): Fire: 75% (+120%), Cold: 26% (+66%), Lightning: 75% (+119%), Poison: 75% (+128%)"
        in summary
    )
    assert "All Skills: +3 | Sorceress Skills: +1" in summary
    assert (
        "Faster Hit Recovery: +80% | Faster Cast Rate: +77% | Faster Run/Walk: +50% | Increased Attack Speed: +0% | Magic Find: +0%"
        in summary
    )

    assert "=== Advanced Stats ===" in info
    assert (
        "Resistances (Nightmare): Fire: 75% (+120%), Cold: 26% (+66%), Lightning: 75% (+119%), Poison: 75% (+128%)"
        in info
    )
    assert "All Skills: +3 | Sorceress Skills: +1" in info
    assert (
        "Faster Hit Recovery: +80% | Faster Cast Rate: +77% | Faster Run/Walk: +50% | Increased Attack Speed: +0% | Magic Find: +0%"
        in info
    )


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


def test_difficulty_detection_and_resist_penalties():
    """Verify current difficulty resolution from town bytes / fallbacks and resist penalties."""
    char = D2SStruct()
    char.version = 0x69
    char.game_version = 3
    assert get_current_difficulty(char) == 0
    assert get_difficulty_resist_penalty(char) == 0

    char.town = b"\x00\x80\x00"  # Nightmare Act I
    char.char_title = 10  # Champion (unlocked Hell, currently in Nightmare)
    assert get_current_difficulty(char) == 1
    assert get_difficulty_resist_penalty(char) == -40

    char.town = b"\x00\x00\x84"  # Hell Act V
    assert get_current_difficulty(char) == 2
    assert get_difficulty_resist_penalty(char) == -100

    # Fallback when town bytes are unset: char_title determines unlocked difficulty
    no_town = D2SStruct()
    no_town.version = 0x69
    no_town.game_version = 3
    no_town.char_title = 15
    assert get_current_difficulty(no_town) == 2

    # Classic difficulty penalties (-20 Nightmare, -50 Hell)
    classic = D2SStruct()
    classic.version = 0x69
    classic.game_version = 0
    classic.town = b"\x00\x80\x00"
    assert get_difficulty_resist_penalty(classic) == -20
    classic.town = b"\x00\x00\x80"
    assert get_difficulty_resist_penalty(classic) == -50


def test_effective_resistances_formatting_and_max_caps(game_data_resolver: GameDataResolver):
    """Effective resistances apply difficulty penalties, min -100% floor, and max resist caps."""
    raw = ResistanceStats(fire=170, cold=179, lightning=208, poison=167)
    assert (
        raw.format_summary(-100)
        == "Fire: 70% (+170%), Cold: 75% (+179%), Lightning: 75% (+208%), Poison: 67% (+167%)"
    )

    # Boosted max resist (e.g. +10 max poison capped below hard 95%) and -100% minimum floor
    extreme = ResistanceStats(fire=200, cold=-50, lightning=50, poison=200)
    max_res = ResistanceStats(fire=95, cold=75, lightning=75, poison=85)
    assert (
        extreme.format_summary(-100, max_res)
        == "Fire: 95% (+200%), Cold: -100% (-50%), Lightning: -50% (+50%), Poison: 85% (+200%)"
    )

    # Paladin character in Hell with gear +max fire resist, passive Resist Lightning (10 pts = +5% max),
    # and mercenary with Andariel's Visage (-30% Fire, +10% Max Poison).
    char = D2SStruct()
    char.version = 0x69
    char.game_version = 3
    char.char_class = 3  # Paladin
    char.char_level = 85
    char.town = b"\x00\x00\x80"  # Hell
    char.item_list = ItemList()
    char.skills.magic = 0x6669
    char.skills.skill_levels[14] = 10  # Resist Lightning -> +5% max lightning resist

    armor = D2Item()
    armor.location = ItemLocation.EQUIPPED.value
    armor.position = EquipSlot.ARMOR.value
    armor.type_name = b"xpl "
    armor.item_info = ItemInfo()
    tp = TypeSpecificInfo()
    pl = PropertyList()
    # raw fire +190, light +190, cold +120, poison +160 (Save Add=50), +5 max fire resist (stat 40, Save Add=0)
    pl.properties = [(39, 0, 240), (41, 0, 240), (43, 0, 170), (45, 0, 210), (40, 0, 5)]
    tp.property_list = pl
    armor.item_info.type_specific_info = tp
    char.item_list.items.append(armor)

    # Mercenary with lvl 80 base (+147 all res) + helm (-30% fire, +70% poison, +10% max poison)
    char.merc_seed = 0x12345678
    char.merc_name_index = 10
    char.merc_hireling_id = 34
    char._merc_experience = 67_392_000

    merc_helm = D2Item()
    merc_helm.location = ItemLocation.EQUIPPED.value
    merc_helm.position = EquipSlot.HELMET.value
    merc_helm.type_name = b"usk "
    merc_helm.item_info = ItemInfo()
    merc_tp = TypeSpecificInfo()
    merc_pl = PropertyList()
    # Save Add=-50 for resists: 20 -> -30 fire, 120 -> +70 poison; Save Add=0 for max poison (+10)
    merc_pl.properties = [(39, 0, 20), (45, 0, 120), (46, 0, 10)]
    merc_tp.property_list = merc_pl
    merc_helm.item_info.type_specific_info = merc_tp
    char.mercenary.items = ItemList()
    char.mercenary.items.items = [merc_helm]
    char.mercenary.items.count = 1

    summary = format_char_summary(char, resolver=game_data_resolver)
    assert (
        "Resistances (Hell): Fire: 80% (+190%), Cold: 20% (+120%), Lightning: 80% (+190%), Poison: 60% (+160%)"
        in summary
    )
    assert (
        "Resistances (Hell): Fire: 17% (+117%), Cold: 47% (+147%), Lightning: 47% (+147%), Poison: 85% (+217%)"
        in summary
    )

    info = format_char_info(char, resolver=game_data_resolver)
    assert (
        "Mercenary Resistances (Hell): Fire: 17% (+117%), Cold: 47% (+147%), Lightning: 47% (+147%), Poison: 85% (+217%)"
        in info
    )


def test_effective_skills_and_speed_bonuses(game_data_resolver: GameDataResolver):
    """Test +All/+Class/+Tab/+Single/+Fire/+Oskill effective levels, FRW, IAS, and swap exclusion."""
    char = D2SStruct()
    char.version = 0x69
    char.game_version = 3
    char.char_class = 1  # Sorceress
    char.weapon_set = 0
    char.town = b"\x00\x00\x80"
    char.skills.magic = 0x6669
    # Warmth (idx 1, Fire), Teleport (idx 18, Lightning), Blizzard (idx 23, Cold), Cold Mastery (idx 29, Cold)
    char.skills.skill_levels[1] = 1
    char.skills.skill_levels[18] = 1
    char.skills.skill_levels[23] = 20
    char.skills.skill_levels[29] = 20

    char.item_list = ItemList()

    def _make_item(slot: EquipSlot, props: list[tuple[int, int, int]]) -> D2Item:
        it = D2Item()
        it.location = ItemLocation.EQUIPPED.value
        it.position = slot.value
        it.type_name = b"amu "
        it.item_info = ItemInfo()
        tp = TypeSpecificInfo()
        pl = PropertyList()
        pl._use_stat_cost = True
        pl.properties = props
        tp.property_list = pl
        it.item_info.type_specific_info = tp
        return it

    # Active gear: +2 All Skills, +2 Sorceress Skills, +1 Cold Spells (tab=2, class=1 -> layer 10),
    # +3 Blizzard (skill 59), +1 Fire Skills (stat 126, elem 1), +4 Teleport oskill (stat 97, capped +3),
    # +20% IAS (stat 93), +30% FRW (stat 96), plus wrong-class +2 Amazon Skills (ignored).
    char.item_list.items.append(
        _make_item(
            EquipSlot.AMULET,
            [
                (127, 0, 2),  # +2 All Skills
                (83, 1, 2),  # +2 Sorceress Skills
                (83, 0, 2),  # +2 Amazon Skills (ignored)
                (188, (1 << 3) | 2, 1),  # +1 Cold Spells (Sorceress Only)
                (107, 59, 3),  # +3 Blizzard
                (126, 1, 1),  # +1 Fire Skills
                (97, 54, 4),  # +4 Teleport oskill (own-class cap +3)
                (93, 0, 20),  # +20% IAS
                (96, 0, 30),  # +30% FRW
            ],
        )
    )

    # Inactive swap weapon (Call to Arms +1 All Skills) should NOT apply while weapon_set == 0
    char.item_list.items.append(_make_item(EquipSlot.WEAPON_II, [(127, 0, 1)]))

    stats = calculate_advanced_stats(char, resolver=game_data_resolver)
    assert stats.all_skills == 2
    assert stats.class_skills == 2
    assert stats.skill_tab_bonuses == {2: 1}
    assert stats.fire_skills == 1
    assert stats.ias == 20
    assert stats.frw == 30

    summary = format_char_summary(char, resolver=game_data_resolver)
    # Warmth: 1 + 2 all + 2 sorc + 1 fire = 6
    assert "Warmth: 1 (6)" in summary
    # Teleport: 1 + 2 all + 2 sorc + min(4, 3) oskill = 8
    assert "Teleport: 1 (8)" in summary
    # Blizzard: 20 + 2 all + 2 sorc + 1 cold + 3 blizzard = 28
    assert "Blizzard: 20 (28)" in summary
    # Cold Mastery: 20 + 2 all + 2 sorc + 1 cold = 25
    assert "Cold Mastery: 20 (25)" in summary
    assert "All Skills: +2 | Sorceress Skills: +2 | Cold Spells: +1 | Fire Skills: +1" in summary
    assert "Faster Run/Walk: +30% | Increased Attack Speed: +20%" in summary

    info = format_char_info(char, resolver=game_data_resolver)
    assert "Skill 23 (Blizzard): 20 (28)" in info
    assert "All Skills: +2 | Sorceress Skills: +2 | Cold Spells: +1 | Fire Skills: +1" in info

    # Without any +skills gear, unboosted skills omit redundant "(base)"
    char.item_list.items = []
    plain_summary = format_char_summary(char, resolver=game_data_resolver)
    assert "Blizzard: 20, Cold Mastery: 20" in plain_summary
    assert "20 (20)" not in plain_summary
