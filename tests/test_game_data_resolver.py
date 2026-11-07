import os
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.d2data import GameDataResolver, init_d2data


class TestGameDataResolver(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
        init_d2data(data_dir)

    def test_default_initialization(self):
        resolver = GameDataResolver()
        self.assertEqual(resolver.version, 0x63)
        self.assertIsNotNone(resolver._mgr)
        self.assertIsNotNone(resolver._legacy)

    def test_custom_version(self):
        resolver = GameDataResolver(version=0x69)
        self.assertEqual(resolver.version, 0x69)

    def test_get_item(self):
        resolver = GameDataResolver(0x63)
        item = resolver.get_item("gsw")
        self.assertIsNotNone(item)
        self.assertEqual(item.name, "Diamond")

        item_none = resolver.get_item("non_existent_xyz")
        self.assertIsNone(item_none)

    def test_get_skill_name(self):
        resolver = GameDataResolver(0x63)
        # Teleport is Sorceress skill id 54
        name = resolver.get_skill_name(54)
        self.assertTrue(len(name) > 0)

        # Non-existent skill ID returns empty string
        invalid_name = resolver.get_skill_name(999999)
        self.assertEqual(invalid_name, "")

    def test_delegation_to_manager_with_version(self):
        mock_mgr = MagicMock()
        mock_mgr.get_item.return_value = "mock_item"
        mock_mgr.get_runeword.return_value = "mock_rw"
        mock_mgr.get_unique_item.return_value = "mock_unique"
        mock_mgr.get_set_item.return_value = "mock_set"
        mock_mgr.get_magic_prefix.return_value = "mock_prefix"
        mock_mgr.get_magic_suffix.return_value = "mock_suffix"
        mock_mgr.get_stat.return_value = "mock_stat"
        mock_mgr.get_property.return_value = "mock_prop"

        resolver = GameDataResolver(version=0x69, mgr=mock_mgr, legacy=None)

        self.assertEqual(resolver.get_item("foo"), "mock_item")
        mock_mgr.get_item.assert_called_once_with("foo", 0x69)

        self.assertEqual(resolver.get_runeword(1), "mock_rw")
        mock_mgr.get_runeword.assert_called_once_with(1, 0x69)

        self.assertEqual(resolver.get_unique_item(2), "mock_unique")
        mock_mgr.get_unique_item.assert_called_once_with(2, 0x69)

        self.assertEqual(resolver.get_set_item(3), "mock_set")
        mock_mgr.get_set_item.assert_called_once_with(3, 0x69)

        self.assertEqual(resolver.get_magic_prefix(4), "mock_prefix")
        mock_mgr.get_magic_prefix.assert_called_once_with(4, 0x69)

        self.assertEqual(resolver.get_magic_suffix(5), "mock_suffix")
        mock_mgr.get_magic_suffix.assert_called_once_with(5, 0x69)

        self.assertEqual(resolver.get_stat(6), "mock_stat")
        mock_mgr.get_stat.assert_called_once_with(6, 0x69)

        self.assertEqual(resolver.get_property(7), "mock_prop")
        mock_mgr.get_property.assert_called_once_with(7, 0x69)

    def test_fallback_to_legacy_when_manager_is_none(self):
        mock_legacy = MagicMock()
        mock_legacy.get_item.return_value = "legacy_item"
        mock_legacy.get_runeword.return_value = "legacy_rw"
        mock_legacy.get_unique_item.return_value = "legacy_unique"
        mock_legacy.get_set_item.return_value = "legacy_set"
        mock_legacy.get_magic_prefix.return_value = "legacy_prefix"
        mock_legacy.get_magic_suffix.return_value = "legacy_suffix"
        mock_legacy.get_skill_name.return_value = "legacy_skill"

        resolver = GameDataResolver(version=0x63, mgr=None, legacy=mock_legacy)

        self.assertEqual(resolver.get_item("bar"), "legacy_item")
        mock_legacy.get_item.assert_called_once_with("bar")

        self.assertEqual(resolver.get_runeword(10), "legacy_rw")
        mock_legacy.get_runeword.assert_called_once_with(10)

        self.assertEqual(resolver.get_unique_item(20), "legacy_unique")
        mock_legacy.get_unique_item.assert_called_once_with(20)

        self.assertEqual(resolver.get_set_item(30), "legacy_set")
        mock_legacy.get_set_item.assert_called_once_with(30, 0x63)

        self.assertEqual(resolver.get_magic_prefix(40), "legacy_prefix")
        mock_legacy.get_magic_prefix.assert_called_once_with(40)

        self.assertEqual(resolver.get_magic_suffix(50), "legacy_suffix")
        mock_legacy.get_magic_suffix.assert_called_once_with(50)

        # For skill name, query non-localized ID so fallback is reached
        self.assertEqual(resolver.get_skill_name(999999), "legacy_skill")
        mock_legacy.get_skill_name.assert_called_once_with(999999)

    def test_graceful_handling_when_both_mgr_and_legacy_none(self):
        resolver = GameDataResolver(version=0x63, mgr=None, legacy=None)

        self.assertIsNone(resolver.get_item("baz"))
        self.assertIsNone(resolver.get_runeword(1))
        self.assertIsNone(resolver.get_unique_item(1))
        self.assertIsNone(resolver.get_set_item(1))
        self.assertIsNone(resolver.get_magic_prefix(1))
        self.assertIsNone(resolver.get_magic_suffix(1))
        self.assertIsNone(resolver.get_stat(1))
        self.assertIsNone(resolver.get_property(1))
        self.assertEqual(resolver.get_skill_name(999999), "")


if __name__ == "__main__":
    unittest.main()
