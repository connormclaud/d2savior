import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from d2savior.core.d2data import GameData, get_game_data
from d2savior.core.d2s_struct import D2SStruct
from d2savior.core.formatters import ensure_data_loaded
from d2savior.core.ibitstream import IBitStream
from d2savior.core.item import D2Item, ExtItemInfo, ItemInfo, TypeSpecificInfo
from d2savior.core.obitstream import OBitStream
from d2savior.core.stash import SharedStash


class TestItemSerialization(unittest.TestCase):
    game_data: GameData

    @classmethod
    def setUpClass(cls):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        ensure_data_loaded()
        gd = get_game_data()
        assert gd is not None
        cls.game_data = gd
        cls.examples_dir = os.path.join(base_dir, "..", "examples")
        cls.items_dir = os.path.join(base_dir, "..", "items")
        cls.fixtures_dir = os.path.join(base_dir, "tests", "fixtures")

    def _deserialize_item(self, file_path: str, version: int | None = None):
        if not os.path.exists(file_path):
            self.skipTest(f"Test file not found: {file_path}")
        with open(file_path, "rb") as f:
            data = f.read()

        ver = version if version is not None else 0x63
        vd = self.game_data.for_version(ver) if self.game_data else None
        bs = IBitStream(data)
        item = D2Item()

        if version is not None:
            item.deserialize(bs, version, read_magic=False, data=vd)
        else:
            item.deserialize(bs, 0x63, read_magic=True, data=vd)

        return item

    def _serialize_item(self, item: D2Item, version: int):
        vd = self.game_data.for_version(version) if self.game_data else None
        bs = OBitStream()
        item.serialize(bs, version, write_magic=False, data=vd)
        return bs.get_data()

    def _compare_items(self, item1: D2Item, item2: D2Item):
        assert item1.type_name == item2.type_name
        assert item1.quality() == item2.quality()
        assert item1.is_identified == item2.is_identified
        assert item1.is_simple == item2.is_simple
        assert item1.is_socketed == item2.is_socketed
        assert item1.is_runeword == item2.is_runeword
        assert item1.is_ethereal == item2.is_ethereal
        assert item1.is_personalized == item2.is_personalized

        if (
            item1.item_info
            and item1.item_info.ext_info
            and item2.item_info
            and item2.item_info.ext_info
        ):
            ext1 = item1.item_info.ext_info
            ext2 = item2.item_info.ext_info
            assert ext1.quality == ext2.quality
            assert ext1.guid == ext2.guid
            assert ext1.gems == ext2.gems

    def _compare_properties(self, item1: D2Item, item2: D2Item):
        if not item1.item_info or not item2.item_info:
            return

        tp1 = item1.item_info.type_specific_info
        tp2 = item2.item_info.type_specific_info

        if not tp1 or not tp2:
            return

        props1 = tp1.property_list.properties
        props2 = tp2.property_list.properties

        assert len(props1) == len(props2), (
            f"Property count mismatch: {len(props1)} vs {len(props2)}"
        )

        for i, (p1, p2) in enumerate(zip(props1, props2, strict=False)):
            assert p1[0] == p2[0], f"Property {i}: ID mismatch"
            assert p1[1] == p2[1], f"Property {i}: Layer mismatch"
            assert p1[2] == p2[2], f"Property {i}: Value mismatch"

        if item1.is_runeword:
            assert tp1.runeword_property_list is not None, "Item1 should have runeword properties"
            assert tp2.runeword_property_list is not None, "Item2 should have runeword properties"

            rw_props1 = tp1.runeword_property_list.properties
            rw_props2 = tp2.runeword_property_list.properties

            assert len(rw_props1) == len(rw_props2), (
                f"Runeword property count mismatch: {len(rw_props1)} vs {len(rw_props2)}"
            )

            for i, (p1, p2) in enumerate(zip(rw_props1, rw_props2, strict=False)):
                assert p1[0] == p2[0], f"Runeword property {i}: ID mismatch"
                assert p1[1] == p2[1], f"Runeword property {i}: Layer mismatch"
                assert p1[2] == p2[2], f"Runeword property {i}: Value mismatch"

        if item1.is_set():
            assert len(tp1.has_set_prop_list) == len(tp2.has_set_prop_list), (
                "Set property list count mismatch"
            )

            for i, (has1, has2) in enumerate(
                zip(tp1.has_set_prop_list, tp2.has_set_prop_list, strict=False)
            ):
                assert has1 == has2, f"Set property {i} existence mismatch"

                if has1 and has2:
                    sp1 = tp1.set_properties[i]
                    set_props1 = sp1.properties if sp1 is not None else []
                    sp2 = tp2.set_properties[i]
                    set_props2 = sp2.properties if sp2 is not None else []

                    assert len(set_props1) == len(set_props2), (
                        f"Set property {i} count mismatch: {len(set_props1)} vs {len(set_props2)}"
                    )

                    for j, (p1, p2) in enumerate(zip(set_props1, set_props2, strict=False)):
                        assert p1[0] == p2[0], f"Set property {i}.{j}: ID mismatch"
                        assert p1[1] == p2[1], f"Set property {i}.{j}: Layer mismatch"
                        assert p1[2] == p2[2], f"Set property {i}.{j}: Value mismatch"

    def test_deserialize_unique_amulet_0x63(self):
        file_path = os.path.join(self.examples_dir, "Rixots Keen.d2i")
        item = self._deserialize_item(file_path)

        assert item.type_name == b"amu "
        assert item.quality() == 7
        assert item.is_identified
        assert not item.is_simple
        assert item.version == 99

    def test_deserialize_runeword_spirit_0x69(self):
        file_path = os.path.join(self.items_dir, "runeword", "Spirit-crystal_sword.d2i")
        item = self._deserialize_item(file_path, version=0x69)

        assert item.type_name == b"crs "
        assert item.is_runeword
        assert item.is_socketed
        assert item.is_identified
        assert not item.is_simple

        if item.item_info and item.item_info.ext_info:
            ext = item.item_info.ext_info
            assert ext.rune_id is not None
            assert ext.rune_id == 20635

    def test_serialize_unique_amulet_0x63(self):
        file_path = os.path.join(self.examples_dir, "Rixots Keen.d2i")
        if not os.path.exists(file_path):
            self.skipTest(f"Test file not found: {file_path}")

        item = self._deserialize_item(file_path)

        serialized_data = self._serialize_item(item, 0x63)

        bs = IBitStream(serialized_data)
        item2 = D2Item()
        item2.deserialize(bs, 0x63, read_magic=False, data=self.game_data.for_version(0x63))

        self._compare_items(item, item2)
        self._compare_properties(item, item2)

    def test_serialize_runeword_spirit_0x69(self):
        file_path = os.path.join(self.items_dir, "runeword", "Spirit-crystal_sword.d2i")

        item = self._deserialize_item(file_path, version=0x69)

        serialized_data = self._serialize_item(item, 0x69)

        bs = IBitStream(serialized_data)
        item2 = D2Item()
        item2.deserialize(bs, 0x69, read_magic=False, data=self.game_data.for_version(0x69))

        self._compare_items(item, item2)
        self._compare_properties(item, item2)

    def test_serialize_magic_item_0x69(self):
        file_path = os.path.join(self.items_dir, "magic", "cm1_006.d2i")

        item = self._deserialize_item(file_path, version=0x69)

        assert item.quality() == 4, "Item should be magic quality"

        serialized_data = self._serialize_item(item, 0x69)

        bs = IBitStream(serialized_data)
        item2 = D2Item()
        item2.deserialize(bs, 0x69, read_magic=False, data=self.game_data.for_version(0x69))

        self._compare_items(item, item2)
        self._compare_properties(item, item2)

    def test_serialize_rare_item_0x69(self):
        file_path = os.path.join(self.items_dir, "rare", "wa4_012.d2i")

        item = self._deserialize_item(file_path, version=0x69)

        assert item.quality() == 6, "Item should be rare quality"

        serialized_data = self._serialize_item(item, 0x69)

        bs = IBitStream(serialized_data)
        item2 = D2Item()
        item2.deserialize(bs, 0x69, read_magic=False, data=self.game_data.for_version(0x69))

        self._compare_items(item, item2)
        self._compare_properties(item, item2)

    def test_serialize_set_item_0x69(self):
        file_path = os.path.join(self.items_dir, "set", "hbl_000.d2i")

        item = self._deserialize_item(file_path, version=0x69)

        assert item.quality() == 5, "Item should be set quality"

        serialized_data = self._serialize_item(item, 0x69)

        bs = IBitStream(serialized_data)
        item2 = D2Item()
        item2.deserialize(bs, 0x69, read_magic=False, data=self.game_data.for_version(0x69))

        self._compare_items(item, item2)
        self._compare_properties(item, item2)

    def test_serialize_normal_item_0x69(self):
        file_path = os.path.join(self.items_dir, "normal", "box_009.d2i")

        item = self._deserialize_item(file_path, version=0x69)

        assert item.quality() == 2, "Item should be normal quality"

        serialized_data = self._serialize_item(item, 0x69)

        bs = IBitStream(serialized_data)
        item2 = D2Item()
        item2.deserialize(bs, 0x69, read_magic=False, data=self.game_data.for_version(0x69))

        self._compare_items(item, item2)

    def test_roundtrip_sork_items(self):
        file_path = os.path.join(self.fixtures_dir, "sork.d2s")
        with open(file_path, "rb") as f:
            raw_data = f.read()

        bs = IBitStream(raw_data)
        d2s = D2SStruct()
        d2s.deserialize(bs, data=self.game_data)

        assert len(d2s.item_list) > 0, "No items found in sork.d2s"

        vd = self.game_data.for_version(d2s.version)

        # Verify bit-exact match against raw save bitstream
        jm_pos = raw_data.find(b"JM")
        assert jm_pos != -1
        bs_raw = IBitStream(raw_data)
        bs_raw._offset = jm_pos * 8
        assert bs_raw.read_word() == 0x4D4A
        count = bs_raw.read_word()

        for i in range(count):
            start = bs_raw.get_offset()
            item = D2Item()
            item.deserialize(bs_raw, d2s.version, False, data=vd)
            end = bs_raw.get_offset()
            bit_len = end - start

            bs_slice = IBitStream(raw_data)
            bs_slice._offset = start
            orig_bits = [bs_slice.read_bits(1) for _ in range(bit_len)]

            obs = OBitStream()
            item.serialize(obs, d2s.version, False, data=vd)
            obs_data = obs.get_data()
            obs_bs = IBitStream(obs_data)
            ser_bits = [obs_bs.read_bits(1) for _ in range(bit_len)]

            assert orig_bits == ser_bits, (
                f"Item {i} ({item.type_name}) bit mismatch against raw file"
            )

            # Verify deserialize -> serialize round-trip
            item2 = D2Item()
            item2.deserialize(IBitStream(obs_data), d2s.version, False, data=vd)
            obs2 = OBitStream()
            item2.serialize(obs2, d2s.version, False, data=vd)
            assert obs_data == obs2.get_data()
            self._compare_items(item, item2)
            self._compare_properties(item, item2)

    def test_roundtrip_stash_items(self):
        file_path = os.path.join(self.fixtures_dir, "ModernSharedStashSoftCoreV2.d2i")
        with open(file_path, "rb") as f:
            raw_data = f.read()

        bs = IBitStream(raw_data)
        stash = SharedStash()
        stash.deserialize(bs, data=self.game_data)

        total_items = 0
        bs_raw = IBitStream(raw_data)

        for tab_idx, _tab in enumerate(stash.tabs):
            start_tab = bs_raw.bytes_pos
            _magic = bs_raw.read_dword()
            _stash_format = bs_raw.read_dword()
            item_format = bs_raw.read_dword()
            _gold = bs_raw.read_dword()
            tab_size = bs_raw.read_word()
            _season = bs_raw.read_word()
            tab_type = bs_raw.read_byte()
            _reserved = bytes(bs_raw.read_byte() for _ in range(43))

            if tab_type == 2:  # chronicle tab
                bs_raw.bytes_pos = start_tab + tab_size
                continue

            vd = self.game_data.for_version(item_format)
            _jm = bs_raw.read_word()
            count = bs_raw.read_word()
            for i in range(count):
                if bs_raw.is_end() or bs_raw.remaining() < 16 * 8:
                    break
                start = bs_raw.get_offset()
                item = D2Item()
                try:
                    item.deserialize(bs_raw, item_format, False, data=vd)
                except ValueError:
                    bs_raw._offset = start
                    continue
                end = bs_raw.get_offset()
                bit_len = end - start

                bs_slice = IBitStream(raw_data)
                bs_slice._offset = start
                orig_bits = [bs_slice.read_bits(1) for _ in range(bit_len)]

                obs = OBitStream()
                item.serialize(obs, item_format, False, data=vd)
                obs_data = obs.get_data()
                obs_bs = IBitStream(obs_data)
                ser_bits = [obs_bs.read_bits(1) for _ in range(bit_len)]

                total_items += 1
                assert orig_bits == ser_bits, (
                    f"Tab {tab_idx} Item {i} ({item.type_name}) bit mismatch against raw file"
                )

                item2 = D2Item()
                item2.deserialize(IBitStream(obs_data), item_format, False, data=vd)
                obs2 = OBitStream()
                item2.serialize(obs2, item_format, False, data=vd)
                assert obs_data == obs2.get_data()
                self._compare_items(item, item2)
                self._compare_properties(item, item2)

            bs_raw.bytes_pos = start_tab + tab_size

        assert total_items == 165

    def test_deserialize_standalone_item_with_game_data(self):
        sork_path = os.path.join(self.fixtures_dir, "sork.d2s")
        if not os.path.exists(sork_path):
            self.skipTest(f"Test file not found: {sork_path}")
        with open(sork_path, "rb") as f:
            d2s_data = f.read()
        char = D2SStruct()
        char.deserialize(IBitStream(d2s_data), data=self.game_data)
        assert len(char.item_list.items) > 0
        first_item = char.item_list.items[0]
        obs = OBitStream()
        first_item.serialize(obs, char.version, write_magic=True, data=self.game_data)
        item_bytes = obs.get_data()

        new_item = D2Item()
        new_item.deserialize(IBitStream(item_bytes), data=self.game_data)
        assert new_item.version == char.version
        assert new_item._data is not None
        assert new_item._data.version == char.version

    def test_roundtrip_gold_item_d2r(self):
        vd = self.game_data.for_version(0x69)
        meta = vd.get_item_meta(b"gld ")
        assert meta is not None

        item = D2Item()
        item.version = 0x69
        item.is_simple = False
        item._meta = meta
        item.item_info = ItemInfo(meta)
        item.item_info.type_name = b"gld "
        item.item_info.ext_info = ExtItemInfo(meta)
        item.item_info.type_specific_info = TypeSpecificInfo(meta)

        from d2savior.core.item_name import GoldQuantity

        gold = GoldQuantity()
        gold.quantity = 1234
        gold.is_not_gold = False
        item.item_info.gold = gold

        obs = OBitStream()
        item.serialize(obs, 0x69, write_magic=True, data=self.game_data)
        data = obs.get_data()

        item2 = D2Item()
        item2.deserialize(IBitStream(data), data=self.game_data)

        assert item2.item_info is not None
        assert item2.item_info.is_gold()
        assert item2.item_info.gold is not None
        assert item2.item_info.gold.quantity == 1234
        assert not item2.item_info.gold.is_not_gold

        obs2 = OBitStream()
        item2.serialize(obs2, 0x69, write_magic=True, data=self.game_data)
        assert data == obs2.get_data()

    def test_roundtrip_chronicle_compact_d2r(self):
        vd = self.game_data.for_version(0x69)
        meta = vd.get_item_meta(b"rin ")
        assert meta is not None

        item = D2Item()
        item.version = 0x69
        item.is_simple = False
        item._meta = meta
        item.item_info = ItemInfo(meta)
        item.item_info.type_name = b"rin "
        item.item_info.ext_info = ExtItemInfo(meta)
        item.item_info.type_specific_info = TypeSpecificInfo(meta)
        item._is_chronicle = True
        item._is_chronicle_compact = True
        item.chronicle_id = 42
        item.chronicle_compact_data = 0x123456789ABCDEF0

        obs = OBitStream()
        item.serialize(obs, 0x69, write_magic=True, data=self.game_data)
        data = obs.get_data()

        item2 = D2Item()
        item2.deserialize(IBitStream(data), data=self.game_data)

        assert item2._is_chronicle
        assert item2._is_chronicle_compact
        assert item2.chronicle_id == 42
        assert item2.chronicle_compact_data == 0x123456789ABCDEF0

        obs2 = OBitStream()
        item2.serialize(obs2, 0x69, write_magic=True, data=self.game_data)
        assert data == obs2.get_data()

    def test_roundtrip_chronicle_multi_entry_d2r(self):
        vd = self.game_data.for_version(0x69)
        meta = vd.get_item_meta(b"amu ")
        assert meta is not None

        item = D2Item()
        item.version = 0x69
        item.is_simple = False
        item._meta = meta
        item.item_info = ItemInfo(meta)
        item.item_info.type_name = b"amu "
        item.item_info.ext_info = ExtItemInfo(meta)
        item.item_info.type_specific_info = TypeSpecificInfo(meta)
        item._is_chronicle = True
        item._is_chronicle_compact = False
        item.chronicle_id = 99
        item.chronicle_data_header = 0xAABBCCDD
        item.chronicle_entries = [0x1111222233334444, 0x5555666677778888]

        obs = OBitStream()
        item.serialize(obs, 0x69, write_magic=True, data=self.game_data)
        data = obs.get_data()

        item2 = D2Item()
        item2.deserialize(IBitStream(data), data=self.game_data)

        assert item2._is_chronicle
        assert not item2._is_chronicle_compact
        assert item2.chronicle_id == 99
        assert item2.chronicle_data_header == 0xAABBCCDD
        assert item2.chronicle_entries == [0x1111222233334444, 0x5555666677778888]

        obs2 = OBitStream()
        item2.serialize(obs2, 0x69, write_magic=True, data=self.game_data)
        assert data == obs2.get_data()

    def test_roundtrip_ear_item(self):
        from d2savior.core.ear import Ear

        item = D2Item()
        item.version = 0x69
        item.is_ear = True
        ear = Ear("HeroKiller")
        ear.ear_class = 3
        ear.ear_level = 85
        item.ear = ear

        obs = OBitStream()
        item.serialize(obs, 0x69, write_magic=True, data=self.game_data)
        data = obs.get_data()

        item2 = D2Item()
        item2.deserialize(IBitStream(data), data=self.game_data)

        assert item2.is_ear
        assert item2.ear is not None
        assert item2.ear.ear_name == "HeroKiller"
        assert item2.ear.ear_class == 3
        assert item2.ear.ear_level == 85

        obs2 = OBitStream()
        item2.serialize(obs2, 0x69, write_magic=True, data=self.game_data)
        assert data == obs2.get_data()

    def test_flag_mutation_on_loaded_item(self):
        sork_path = os.path.join(self.fixtures_dir, "sork.d2s")
        if not os.path.exists(sork_path):
            self.skipTest(f"Test file not found: {sork_path}")
        with open(sork_path, "rb") as f:
            d2s_data = f.read()
        char = D2SStruct()
        char.deserialize(IBitStream(d2s_data), data=self.game_data)
        item = char.item_list.items[0]
        assert item.is_identified is True

        item.is_identified = False
        obs = OBitStream()
        item.serialize(obs, char.version, write_magic=True, data=self.game_data)

        item2 = D2Item()
        item2.deserialize(IBitStream(obs.get_data()), data=self.game_data)
        assert item2.is_identified is False

    def test_d2item_serialize_default_version(self):
        item = D2Item()
        assert item.version == 0
        obs = OBitStream()
        item.serialize(obs, 0x69, write_magic=True, data=self.game_data)

        item2 = D2Item()
        item2.deserialize(IBitStream(obs.get_data()), data=self.game_data)
        assert item2.version == 0x69

    def test_roundtrip_classic_ear(self):
        from d2savior.core.ear import Ear

        ear = Ear("ClassicHero")
        ear.ear_class = 2
        ear.ear_level = 42

        obs = OBitStream()
        ear.serialize(obs, 0x60)
        data = obs.get_data()

        ear2 = Ear()
        ear2.deserialize(IBitStream(data), 0x60)
        assert ear2.ear_name == "ClassicHero"
        assert ear2.ear_class == 2
        assert ear2.ear_level == 42

        item = D2Item()
        item.version = 0x60
        item.is_ear = True
        item.ear = Ear("PVPVictim")
        item.ear.ear_class = 1
        item.ear.ear_level = 70

        obs_item = OBitStream()
        item.serialize(obs_item, 0x60, write_magic=True)
        item_data = obs_item.get_data()

        item2 = D2Item()
        item2.deserialize(IBitStream(item_data), 0x60, read_magic=True)
        assert item2.is_ear
        assert item2.ear is not None
        assert item2.ear.ear_name == "PVPVictim"
        assert item2.ear.ear_class == 1
        assert item2.ear.ear_level == 70


if __name__ == "__main__":
    unittest.main()
