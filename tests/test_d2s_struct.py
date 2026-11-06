import unittest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.d2s_struct import D2SStruct
from core.ibitstream import IBitStream
from core.obitstream import OBitStream

class TestD2SStruct(unittest.TestCase):
    def test_char_class_name(self):
        char_data = D2SStruct()
        char_data.charClass = 0
        self.assertEqual(char_data.get_char_class_name(), "Amazon")
        char_data.charClass = 1
        self.assertEqual(char_data.get_char_class_name(), "Sorceress")
        char_data.charClass = 2
        self.assertEqual(char_data.get_char_class_name(), "Necromancer")
        char_data.charClass = 3
        self.assertEqual(char_data.get_char_class_name(), "Paladin")
        char_data.charClass = 4
        self.assertEqual(char_data.get_char_class_name(), "Barbarian")
        char_data.charClass = 5
        self.assertEqual(char_data.get_char_class_name(), "Druid")
        char_data.charClass = 6
        self.assertEqual(char_data.get_char_class_name(), "Assassin")
        char_data.charClass = 7
        self.assertEqual(char_data.get_char_class_name(), "Warlock")
        char_data.charClass = 8
        self.assertEqual(char_data.get_char_class_name(), "Unknown")
    
    def test_char_name(self):
        char_data = D2SStruct()
        # 测试 ASCII 名称
        char_data.Name = b"TestChar\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        char_data.NamePTR = b"\x00" * 64
        char_data.dwVersion = 0x60  # 1.10 版本
        self.assertEqual(char_data.get_char_name(), "TestChar")
        
        # 测试 PTR2.4+ UTF-8 名称
        char_data.Name = b"\x00" * 16
        char_data.NamePTR = b"TestCharUTF8\x00" + b"\x00" * 50
        char_data.dwVersion = 0x62  # PTR2.4 版本
        self.assertEqual(char_data.get_char_name(), "TestCharUTF8")
    
    def test_flags(self):
        char_data = D2SStruct()
        # 测试 hardcore 标志
        char_data.charFlags = 0x4
        self.assertTrue(char_data.is_hardcore())
        char_data.charFlags = 0x0
        self.assertFalse(char_data.is_hardcore())
        
        # 测试 ladder 标志
        char_data.charFlags = 0x40
        self.assertTrue(char_data.is_ladder())
        char_data.charFlags = 0x0
        self.assertFalse(char_data.is_ladder())
        
        # 测试 expansion 标志
        char_data.charFlags = 0x20
        self.assertTrue(char_data.is_expansion())
        char_data.charFlags = 0x0
        self.assertFalse(char_data.is_expansion())
        
        # 测试 died_before 标志
        char_data.charFlags = 0x8
        self.assertTrue(char_data.is_died_before())
        char_data.charFlags = 0x0
        self.assertFalse(char_data.is_died_before())

    def test_has_mercenary_0x63(self):
        """测试 0x63 版本雇佣兵判断逻辑: dwMercControl != 0"""
        char_data = D2SStruct()
        char_data.dwVersion = 0x63
        
        char_data.dwMercControl = 0
        self.assertFalse(char_data.has_mercenary())
        
        char_data.dwMercControl = 1
        self.assertTrue(char_data.has_mercenary())
        
        char_data.dwMercControl = 0x12345678
        self.assertTrue(char_data.has_mercenary())

    def test_has_mercenary_0x69(self):
        """测试 0x69 版本雇佣兵判断逻辑: mercSeed!=0 or mercNameIndex!=0 or mercExperience!=0"""
        char_data = D2SStruct()
        char_data.dwVersion = 0x69
        
        char_data.mercSeed = 0
        char_data.mercNameIndex = 0
        char_data.mercExperience = 0
        self.assertFalse(char_data.has_mercenary())
        
        char_data.mercSeed = 1
        char_data.mercNameIndex = 0
        char_data.mercExperience = 0
        self.assertTrue(char_data.has_mercenary())
        
        char_data.mercSeed = 0
        char_data.mercNameIndex = 1
        char_data.mercExperience = 0
        self.assertTrue(char_data.has_mercenary())
        
        char_data.mercSeed = 0
        char_data.mercNameIndex = 0
        char_data.mercExperience = 1
        self.assertTrue(char_data.has_mercenary())
        
        char_data.mercSeed = 0x12345678
        char_data.mercNameIndex = 0
        char_data.mercExperience = 0
        self.assertTrue(char_data.has_mercenary())

    def test_has_mercenary_classic(self):
        """测试 Classic 版本雇佣兵判断逻辑: wMercName > 0"""
        char_data = D2SStruct()
        char_data.dwVersion = 0x60
        
        char_data.wMercName = 0
        self.assertFalse(char_data.has_mercenary())
        
        char_data.wMercName = 1
        self.assertTrue(char_data.has_mercenary())

    def test_is_expansion_0x63_charflags(self):
        """测试 0x63 版本资料片判断: charFlags & 0x20"""
        char_data = D2SStruct()
        char_data.dwVersion = 0x63
        char_data.QuestInfo = None
        
        char_data.charFlags = 0x20
        self.assertTrue(char_data.is_expansion())
        
        char_data.charFlags = 0x00
        self.assertFalse(char_data.is_expansion())
        
        char_data.charFlags = 0x24
        self.assertTrue(char_data.is_expansion())

    def test_is_expansion_0x63_acts(self):
        """测试 0x63 版本资料片判断回退: QuestInfo.dwActs >= 5"""
        from core.d2s_struct import QuestInfo
        char_data = D2SStruct()
        char_data.dwVersion = 0x63
        char_data.charFlags = 0x00
        char_data.QuestInfo = QuestInfo()
        
        char_data.QuestInfo.dwActs = 4
        self.assertFalse(char_data.is_expansion())
        
        char_data.QuestInfo.dwActs = 5
        self.assertTrue(char_data.is_expansion())

    def test_is_expansion_0x69(self):
        """测试 0x69 版本资料片判断: gameVersion > 1"""
        char_data = D2SStruct()
        char_data.dwVersion = 0x69
        
        char_data.gameVersion = 1
        self.assertFalse(char_data.is_expansion())
        
        char_data.gameVersion = 2
        self.assertTrue(char_data.is_expansion())
        
        char_data.gameVersion = 3
        self.assertTrue(char_data.is_expansion())

    def test_player_stats_magic(self):
        """测试 PlayerStats 魔法数"""
        from core.d2s_struct import PlayerStats
        
        ps = PlayerStats()
        self.assertEqual(ps.wMajic, 0)
        self.assertEqual(len(ps.m_adwValue), 16)
    
    def test_player_stats_read_data(self):
        """测试 PlayerStats 从 bitstream 解析"""
        from core.d2s_struct import PlayerStats
        
        PLAYER_STATS_BITS_COUNT = [10, 10, 10, 10, 10, 8, 21, 21, 21, 21, 21, 21, 7, 32, 25, 25]
        
        obs = OBitStream()
        obs.write_word(0x6667)
        obs.write_bits(9, 0)
        obs.write_bits(PLAYER_STATS_BITS_COUNT[0], 50)
        obs.write_bits(9, 3)
        obs.write_bits(PLAYER_STATS_BITS_COUNT[3], 25)
        obs.write_bits(9, 0x10)
        obs.align_byte()
        
        bs = IBitStream(obs.get_data())
        ps = PlayerStats()
        ps.deserialize(bs)
        
        self.assertEqual(ps.wMajic, 0x6667)
        self.assertEqual(ps.m_adwValue[0], 50)
        self.assertEqual(ps.m_adwValue[3], 25)
    
    def test_player_stats_invalid_magic(self):
        """测试 PlayerStats 无效魔法数时跳过解析"""
        from core.d2s_struct import PlayerStats
        
        obs = OBitStream()
        obs.write_word(0x1234)
        obs.align_byte()
        
        bs = IBitStream(obs.get_data())
        ps = PlayerStats()
        ps.deserialize(bs)
        
        self.assertNotEqual(ps.wMajic, 0x6667)
    
    def test_player_stats_all_stats(self):
        """测试 PlayerStats 解析所有16个属性"""
        from core.d2s_struct import PlayerStats
        
        PLAYER_STATS_BITS_COUNT = [10, 10, 10, 10, 10, 8, 21, 21, 21, 21, 21, 21, 7, 32, 25, 25]
        test_values = [100, 200, 300, 400, 500, 200, 100000, 200000, 300000, 400000, 500000, 600000, 50, 0xDEADBEEF, 1000000, 2000000]
        
        obs = OBitStream()
        obs.write_word(0x6667)
        for i in range(16):
            obs.write_bits(9, i)
            max_val = (1 << PLAYER_STATS_BITS_COUNT[i]) - 1
            obs.write_bits(PLAYER_STATS_BITS_COUNT[i], min(test_values[i], max_val))
        obs.write_bits(9, 0x10)
        obs.align_byte()
        
        bs = IBitStream(obs.get_data())
        ps = PlayerStats()
        ps.deserialize(bs)
        
        self.assertEqual(ps.wMajic, 0x6667)
        for i in range(16):
            max_val = (1 << PLAYER_STATS_BITS_COUNT[i]) - 1
            expected = min(test_values[i], max_val)
            self.assertEqual(ps.m_adwValue[i], expected,
                             f"Stat index {i}: expected {expected}, got {ps.m_adwValue[i]}")

    def test_demon_default(self):
        """测试 Demon 默认状态"""
        from core.d2s_struct import Demon
        
        demon = Demon()
        self.assertFalse(demon.hasDemon)
        self.assertEqual(demon.wMagic, 0)
    
    def test_demon_read_data_no_demon(self):
        """测试 Demon 解析: 无 Demon 数据 (hasDemon=False)"""
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
        
        self.assertEqual(demon.wMagic, 0x666C)
        self.assertFalse(demon.hasDemon)
    
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
        
        self.assertNotEqual(demon.wMagic, 0x666C)
        self.assertFalse(demon.hasDemon)

    def test_char_name_0x69(self):
        """测试 0x69 版本角色名称从 Name 字段读取"""
        char_data = D2SStruct()
        char_data.dwVersion = 0x69
        char_data.Name = b"D2RChar\x00" + b"\x00" * 8
        self.assertEqual(char_data.get_char_name(), "D2RChar")

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
            self.assertEqual(str(EquipSlot(pos)), name)
            self.assertEqual(EquipSlot(pos).display_name, name)

    def test_format_item_info_equipped_position(self):
        from d2s_parse import format_item_info
        from core.item import D2Item, ItemInfo
        from core.enums import ItemLocation

        item = D2Item()
        item.pItemInfo = ItemInfo()
        item.pItemInfo.sTypeName = b'bsd '
        item.iLocation = int(ItemLocation.EQUIPPED)
        item.iPosition = 4

        lines = format_item_info(item)
        full_text = "\n".join(lines)
        self.assertIn("Location: EQUIPPED, Position: 4 (Weapon I)", full_text)

        # Stored item should not have equip slot name
        item_stored = D2Item()
        item_stored.pItemInfo = ItemInfo()
        item_stored.pItemInfo.sTypeName = b'bsd '
        item_stored.iLocation = int(ItemLocation.STORED)
        item_stored.iPosition = 0
        lines_stored = format_item_info(item_stored)
        full_text_stored = "\n".join(lines_stored)
        self.assertIn("Location: STORED, Position: 0", full_text_stored)
        self.assertNotIn("Weapon", full_text_stored)

    def test_format_timestamp(self):
        from d2s_parse import format_timestamp
        self.assertEqual(format_timestamp(0), "N/A")
        self.assertEqual(format_timestamp(0xFFFFFFFF), "N/A")
        self.assertEqual(format_timestamp(-1), "N/A")
        self.assertEqual(format_timestamp(1793981148), "2026-11-06 16:05:48 UTC")

    def test_format_duration(self):
        from d2s_parse import format_duration
        self.assertEqual(format_duration(0xFFFFFFFF), "N/A")
        self.assertEqual(format_duration(-5), "N/A")
        self.assertEqual(format_duration(0), "0s")
        self.assertEqual(format_duration(45), "45s")
        self.assertEqual(format_duration(3600), "1h")
        self.assertEqual(format_duration(3665), "1h 1m 5s")
        self.assertEqual(format_duration(90061), "1d 1h 1m 1s")

    def test_format_char_info_waypoints_and_quests(self):
        from d2s_parse import format_char_info
        char = D2SStruct()
        char.dwVersion = 0x69
        char.Name = b"TestHero\x00" + b"\x00" * 7
        char.charClass = 1

        # Setup waypoints
        char.Waypoints.wMajic = 0x5357
        # Normal: all 39 waypoints active (5 bytes: 0xFF, 0xFF, 0xFF, 0xFF, 0x7F)
        char.Waypoints.wp[0].Waypoints = [0xFF, 0xFF, 0xFF, 0xFF, 0x7F]
        # Nightmare: bit 2 (Stony Field) missing in Act 1
        char.Waypoints.wp[1].Waypoints = [0xFB, 0xFF, 0xFF, 0xFF, 0x7F]
        # Hell: none active
        char.Waypoints.wp[2].Waypoints = [0x00, 0x00, 0x00, 0x00, 0x00]

        # Setup quests
        char.QuestInfo.dwMajic = 0x216F6F57
        # Normal: all completed, Akara reset used
        char.QuestInfo.QIData[0].bResetStats = 1
        char.QuestInfo.QIData[0].wActI = [1] * 6
        char.QuestInfo.QIData[0].wActII = [1] * 6
        char.QuestInfo.QIData[0].wActIII = [1] * 6
        char.QuestInfo.QIData[0].wActIV = [1] * 3
        char.QuestInfo.QIData[0].wActV = [1] * 6

        # Nightmare: Akara reset available
        # Act I quest 2 (Tools of the Trade): reward unclaimed (0x804a)
        # Act V quest 0 (Siege on Harrogath): reward unclaimed (0x8022)
        # Act V quest 3 (Betrayal of Harrogath): not attempted (0x000c)
        char.QuestInfo.QIData[1].bResetStats = 2
        char.QuestInfo.QIData[1].wActI = [1, 1, 0x804a, 1, 1, 1]
        char.QuestInfo.QIData[1].wActII = [1] * 6
        char.QuestInfo.QIData[1].wActIII = [1] * 6
        char.QuestInfo.QIData[1].wActIV = [1] * 3
        char.QuestInfo.QIData[1].wActV = [0x8022, 1, 1, 0x000c, 1, 1]

        # Hell: not started, reset locked
        char.QuestInfo.QIData[2].bResetStats = 0
        char.QuestInfo.QIData[2].wActI = [0] * 6
        char.QuestInfo.QIData[2].wActII = [0] * 6
        char.QuestInfo.QIData[2].wActIII = [0] * 6
        char.QuestInfo.QIData[2].wActIV = [0] * 3
        char.QuestInfo.QIData[2].wActV = [0] * 6

        output = format_char_info(char)

        # Check waypoints
        self.assertIn("Normal (39/39 unlocked):", output)
        self.assertIn("All unlocked", output)
        self.assertIn("Nightmare (38/39 unlocked):", output)
        self.assertIn("Act I: Stony Field", output)
        self.assertIn("Hell (0/39 unlocked):", output)
        self.assertIn("None unlocked", output)

        # Check quests
        self.assertIn("Normal (27/27 completed) — Akara Reset: Used", output)
        self.assertIn("Act I: [x] [x] [x] [x] [x] [x]", output)
        self.assertIn("Nightmare (26/27 completed, 2 rewards unclaimed) — Akara Reset: Available", output)
        self.assertIn("Act I: [x] [x] [!] Tools of the Trade (reward unclaimed) [x] [x] [x]", output)
        self.assertIn("Act V: [!] Siege on Harrogath (reward unclaimed) [x] [x] [ ] Betrayal of Harrogath [x] [x]", output)
        self.assertIn("Hell (0/27 completed) — Akara Reset: Locked", output)
        self.assertIn("Act I: [ ] [ ] [ ] [ ] [ ] [ ]", output)

if __name__ == '__main__':
    unittest.main()