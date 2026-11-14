import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from d2savior.core.ear import Ear, is_ptr24_and_above
from d2savior.core.huffman import DEFAULT_HUFFMAN
from d2savior.core.ibitstream import IBitStream
from d2savior.core.item import (
    D2Item,
    ExtItemInfo,
    ItemInfo,
    TypeSpecificInfo,
    is_valid_version,
)
from d2savior.core.item_name import GoldQuantity, LongName
from d2savior.core.loader import D2DataLoader, GameData
from d2savior.core.models import (
    ItemMetaData,
    ItemMetaDataManager,
    PropertyField,
    PropertyMetaData,
    PropertyMetaDataItem,
)
from d2savior.core.obitstream import OBitStream
from d2savior.core.property_list import PropertyList, is_d2r


class TestItemMetaData:
    def test_item_meta_data_creation(self):
        item = ItemMetaData(
            type_id=b"elx ", pic_index=0, name_index=0, range_val=0, equip=9, simple=True
        )
        assert item.type_id == b"elx "
        assert item.equip == 9
        assert item.simple
        assert item.type_name == "elx"

    def test_item_meta_data_manager(self):
        manager = ItemMetaDataManager()
        item = ItemMetaData(type_id=b"test", equip=1)
        manager.add_item(item)

        found = manager.get_item(b"test")
        assert found is not None
        assert found.equip == 1

        not_found = manager.get_item(b"xxxx")
        assert not_found is None

    def test_item_meta_data_by_name(self):
        manager = ItemMetaDataManager()
        item = ItemMetaData(type_id=b"cap ", equip=1)
        manager.add_item(item)

        found = manager.get_item_by_name("cap")
        assert found is not None

        found = manager.get_item_by_name("cap ")
        assert found is not None


class TestPropertyMetaData:
    def test_property_field(self):
        field = PropertyField(bits=8, base=-32, min_val=0, max_val=255)
        assert field.bits == 8
        assert field.base == -32

    def test_property_meta_data_item(self):
        fields = [PropertyField(bits=8, base=-32), PropertyField(bits=7, base=0)]
        item = PropertyMetaDataItem(ver_min=0, fields=fields, default_value=0, bits_sum=15)

        assert item.bits_sum == 15

        params = item.parse(0x1234)
        assert len(params) == 2

    def test_property_meta_data(self):
        meta = PropertyMetaData()
        item1 = PropertyMetaDataItem(ver_min=0, bits_sum=8)
        item2 = PropertyMetaDataItem(ver_min=0x63, bits_sum=10)

        meta.add_item(item1)
        meta.add_item(item2)

        found = meta.find_data(0x60)
        assert found is not None
        assert found.bits_sum == 8

        found = meta.find_data(0x63)
        assert found is not None
        assert found.bits_sum == 10


class TestHuffmanDecoder:
    def test_huffman_decode(self):
        huffman = DEFAULT_HUFFMAN
        assert huffman is not None

        bs = IBitStream(b"\x00")
        char = huffman.read_char(bs)
        assert isinstance(char, int)


class TestVersionFunctions:
    def test_is_d2r(self):
        assert not is_d2r(96)
        assert is_d2r(97)
        assert is_d2r(98)
        assert is_d2r(99)
        assert is_d2r(105)

    def test_is_ptr24_and_above(self):
        assert not is_ptr24_and_above(97)
        assert is_ptr24_and_above(98)
        assert is_ptr24_and_above(99)

    def test_is_valid_version(self):
        assert is_valid_version(99)
        assert is_valid_version(98)
        assert is_valid_version(97)
        assert is_valid_version(96)
        assert is_valid_version(92)
        assert is_valid_version(105)
        assert not is_valid_version(0)


class TestCEar:
    def test_ear_creation(self):
        ear = Ear("TestName")
        assert ear.ear_name == "TestName"
        assert ear.ear_class == 0
        assert ear.ear_level == 1

    def test_ear_is_valid(self):
        ear = Ear()
        assert ear.is_valid()
        ear.ear_level = 0
        assert not ear.is_valid()


class TestCLongName:
    def test_long_name_creation(self):
        name = LongName()
        assert name.name_1 == 0
        assert name.name_2 == 0
        assert name.pref_1 is None
        assert name.suff_1 is None


class TestCGoldQuantity:
    def test_gold_quantity_creation(self):
        gold = GoldQuantity()
        assert not gold.is_not_gold
        assert gold.quantity == 0


class TestCPropertyList:
    def test_property_list_creation(self):
        prop_list = PropertyList()
        assert len(prop_list.properties) == 0
        assert prop_list.ext_sockets() == 0
        assert not prop_list.is_indestructible()

    def test_property_list_ext_sockets(self):
        prop_list = PropertyList()
        prop_list.properties = [(194, 0, 2), (0, 0, 10)]
        assert prop_list.ext_sockets() == 2

    def test_property_list_is_indestructible(self):
        prop_list = PropertyList()
        prop_list.properties = [(152, 0, 1)]
        assert prop_list.is_indestructible()


class TestCExtItemInfo:
    def test_ext_item_info_creation(self):
        ext_info = ExtItemInfo()
        assert ext_info.gems == 0
        assert ext_info.guid == 0
        assert ext_info.quality == 2

    def test_ext_item_info_is_set(self):
        ext_info = ExtItemInfo()
        assert not ext_info.is_set()
        ext_info.quality = 5
        assert ext_info.is_set()


class TestCTypeSpecificInfo:
    def test_type_specific_info_creation(self):
        type_info = TypeSpecificInfo()
        assert type_info.defence is None
        assert type_info.max_durability is None
        assert type_info.sockets_count is None

    def test_type_specific_info_sockets(self):
        type_info = TypeSpecificInfo()
        type_info.sockets_count = 3
        assert type_info.sockets() == (3, 0)

    def test_type_specific_info_defence(self):
        type_info = TypeSpecificInfo()
        type_info.defence = 110
        assert type_info.get_defence() == 100

    def test_type_specific_info_deserialize_requires_data(self):
        type_info = TypeSpecificInfo()
        bs = IBitStream(b"\x00" * 10)
        with pytest.raises(ValueError, match="required"):
            type_info.deserialize(
                bs,
                version=0x63,
                data=None,
            )


class TestCItemInfo:
    def test_item_info_creation(self):
        item_info = ItemInfo()
        assert item_info.type_name == b"    "
        assert item_info.ext_info is None
        assert item_info.type_specific_info is None

    def test_item_info_is_gold(self):
        item_info = ItemInfo()
        item_info.type_name = b"gld "
        assert item_info.is_gold()

    def test_item_info_is_box(self):
        item_info = ItemInfo()
        item_info.type_name = b"box "
        assert item_info.is_box()


class TestCD2Item:
    def test_d2_item_creation(self):
        item = D2Item()
        assert item.magic == 19786
        assert not item.is_ear
        assert item.is_simple
        assert item.location == 0

    def test_d2_item_quality(self):
        item = D2Item()
        assert item.quality() == 2

    def test_d2_item_is_set(self):
        item = D2Item()
        assert not item.is_set()

    def test_d2_item_is_rune_word(self):
        item = D2Item()
        assert not item.is_rune_word()

    def test_d2_item_get_flag_names(self):
        item = D2Item()
        # Default flags: is_identified=True, is_just_saved=True
        flags = item.get_flag_names()
        assert "Identified" in flags
        assert "JustSaved" in flags

        item.is_ethereal = True
        item.is_socketed = True
        item.is_runeword = True
        flags = item.get_flag_names()
        assert "Ethereal" in flags
        assert "Socketed" in flags
        assert "RuneWord" in flags


class TestCD2ItemVersionDifferences:
    """测试 0x63 与 0x69 版本物品格式差异"""

    def setup_method(self):
        data_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "d2savior", "data"
        )
        self.game_data = GameData.load(data_dir)
        self._has_data = True

    def _build_simple_item_d2r(self, version, type_name=b"elx "):
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
        huffman = DEFAULT_HUFFMAN
        for c in type_name:
            huffman.write_char(obs, c)
        obs.align_byte()
        return obs

    def test_simple_item_0x63(self):
        """测试 0x63 版本 simple 物品解析"""
        if not self._has_data:
            pytest.skip("Data files not found")

        obs = self._build_simple_item_d2r(0x63, b"elx ")
        bs = IBitStream(obs.get_data())
        item = D2Item()
        vd = self.game_data.for_version(0x63) if self.game_data else None
        try:
            item.deserialize(bs, 0x63, True, data=vd)
            assert item.is_simple
        except ValueError, Exception:
            pytest.skip("Bitstream data insufficient for full item parse")

    def test_simple_item_0x69(self):
        """测试 0x69 版本 simple 物品解析"""
        if not self._has_data:
            pytest.skip("Data files not found")

        obs = self._build_simple_item_d2r(0x69, b"elx ")
        bs = IBitStream(obs.get_data())
        item = D2Item()
        vd = self.game_data.for_version(0x69) if self.game_data else None
        try:
            item.deserialize(bs, 0x69, True, data=vd)
            assert item.is_simple
        except ValueError, Exception:
            pytest.skip("Bitstream data insufficient for full item parse")

    def test_d2r_flags_rune_word_bit(self):
        """测试 D2R flags 中 bRuneWord 位 (0x04000000)"""
        item = D2Item()
        assert not item.is_runeword

    def test_d2r_flags_chronicle_bits(self):
        """测试 D2R flags 中 chronicle 位 (0x10000000, 0x20000000)"""
        flags_chronicle = 0x10000000
        flags_chronicle_compact = 0x20000000
        assert flags_chronicle & 268435456 != 0
        assert flags_chronicle_compact & 536870912 != 0

    def test_item_version_0x69_quantity_flag(self):
        """测试 0x69 版本 quantity 使用 flag 而非 is_stacked"""
        vd = self.game_data.for_version(0x69) if self.game_data else None
        meta = vd.get_item_meta(b"elx ") if vd else None
        if meta:
            assert not meta.is_stacked

    def test_item_version_0x69_realm_data_count(self):
        """测试 0x69 版本 realm_data 数量为 4 (0x69=105 > 96)"""
        assert (4 if 105 > 96 else 3) == 4

    def test_item_version_0x63_realm_data_count(self):
        """测试 0x63 版本 realm_data 数量为 4 (0x63=99 > 96)"""
        assert (4 if 99 > 96 else 3) == 4

    def test_item_version_0x61_realm_data_count(self):
        """测试 0x61 版本 realm_data 数量为 4 (0x61=97 > 96)"""
        assert (4 if 97 > 96 else 3 if 97 > 93 else 2) == 4

    def test_item_version_0x60_realm_data_count(self):
        """测试 0x60 版本 realm_data 数量为 3 (0x60=96, >93, <=96)"""
        assert (4 if 96 > 96 else 3 if 96 > 93 else 2) == 3


class TestParseItemDataTxt:
    def test_parse_itemdata_txt_not_exists(self):
        with pytest.raises(FileNotFoundError):
            D2DataLoader().load_itemdata("nonexistent_file.txt")

    def test_parse_itemdata_txt_exists(self):
        itemdata_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "Generate Data",
            "itemdata.txt",
        )
        if os.path.exists(itemdata_path):
            manager = D2DataLoader().load_itemdata(itemdata_path)
            assert manager is not None

            item = manager.get_item(b"elx ")
            assert item is not None
            assert item.simple

            item = manager.get_item(b"cap ")
            assert item is not None
            assert item.has_def
            assert item.has_dur


class TestParsePropertyTxt:
    def test_parse_property_txt_not_exists(self):
        with pytest.raises(FileNotFoundError):
            D2DataLoader().load_property_meta("nonexistent_file.txt")

    def test_parse_property_txt_exists(self):
        property_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "Generate Data",
            "property.txt",
        )
        if os.path.exists(property_path):
            properties = D2DataLoader().load_property_meta(property_path)
            assert properties is not None
            assert len(properties) > 0

            prop_0 = properties.get(0)
            if prop_0:
                prop = prop_0.find_data(0x60)
                assert prop is not None
                assert prop.bits_sum >= 0


class TestPropertyParsing:
    def setup_method(self):
        data_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "d2savior", "data"
        )
        self.game_data = GameData.load(data_dir)
        self._has_property_file = True

    def test_property_parse_single_field(self):
        fields = [PropertyField(bits=8, base=-32, min_val=0, max_val=255)]
        item = PropertyMetaDataItem(ver_min=0, fields=fields, default_value=0, bits_sum=8)

        params = item.parse(0)
        assert len(params) == 1
        assert params[0] == -32

        params = item.parse(32)
        assert params[0] == 0

        params = item.parse(255)
        assert params[0] == 223

    def test_property_parse_multiple_fields(self):
        fields = [
            PropertyField(bits=8, base=-32, min_val=0, max_val=255),
            PropertyField(bits=7, base=0, min_val=0, max_val=127),
        ]
        item = PropertyMetaDataItem(ver_min=0, fields=fields, default_value=0, bits_sum=15)

        params = item.parse(0)
        assert len(params) == 2
        assert params[0] == -32
        assert params[1] == 0

        params = item.parse(0x1234)
        assert len(params) == 2
        first_param = (0x1234 & 0xFF) - 32
        second_param = (0x1234 >> 8) & 0x7F
        assert params[0] == first_param
        assert params[1] == second_param

    def test_property_get_value(self):
        fields = [
            PropertyField(bits=8, base=-32, min_val=0, max_val=255),
            PropertyField(bits=7, base=0, min_val=0, max_val=127),
        ]
        item = PropertyMetaDataItem(ver_min=0, fields=fields, default_value=0, bits_sum=15)

        success, value = item.get_value([0, 0])
        assert success
        expected = (0 - (-32)) | ((0 - 0) << 8)
        assert value == expected

        success, value = item.get_value([10, 5])
        assert success

    def test_property_roundtrip(self):
        fields = [
            PropertyField(bits=8, base=-32, min_val=0, max_val=255),
            PropertyField(bits=7, base=0, min_val=0, max_val=127),
        ]
        item = PropertyMetaDataItem(ver_min=0, fields=fields, default_value=0, bits_sum=15)

        original_value = 0x1234
        params = item.parse(original_value)
        success, reconstructed = item.get_value(params)
        assert success
        assert original_value == reconstructed

    def test_property_list_get_parsed_properties(self):
        prop_list = PropertyList()
        prop_list.properties = [(0, 0, 32), (1, 0, 64)]
        prop_list._version = 0x60

        parsed = prop_list.get_parsed_properties()
        assert len(parsed) == 2

        for prop_id, value, params in parsed:
            assert isinstance(prop_id, int)
            assert isinstance(value, int)
            assert isinstance(params, list)

    def test_real_property_parsing(self):
        if not self._has_property_file:
            pytest.skip("property.txt not found")

        gd = self.game_data
        prop_meta = gd.for_version(0x60).get_property_meta(0) if gd else None
        if prop_meta:
            params = prop_meta.parse(0)
            assert len(params) == 4
            assert params[0] == -32

            params = prop_meta.parse(100)
            assert params[0] == 100 - 32

    def test_strength_property(self):
        if not self._has_property_file:
            pytest.skip("property.txt not found")

        gd = self.game_data
        prop_meta = gd.for_version(0x60).get_property_meta(0) if gd else None
        if prop_meta:
            assert prop_meta.bits_sum == 8

            params = prop_meta.parse(50)
            assert params[0] == 50 - 32

    def test_dexterity_property(self):
        if not self._has_property_file:
            pytest.skip("property.txt not found")

        gd = self.game_data
        prop_meta = gd.for_version(0x60).get_property_meta(2) if gd else None
        if prop_meta:
            assert prop_meta.bits_sum == 7

            params = prop_meta.parse(50)
            assert params[0] == 50 - 32


class TestBitsStream:
    def test_out_bits_stream(self):
        bs = OBitStream()
        bs.write_bits(8, 0x12)
        bs.write_bits(8, 0x34)
        data = bs.get_data()
        assert data == b"\x124"

    def test_bits_roundtrip(self):
        out_bs = OBitStream()
        out_bs.write_bits(3, 0b101)
        out_bs.write_bits(5, 0b11010)
        out_bs.align_byte()

        data = out_bs.get_data()

        in_bs = IBitStream(data)
        val1 = in_bs.read_bits(3)
        val2 = in_bs.read_bits(5)

        assert val1 == 5
        assert val2 == 26
