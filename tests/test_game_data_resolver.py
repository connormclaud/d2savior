import os
from unittest.mock import MagicMock

from d2savior.core.d2data import GameDataResolver, VersionData, get_game_data, init_d2data


class TestGameDataResolver:
    @classmethod
    def setup_class(cls):
        data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "d2savior", "data")
        init_d2data(data_dir)

    def test_default_initialization(self):
        resolver = GameDataResolver()
        assert resolver.version == 99
        assert resolver.data is not None

    def test_custom_version(self):
        resolver = GameDataResolver(0x69)
        assert resolver.version == 105
        assert resolver.data.version == 105

    def test_keyword_argument_version(self):
        resolver = GameDataResolver(version=0x69)
        assert resolver.version == 105
        assert resolver.data.version == 105

    def test_init_with_version_data(self):
        gd = get_game_data()
        assert gd is not None
        v69 = gd.for_version(0x69)
        resolver = GameDataResolver(v69)
        assert resolver.version == 105
        assert resolver.data is v69

    def test_get_item(self):
        resolver = GameDataResolver(0x63)
        item = resolver.get_item("gsw")
        assert item is not None
        assert item.name == "Diamond"

        item_none = resolver.get_item("non_existent_xyz")
        assert item_none is None

    def test_get_skill_name(self):
        resolver = GameDataResolver(0x63)
        # Teleport is Sorceress skill id 54
        name = resolver.get_skill_name(54)
        assert len(name) > 0

        # Non-existent skill ID returns empty string
        invalid_name = resolver.get_skill_name(999999)
        assert invalid_name == ""

    def test_delegation_to_version_data(self):
        mock_data = MagicMock(spec=VersionData)
        mock_data.version = 0x69
        mock_data.get_item.return_value = "mock_item"
        mock_data.get_runeword.return_value = "mock_rw"
        mock_data.get_unique_item.return_value = "mock_unique"
        mock_data.get_set_item.return_value = "mock_set"
        mock_data.get_magic_prefix.return_value = "mock_prefix"
        mock_data.get_magic_suffix.return_value = "mock_suffix"
        mock_data.get_stat.return_value = "mock_stat"
        mock_data.get_property.return_value = "mock_prop"

        resolver = GameDataResolver(mock_data)

        assert resolver.get_item("foo") == "mock_item"
        mock_data.get_item.assert_called_once_with("foo")

        assert resolver.get_runeword(1) == "mock_rw"
        mock_data.get_runeword.assert_called_once_with(1)

        assert resolver.get_unique_item(2) == "mock_unique"
        mock_data.get_unique_item.assert_called_once_with(2)

        assert resolver.get_set_item(3) == "mock_set"
        mock_data.get_set_item.assert_called_once_with(3)

        assert resolver.get_magic_prefix(4) == "mock_prefix"
        mock_data.get_magic_prefix.assert_called_once_with(4)

        assert resolver.get_magic_suffix(5) == "mock_suffix"
        mock_data.get_magic_suffix.assert_called_once_with(5)

        assert resolver.get_stat(6) == "mock_stat"
        mock_data.get_stat.assert_called_once_with(6)

        assert resolver.get_property(7) == "mock_prop"
        mock_data.get_property.assert_called_once_with(7)
