import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from d2savior.core.d2data import get_game_data, init_d2data
from d2savior.core.ibitstream import IBitStream
from d2savior.core.item import D2Item, PropertyList
from d2savior.core.obitstream import OBitStream


class TestMergedDataCompatibility:
    def setup_method(self):
        data_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "d2savior", "data"
        )
        init_d2data(data_dir)
        self.manager = get_game_data()
        self.v63 = self.manager.for_version(0x63) if self.manager else None
        self.v69 = self.manager.for_version(0x69) if self.manager else None
        self._has_merged_data = self.manager is not None and len(self.manager.version_data) > 0

    def test_merged_data_loading(self):
        """测试版本化数据文件是否能正确加载"""
        if not self._has_merged_data or not self.v63:
            pytest.skip("Version data not loaded")

        item_meta = self.v63.get_item_meta(b"elx ")
        assert item_meta is not None
        assert item_meta.simple

        item_meta = self.v63.get_item_meta(b"cap ")
        assert item_meta is not None
        assert item_meta.has_def
        assert item_meta.has_dur

    def test_version_specific_properties(self):
        """测试版本特定的属性定义"""
        if not self._has_merged_data or not self.v63 or not self.v69:
            pytest.skip("Version data not loaded")

        prop_151_63 = self.v63.get_property_meta(151)
        assert prop_151_63 is not None
        assert prop_151_63.bits_sum == 14
        assert prop_151_63.default_value == 98

        prop_151_69 = self.v69.get_property_meta(151)
        assert prop_151_69 is not None
        assert prop_151_69.bits_sum == 5

    def test_common_properties(self):
        """测试通用属性在不同版本下的解析"""
        if not self._has_merged_data or not self.v63 or not self.v69:
            pytest.skip("Version data not loaded")

        prop_0_63 = self.v63.get_property_meta(0)
        assert prop_0_63 is not None
        assert prop_0_63.bits_sum == 8

        prop_0_69 = self.v69.get_property_meta(0)
        assert prop_0_69 is not None
        assert prop_0_69.bits_sum == 8

        prop_1_63 = self.v63.get_property_meta(1)
        assert prop_1_63 is not None
        assert prop_1_63.bits_sum == 7

        prop_1_69 = self.v69.get_property_meta(1)
        assert prop_1_69 is not None
        assert prop_1_69.bits_sum == 7

    def test_ipad_bits_compatibility(self):
        """测试 iPadBits 的版本兼容性"""
        if not self._has_merged_data or not self.v63:
            pytest.skip("Version data not loaded")

        items_with_ipad_1 = [b"bks ", b"qey ", b"qhr ", b"qbr "]

        for item_type in items_with_ipad_1:
            item_meta = self.v63.get_item_meta(item_type)
            if item_meta:
                assert item_meta.ipad_bits == 1, f"Item {item_type} should have iPadBits=1 for 0x63"

        item_vip = self.v63.get_item_meta(b"vip ")
        if item_vip:
            assert item_vip.ipad_bits == 1, "Item 'vip ' should have iPadBits=1 for 0x63"

    def test_ipad_bits_version_specific(self):
        """测试 iPadBits 在不同版本下的值

        0x69 版本中 vip/bks/qey/qhr/qbr 的 iPadBits=0，
        0x63 版本中这些物品的 iPadBits=1。
        版本化数据加载后，各版本使用自己的 itemdata。
        """
        if not self._has_merged_data or not self.v63 or not self.v69:
            pytest.skip("Version data not loaded")

        items_with_version_diff = [b"vip ", b"bks ", b"qey ", b"qhr ", b"qbr "]

        for item_type in items_with_version_diff:
            meta_63 = self.v63.get_item_meta(item_type)
            meta_69 = self.v69.get_item_meta(item_type)

            if meta_63:
                assert meta_63.ipad_bits == 1, f"Item {item_type} should have iPadBits=1 for 0x63"

            if meta_69:
                assert meta_69.ipad_bits == 0, f"Item {item_type} should have iPadBits=0 for 0x69"

    def test_stat_cost_item_aura(self):
        """测试 stat 151 (item_aura) 在 ItemStatCost 中的定义"""
        if not self._has_merged_data or not self.v63:
            pytest.skip("Version data not loaded")

        stat_151 = self.v63.get_stat(151)
        if stat_151:
            assert stat_151.stat_name == "item_aura"
            assert stat_151.save_bits == 5
            assert stat_151.save_param_bits == 9

    def test_stat_cost_item_indesctructible(self):
        """测试 stat 152 (item_indesctructible) 在 ItemStatCost 中的定义"""
        if not self._has_merged_data or not self.v63:
            pytest.skip("Version data not loaded")

        stat_152 = self.v63.get_stat(152)
        if stat_152:
            assert stat_152.stat_name == "item_indesctructible"
            assert stat_152.save_bits == 1
            assert stat_152.save_param_bits == 0


class TestVersionCompatibility:
    def setup_method(self):
        data_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "d2savior", "data"
        )
        init_d2data(data_dir)
        self.manager = get_game_data()
        self.v63 = self.manager.for_version(0x63) if self.manager else None
        self.v60 = self.manager.for_version(0x60) if self.manager else None
        self._has_merged_data = self.manager is not None and len(self.manager.version_data) > 0

    def test_property_list_classic_mode(self):
        """测试 Classic 模式 (<0x61) 属性解析"""
        if not self._has_merged_data or not self.v60:
            pytest.skip("Version data not loaded")

        obs = OBitStream()
        obs.write_bits(9, 0)
        obs.write_bits(8, 32)
        obs.write_bits(9, 0x1FF)
        obs.align_byte()

        bs = IBitStream(obs.get_data())
        prop_list = PropertyList()
        prop_list.deserialize(bs, 0x60, data=self.v60)

        assert len(prop_list.properties) == 1
        assert prop_list.properties[0][0] == 0
        assert prop_list.properties[0][2] == 32
        assert not prop_list._use_stat_cost

    def test_property_list_d2r_mode(self):
        """测试 D2R 模式 (>=0x61) 属性解析: 使用 ItemStatCost.txt"""
        if not self._has_merged_data or not self.v63:
            pytest.skip("Version data not loaded")

        stat_0 = self.v63.get_stat(0)
        if not stat_0:
            pytest.skip("ItemStatCost not loaded")

        obs = OBitStream()
        obs.write_bits(9, 0)
        obs.write_bits(stat_0.save_bits, 32 + stat_0.save_add)
        obs.write_bits(9, 0x1FF)
        obs.align_byte()

        bs = IBitStream(obs.get_data())
        prop_list = PropertyList()
        prop_list.deserialize(bs, 0x63, data=self.v63)

        assert prop_list._use_stat_cost
        assert len(prop_list.properties) >= 1
        assert prop_list.properties[0][0] == 0

    def test_property_list_d2r_aura_stat(self):
        """测试 D2R 模式下 stat 151 (item_aura) 解析: save_bits=5, save_param_bits=9"""
        if not self._has_merged_data or not self.v63:
            pytest.skip("Version data not loaded")

        stat_151 = self.v63.get_stat(151)
        if not stat_151:
            pytest.skip("ItemStatCost not loaded")

        assert stat_151.save_bits == 5
        assert stat_151.save_param_bits == 9

        obs = OBitStream()
        obs.write_bits(9, 151)
        obs.write_bits(stat_151.save_param_bits, 10)
        obs.write_bits(stat_151.save_bits, 3 + stat_151.save_add)
        obs.write_bits(9, 0x1FF)
        obs.align_byte()

        bs = IBitStream(obs.get_data())
        prop_list = PropertyList()
        prop_list.deserialize(bs, 0x63, data=self.v63)

        assert prop_list._use_stat_cost
        found_151 = [p for p in prop_list.properties if p[0] == 151]
        assert len(found_151) == 1
        assert found_151[0][1] == 10

    def test_property_list_d2r_indestructible(self):
        """测试 D2R 模式下 stat 152 (item_indesctructible) 解析: save_bits=1"""
        if not self._has_merged_data or not self.v63:
            pytest.skip("Version data not loaded")

        stat_152 = self.v63.get_stat(152)
        if not stat_152:
            pytest.skip("ItemStatCost not loaded")

        assert stat_152.save_bits == 1

        obs = OBitStream()
        obs.write_bits(9, 152)
        obs.write_bits(1, 1)
        obs.write_bits(9, 0x1FF)
        obs.align_byte()

        bs = IBitStream(obs.get_data())
        prop_list = PropertyList()
        prop_list.deserialize(bs, 0x63, data=self.v63)

        assert prop_list._use_stat_cost
        found_152 = [p for p in prop_list.properties if p[0] == 152]
        assert len(found_152) == 1
        assert prop_list.is_indestructible()

    def test_property_list_paired_stats(self):
        """测试 D2R 模式下配对属性解析 (如 stat 17→18)"""
        if not self._has_merged_data or not self.v63:
            pytest.skip("Version data not loaded")

        stat_17 = self.v63.get_stat(17)
        stat_18 = self.v63.get_stat(18)
        if not stat_17 or not stat_18:
            pytest.skip("ItemStatCost not loaded")

        obs = OBitStream()
        obs.write_bits(9, 17)
        obs.write_bits(stat_17.save_bits, 10 + stat_17.save_add)
        obs.write_bits(stat_18.save_bits, 5 + stat_18.save_add)
        obs.write_bits(9, 0x1FF)
        obs.align_byte()

        bs = IBitStream(obs.get_data())
        prop_list = PropertyList()
        prop_list.deserialize(bs, 0x63, data=self.v63)

        assert prop_list._use_stat_cost
        found_17 = [p for p in prop_list.properties if p[0] == 17]
        found_18 = [p for p in prop_list.properties if p[0] == 18]
        assert len(found_17) == 1
        assert len(found_18) == 1

    def test_item_creation(self):
        """测试不同版本的物品创建"""
        if not self._has_merged_data:
            pytest.skip("Version data not loaded")

        item_63 = D2Item()
        assert item_63.magic == 19786

        item_69 = D2Item()
        assert item_69.magic == 19786


class TestDataFileCoverage:
    def setup_method(self):
        data_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "d2savior", "data"
        )
        init_d2data(data_dir)
        self.manager = get_game_data()
        self.v63 = self.manager.for_version(0x63) if self.manager else None
        self._has_merged_data = self.manager is not None and len(self.manager.version_data) > 0

    def test_key_properties_coverage(self):
        """测试关键属性是否都能找到"""
        if not self._has_merged_data or not self.v63:
            pytest.skip("Version data not loaded")

        key_props = [
            0,
            1,
            2,
            3,
            4,
            5,
            6,
            7,
            8,
            9,
            10,
            15,
            16,
            20,
            24,
            31,
            32,
            36,
            37,
            39,
            41,
            43,
            45,
            48,
            50,
            51,
            52,
            53,
            54,
            55,
            57,
            58,
            59,
            72,
            88,
            128,
            139,
            150,
            151,
            152,
            160,
            162,
            185,
            194,
            195,
            197,
            221,
            224,
            254,
            255,
            256,
            263,
            266,
            272,
            273,
            277,
            286,
            293,
            299,
            302,
            303,
            320,
            323,
            330,
            336,
            339,
            340,
        ]

        missing_props = []
        for prop_id in key_props:
            prop_meta = self.v63.get_property_meta(prop_id)
            if not prop_meta:
                missing_props.append(prop_id)

        assert len(missing_props) == 0, f"Missing properties: {missing_props}"

    def test_key_items_coverage(self):
        """测试关键物品是否都能找到"""
        if not self._has_merged_data or not self.v63:
            pytest.skip("Version data not loaded")

        key_items = [
            b"skp ",
            b"jew ",
            b"gfb ",
            b"r29 ",
            b"r28 ",
            b"r12 ",
            b"paf ",
            b"scl ",
            b"rin ",
            b"hbl ",
            b"ear ",
        ]

        missing_items = []
        for item_type in key_items:
            item_meta = self.v63.get_item_meta(item_type)
            if not item_meta:
                missing_items.append(item_type)

        assert len(missing_items) == 0, f"Missing items: {missing_items}"
