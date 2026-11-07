import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from d2savior.core.d2data import init_d2data
from d2savior.core.d2s_struct import D2SStruct
from d2savior.core.ibitstream import IBitStream
from d2savior.core.item import init_item_data
from d2savior.core.localized_data import init_localized_data
from d2savior.core.obitstream import OBitStream

EXAMPLES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "examples"
)


def _load_d2s(save_file):
    with open(save_file, "rb") as f:
        data = f.read()
    bs = IBitStream(data)
    d2s = D2SStruct()
    d2s.deserialize(bs)
    return d2s


@pytest.fixture(scope="module", autouse=True)
def init_data():
    data_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "d2savior", "data"
    )
    init_item_data(
        os.path.join(data_dir, "itemdata.txt"),
        os.path.join(data_dir, "property.txt"),
        os.path.join(data_dir, "ItemStatCost.txt"),
    )
    init_d2data(data_dir)
    init_localized_data(os.path.join(data_dir, "local"), lang_key="enUS")


class Test0x69Warlock:
    SAVE_FILE = os.path.join(EXAMPLES_DIR, "0x69", "warlock.d2s")

    @pytest.fixture(autouse=True)
    def load_char(self):
        if not os.path.exists(self.SAVE_FILE):
            pytest.skip(f"Save file not found: {self.SAVE_FILE}")
        self.d2s = _load_d2s(self.SAVE_FILE)

    def test_version(self):
        assert self.d2s.version == 0x69

    def test_char_class(self):
        assert self.d2s.char_class == 7
        assert self.d2s.get_char_class_name() == "Warlock"

    def test_char_name(self):
        assert self.d2s.get_char_name() == "warlock"

    def test_game_version(self):
        assert self.d2s.game_version == 3

    def test_is_expansion(self):
        assert self.d2s.is_expansion() is True

    def test_is_hardcore(self):
        assert self.d2s.is_hardcore() is False

    def test_is_ladder(self):
        assert self.d2s.is_ladder() is False

    def test_is_died_before(self):
        assert self.d2s.is_died_before() is False

    def test_char_level(self):
        assert self.d2s.char_level == 92

    def test_char_title(self):
        assert self.d2s.char_title == 15

    def test_weapon_set(self):
        assert self.d2s.weapon_set == 0

    def test_has_mercenary(self):
        assert self.d2s.has_mercenary() is True

    def test_player_stats(self):
        ps = self.d2s.player_stats
        assert ps.magic == 0x6667
        assert ps.stat_values[0] == 85
        assert ps.stat_values[1] == 20
        assert ps.stat_values[2] == 40
        assert ps.stat_values[3] == 279

    def test_demon_present(self):
        assert self.d2s.demon.has_demon is True

    def test_item_list_not_empty(self):
        assert len(self.d2s.item_list.items) > 0

    def test_preview_data(self):
        assert len(self.d2s.preview_data) == 228
        assert self.d2s.preview_data[0x49] == 3

    def test_char_flags(self):
        assert self.d2s.char_flags == 0xF00


class Test0x69Amazon:
    SAVE_FILE = os.path.join(EXAMPLES_DIR, "0x69", "白皮克星.d2s")

    @pytest.fixture(autouse=True)
    def load_char(self):
        if not os.path.exists(self.SAVE_FILE):
            pytest.skip(f"Save file not found: {self.SAVE_FILE}")
        self.d2s = _load_d2s(self.SAVE_FILE)

    def test_version(self):
        assert self.d2s.version == 0x69

    def test_char_class(self):
        assert self.d2s.char_class == 0
        assert self.d2s.get_char_class_name() == "Amazon"

    def test_char_name(self):
        assert self.d2s.get_char_name() == "白皮克星"

    def test_game_version(self):
        assert self.d2s.game_version == 3

    def test_is_expansion(self):
        assert self.d2s.is_expansion() is True

    def test_is_hardcore(self):
        assert self.d2s.is_hardcore() is False

    def test_char_level(self):
        assert self.d2s.char_level == 25

    def test_char_title(self):
        assert self.d2s.char_title == 1

    def test_weapon_set(self):
        assert self.d2s.weapon_set == 0

    def test_has_mercenary(self):
        assert self.d2s.has_mercenary() is True

    def test_player_stats(self):
        ps = self.d2s.player_stats
        assert ps.magic == 0x6667
        assert ps.stat_values[0] == 75
        assert ps.stat_values[1] == 15
        assert ps.stat_values[2] == 25
        assert ps.stat_values[3] == 80

    def test_demon_not_present(self):
        assert self.d2s.demon.has_demon is False

    def test_char_flags(self):
        assert self.d2s.char_flags == 0x100


class Test0x69Necromancer:
    SAVE_FILE = os.path.join(EXAMPLES_DIR, "0x69", "魑魅.d2s")

    @pytest.fixture(autouse=True)
    def load_char(self):
        if not os.path.exists(self.SAVE_FILE):
            pytest.skip(f"Save file not found: {self.SAVE_FILE}")
        self.d2s = _load_d2s(self.SAVE_FILE)

    def test_version(self):
        assert self.d2s.version == 0x69

    def test_char_class(self):
        assert self.d2s.char_class == 2
        assert self.d2s.get_char_class_name() == "Necromancer"

    def test_char_name(self):
        assert self.d2s.get_char_name() == "魑魅"

    def test_game_version(self):
        assert self.d2s.game_version == 3

    def test_is_expansion(self):
        assert self.d2s.is_expansion() is True

    def test_is_hardcore(self):
        assert self.d2s.is_hardcore() is False

    def test_char_level(self):
        assert self.d2s.char_level == 64

    def test_char_title(self):
        assert self.d2s.char_title == 7

    def test_weapon_set(self):
        assert self.d2s.weapon_set == 1

    def test_has_mercenary(self):
        assert self.d2s.has_mercenary() is True

    def test_player_stats(self):
        ps = self.d2s.player_stats
        assert ps.magic == 0x6667
        assert ps.stat_values[0] == 50
        assert ps.stat_values[1] == 25
        assert ps.stat_values[2] == 25
        assert ps.stat_values[3] == 230

    def test_demon_not_present(self):
        assert self.d2s.demon.has_demon is False

    def test_char_flags(self):
        assert self.d2s.char_flags == 0x720


class Test0x69Sorceress:
    SAVE_FILE = os.path.join(EXAMPLES_DIR, "0x69", "大明女医.d2s")

    @pytest.fixture(autouse=True)
    def load_char(self):
        if not os.path.exists(self.SAVE_FILE):
            pytest.skip(f"Save file not found: {self.SAVE_FILE}")
        self.d2s = _load_d2s(self.SAVE_FILE)

    def test_version(self):
        assert self.d2s.version == 0x69

    def test_char_class(self):
        assert self.d2s.char_class == 1
        assert self.d2s.get_char_class_name() == "Sorceress"

    def test_char_name(self):
        assert self.d2s.get_char_name() == "大明女医"

    def test_game_version(self):
        assert self.d2s.game_version == 2

    def test_is_expansion(self):
        assert self.d2s.is_expansion() is True

    def test_is_hardcore(self):
        assert self.d2s.is_hardcore() is False

    def test_char_level(self):
        assert self.d2s.char_level == 1

    def test_char_title(self):
        assert self.d2s.char_title == 0

    def test_weapon_set(self):
        assert self.d2s.weapon_set == 1

    def test_has_mercenary(self):
        assert self.d2s.has_mercenary() is False

    def test_player_stats(self):
        ps = self.d2s.player_stats
        assert ps.magic == 0x6667
        assert ps.stat_values[0] == 10
        assert ps.stat_values[1] == 35
        assert ps.stat_values[2] == 25
        assert ps.stat_values[3] == 10

    def test_demon_not_present(self):
        assert self.d2s.demon.has_demon is False

    def test_char_flags(self):
        assert self.d2s.char_flags == 0x0


class Test0x69PaladinPet:
    SAVE_FILE = os.path.join(EXAMPLES_DIR, "0x69", "pet.d2s")

    @pytest.fixture(autouse=True)
    def load_char(self):
        if not os.path.exists(self.SAVE_FILE):
            pytest.skip(f"Save file not found: {self.SAVE_FILE}")
        self.d2s = _load_d2s(self.SAVE_FILE)

    def test_version(self):
        assert self.d2s.version == 0x69

    def test_char_class(self):
        assert self.d2s.char_class == 3
        assert self.d2s.get_char_class_name() == "Paladin"

    def test_char_name(self):
        assert self.d2s.get_char_name() == "pet"

    def test_game_version(self):
        assert self.d2s.game_version == 3

    def test_is_expansion(self):
        assert self.d2s.is_expansion() is True

    def test_is_hardcore(self):
        assert self.d2s.is_hardcore() is False

    def test_char_level(self):
        assert self.d2s.char_level == 1

    def test_char_title(self):
        assert self.d2s.char_title == 0

    def test_weapon_set(self):
        assert self.d2s.weapon_set == 0

    def test_has_mercenary(self):
        assert self.d2s.has_mercenary() is False

    def test_player_stats(self):
        ps = self.d2s.player_stats
        assert ps.magic == 0x6667
        assert ps.stat_values[0] == 25
        assert ps.stat_values[1] == 15
        assert ps.stat_values[2] == 20
        assert ps.stat_values[3] == 25

    def test_demon_not_present(self):
        assert self.d2s.demon.has_demon is False

    def test_char_flags(self):
        assert self.d2s.char_flags == 0x20


class Test0x63Paladin:
    SAVE_FILE = os.path.join(EXAMPLES_DIR, "0x63", "武装神棍.d2s")

    @pytest.fixture(autouse=True)
    def load_char(self):
        if not os.path.exists(self.SAVE_FILE):
            pytest.skip(f"Save file not found: {self.SAVE_FILE}")
        self.d2s = _load_d2s(self.SAVE_FILE)

    def test_version(self):
        assert self.d2s.version == 0x63

    def test_char_class(self):
        assert self.d2s.char_class == 3
        assert self.d2s.get_char_class_name() == "Paladin"

    def test_char_name(self):
        assert self.d2s.get_char_name() == "武装神棍"

    def test_is_expansion(self):
        assert self.d2s.is_expansion() is True

    def test_is_hardcore(self):
        assert self.d2s.is_hardcore() is False

    def test_is_died_before(self):
        assert self.d2s.is_died_before() is True

    def test_char_level(self):
        assert self.d2s.char_level == 93

    def test_char_title(self):
        assert self.d2s.char_title == 15

    def test_weapon_set(self):
        assert self.d2s.weapon_set == 0

    def test_has_mercenary(self):
        assert self.d2s.has_mercenary() is True

    def test_player_stats(self):
        ps = self.d2s.player_stats
        assert ps.magic == 0x6667
        assert ps.stat_values[0] == 125
        assert ps.stat_values[1] == 15
        assert ps.stat_values[2] == 120
        assert ps.stat_values[3] == 300

    def test_char_flags(self):
        assert self.d2s.char_flags == 0x28

    def test_game_version_zero(self):
        assert self.d2s.game_version == 0


class Test0x69PreviewData:
    def test_preview_data_size(self):
        save_file = os.path.join(EXAMPLES_DIR, "0x69", "warlock.d2s")
        if not os.path.exists(save_file):
            pytest.skip(f"Save file not found: {save_file}")
        d2s = _load_d2s(save_file)
        assert len(d2s.preview_data) == 228

    def test_game_version_from_preview_data(self):
        save_file = os.path.join(EXAMPLES_DIR, "0x69", "warlock.d2s")
        if not os.path.exists(save_file):
            pytest.skip(f"Save file not found: {save_file}")
        d2s = _load_d2s(save_file)
        assert d2s.preview_data[0x49] == 3
        assert d2s.game_version == 3

    def test_game_version_expansion_classic(self):
        save_file = os.path.join(EXAMPLES_DIR, "0x69", "大明女医.d2s")
        if not os.path.exists(save_file):
            pytest.skip(f"Save file not found: {save_file}")
        d2s = _load_d2s(save_file)
        assert d2s.game_version == 2
        assert d2s.is_expansion() is True

    def test_name_from_preview_data(self):
        save_file = os.path.join(EXAMPLES_DIR, "0x69", "warlock.d2s")
        if not os.path.exists(save_file):
            pytest.skip(f"Save file not found: {save_file}")
        d2s = _load_d2s(save_file)
        name_bytes = d2s.preview_data[0x7C : 0x7C + 96]
        name = name_bytes.split(b"\x00")[0].decode("utf-8", errors="replace")
        assert name == "warlock"

    def test_name_from_preview_data_utf8(self):
        save_file = os.path.join(EXAMPLES_DIR, "0x69", "魑魅.d2s")
        if not os.path.exists(save_file):
            pytest.skip(f"Save file not found: {save_file}")
        d2s = _load_d2s(save_file)
        name_bytes = d2s.preview_data[0x7C : 0x7C + 96]
        name = name_bytes.split(b"\x00")[0].decode("utf-8", errors="replace")
        assert name == "魑魅"


class Test0x69GameVersionExpansionLogic:
    def test_game_version_1_not_expansion(self):
        d2s = D2SStruct()
        d2s.version = 0x69
        d2s.game_version = 1
        assert d2s.is_expansion() is False

    def test_game_version_2_is_expansion(self):
        d2s = D2SStruct()
        d2s.version = 0x69
        d2s.game_version = 2
        assert d2s.is_expansion() is True

    def test_game_version_3_is_expansion(self):
        d2s = D2SStruct()
        d2s.version = 0x69
        d2s.game_version = 3
        assert d2s.is_expansion() is True

    def test_game_version_0_not_expansion(self):
        d2s = D2SStruct()
        d2s.version = 0x69
        d2s.game_version = 0
        assert d2s.is_expansion() is False

    def test_charflags_expansion_bit_ignored_in_0x69(self):
        d2s = D2SStruct()
        d2s.version = 0x69
        d2s.char_flags = 0x20
        d2s.game_version = 1
        assert d2s.is_expansion() is False

    def test_charflags_no_expansion_but_gameversion_says_expansion(self):
        d2s = D2SStruct()
        d2s.version = 0x69
        d2s.char_flags = 0x0
        d2s.game_version = 3
        assert d2s.is_expansion() is True


class Test0x69DemonLogic:
    def test_demon_present_when_warlock_expansion(self):
        save_file = os.path.join(EXAMPLES_DIR, "0x69", "warlock.d2s")
        if not os.path.exists(save_file):
            pytest.skip(f"Save file not found: {save_file}")
        d2s = _load_d2s(save_file)
        assert d2s.game_version >= 3
        assert d2s.demon.has_demon is True

    def test_demon_absent_when_not_warlock_expansion(self):
        save_file = os.path.join(EXAMPLES_DIR, "0x69", "白皮克星.d2s")
        if not os.path.exists(save_file):
            pytest.skip(f"Save file not found: {save_file}")
        d2s = _load_d2s(save_file)
        assert d2s.demon.has_demon is False

    def test_demon_absent_in_classic_expansion(self):
        save_file = os.path.join(EXAMPLES_DIR, "0x69", "大明女医.d2s")
        if not os.path.exists(save_file):
            pytest.skip(f"Save file not found: {save_file}")
        d2s = _load_d2s(save_file)
        assert d2s.game_version == 2
        assert d2s.demon.has_demon is False


class Test0x69Roundtrip:
    def _test_roundtrip(self, save_file):
        with open(save_file, "rb") as f:
            original_data = f.read()

        bs = IBitStream(original_data)
        d2s = D2SStruct()
        d2s.deserialize(bs)

        obs = OBitStream()
        d2s.serialize(obs)
        serialized_data = obs.get_data()

        assert len(original_data) == len(serialized_data), (
            f"Size mismatch: {len(original_data)} vs {len(serialized_data)}"
        )
        assert original_data == serialized_data, "Data mismatch after round-trip"

    def test_roundtrip_warlock(self):
        save_file = os.path.join(EXAMPLES_DIR, "0x69", "warlock.d2s")
        if not os.path.exists(save_file):
            pytest.skip(f"Save file not found: {save_file}")
        self._test_roundtrip(save_file)

    def test_roundtrip_amazon(self):
        save_file = os.path.join(EXAMPLES_DIR, "0x69", "白皮克星.d2s")
        if not os.path.exists(save_file):
            pytest.skip(f"Save file not found: {save_file}")
        self._test_roundtrip(save_file)

    def test_roundtrip_necromancer(self):
        save_file = os.path.join(EXAMPLES_DIR, "0x69", "魑魅.d2s")
        if not os.path.exists(save_file):
            pytest.skip(f"Save file not found: {save_file}")
        self._test_roundtrip(save_file)

    def test_roundtrip_sorceress(self):
        save_file = os.path.join(EXAMPLES_DIR, "0x69", "大明女医.d2s")
        if not os.path.exists(save_file):
            pytest.skip(f"Save file not found: {save_file}")
        self._test_roundtrip(save_file)

    def test_roundtrip_paladin_pet(self):
        save_file = os.path.join(EXAMPLES_DIR, "0x69", "pet.d2s")
        if not os.path.exists(save_file):
            pytest.skip(f"Save file not found: {save_file}")
        self._test_roundtrip(save_file)

    def test_roundtrip_0x63_paladin(self):
        save_file = os.path.join(EXAMPLES_DIR, "0x63", "武装神棍.d2s")
        if not os.path.exists(save_file):
            pytest.skip(f"Save file not found: {save_file}")
        self._test_roundtrip(save_file)
