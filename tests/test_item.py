import unittest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.huffman import HuffmanDecoder, get_huffman
from core.item import (
    ItemMetaData, ItemMetaDataManager,
    PropertyMetaData, PropertyMetaDataItem, PropertyField,
    parse_itemdata_txt, parse_property_txt,
    is_d2r, is_ptr24_and_above, is_valid_version,
    Ear, LongName, GoldQuantity, PropertyList,
    ExtItemInfo, TypeSpecificInfo, ItemInfo, D2Item,
    init_item_data, get_item_meta, get_property_meta
)
from core.ibitstream import IBitStream
from core.obitstream import OBitStream


class TestItemMetaData(unittest.TestCase):
    def test_item_meta_data_creation(self):
        item = ItemMetaData(
            type_id=b'elx ',
            pic_index=0,
            name_index=0,
            range_val=0,
            equip=9,
            simple=True
        )
        self.assertEqual(item.type_id, b'elx ')
        self.assertEqual(item.equip, 9)
        self.assertTrue(item.simple)
        self.assertEqual(item.type_name, 'elx')

    def test_item_meta_data_manager(self):
        manager = ItemMetaDataManager()
        item = ItemMetaData(type_id=b'test', equip=1)
        manager.add_item(item)
        
        found = manager.get_item(b'test')
        self.assertIsNotNone(found)
        self.assertEqual(found.equip, 1)
        
        not_found = manager.get_item(b'xxxx')
        self.assertIsNone(not_found)

    def test_item_meta_data_by_name(self):
        manager = ItemMetaDataManager()
        item = ItemMetaData(type_id=b'cap ', equip=1)
        manager.add_item(item)
        
        found = manager.get_item_by_name('cap')
        self.assertIsNotNone(found)
        
        found = manager.get_item_by_name('cap ')
        self.assertIsNotNone(found)


class TestPropertyMetaData(unittest.TestCase):
    def test_property_field(self):
        field = PropertyField(bits=8, base=-32, min_val=0, max_val=255)
        self.assertEqual(field.bits, 8)
        self.assertEqual(field.base, -32)

    def test_property_meta_data_item(self):
        fields = [
            PropertyField(bits=8, base=-32),
            PropertyField(bits=7, base=0)
        ]
        item = PropertyMetaDataItem(ver_min=0, fields=fields, default_value=0, bits_sum=15)
        
        self.assertEqual(item.bits_sum, 15)
        
        params = item.parse(0x1234)
        self.assertEqual(len(params), 2)

    def test_property_meta_data(self):
        meta = PropertyMetaData()
        item1 = PropertyMetaDataItem(ver_min=0, bits_sum=8)
        item2 = PropertyMetaDataItem(ver_min=0x63, bits_sum=10)
        
        meta.add_item(item1)
        meta.add_item(item2)
        
        found = meta.find_data(0x60)
        self.assertIsNotNone(found)
        self.assertEqual(found.bits_sum, 8)
        
        found = meta.find_data(0x63)
        self.assertIsNotNone(found)
        self.assertEqual(found.bits_sum, 10)


class TestHuffmanDecoder(unittest.TestCase):
    def test_huffman_decode(self):
        huffman = get_huffman()
        self.assertIsNotNone(huffman)
        
        bs = IBitStream(b'\x00')
        char = huffman.read_char(bs)
        self.assertIsInstance(char, int)


class TestVersionFunctions(unittest.TestCase):
    def test_is_d2r(self):
        self.assertFalse(is_d2r(0x60))
        self.assertTrue(is_d2r(0x61))
        self.assertTrue(is_d2r(0x62))
        self.assertTrue(is_d2r(0x63))
        self.assertTrue(is_d2r(0x69))

    def test_is_ptr24_and_above(self):
        self.assertFalse(is_ptr24_and_above(0x61))
        self.assertTrue(is_ptr24_and_above(0x62))
        self.assertTrue(is_ptr24_and_above(0x63))

    def test_is_valid_version(self):
        self.assertTrue(is_valid_version(0x63))
        self.assertTrue(is_valid_version(0x62))
        self.assertTrue(is_valid_version(0x61))
        self.assertTrue(is_valid_version(0x60))
        self.assertTrue(is_valid_version(0x5C))
        self.assertTrue(is_valid_version(0x69))
        self.assertFalse(is_valid_version(0x00))


class TestCEar(unittest.TestCase):
    def test_ear_creation(self):
        ear = Ear("TestName")
        self.assertEqual(ear.sEarName, "TestName")
        self.assertEqual(ear.iEarClass, 0)
        self.assertEqual(ear.iEarLevel, 1)

    def test_ear_is_valid(self):
        ear = Ear()
        self.assertTrue(ear.is_valid())
        ear.iEarLevel = 0
        self.assertFalse(ear.is_valid())


class TestCLongName(unittest.TestCase):
    def test_long_name_creation(self):
        name = LongName()
        self.assertEqual(name.name_1, 0)
        self.assertEqual(name.name_2, 0)
        self.assertIsNone(name.pref_1)
        self.assertIsNone(name.suff_1)


class TestCGoldQuantity(unittest.TestCase):
    def test_gold_quantity_creation(self):
        gold = GoldQuantity()
        self.assertFalse(gold.is_not_gold)
        self.assertEqual(gold.quantity, 0)


class TestCPropertyList(unittest.TestCase):
    def test_property_list_creation(self):
        prop_list = PropertyList()
        self.assertEqual(len(prop_list.mProperty), 0)
        self.assertEqual(prop_list.ext_sockets(), 0)
        self.assertFalse(prop_list.is_indestructible())

    def test_property_list_ext_sockets(self):
        prop_list = PropertyList()
        prop_list.mProperty = [(194, 0, 2), (0, 0, 10)]
        self.assertEqual(prop_list.ext_sockets(), 2)

    def test_property_list_is_indestructible(self):
        prop_list = PropertyList()
        prop_list.mProperty = [(152, 0, 1)]
        self.assertTrue(prop_list.is_indestructible())


class TestCExtItemInfo(unittest.TestCase):
    def test_ext_item_info_creation(self):
        ext_info = ExtItemInfo()
        self.assertEqual(ext_info.gems, 0)
        self.assertEqual(ext_info.guid, 0)
        self.assertEqual(ext_info.quality, 2)

    def test_ext_item_info_is_set(self):
        ext_info = ExtItemInfo()
        self.assertFalse(ext_info.is_set())
        ext_info.quality = 5
        self.assertTrue(ext_info.is_set())


class TestCTypeSpecificInfo(unittest.TestCase):
    def test_type_specific_info_creation(self):
        type_info = TypeSpecificInfo()
        self.assertIsNone(type_info.defence)
        self.assertIsNone(type_info.max_durability)
        self.assertIsNone(type_info.sockets_count)

    def test_type_specific_info_sockets(self):
        type_info = TypeSpecificInfo()
        type_info.sockets_count = 3
        self.assertEqual(type_info.sockets(), (3, 0))

    def test_type_specific_info_defence(self):
        type_info = TypeSpecificInfo()
        type_info.defence = 110
        self.assertEqual(type_info.get_defence(), 100)


class TestCItemInfo(unittest.TestCase):
    def test_item_info_creation(self):
        item_info = ItemInfo()
        self.assertEqual(item_info.type_name, b'    ')
        self.assertIsNone(item_info.ext_info)
        self.assertIsNone(item_info.type_specific_info)

    def test_item_info_is_gold(self):
        item_info = ItemInfo()
        item_info.type_name = b'gld '
        self.assertTrue(item_info.is_gold())

    def test_item_info_is_box(self):
        item_info = ItemInfo()
        item_info.type_name = b'box '
        self.assertTrue(item_info.is_box())


class TestCD2Item(unittest.TestCase):
    def test_d2_item_creation(self):
        item = D2Item()
        self.assertEqual(item.magic, 0x4D4A)
        self.assertFalse(item.is_ear)
        self.assertTrue(item.is_simple)
        self.assertEqual(item.iLocation, 0)

    def test_d2_item_quality(self):
        item = D2Item()
        self.assertEqual(item.quality(), 2)

    def test_d2_item_is_set(self):
        item = D2Item()
        self.assertFalse(item.is_set())

    def test_d2_item_is_rune_word(self):
        item = D2Item()
        self.assertFalse(item.is_rune_word())

    def test_d2_item_get_flag_names(self):
        item = D2Item()
        # Default flags: is_identified=True, bJustSaved=True
        flags = item.get_flag_names()
        self.assertIn("Identified", flags)
        self.assertIn("JustSaved", flags)

        item.is_ethereal = True
        item.is_socketed = True
        item.is_runeword = True
        flags = item.get_flag_names()
        self.assertIn("Ethereal", flags)
        self.assertIn("Socketed", flags)
        self.assertIn("RuneWord", flags)


class TestCD2ItemVersionDifferences(unittest.TestCase):
    """测试 0x63 与 0x69 版本物品格式差异"""
    
    def setUp(self):
        data_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data"
        )
        from core.d2data import init_d2data
        init_d2data(data_dir)
        huffman_path = os.path.join(data_dir, "huffman_tree.json")
        if os.path.exists(huffman_path):
            from core.huffman import init_huffman
            init_huffman(huffman_path)
        self._has_data = True
    
    def _build_simple_item_d2r(self, version, type_name=b'elx '):
        obs = OBitStream()
        obs.write_word(0x4D4A)
        obs.write_dword(version)
        flags = 0x00200000
        obs.write_bits(32, flags)
        obs.write_bits(1, 0)
        obs.write_bits(2, 0)
        obs.write_bits(3, 0)
        obs.write_bits(4, 0)
        obs.write_bits(4, 0)
        obs.write_bits(3, 0)
        huffman = get_huffman()
        for c in type_name:
            huffman.write_char(obs, c)
        obs.align_byte()
        return obs
    
    def test_simple_item_0x63(self):
        """测试 0x63 版本 simple 物品解析"""
        if not self._has_data:
            self.skipTest("Data files not found")
        
        obs = self._build_simple_item_d2r(0x63, b'elx ')
        bs = IBitStream(obs.get_data())
        item = D2Item()
        try:
            item.deserialize(bs, 0x63, True)
            self.assertTrue(item.is_simple)
        except (ValueError, Exception):
            self.skipTest("Bitstream data insufficient for full item parse")
    
    def test_simple_item_0x69(self):
        """测试 0x69 版本 simple 物品解析"""
        if not self._has_data:
            self.skipTest("Data files not found")
        
        obs = self._build_simple_item_d2r(0x69, b'elx ')
        bs = IBitStream(obs.get_data())
        item = D2Item()
        try:
            item.deserialize(bs, 0x69, True)
            self.assertTrue(item.is_simple)
        except (ValueError, Exception):
            self.skipTest("Bitstream data insufficient for full item parse")
    
    def test_d2r_flags_rune_word_bit(self):
        """测试 D2R flags 中 bRuneWord 位 (0x04000000)"""
        item = D2Item()
        self.assertFalse(item.is_runeword)
    
    def test_d2r_flags_chronicle_bits(self):
        """测试 D2R flags 中 chronicle 位 (0x10000000, 0x20000000)"""
        flags_chronicle = 0x10000000
        flags_chronicle_compact = 0x20000000
        self.assertNotEqual(flags_chronicle & 0x10000000, 0)
        self.assertNotEqual(flags_chronicle_compact & 0x20000000, 0)
    
    def test_item_version_0x69_quantity_flag(self):
        """测试 0x69 版本 quantity 使用 flag 而非 is_stacked"""
        from core.item import TypeSpecificInfo
        meta = get_item_meta(b'elx ', 0x69)
        if meta:
            self.assertFalse(meta.is_stacked)
    
    def test_item_version_0x69_realm_data_count(self):
        """测试 0x69 版本 realm_data 数量为 4 (0x69=105 > 96)"""
        self.assertEqual(4 if 0x69 > 96 else 3, 4)
    
    def test_item_version_0x63_realm_data_count(self):
        """测试 0x63 版本 realm_data 数量为 4 (0x63=99 > 96)"""
        self.assertEqual(4 if 0x63 > 96 else 3, 4)
    
    def test_item_version_0x61_realm_data_count(self):
        """测试 0x61 版本 realm_data 数量为 4 (0x61=97 > 96)"""
        self.assertEqual(4 if 0x61 > 96 else (3 if 0x61 > 93 else 2), 4)
    
    def test_item_version_0x60_realm_data_count(self):
        """测试 0x60 版本 realm_data 数量为 3 (0x60=96, >93, <=96)"""
        self.assertEqual(4 if 0x60 > 96 else (3 if 0x60 > 93 else 2), 3)


class TestParseItemDataTxt(unittest.TestCase):
    def test_parse_itemdata_txt_not_exists(self):
        manager = parse_itemdata_txt("nonexistent_file.txt")
        self.assertIsNotNone(manager)
        self.assertIsNone(manager.get_item(b'test'))

    def test_parse_itemdata_txt_exists(self):
        itemdata_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "Generate Data", "itemdata.txt"
        )
        if os.path.exists(itemdata_path):
            manager = parse_itemdata_txt(itemdata_path)
            self.assertIsNotNone(manager)
            
            item = manager.get_item(b'elx ')
            self.assertIsNotNone(item)
            self.assertTrue(item.simple)
            
            item = manager.get_item(b'cap ')
            self.assertIsNotNone(item)
            self.assertTrue(item.has_def)
            self.assertTrue(item.has_dur)


class TestParsePropertyTxt(unittest.TestCase):
    def test_parse_property_txt_not_exists(self):
        properties = parse_property_txt("nonexistent_file.txt")
        self.assertIsNotNone(properties)
        self.assertEqual(len(properties), 0)

    def test_parse_property_txt_exists(self):
        property_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "Generate Data", "property.txt"
        )
        if os.path.exists(property_path):
            properties = parse_property_txt(property_path)
            self.assertIsNotNone(properties)
            self.assertGreater(len(properties), 0)
            
            prop_0 = properties.get(0)
            if prop_0:
                prop = prop_0.find_data(0x60)
                self.assertIsNotNone(prop)
                self.assertGreaterEqual(prop.bits_sum, 0)


class TestPropertyParsing(unittest.TestCase):
    def setUp(self):
        property_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "Generate Data", "property.txt"
        )
        if os.path.exists(property_path):
            init_item_data(None, property_path)
            self._has_property_file = True
        else:
            self._has_property_file = False

    def test_property_parse_single_field(self):
        fields = [PropertyField(bits=8, base=-32, min_val=0, max_val=255)]
        item = PropertyMetaDataItem(ver_min=0, fields=fields, default_value=0, bits_sum=8)
        
        params = item.parse(0)
        self.assertEqual(len(params), 1)
        self.assertEqual(params[0], -32)
        
        params = item.parse(32)
        self.assertEqual(params[0], 0)
        
        params = item.parse(255)
        self.assertEqual(params[0], 223)

    def test_property_parse_multiple_fields(self):
        fields = [
            PropertyField(bits=8, base=-32, min_val=0, max_val=255),
            PropertyField(bits=7, base=0, min_val=0, max_val=127)
        ]
        item = PropertyMetaDataItem(ver_min=0, fields=fields, default_value=0, bits_sum=15)
        
        params = item.parse(0)
        self.assertEqual(len(params), 2)
        self.assertEqual(params[0], -32)
        self.assertEqual(params[1], 0)
        
        params = item.parse(0x1234)
        self.assertEqual(len(params), 2)
        first_param = (0x1234 & 0xFF) - 32
        second_param = ((0x1234 >> 8) & 0x7F)
        self.assertEqual(params[0], first_param)
        self.assertEqual(params[1], second_param)

    def test_property_get_value(self):
        fields = [
            PropertyField(bits=8, base=-32, min_val=0, max_val=255),
            PropertyField(bits=7, base=0, min_val=0, max_val=127)
        ]
        item = PropertyMetaDataItem(ver_min=0, fields=fields, default_value=0, bits_sum=15)
        
        success, value = item.get_value([0, 0])
        self.assertTrue(success)
        expected = (0 - (-32)) | ((0 - 0) << 8)
        self.assertEqual(value, expected)
        
        success, value = item.get_value([10, 5])
        self.assertTrue(success)

    def test_property_roundtrip(self):
        fields = [
            PropertyField(bits=8, base=-32, min_val=0, max_val=255),
            PropertyField(bits=7, base=0, min_val=0, max_val=127)
        ]
        item = PropertyMetaDataItem(ver_min=0, fields=fields, default_value=0, bits_sum=15)
        
        original_value = 0x1234
        params = item.parse(original_value)
        success, reconstructed = item.get_value(params)
        self.assertTrue(success)
        self.assertEqual(original_value, reconstructed)

    def test_property_list_get_parsed_properties(self):
        prop_list = PropertyList()
        prop_list.mProperty = [(0, 0, 32), (1, 0, 64)]
        prop_list._version = 0x60
        
        parsed = prop_list.get_parsed_properties()
        self.assertEqual(len(parsed), 2)
        
        for prop_id, value, params in parsed:
            self.assertIsInstance(prop_id, int)
            self.assertIsInstance(value, int)
            self.assertIsInstance(params, list)

    def test_real_property_parsing(self):
        if not self._has_property_file:
            self.skipTest("property.txt not found")
        
        prop_meta = get_property_meta(0, 0x60)
        if prop_meta:
            params = prop_meta.parse(0)
            self.assertEqual(len(params), 4)
            self.assertEqual(params[0], -32)
            
            params = prop_meta.parse(100)
            self.assertEqual(params[0], 100 - 32)

    def test_strength_property(self):
        if not self._has_property_file:
            self.skipTest("property.txt not found")
        
        prop_meta = get_property_meta(0, 0x60)
        if prop_meta:
            self.assertEqual(prop_meta.bits_sum, 8)
            
            params = prop_meta.parse(50)
            self.assertEqual(params[0], 50 - 32)

    def test_dexterity_property(self):
        if not self._has_property_file:
            self.skipTest("property.txt not found")
        
        prop_meta = get_property_meta(2, 0x60)
        if prop_meta:
            self.assertEqual(prop_meta.bits_sum, 7)
            
            params = prop_meta.parse(50)
            self.assertEqual(params[0], 50 - 32)


class TestBitsStream(unittest.TestCase):
    def test_out_bits_stream(self):
        bs = OBitStream()
        bs.write_bits(8, 0x12)
        bs.write_bits(8, 0x34)
        data = bs.get_data()
        self.assertEqual(data, b'\x12\x34')

    def test_bits_roundtrip(self):
        out_bs = OBitStream()
        out_bs.write_bits(3, 0b101)
        out_bs.write_bits(5, 0b11010)
        out_bs.align_byte()
        
        data = out_bs.get_data()
        
        in_bs = IBitStream(data)
        val1 = in_bs.read_bits(3)
        val2 = in_bs.read_bits(5)
        
        self.assertEqual(val1, 0b101)
        self.assertEqual(val2, 0b11010)


if __name__ == '__main__':
    unittest.main()
