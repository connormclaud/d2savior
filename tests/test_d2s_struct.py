import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.d2s_struct import D2SStruct
from core.ibitstream import IBitStream
from core.obitstream import OBitStream


class TestD2SStruct:
    def test_char_class_name(self):
        char_data = D2SStruct()
        char_data.char_class = 0
        assert char_data.get_char_class_name() == "Amazon"
        char_data.char_class = 1
        assert char_data.get_char_class_name() == "Sorceress"
        char_data.char_class = 2
        assert char_data.get_char_class_name() == "Necromancer"
        char_data.char_class = 3
        assert char_data.get_char_class_name() == "Paladin"
        char_data.char_class = 4
        assert char_data.get_char_class_name() == "Barbarian"
        char_data.char_class = 5
        assert char_data.get_char_class_name() == "Druid"
        char_data.char_class = 6
        assert char_data.get_char_class_name() == "Assassin"
        char_data.char_class = 7
        assert char_data.get_char_class_name() == "Warlock"
        char_data.char_class = 8
        assert char_data.get_char_class_name() == "Unknown"

    def test_char_name(self):
        char_data = D2SStruct()
        # 测试 ASCII 名称
        char_data.name = b"TestChar\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        char_data.name_ptr = b"\x00" * 64
        char_data.version = 0x60  # 1.10 版本
        assert char_data.get_char_name() == "TestChar"

        # 测试 PTR2.4+ UTF-8 名称
        char_data.name = b"\x00" * 16
        char_data.name_ptr = b"TestCharUTF8\x00" + b"\x00" * 50
        char_data.version = 0x62  # PTR2.4 版本
        assert char_data.get_char_name() == "TestCharUTF8"

    def test_flags(self):
        char_data = D2SStruct()
        # 测试 hardcore 标志
        char_data.char_flags = 0x4
        assert char_data.is_hardcore()
        char_data.char_flags = 0x0
        assert not char_data.is_hardcore()

        # 测试 ladder 标志
        char_data.char_flags = 0x40
        assert char_data.is_ladder()
        char_data.char_flags = 0x0
        assert not char_data.is_ladder()

        # 测试 expansion 标志
        char_data.char_flags = 0x20
        assert char_data.is_expansion()
        char_data.char_flags = 0x0
        assert not char_data.is_expansion()

        # 测试 died_before 标志
        char_data.char_flags = 0x8
        assert char_data.is_died_before()
        char_data.char_flags = 0x0
        assert not char_data.is_died_before()

    def test_has_mercenary_0x63(self):
        """测试 0x63 版本雇佣兵判断逻辑: merc_control != 0"""
        char_data = D2SStruct()
        char_data.version = 0x63

        char_data.merc_control = 0
        assert not char_data.has_mercenary()

        char_data.merc_control = 1
        assert char_data.has_mercenary()

        char_data.merc_control = 0x12345678
        assert char_data.has_mercenary()

    def test_has_mercenary_0x69(self):
        """测试 0x69 版本雇佣兵判断逻辑: merc_seed!=0 or merc_name_index!=0 or merc_experience!=0"""
        char_data = D2SStruct()
        char_data.version = 0x69

        char_data.merc_seed = 0
        char_data.merc_name_index = 0
        char_data.merc_experience = 0
        assert not char_data.has_mercenary()

        char_data.merc_seed = 1
        char_data.merc_name_index = 0
        char_data.merc_experience = 0
        assert char_data.has_mercenary()

        char_data.merc_seed = 0
        char_data.merc_name_index = 1
        char_data.merc_experience = 0
        assert char_data.has_mercenary()

        char_data.merc_seed = 0
        char_data.merc_name_index = 0
        char_data.merc_experience = 1
        assert char_data.has_mercenary()

        char_data.merc_seed = 0x12345678
        char_data.merc_name_index = 0
        char_data.merc_experience = 0
        assert char_data.has_mercenary()

    def test_has_mercenary_classic(self):
        """测试 Classic 版本雇佣兵判断逻辑: merc_name > 0"""
        char_data = D2SStruct()
        char_data.version = 0x60

        char_data.merc_name = 0
        assert not char_data.has_mercenary()

        char_data.merc_name = 1
        assert char_data.has_mercenary()

    def test_is_expansion_0x63_charflags(self):
        """测试 0x63 版本资料片判断: char_flags & 0x20"""
        char_data = D2SStruct()
        char_data.version = 0x63
        char_data.quests = None

        char_data.char_flags = 0x20
        assert char_data.is_expansion()

        char_data.char_flags = 0x00
        assert not char_data.is_expansion()

        char_data.char_flags = 0x24
        assert char_data.is_expansion()

    def test_is_expansion_0x63_acts(self):
        """测试 0x63 版本资料片判断回退: QuestInfo.dwActs >= 5"""
        from core.d2s_struct import QuestInfo

        char_data = D2SStruct()
        char_data.version = 0x63
        char_data.char_flags = 0x00
        char_data.quests = QuestInfo()

        char_data.quests.acts = 4
        assert not char_data.is_expansion()

        char_data.quests.acts = 5
        assert char_data.is_expansion()

    def test_is_expansion_0x69(self):
        """测试 0x69 版本资料片判断: game_version > 1"""
        char_data = D2SStruct()
        char_data.version = 0x69

        char_data.game_version = 1
        assert not char_data.is_expansion()

        char_data.game_version = 2
        assert char_data.is_expansion()

        char_data.game_version = 3
        assert char_data.is_expansion()

    def test_player_stats_magic(self):
        """测试 PlayerStats 魔法数"""
        from core.d2s_struct import PlayerStats

        ps = PlayerStats()
        assert ps.magic == 0
        assert len(ps.stat_values) == 16

    def test_player_stats_read_data(self):
        """测试 PlayerStats 从 bitstream 解析"""
        from core.d2s_struct import PlayerStats

        player_stats_bits_count = [10, 10, 10, 10, 10, 8, 21, 21, 21, 21, 21, 21, 7, 32, 25, 25]

        obs = OBitStream()
        obs.write_word(0x6667)
        obs.write_bits(9, 0)
        obs.write_bits(player_stats_bits_count[0], 50)
        obs.write_bits(9, 3)
        obs.write_bits(player_stats_bits_count[3], 25)
        obs.write_bits(9, 0x10)
        obs.align_byte()

        bs = IBitStream(obs.get_data())
        ps = PlayerStats()
        ps.deserialize(bs)

        assert ps.magic == 26215
        assert ps.stat_values[0] == 50
        assert ps.stat_values[3] == 25

    def test_player_stats_invalid_magic(self):
        """测试 PlayerStats 无效魔法数时跳过解析"""
        from core.d2s_struct import PlayerStats

        obs = OBitStream()
        obs.write_word(0x1234)
        obs.align_byte()

        bs = IBitStream(obs.get_data())
        ps = PlayerStats()
        ps.deserialize(bs)

        assert ps.magic != 26215

    def test_player_stats_all_stats(self):
        """测试 PlayerStats 解析所有16个属性"""
        from core.d2s_struct import PlayerStats

        player_stats_bits_count = [10, 10, 10, 10, 10, 8, 21, 21, 21, 21, 21, 21, 7, 32, 25, 25]
        test_values = [
            100,
            200,
            300,
            400,
            500,
            200,
            100000,
            200000,
            300000,
            400000,
            500000,
            600000,
            50,
            0xDEADBEEF,
            1000000,
            2000000,
        ]

        obs = OBitStream()
        obs.write_word(0x6667)
        for i in range(16):
            obs.write_bits(9, i)
            max_val = (1 << player_stats_bits_count[i]) - 1
            obs.write_bits(player_stats_bits_count[i], min(test_values[i], max_val))
        obs.write_bits(9, 0x10)
        obs.align_byte()

        bs = IBitStream(obs.get_data())
        ps = PlayerStats()
        ps.deserialize(bs)

        assert ps.magic == 26215
        for i in range(16):
            max_val = (1 << player_stats_bits_count[i]) - 1
            expected = min(test_values[i], max_val)
            assert ps.stat_values[i] == expected, (
                f"Stat index {i}: expected {expected}, got {ps.stat_values[i]}"
            )

    def test_demon_default(self):
        """测试 Demon 默认状态"""
        from core.d2s_struct import Demon

        demon = Demon()
        assert not demon.has_demon
        assert demon.magic == 0

    def test_demon_read_data_no_demon(self):
        """测试 Demon 解析: 无 Demon 数据 (has_demon=False)"""
        from core.d2s_struct import Demon

        obs = OBitStream()
        obs.write_word(1)
        obs.write_word(0x666C)
        obs.write_byte(0)
        obs.write_byte(0)
        obs.align_byte()

        bs = IBitStream(obs.get_data())
        demon = Demon()
        demon.deserialize(bs)

        assert demon.magic == 26220
        assert not demon.has_demon

    def test_demon_read_data_invalid_magic(self):
        """测试 Demon 解析: 无效魔法数时跳过"""
        from core.d2s_struct import Demon

        obs = OBitStream()
        obs.write_word(1)
        obs.write_word(0x1234)
        obs.align_byte()

        bs = IBitStream(obs.get_data())
        demon = Demon()
        demon.deserialize(bs)

        assert demon.magic != 26220
        assert not demon.has_demon

    def test_char_name_0x69(self):
        """测试 0x69 版本角色名称从 name 字段读取"""
        char_data = D2SStruct()
        char_data.version = 0x69
        char_data.name = b"D2RChar\x00" + b"\x00" * 8
        assert char_data.get_char_name() == "D2RChar"

    def test_equip_slot_enum(self):
        from core.enums import EquipSlot

        expected = {
            1: "Helmet",
            2: "Amulet",
            3: "Armor",
            4: "Weapon I",
            5: "Shield I",
            6: "Ring (Right)",
            7: "Ring (Left)",
            8: "Belt",
            9: "Boots",
            10: "Gloves",
            11: "Weapon II",
            12: "Shield II",
        }
        for pos, name in expected.items():
            assert str(EquipSlot(pos)) == name
            assert EquipSlot(pos).display_name == name

    def test_format_item_info_equipped_position(self):
        from core.enums import ItemLocation
        from core.formatters import format_item_info
        from core.item import D2Item, ItemInfo

        item = D2Item()
        item.item_info = ItemInfo()
        item.type_name = b"bsd "
        item.location = int(ItemLocation.EQUIPPED)
        item.position = 4

        full_text = format_item_info(item)
        assert isinstance(full_text, str)
        assert "Location: EQUIPPED, Position: 4 (Weapon I)" in full_text

        # Stored item should not have equip slot name
        item_stored = D2Item()
        item_stored.item_info = ItemInfo()
        item_stored.type_name = b"bsd "
        item_stored.location = int(ItemLocation.STORED)
        item_stored.position = 0
        full_text_stored = format_item_info(item_stored)
        assert isinstance(full_text_stored, str)
        assert "Location: STORED, Position: 0" in full_text_stored
        assert "Weapon" not in full_text_stored

    def test_format_timestamp(self):
        from core.formatters import format_timestamp

        assert format_timestamp(0) == "N/A"
        assert format_timestamp(4294967295) == "N/A"
        assert format_timestamp(-1) == "N/A"
        assert format_timestamp(1793981148) == "2026-11-06 16:05:48 UTC"

    def test_format_duration(self):
        from core.formatters import format_duration

        assert format_duration(4294967295) == "N/A"
        assert format_duration(-5) == "N/A"
        assert format_duration(0) == "0s"
        assert format_duration(45) == "45s"
        assert format_duration(3600) == "1h"
        assert format_duration(3665) == "1h 1m 5s"
        assert format_duration(90061) == "1d 1h 1m 1s"

    def test_format_char_info_waypoints_and_quests(self):
        from core.formatters import format_char_info

        char = D2SStruct()
        char.version = 0x69
        char.name = b"TestHero\x00" + b"\x00" * 7
        char.char_class = 1

        # Setup waypoints
        char.waypoints.magic = 0x5357
        # Normal: all 39 waypoints active (5 bytes: 0xFF, 0xFF, 0xFF, 0xFF, 0x7F)
        char.waypoints.wp[0].waypoints = [0xFF, 0xFF, 0xFF, 0xFF, 0x7F]
        # Nightmare: bit 2 (Stony Field) missing in Act 1
        char.waypoints.wp[1].waypoints = [0xFB, 0xFF, 0xFF, 0xFF, 0x7F]
        # Hell: none active
        char.waypoints.wp[2].waypoints = [0x00, 0x00, 0x00, 0x00, 0x00]

        # Setup quests
        char.quests.magic = 0x216F6F57
        # Normal: all completed, Akara reset used
        char.quests.qi_data[0].reset_stats = 1
        char.quests.qi_data[0].act_1 = [1] * 6
        char.quests.qi_data[0].act_2 = [1] * 6
        char.quests.qi_data[0].act_3 = [1] * 6
        char.quests.qi_data[0].act_4 = [1] * 3
        char.quests.qi_data[0].act_5 = [1] * 6

        # Nightmare: Akara reset available
        # Act I quest 2 (Tools of the Trade): reward unclaimed (0x804a)
        # Act V quest 0 (Siege on Harrogath): reward unclaimed (0x8022)
        # Act V quest 3 (Betrayal of Harrogath): not attempted (0x000c)
        char.quests.qi_data[1].reset_stats = 2
        char.quests.qi_data[1].act_1 = [1, 1, 0x804A, 1, 1, 1]
        char.quests.qi_data[1].act_2 = [1] * 6
        char.quests.qi_data[1].act_3 = [1] * 6
        char.quests.qi_data[1].act_4 = [1] * 3
        char.quests.qi_data[1].act_5 = [0x8022, 1, 1, 0x000C, 1, 1]

        # Hell: not started, reset locked
        char.quests.qi_data[2].reset_stats = 0
        char.quests.qi_data[2].act_1 = [0] * 6
        char.quests.qi_data[2].act_2 = [0] * 6
        char.quests.qi_data[2].act_3 = [0] * 6
        char.quests.qi_data[2].act_4 = [0] * 3
        char.quests.qi_data[2].act_5 = [0] * 6

        output = format_char_info(char)

        # Check waypoints
        assert "Normal (39/39 unlocked): All unlocked" in output
        assert "Nightmare (38/39 unlocked, 1 missing):" in output
        assert "Act I (8/9): Missing Stony Field" in output
        assert "Act II (9/9): All unlocked" in output
        assert "Hell: Not started" in output

        # Check quests
        assert "Normal (27/27 completed) — Akara Reset: Used" in output
        assert "Act I: [x] [x] [x] [x] [x] [x]" in output
        assert "Nightmare (26/27 completed, 2 rewards unclaimed) — Akara Reset: Available" in output
        assert "Act I: [x] [x] [x] [x] [!] Tools of the Trade (reward unclaimed) [x]" in output
        assert (
            "Act V: [!] Siege on Harrogath (reward unclaimed) [x] [x] [ ] Betrayal of Harrogath [x] [x]"
            in output
        )

    def test_player_stats_properties(self):
        from core.d2s_struct import PLAYER_STATS_MAGIC, PlayerStats

        stats = PlayerStats()
        assert not stats.is_valid

        stats.magic = PLAYER_STATS_MAGIC
        assert stats.is_valid

        stats.stat_values[0] = 100  # str
        stats.stat_values[1] = 50  # ene
        stats.stat_values[2] = 75  # dex
        stats.stat_values[3] = 120  # vit
        stats.stat_values[4] = 5  # stat pts
        stats.stat_values[5] = 2  # skill pts
        stats.stat_values[6] = 500 << 8  # cur life
        stats.stat_values[7] = 600 << 8  # max life
        stats.stat_values[8] = 200 << 8  # cur mana
        stats.stat_values[9] = 250 << 8  # max mana
        stats.stat_values[0xA] = 150 << 8  # cur stam
        stats.stat_values[0xB] = 180 << 8  # max stam
        stats.stat_values[0xC] = 85  # level
        stats.stat_values[0xD] = 1234567  # exp
        stats.stat_values[0xE] = 10000  # gold
        stats.stat_values[0xF] = 2500000  # gold stash

        assert stats.strength == 100
        assert stats.energy == 50
        assert stats.dexterity == 75
        assert stats.vitality == 120
        assert stats.stat_points_remaining == 5
        assert stats.skill_points_remaining == 2
        assert stats.current_life == 500
        assert stats.max_life == 600
        assert stats.current_mana == 200
        assert stats.max_mana == 250
        assert stats.current_stamina == 150
        assert stats.max_stamina == 180
        assert stats.level == 85
        assert stats.experience == 1234567
        assert stats.gold == 10000
        assert stats.gold_stash == 2500000

    def test_mercenary_properties(self):
        # Version < 0x69
        char_v60 = D2SStruct()
        char_v60.version = 0x60
        char_v60.merc_name = 12
        char_v60.merc_type = 3
        char_v60.merc_exp = 99999
        char_v60.merc_dead = 1
        assert char_v60.merc_name_id == 12
        assert char_v60.merc_type_id == 3
        assert char_v60.merc_experience == 99999
        assert char_v60.merc_is_dead

        # Version >= 0x69
        char_v69 = D2SStruct()
        char_v69.version = 0x69
        char_v69.merc_name_index = 42
        char_v69.merc_hireling_id = 7
        char_v69.merc_experience = 1500000
        assert char_v69.merc_name_id == 42
        assert char_v69.merc_type_id == 7
        assert char_v69.merc_experience == 1500000
        assert not char_v69.merc_is_dead

    def test_quest_info_data_travel_properties(self):
        from core.d2s_struct import QuestInfoData

        qid = QuestInfoData()
        assert qid.travel_1 == 0
        assert qid.travel_2 == 0
        assert qid.travel_3 == 0
        assert qid.travel_4 == 0

        # Pythonic attributes
        qid.travel_1 = 1
        qid.travel_2 = 2
        qid.travel_3 = 3
        qid.travel_4 = 4
        assert qid.travel_1 == 1
        assert qid.travel_2 == 2
        assert qid.travel_3 == 3
        assert qid.travel_4 == 4
