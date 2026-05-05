import unittest
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

if __name__ == '__main__':
    unittest.main()