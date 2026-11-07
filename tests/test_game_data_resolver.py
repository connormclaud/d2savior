import os
from unittest.mock import MagicMock

from d2savior.core.d2data import GameData, GameDataResolver, VersionData


class TestGameDataResolver:
    @classmethod
    def setup_class(cls):
        data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "d2savior", "data")
        cls.game_data = GameData.load(data_dir)

    def test_default_initialization(self):
        resolver = GameDataResolver.load()
        assert resolver.version == 105
        assert resolver.data is not None

    def test_custom_version(self):
        resolver = GameDataResolver.load(version=0x63)
        assert resolver.version == 99
        assert resolver.data.version == 99

    def test_for_version(self):
        resolver = GameDataResolver.load()
        v63 = resolver.for_version(0x63)
        assert v63.version == 99
        assert v63.data.version == 99

    def test_init_with_version_data(self):
        v69 = self.game_data.for_version(0x69)
        resolver = GameDataResolver(v69, game_data=self.game_data)
        assert resolver.version == 105
        assert resolver.data is v69

    def test_get_item(self):
        resolver = GameDataResolver.load(version=0x63)
        item = resolver.get_item("gsw")
        assert item is not None
        assert item.name == "Diamond"

        item_none = resolver.get_item("non_existent_xyz")
        assert item_none is None

    def test_get_skill_name(self):
        resolver = GameDataResolver.load(version=0x63)
        # Teleport is Sorceress skill id 54
        name = resolver.get_skill_name(54)
        assert len(name) > 0

        # Non-existent skill ID returns empty string
        invalid_name = resolver.get_skill_name(999999)
        assert invalid_name == ""

    def test_language_isolation(self):
        r_en = GameDataResolver.load(lang_key="enUS")
        r_ru = GameDataResolver.load(lang_key="ruRU")
        r_zh = GameDataResolver.load(lang_key="zhCN")

        assert r_en.lang_key == "enUS"
        assert r_ru.lang_key == "ruRU"
        assert r_zh.lang_key == "zhCN"

        assert r_en.get_item_modifier("ItemStats1h") != r_ru.get_item_modifier("ItemStats1h")
        assert r_en.get_item_modifier("ItemStats1h") != r_zh.get_item_modifier("ItemStats1h")
        assert r_en.get_item_modifier("ItemStats1h") == "Defense: %d"
        assert r_ru.get_item_modifier("ItemStats1h") == "Защита: %d"
        assert r_zh.get_item_modifier("ItemStats1h") == "防御: %d"

        assert r_en.loc.current_lang == "enUS"
        assert r_ru.loc.current_lang == "ruRU"
        assert r_zh.loc.current_lang == "zhCN"

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

        resolver = GameDataResolver(mock_data, game_data=self.game_data)

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
