import unittest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.item import (
    get_item_meta, get_property_meta,
    D2Item, PropertyList
)
from core.d2data import init_d2data, get_d2data_manager
from core.obitstream import OBitStream
from core.ibitstream import IBitStream


class TestMergedDataCompatibility(unittest.TestCase):
    def setUp(self):
        data_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data"
        )
        init_d2data(data_dir)
        manager = get_d2data_manager()
        self._has_merged_data = manager is not None and len(manager.version_data) > 0
    
    def test_merged_data_loading(self):
        """测试版本化数据文件是否能正确加载"""
        if not self._has_merged_data:
            self.skipTest("Version data not loaded")
        
        item_meta = get_item_meta(b'elx ', 0x63)
        self.assertIsNotNone(item_meta)
        self.assertTrue(item_meta.simple)
        
        item_meta = get_item_meta(b'cap ', 0x63)
        self.assertIsNotNone(item_meta)
        self.assertTrue(item_meta.has_def)
        self.assertTrue(item_meta.has_dur)
    
    def test_version_specific_properties(self):
        """测试版本特定的属性定义"""
        if not self._has_merged_data:
            self.skipTest("Version data not loaded")
        
        prop_151_63 = get_property_meta(151, 0x63)
        self.assertIsNotNone(prop_151_63)
        self.assertEqual(prop_151_63.bits_sum, 14)
        self.assertEqual(prop_151_63.default_value, 98)
        
        prop_151_69 = get_property_meta(151, 0x69)
        self.assertIsNotNone(prop_151_69)
        self.assertEqual(prop_151_69.bits_sum, 5)
    
    def test_common_properties(self):
        """测试通用属性在不同版本下的解析"""
        if not self._has_merged_data:
            self.skipTest("Version data not loaded")
        
        prop_0_63 = get_property_meta(0, 0x63)
        self.assertIsNotNone(prop_0_63)
        self.assertEqual(prop_0_63.bits_sum, 8)
        
        prop_0_69 = get_property_meta(0, 0x69)
        self.assertIsNotNone(prop_0_69)
        self.assertEqual(prop_0_69.bits_sum, 8)
        
        prop_1_63 = get_property_meta(1, 0x63)
        self.assertIsNotNone(prop_1_63)
        self.assertEqual(prop_1_63.bits_sum, 7)
        
        prop_1_69 = get_property_meta(1, 0x69)
        self.assertIsNotNone(prop_1_69)
        self.assertEqual(prop_1_69.bits_sum, 7)
    
    def test_ipad_bits_compatibility(self):
        """测试 iPadBits 的版本兼容性"""
        if not self._has_merged_data:
            self.skipTest("Version data not loaded")
        
        items_with_ipad_1 = [b'bks ', b'qey ', b'qhr ', b'qbr ']
        
        for item_type in items_with_ipad_1:
            item_meta = get_item_meta(item_type, 0x63)
            if item_meta:
                self.assertEqual(item_meta.ipad_bits, 1,
                                 f"Item {item_type} should have iPadBits=1 for 0x63")
        
        item_vip = get_item_meta(b'vip ', 0x63)
        if item_vip:
            self.assertEqual(item_vip.ipad_bits, 1,
                             "Item 'vip ' should have iPadBits=1 for 0x63")
    
    def test_ipad_bits_version_specific(self):
        """测试 iPadBits 在不同版本下的值
        
        0x69 版本中 vip/bks/qey/qhr/qbr 的 iPadBits=0，
        0x63 版本中这些物品的 iPadBits=1。
        版本化数据加载后，各版本使用自己的 itemdata。
        """
        if not self._has_merged_data:
            self.skipTest("Version data not loaded")
        
        items_with_version_diff = [b'vip ', b'bks ', b'qey ', b'qhr ', b'qbr ']
        
        for item_type in items_with_version_diff:
            meta_63 = get_item_meta(item_type, 0x63)
            meta_69 = get_item_meta(item_type, 0x69)
            
            if meta_63:
                self.assertEqual(meta_63.ipad_bits, 1,
                                 f"Item {item_type} should have iPadBits=1 for 0x63")
            
            if meta_69:
                self.assertEqual(meta_69.ipad_bits, 0,
                                 f"Item {item_type} should have iPadBits=0 for 0x69")
    
    def test_stat_cost_item_aura(self):
        """测试 stat 151 (item_aura) 在 ItemStatCost 中的定义"""
        if not self._has_merged_data:
            self.skipTest("Version data not loaded")
        
        from core.item import get_stat_cost
        stat_151 = get_stat_cost(151)
        if stat_151:
            self.assertEqual(stat_151.stat_name, 'item_aura')
            self.assertEqual(stat_151.save_bits, 5)
            self.assertEqual(stat_151.save_param_bits, 9)
    
    def test_stat_cost_item_indesctructible(self):
        """测试 stat 152 (item_indesctructible) 在 ItemStatCost 中的定义"""
        if not self._has_merged_data:
            self.skipTest("Version data not loaded")
        
        from core.item import get_stat_cost
        stat_152 = get_stat_cost(152)
        if stat_152:
            self.assertEqual(stat_152.stat_name, 'item_indesctructible')
            self.assertEqual(stat_152.save_bits, 1)
            self.assertEqual(stat_152.save_param_bits, 0)
    

class TestVersionCompatibility(unittest.TestCase):
    def setUp(self):
        data_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data"
        )
        init_d2data(data_dir)
        manager = get_d2data_manager()
        self._has_merged_data = manager is not None and len(manager.version_data) > 0
    
    def test_property_list_classic_mode(self):
        """测试 Classic 模式 (<0x61) 属性解析"""
        if not self._has_merged_data:
            self.skipTest("Version data not loaded")
        
        obs = OBitStream()
        obs.write_bits(9, 0)
        obs.write_bits(8, 32)
        obs.write_bits(9, 0x1FF)
        obs.align_byte()
        
        bs = IBitStream(obs.get_data())
        prop_list = PropertyList()
        prop_list.deserialize(bs, 0x60)
        
        self.assertEqual(len(prop_list.mProperty), 1)
        self.assertEqual(prop_list.mProperty[0][0], 0)
        self.assertEqual(prop_list.mProperty[0][2], 32)
        self.assertFalse(prop_list._use_stat_cost)
    
    def test_property_list_d2r_mode(self):
        """测试 D2R 模式 (>=0x61) 属性解析: 使用 ItemStatCost.txt"""
        if not self._has_merged_data:
            self.skipTest("Version data not loaded")
        
        from core.item import get_stat_cost
        stat_0 = get_stat_cost(0)
        if not stat_0:
            self.skipTest("ItemStatCost not loaded")
        
        obs = OBitStream()
        obs.write_bits(9, 0)
        obs.write_bits(stat_0.save_bits, 32 + stat_0.save_add)
        obs.write_bits(9, 0x1FF)
        obs.align_byte()
        
        bs = IBitStream(obs.get_data())
        prop_list = PropertyList()
        prop_list.deserialize(bs, 0x63)
        
        self.assertTrue(prop_list._use_stat_cost)
        self.assertGreaterEqual(len(prop_list.mProperty), 1)
        self.assertEqual(prop_list.mProperty[0][0], 0)
    
    def test_property_list_d2r_aura_stat(self):
        """测试 D2R 模式下 stat 151 (item_aura) 解析: save_bits=5, save_param_bits=9"""
        if not self._has_merged_data:
            self.skipTest("Version data not loaded")
        
        from core.item import get_stat_cost
        stat_151 = get_stat_cost(151)
        if not stat_151:
            self.skipTest("ItemStatCost not loaded")
        
        self.assertEqual(stat_151.save_bits, 5)
        self.assertEqual(stat_151.save_param_bits, 9)
        
        obs = OBitStream()
        obs.write_bits(9, 151)
        obs.write_bits(stat_151.save_param_bits, 10)
        obs.write_bits(stat_151.save_bits, 3 + stat_151.save_add)
        obs.write_bits(9, 0x1FF)
        obs.align_byte()
        
        bs = IBitStream(obs.get_data())
        prop_list = PropertyList()
        prop_list.deserialize(bs, 0x63)
        
        self.assertTrue(prop_list._use_stat_cost)
        found_151 = [p for p in prop_list.mProperty if p[0] == 151]
        self.assertEqual(len(found_151), 1)
        self.assertEqual(found_151[0][1], 10)
    
    def test_property_list_d2r_indestructible(self):
        """测试 D2R 模式下 stat 152 (item_indesctructible) 解析: save_bits=1"""
        if not self._has_merged_data:
            self.skipTest("Version data not loaded")
        
        from core.item import get_stat_cost
        stat_152 = get_stat_cost(152)
        if not stat_152:
            self.skipTest("ItemStatCost not loaded")
        
        self.assertEqual(stat_152.save_bits, 1)
        
        obs = OBitStream()
        obs.write_bits(9, 152)
        obs.write_bits(1, 1)
        obs.write_bits(9, 0x1FF)
        obs.align_byte()
        
        bs = IBitStream(obs.get_data())
        prop_list = PropertyList()
        prop_list.deserialize(bs, 0x63)
        
        self.assertTrue(prop_list._use_stat_cost)
        found_152 = [p for p in prop_list.mProperty if p[0] == 152]
        self.assertEqual(len(found_152), 1)
        self.assertTrue(prop_list.is_indestructible())
    
    def test_property_list_paired_stats(self):
        """测试 D2R 模式下配对属性解析 (如 stat 17→18)"""
        if not self._has_merged_data:
            self.skipTest("Version data not loaded")
        
        from core.item import get_stat_cost
        stat_17 = get_stat_cost(17)
        stat_18 = get_stat_cost(18)
        if not stat_17 or not stat_18:
            self.skipTest("ItemStatCost not loaded")
        
        obs = OBitStream()
        obs.write_bits(9, 17)
        obs.write_bits(stat_17.save_bits, 10 + stat_17.save_add)
        obs.write_bits(stat_18.save_bits, 5 + stat_18.save_add)
        obs.write_bits(9, 0x1FF)
        obs.align_byte()
        
        bs = IBitStream(obs.get_data())
        prop_list = PropertyList()
        prop_list.deserialize(bs, 0x63)
        
        self.assertTrue(prop_list._use_stat_cost)
        found_17 = [p for p in prop_list.mProperty if p[0] == 17]
        found_18 = [p for p in prop_list.mProperty if p[0] == 18]
        self.assertEqual(len(found_17), 1)
        self.assertEqual(len(found_18), 1)
    
    def test_item_creation(self):
        """测试不同版本的物品创建"""
        if not self._has_merged_data:
            self.skipTest("Version data not loaded")
        
        item_63 = D2Item()
        self.assertEqual(item_63.magic, 0x4D4A)
        
        item_69 = D2Item()
        self.assertEqual(item_69.magic, 0x4D4A)
    

class TestDataFileCoverage(unittest.TestCase):
    def setUp(self):
        data_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data"
        )
        init_d2data(data_dir)
        manager = get_d2data_manager()
        self._has_merged_data = manager is not None and len(manager.version_data) > 0
    
    def test_key_properties_coverage(self):
        """测试关键属性是否都能找到"""
        if not self._has_merged_data:
            self.skipTest("Version data not loaded")
        
        key_props = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 15, 16, 20, 24, 31, 32, 36, 37, 39, 41, 43, 45, 48, 50, 51, 52, 53, 54, 55, 57, 58, 59, 72, 88, 128, 139, 150, 151, 152, 160, 162, 185, 194, 195, 197, 221, 224, 254, 255, 256, 263, 266, 272, 273, 277, 286, 293, 299, 302, 303, 320, 323, 330, 336, 339, 340]
        
        missing_props = []
        for prop_id in key_props:
            prop_meta = get_property_meta(prop_id, 0x63)
            if not prop_meta:
                missing_props.append(prop_id)
        
        self.assertEqual(len(missing_props), 0, f"Missing properties: {missing_props}")
    
    def test_key_items_coverage(self):
        """测试关键物品是否都能找到"""
        if not self._has_merged_data:
            self.skipTest("Version data not loaded")
        
        key_items = [b'skp ', b'jew ', b'gfb ', b'r29 ', b'r28 ', b'r12 ', b'paf ', b'scl ', b'rin ', b'hbl ', b'ear ']
        
        missing_items = []
        for item_type in key_items:
            item_meta = get_item_meta(item_type, 0x63)
            if not item_meta:
                missing_items.append(item_type)
        
        self.assertEqual(len(missing_items), 0, f"Missing items: {missing_items}")


if __name__ == '__main__':
    unittest.main()
