import os
import struct
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from d2savior.core.ibitstream import IBitStream
from d2savior.core.obitstream import OBitStream
from d2savior.core.stash import (
    ADVANCED_SUBTYPE_GEM,
    ADVANCED_SUBTYPE_MATERIAL,
    ADVANCED_SUBTYPE_RUNE,
    ADVANCED_SUBTYPE_UNKNOWN,
    GEM_CODES,
    GEM_LAYOUT,
    GEM_SLOT_ORDER,
    MATERIAL_CODES,
    MATERIAL_LAYOUT,
    MATERIAL_SLOT_ORDER,
    NORMAL_LAYOUT,
    RUNE_CODES,
    RUNE_LAYOUT,
    RUNE_SLOT_ORDER,
    STASH_TAB_HEADER_SIZE,
    STASH_TAB_MAGIC,
    STASH_TAB_TYPE_ADVANCED,
    STASH_TAB_TYPE_CHRONICLE,
    STASH_TAB_TYPE_NORMAL,
    SharedStash,
    StashTab,
    classify_advanced_tab,
    compute_advanced_grid,
    get_advanced_layout,
    get_advanced_slot_order,
)


def _build_stash_tab_header(
    stash_format=1, item_format=99, gold=0, tab_size=64, season=0, tab_type=0, reserved=None
):
    header = struct.pack("<I", STASH_TAB_MAGIC)
    header += struct.pack("<I", stash_format)
    header += struct.pack("<I", item_format)
    header += struct.pack("<I", gold)
    header += struct.pack("<H", tab_size)
    header += struct.pack("<H", season)
    header += struct.pack("<B", tab_type)
    if reserved is None:
        reserved = b"\x00" * 43
    header += reserved
    assert len(header) == STASH_TAB_HEADER_SIZE
    return header


def _build_empty_item_list(version=99):
    obs = OBitStream()
    obs.write_word(0x4D4A)
    obs.write_dword(version)
    obs.write_bits(32, 0)
    obs.write_bits(1, 0)
    obs.write_bits(2, 0)
    obs.write_bits(3, 0)
    obs.write_bits(4, 0)
    obs.write_bits(4, 0)
    obs.write_bits(3, 0)
    obs.align_byte()
    return obs.get_data()


class TestCStashTabHeader:
    def test_default_values(self):
        tab = StashTab()
        assert tab.stash_format == 0
        assert tab.item_format == 0
        assert tab.gold == 0
        assert tab.season == 0
        assert tab.tab_type == STASH_TAB_TYPE_NORMAL
        assert tab.reserved == b"\x00" * 43
        assert tab.items is None
        assert tab.chronicle is None
        assert tab._tab_size == 0

    def test_read_classic_header(self):
        header = _build_stash_tab_header(
            stash_format=1, item_format=99, gold=12345, tab_size=64, season=0, tab_type=0
        )
        bs = IBitStream(header)
        tab = StashTab()
        tab.deserialize(bs, version=99)
        assert tab.stash_format == 1
        assert tab.item_format == 99
        assert tab.gold == 12345
        assert tab.tab_type == STASH_TAB_TYPE_NORMAL

    def test_read_modern_header(self):
        header = _build_stash_tab_header(
            stash_format=2,
            item_format=105,
            gold=50000,
            tab_size=64,
            season=3,
            tab_type=STASH_TAB_TYPE_NORMAL,
        )
        bs = IBitStream(header)
        tab = StashTab()
        tab.deserialize(bs, version=105)
        assert tab.stash_format == 2
        assert tab.item_format == 105
        assert tab.gold == 50000
        assert tab.season == 3
        assert tab.tab_type == STASH_TAB_TYPE_NORMAL

    def test_invalid_magic_raises(self):
        header = struct.pack("<I", 0xDEADBEEF)
        header += b"\x00" * (STASH_TAB_HEADER_SIZE - 4)
        bs = IBitStream(header)
        tab = StashTab()
        with pytest.raises(ValueError, match="Invalid stash tab magic") as ctx:
            tab.deserialize(bs)
        assert "Invalid stash tab magic" in str(ctx.value)

    def test_stash_format_1_forces_normal_type(self):
        header = _build_stash_tab_header(
            stash_format=1, item_format=99, gold=0, tab_size=64, tab_type=STASH_TAB_TYPE_ADVANCED
        )
        bs = IBitStream(header)
        tab = StashTab()
        tab.deserialize(bs, version=99)
        assert tab.stash_format == 1
        assert tab.tab_type == STASH_TAB_TYPE_NORMAL

    def test_stash_format_2_preserves_tab_type(self):
        header = _build_stash_tab_header(
            stash_format=2, item_format=105, gold=0, tab_size=64, tab_type=STASH_TAB_TYPE_ADVANCED
        )
        bs = IBitStream(header)
        tab = StashTab()
        tab.deserialize(bs, version=105)
        assert tab.stash_format == 2
        assert tab.tab_type == STASH_TAB_TYPE_ADVANCED

    def test_stash_format_2_chronicle_type(self):
        header = _build_stash_tab_header(
            stash_format=2, item_format=105, gold=0, tab_size=64, tab_type=STASH_TAB_TYPE_CHRONICLE
        )
        bs = IBitStream(header)
        tab = StashTab()
        tab.deserialize(bs, version=105)
        assert tab.stash_format == 2
        assert tab.tab_type == STASH_TAB_TYPE_CHRONICLE

    def test_reserved_bytes_read(self):
        custom_reserved = bytes([i % 256 for i in range(43)])
        header = _build_stash_tab_header(
            stash_format=1, item_format=99, gold=0, tab_size=64, reserved=custom_reserved
        )
        bs = IBitStream(header)
        tab = StashTab()
        tab.deserialize(bs, version=99)
        assert tab.reserved == custom_reserved


class TestCStashTabChronicle:
    def test_read_chronicle_tab(self):
        chronicle_body = b"\xab\xcd\xef\x01\x23"
        total_size = STASH_TAB_HEADER_SIZE + len(chronicle_body)
        header = _build_stash_tab_header(
            stash_format=2,
            item_format=105,
            gold=0,
            tab_size=total_size,
            tab_type=STASH_TAB_TYPE_CHRONICLE,
        )
        data = header + chronicle_body
        bs = IBitStream(data)
        tab = StashTab()
        tab.deserialize(bs, version=105)
        assert tab.tab_type == STASH_TAB_TYPE_CHRONICLE
        assert tab.chronicle is not None
        assert tab.chronicle == chronicle_body

    def test_read_chronicle_tab_empty_body(self):
        header = _build_stash_tab_header(
            stash_format=2,
            item_format=105,
            gold=0,
            tab_size=STASH_TAB_HEADER_SIZE,
            tab_type=STASH_TAB_TYPE_CHRONICLE,
        )
        bs = IBitStream(header)
        tab = StashTab()
        tab.deserialize(bs, version=105)
        assert tab.tab_type == STASH_TAB_TYPE_CHRONICLE
        assert tab.chronicle is not None
        assert len(tab.chronicle) == 0

    def test_read_chronicle_tab_large_body(self):
        chronicle_body = bytes(range(256)) * 4
        total_size = STASH_TAB_HEADER_SIZE + len(chronicle_body)
        header = _build_stash_tab_header(
            stash_format=2,
            item_format=105,
            gold=0,
            tab_size=total_size,
            tab_type=STASH_TAB_TYPE_CHRONICLE,
        )
        data = header + chronicle_body
        bs = IBitStream(data)
        tab = StashTab()
        tab.deserialize(bs, version=105)
        assert tab.chronicle == chronicle_body


class TestCStashTabSerialize:
    def test_serialize_header_fields(self):
        tab = StashTab()
        tab.stash_format = 2
        tab.item_format = 105
        tab.gold = 99999
        tab.season = 5
        tab.tab_type = STASH_TAB_TYPE_NORMAL
        tab.reserved = b"\x00" * 43

        obs = OBitStream()
        tab.serialize(obs, version=105)
        data = obs.get_data()

        bs = IBitStream(data)
        magic = bs.read_dword()
        assert magic == STASH_TAB_MAGIC
        stash_format = bs.read_dword()
        assert stash_format == 2
        item_format = bs.read_dword()
        assert item_format == 105
        gold = bs.read_dword()
        assert gold == 99999
        tab_size = bs.read_word()
        assert tab_size == 0
        season = bs.read_word()
        assert season == 5
        tab_type = bs.read_byte()
        assert tab_type == STASH_TAB_TYPE_NORMAL

    def test_serialize_chronicle_tab(self):
        tab = StashTab()
        tab.stash_format = 2
        tab.item_format = 105
        tab.tab_type = STASH_TAB_TYPE_CHRONICLE
        tab.chronicle = b"\x01\x02\x03\x04\x05"
        tab.reserved = b"\x00" * 43

        obs = OBitStream()
        tab.serialize(obs, version=105)
        data = obs.get_data()

        assert len(data) > STASH_TAB_HEADER_SIZE
        chronicle_in_data = data[STASH_TAB_HEADER_SIZE:]
        assert chronicle_in_data == b"\x01\x02\x03\x04\x05"


class TestCSharedStash:
    def test_default_values(self):
        stash = SharedStash()
        assert stash.tabs == []
        assert stash.file_path == ""
        assert stash.get_tab_count() == 0

    def test_get_tab_out_of_range(self):
        stash = SharedStash()
        assert stash.get_tab(-1) is None
        assert stash.get_tab(0) is None
        assert stash.get_tab(99) is None

    def test_get_tab_gold_no_tabs(self):
        stash = SharedStash()
        assert stash.get_tab_gold(0) == 0

    def test_get_tab_items_no_tabs(self):
        stash = SharedStash()
        assert stash.get_tab_items(0) == []

    def test_read_single_classic_tab(self):
        header = _build_stash_tab_header(
            stash_format=1, item_format=99, gold=1000, tab_size=64, tab_type=STASH_TAB_TYPE_NORMAL
        )
        bs = IBitStream(header)
        stash = SharedStash()
        stash.deserialize(bs, version=99)
        assert stash.get_tab_count() == 1
        tab = stash.get_tab(0)
        assert tab is not None
        assert tab.stash_format == 1
        assert stash.get_tab_gold(0) == 1000

    def test_read_multiple_tabs(self):
        tab1 = _build_stash_tab_header(
            stash_format=2,
            item_format=105,
            gold=1000,
            tab_size=64,
            season=1,
            tab_type=STASH_TAB_TYPE_NORMAL,
        )
        tab2 = _build_stash_tab_header(
            stash_format=2,
            item_format=105,
            gold=2000,
            tab_size=64,
            season=2,
            tab_type=STASH_TAB_TYPE_ADVANCED,
        )
        tab3 = _build_stash_tab_header(
            stash_format=2,
            item_format=105,
            gold=3000,
            tab_size=64,
            season=3,
            tab_type=STASH_TAB_TYPE_CHRONICLE,
        )
        data = tab1 + tab2 + tab3
        bs = IBitStream(data)
        stash = SharedStash()
        stash.deserialize(bs, version=105)
        assert stash.get_tab_count() == 3
        assert stash.get_tab_gold(0) == 1000
        assert stash.get_tab_gold(1) == 2000
        assert stash.get_tab_gold(2) == 3000
        for idx, expected_season in enumerate([1, 2, 3]):
            tab = stash.get_tab(idx)
            assert tab is not None
            assert tab.season == expected_season

    def test_read_stops_on_invalid_magic(self):
        tab1 = _build_stash_tab_header(stash_format=1, item_format=99, gold=500, tab_size=64)
        garbage = struct.pack("<I", 0xDEADBEEF) + b"\x00" * 60
        data = tab1 + garbage
        bs = IBitStream(data)
        stash = SharedStash()
        stash.deserialize(bs, version=99)
        assert stash.get_tab_count() == 1

    def test_read_empty_data(self):
        bs = IBitStream(b"")
        stash = SharedStash()
        stash.deserialize(bs, version=99)
        assert stash.get_tab_count() == 0

    def test_read_insufficient_data(self):
        short_data = b"\x00" * 10
        bs = IBitStream(short_data)
        stash = SharedStash()
        stash.deserialize(bs, version=99)
        assert stash.get_tab_count() == 0

    def test_serialize_updates_tab_size(self):
        tab = StashTab()
        tab.stash_format = 2
        tab.item_format = 105
        tab.gold = 1234
        tab.tab_type = STASH_TAB_TYPE_CHRONICLE
        tab.chronicle = b"\xaa\xbb\xcc"
        tab.reserved = b"\x00" * 43

        stash = SharedStash()
        stash.tabs = [tab]

        obs = OBitStream()
        stash.serialize(obs, version=105)
        data = obs.get_data()

        tab_size_in_data = struct.unpack_from("<H", data, 16)[0]
        expected_size = STASH_TAB_HEADER_SIZE + len(tab.chronicle)
        assert tab_size_in_data == expected_size

    def test_roundtrip_chronicle_tab(self):
        chronicle_body = bytes(range(100))
        total_size = STASH_TAB_HEADER_SIZE + len(chronicle_body)
        header = _build_stash_tab_header(
            stash_format=2,
            item_format=105,
            gold=55555,
            tab_size=total_size,
            season=7,
            tab_type=STASH_TAB_TYPE_CHRONICLE,
        )
        data = header + chronicle_body

        bs = IBitStream(data)
        stash = SharedStash()
        stash.deserialize(bs, version=105)

        assert stash.get_tab_count() == 1
        tab = stash.get_tab(0)
        assert tab is not None
        assert tab.chronicle == chronicle_body
        assert tab.gold == 55555
        assert tab.season == 7

        obs = OBitStream()
        stash.serialize(obs, version=105)
        serialized = obs.get_data()

        bs2 = IBitStream(serialized)
        stash2 = SharedStash()
        stash2.deserialize(bs2, version=105)
        assert stash2.get_tab_count() == 1
        tab2 = stash2.get_tab(0)
        assert tab2 is not None
        assert tab2.chronicle == chronicle_body
        assert tab2.gold == 55555
        assert tab2.season == 7

    def test_roundtrip_multiple_tabs(self):
        tabs_data = b""
        for i in range(3):
            body = bytes([i] * 20)
            total_size = STASH_TAB_HEADER_SIZE + len(body)
            header = _build_stash_tab_header(
                stash_format=2,
                item_format=105,
                gold=1000 * (i + 1),
                tab_size=total_size,
                season=i,
                tab_type=STASH_TAB_TYPE_CHRONICLE,
            )
            tabs_data += header + body

        bs = IBitStream(tabs_data)
        stash = SharedStash()
        stash.deserialize(bs, version=105)

        obs = OBitStream()
        stash.serialize(obs, version=105)
        serialized = obs.get_data()

        bs2 = IBitStream(serialized)
        stash2 = SharedStash()
        stash2.deserialize(bs2, version=105)

        assert stash2.get_tab_count() == 3
        for i in range(3):
            tab = stash2.get_tab(i)
            assert tab is not None
            assert tab.gold == 1000 * (i + 1)
            assert tab.season == i
            assert tab.chronicle == bytes([i] * 20)


class TestClassifyAdvancedTab:
    def _make_item(self, type_name):
        class FakeItem:
            def __init__(self, tn):
                self.type_name = tn

        return FakeItem(type_name)

    def test_empty_items(self):
        assert classify_advanced_tab([]) == ADVANCED_SUBTYPE_UNKNOWN

    def test_none_items(self):
        assert classify_advanced_tab(None) == ADVANCED_SUBTYPE_UNKNOWN

    def test_rune_only(self):
        items = [self._make_item(b"r01 "), self._make_item(b"r33 ")]
        assert classify_advanced_tab(items) == ADVANCED_SUBTYPE_RUNE

    def test_gem_only(self):
        items = [self._make_item(b"gcv "), self._make_item(b"skz ")]
        assert classify_advanced_tab(items) == ADVANCED_SUBTYPE_GEM

    def test_material_only(self):
        items = [self._make_item(b"rvs "), self._make_item(b"ua5 ")]
        assert classify_advanced_tab(items) == ADVANCED_SUBTYPE_MATERIAL

    def test_unknown_items_only(self):
        items = [self._make_item(b"cap "), self._make_item(b"axf ")]
        assert classify_advanced_tab(items) == ADVANCED_SUBTYPE_UNKNOWN

    def test_mixed_majority_rune(self):
        items = [self._make_item(b"r01 "), self._make_item(b"r02 "), self._make_item(b"gcv ")]
        assert classify_advanced_tab(items) == ADVANCED_SUBTYPE_RUNE

    def test_mixed_majority_gem(self):
        items = [self._make_item(b"gcv "), self._make_item(b"gfy "), self._make_item(b"r01 ")]
        assert classify_advanced_tab(items) == ADVANCED_SUBTYPE_GEM

    def test_mixed_majority_material(self):
        items = [self._make_item(b"rvs "), self._make_item(b"dhn "), self._make_item(b"r01 ")]
        assert classify_advanced_tab(items) == ADVANCED_SUBTYPE_MATERIAL


class TestGetAdvancedLayout:
    def test_gem_layout(self):
        assert get_advanced_layout(ADVANCED_SUBTYPE_GEM) == GEM_LAYOUT
        assert GEM_LAYOUT == (7, 5)

    def test_rune_layout(self):
        assert get_advanced_layout(ADVANCED_SUBTYPE_RUNE) == RUNE_LAYOUT
        assert RUNE_LAYOUT == (9, 4)

    def test_material_layout(self):
        assert get_advanced_layout(ADVANCED_SUBTYPE_MATERIAL) == MATERIAL_LAYOUT
        assert MATERIAL_LAYOUT == (10, 3)

    def test_unknown_layout(self):
        assert get_advanced_layout(ADVANCED_SUBTYPE_UNKNOWN) == NORMAL_LAYOUT
        assert NORMAL_LAYOUT == (10, 10)


class TestGetAdvancedSlotOrder:
    def test_gem_slot_order(self):
        result = get_advanced_slot_order(ADVANCED_SUBTYPE_GEM)
        assert result == GEM_SLOT_ORDER
        assert len(GEM_SLOT_ORDER) == 35

    def test_rune_slot_order(self):
        result = get_advanced_slot_order(ADVANCED_SUBTYPE_RUNE)
        assert result == RUNE_SLOT_ORDER
        assert len(RUNE_SLOT_ORDER) == 33

    def test_material_slot_order(self):
        result = get_advanced_slot_order(ADVANCED_SUBTYPE_MATERIAL)
        assert result == MATERIAL_SLOT_ORDER
        assert len(MATERIAL_SLOT_ORDER) == 23

    def test_unknown_slot_order(self):
        result = get_advanced_slot_order(ADVANCED_SUBTYPE_UNKNOWN)
        assert result == GEM_SLOT_ORDER + RUNE_SLOT_ORDER + MATERIAL_SLOT_ORDER


class TestComputeAdvancedGrid:
    def _make_item(self, type_name):
        class FakeItem:
            def __init__(self, tn):
                self.type_name = tn

        return FakeItem(type_name)

    def test_empty_items_gem(self):
        cols, rows, slots = compute_advanced_grid([], ADVANCED_SUBTYPE_GEM)
        assert cols == GEM_LAYOUT[0]
        assert rows == GEM_LAYOUT[1]
        assert slots == GEM_SLOT_ORDER

    def test_empty_items_rune(self):
        cols, rows, _slots = compute_advanced_grid([], ADVANCED_SUBTYPE_RUNE)
        assert cols == RUNE_LAYOUT[0]
        assert rows == RUNE_LAYOUT[1]

    def test_empty_items_material(self):
        cols, rows, _slots = compute_advanced_grid([], ADVANCED_SUBTYPE_MATERIAL)
        assert cols == MATERIAL_LAYOUT[0]
        assert rows == MATERIAL_LAYOUT[1]

    def test_with_items_within_base_layout(self):
        items = [self._make_item(b"r01 "), self._make_item(b"r02 ")]
        cols, rows, _slots = compute_advanced_grid(items, ADVANCED_SUBTYPE_RUNE)
        assert cols == RUNE_LAYOUT[0]
        assert rows == RUNE_LAYOUT[1]

    def test_with_items_exceeding_base_rows(self):
        items = [self._make_item(f"r{i:02d} ".encode()) for i in range(1, 40)]
        cols, rows, _slots = compute_advanced_grid(items, ADVANCED_SUBTYPE_RUNE)
        assert cols == RUNE_LAYOUT[0]
        assert rows * cols >= len(items)


class TestCodeSets:
    def test_rune_codes_count(self):
        assert len(RUNE_CODES) == 33

    def test_gem_codes_count(self):
        assert len(GEM_CODES) == 35

    def test_material_codes_count(self):
        assert len(MATERIAL_CODES) == 23

    def test_rune_slot_order_matches_codes(self):
        for code in RUNE_SLOT_ORDER:
            assert code in RUNE_CODES

    def test_gem_slot_order_matches_codes(self):
        for code in GEM_SLOT_ORDER:
            assert code in GEM_CODES

    def test_material_slot_order_matches_codes(self):
        for code in MATERIAL_SLOT_ORDER:
            assert code in MATERIAL_CODES

    def test_no_overlap_between_code_sets(self):
        assert set() == RUNE_CODES & GEM_CODES
        assert set() == RUNE_CODES & MATERIAL_CODES
        assert set() == GEM_CODES & MATERIAL_CODES
