import unittest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.d2s_struct import D2SStruct
from core.item import D2Item, ItemInfo, ExtItemInfo, TypeSpecificInfo, GoldQuantity
from core.enums import ItemLocation, StoredIn, EquipSlot, ItemQuality
from core.stash import (
    SharedStash, StashTab,
    STASH_TAB_TYPE_NORMAL, STASH_TAB_TYPE_ADVANCED, STASH_TAB_TYPE_CHRONICLE
)
from d2s_parse import (
    get_item_display_name,
    format_item_summary,
    format_stash_summary,
    format_char_summary,
    main,
)


class TestSummaryMode(unittest.TestCase):
    def test_item_summary_gold(self):
        item = D2Item()
        item.pItemInfo = ItemInfo()
        gold = GoldQuantity()
        gold.wQuantity = 50000
        item.pItemInfo.pGold = gold
        summary = format_item_summary(item)
        self.assertEqual(summary, "Gold: 50000")

    def test_item_summary_simple(self):
        item = D2Item()
        item.sTypeName = b'hp1 '
        summary = format_item_summary(item)
        self.assertIn("Healing Potion", summary)

    def test_item_summary_unique_with_defence(self):
        item = D2Item()
        item.sTypeName = b'uap '  # Shako
        item.pItemInfo = ItemInfo()
        item.pItemInfo.pExtItemInfo = ExtItemInfo()
        item.pItemInfo.pExtItemInfo.wUniID.ensure(0x00F8)  # Harlequin Crest (248)
        item.pItemInfo.pTpSpInfo = TypeSpecificInfo()
        item.pItemInfo.pTpSpInfo.iDefence.ensure(130)

        summary = format_item_summary(item)
        self.assertIn("Harlequin Crest", summary)
        self.assertIn("Shako", summary)
        self.assertIn("Def: 120", summary)

    def test_item_summary_unmapped_property_fallback(self):
        from unittest.mock import patch

        item = D2Item()
        item.sTypeName = b'amu '  # Amulet
        item.pItemInfo = ItemInfo()
        item.pItemInfo.pTpSpInfo = TypeSpecificInfo()
        
        class MockPropertyList:
            def __init__(self, props):
                self.mProperty = True
                self.props = props
            def get_parsed_properties(self, version=0x63):
                return self.props
            def ext_sockets(self):
                return 0
                
        item.pItemInfo.pTpSpInfo.stPropertyList = MockPropertyList([
            (999, 42, [1, 2]),
            (998, 15, [])
        ])

        with patch('d2s_parse.format_property', return_value=None):
            summary = format_item_summary(item)
            self.assertIn("ID 999: raw=42, params=[1, 2]", summary)
            self.assertIn("ID 998: 15", summary)

    def test_item_summary_currency_stack(self):
        item = D2Item()
        item.sTypeName = b'r20 '  # Lem Rune
        item.pItemInfo = ItemInfo()
        item.pItemInfo.iAdvancedStashStackSize = 5

        summary = format_item_summary(item)
        self.assertIn("Lem Rune", summary)
        self.assertIn("x5", summary)

    def test_stash_summary_currency_and_normal(self):
        stash = SharedStash()
        
        # Tab 1: Normal with 1 unique item
        tab1 = StashTab()
        tab1.TabType = STASH_TAB_TYPE_NORMAL
        item1 = D2Item()
        item1.sTypeName = b'uap '
        item1.pItemInfo = ItemInfo()
        item1.pItemInfo.pExtItemInfo = ExtItemInfo()
        item1.pItemInfo.pExtItemInfo.wUniID.ensure(0x00F8)
        item1.pItemInfo.pTpSpInfo = TypeSpecificInfo()
        item1.pItemInfo.pTpSpInfo.iDefence.ensure(120)
        
        class MockItemList:
            def __init__(self, items):
                self.vItems = items
                self.nItems = len(items)
        
        tab1.Items = MockItemList([item1])
        stash.tabs.append(tab1)

        # Tab 2: Advanced (Currency)
        tab2 = StashTab()
        tab2.TabType = STASH_TAB_TYPE_ADVANCED
        
        rune_pul = D2Item()
        rune_pul.sTypeName = b'r21 '  # Pul
        rune_pul.pItemInfo = ItemInfo()
        rune_pul.pItemInfo.iAdvancedStashStackSize = 2

        rune_hel = D2Item()
        rune_hel.sTypeName = b'r15 '  # Hel
        rune_hel.pItemInfo = ItemInfo()
        rune_hel.pItemInfo.iAdvancedStashStackSize = 3

        gem_topaz = D2Item()
        gem_topaz.sTypeName = b'gpw '  # Perfect Diamond / Topaz
        gem_topaz.pItemInfo = ItemInfo()
        gem_topaz.pItemInfo.iAdvancedStashStackSize = 10

        empty_item = D2Item()
        empty_item.sTypeName = b'r01 '
        empty_item.pItemInfo = ItemInfo()
        empty_item.pItemInfo.iAdvancedStashStackSize = 0

        tab2.Items = MockItemList([rune_pul, rune_hel, gem_topaz, empty_item])
        stash.tabs.append(tab2)

        # Tab 3: Normal tab with repeated items (jewels)
        tab3 = StashTab()
        tab3.TabType = STASH_TAB_TYPE_NORMAL
        jewels = []
        for _ in range(24):
            jewel = D2Item()
            jewel.sTypeName = b'jew '
            jewels.append(jewel)
        tab3.Items = MockItemList(jewels)
        stash.tabs.append(tab3)

        output = format_stash_summary(stash)

        self.assertIn("Total Tabs: 3", output)
        self.assertIn("Tab 1: Normal", output)
        self.assertIn("Tab 2: Advanced (Currency)", output)
        self.assertIn("=== Tab 1 (Normal) ===", output)
        self.assertIn("  - Harlequin Crest (Shako) [Def: 110]", output)
        self.assertIn("=== Tab 2 (Advanced (Currency)) ===", output)
        self.assertIn("Runes: Hel: 3, Pul: 2", output)
        self.assertIn("Diamond: p 10, o 0", output)
        self.assertNotIn("El: 0", output)
        self.assertIn("=== Tab 3 (Normal) ===", output)
        self.assertIn("  - 24x Jewels", output)

    def test_stash_summary_gem_compaction(self):
        stash = SharedStash()
        tab = StashTab()
        tab.TabType = STASH_TAB_TYPE_ADVANCED

        items = []
        # Perfect Ruby x 5
        gpr = D2Item()
        gpr.sTypeName = b'gpr '
        gpr.pItemInfo = ItemInfo()
        gpr.pItemInfo.iAdvancedStashStackSize = 5
        items.append(gpr)

        # Flawless Ruby x 10, Normal Ruby x 10, Flawed Ruby x 9, Chipped Ruby x 5 = 34 other rubies
        for code, count in [(b'glr ', 10), (b'gsr ', 10), (b'gfr ', 9), (b'gcr ', 5)]:
            it = D2Item()
            it.sTypeName = code
            it.pItemInfo = ItemInfo()
            it.pItemInfo.iAdvancedStashStackSize = count
            items.append(it)

        class MockItemList:
            def __init__(self, items):
                self.vItems = items
                self.nItems = len(items)

        tab.Items = MockItemList(items)
        stash.tabs.append(tab)

        output = format_stash_summary(stash)
        self.assertIn("Gems (p=perfect, o=other): Ruby: p 5, o 34", output)

    def test_char_summary_formatting(self):
        char = D2SStruct()
        char.Name = b"Sork\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        char.charClass = 1  # Sorceress
        char.charLevel = 85
        char.charFlags = 0x24  # Expansion | Hardcore

        # Stats
        char.PlayerStats.wMajic = 0x6667
        char.PlayerStats.m_adwValue[0] = 156  # Str
        char.PlayerStats.m_adwValue[1] = 35   # Ene
        char.PlayerStats.m_adwValue[2] = 25   # Dex
        char.PlayerStats.m_adwValue[3] = 300  # Vit
        char.PlayerStats.m_adwValue[4] = 10   # Stat points remaining
        char.PlayerStats.m_adwValue[5] = 2    # Skill points remaining
        char.PlayerStats.m_adwValue[6] = 900 << 8  # Life
        char.PlayerStats.m_adwValue[7] = 900 << 8
        char.PlayerStats.m_adwValue[8] = 450 << 8  # Mana
        char.PlayerStats.m_adwValue[9] = 450 << 8
        char.PlayerStats.m_adwValue[0xE] = 12000   # Gold person
        char.PlayerStats.m_adwValue[0xF] = 2500000 # Gold stash

        # Skills
        char.Skills.wMagic = 0x6669
        char.Skills.bSkillLevel[20] = 20  # Blizzard
        char.Skills.bSkillLevel[25] = 15  # Cold Mastery
        char.Skills.bSkillLevel[8] = 1    # Teleport

        # Items
        class MockItemList:
            def __init__(self, items):
                self.wMajic = 0x4D4A
                self.vItems = items
                self.nItems = len(items)

        # Equipped Helm
        helm = D2Item()
        helm.iLocation = ItemLocation.EQUIPPED
        helm.iPosition = EquipSlot.HELMET.value
        helm.sTypeName = b'uap '
        helm.pItemInfo = ItemInfo()
        helm.pItemInfo.pExtItemInfo = ExtItemInfo()
        helm.pItemInfo.pExtItemInfo.wUniID.ensure(0x00F8)
        helm.pItemInfo.pTpSpInfo = TypeSpecificInfo()
        helm.pItemInfo.pTpSpInfo.iDefence.ensure(141)

        # Stored Charm in Inventory
        charm = D2Item()
        charm.iLocation = ItemLocation.STORED
        charm.iStoredIn = StoredIn.INVENTORY
        charm.sTypeName = b'cm3 '  # Grand Charm

        # Belt potions
        pot1 = D2Item()
        pot1.iLocation = ItemLocation.BELT
        pot1.sTypeName = b'hp5 '

        pot2 = D2Item()
        pot2.iLocation = ItemLocation.BELT
        pot2.sTypeName = b'hp5 '

        char.ItemList = MockItemList([helm, charm, pot1, pot2])

        output = format_char_summary(char)

        self.assertIn("=== Diablo II Character Summary ===", output)
        self.assertIn("Name: Sork | Class: Sorceress | Level: 85", output)
        self.assertIn("Status: Expansion | Hardcore", output)
        self.assertIn("Attributes: Str: 156, Dex: 25, Vit: 300, Ene: 35", output)
        self.assertIn("Life: 900/900 | Mana: 450/450", output)
        self.assertIn("Gold: 12000 (Person), 2500000 (Stash)", output)
        self.assertIn("Remaining Points: 10 Stat, 2 Skill", output)

        # Skills
        self.assertIn("Meteor: 20", output)
        self.assertIn("Fire Mastery: 15", output)
        self.assertIn("Frost Nova: 1", output)

        # Equipped Gear
        self.assertIn("=== Equipped Gear ===", output)
        self.assertIn("- Helmet: Harlequin Crest (Shako) [Def: 131]", output)

        # Stored items & grouped belt potions
        self.assertIn("=== Inventory & Stash ===", output)
        self.assertIn("- [Inventory] Grand Charm", output)
        self.assertIn("- [Belt] Super Healing Potion (x2)", output)

    def test_cli_argument_parsing(self):
        import argparse
        from unittest.mock import patch, MagicMock
        from d2s_parse import process_file

        # Test single file without summary
        with patch('sys.argv', ['d2s_parse.py', 'char.d2s']):
            import d2s_parse
            # Test that argparse accepts positional file_path as list and summary flag
            parser = argparse.ArgumentParser()
            parser.add_argument('file_path', nargs='+')
            parser.add_argument('--summary', action='store_true')
            args = parser.parse_args(['char.d2s'])
            self.assertEqual(args.file_path, ['char.d2s'])
            self.assertFalse(args.summary)

            # Test multiple files with --summary
            args_summary = parser.parse_args(['--summary', 'char1.d2s', 'char2.d2s', 'stash.d2i'])
            self.assertEqual(args_summary.file_path, ['char1.d2s', 'char2.d2s', 'stash.d2i'])
            self.assertTrue(args_summary.summary)

    def test_process_file_dispatch(self):
        from unittest.mock import patch, MagicMock
        import argparse
        from d2s_parse import process_file

        mock_char = D2SStruct()
        mock_char.Name = b"Test\x00"

        mock_stash = SharedStash()

        # Test d2s dispatch
        with patch('os.path.exists', return_value=True), \
             patch('d2s_parse.parse_d2s_file', return_value=(True, mock_char, MagicMock())), \
             patch('d2s_parse.format_char_summary', return_value="SUMMARY_CHAR") as mock_summary, \
             patch('d2s_parse.format_char_info', return_value="INFO_CHAR") as mock_info, \
             patch('builtins.print') as mock_print:

            args = argparse.Namespace(summary=True, debug=False, search=None, search_bytes=None)
            process_file('test.d2s', args)
            mock_summary.assert_called_once_with(mock_char)
            mock_info.assert_not_called()
            mock_print.assert_called_with("SUMMARY_CHAR")

            mock_summary.reset_mock()
            mock_info.reset_mock()
            args.summary = False
            process_file('test.d2s', args)
            mock_info.assert_called_once_with(mock_char)
            mock_summary.assert_not_called()

        # Test d2i stash dispatch
        with patch('os.path.exists', return_value=True), \
             patch('d2s_parse.parse_d2i_file', return_value=(True, mock_stash, "stash", MagicMock())), \
             patch('d2s_parse.format_stash_summary', return_value="SUMMARY_STASH") as mock_stash_summary, \
             patch('d2s_parse.format_stash_info', return_value="INFO_STASH") as mock_stash_info, \
             patch('builtins.print') as mock_print:

            args = argparse.Namespace(summary=True, debug=False, search=None, search_bytes=None)
            process_file('test.d2i', args)
            mock_stash_summary.assert_called_once_with(mock_stash)
            mock_stash_info.assert_not_called()

            mock_stash_summary.reset_mock()
            mock_stash_info.reset_mock()
            args.summary = False
            process_file('test.d2i', args)
            mock_stash_info.assert_called_once_with(mock_stash)
            mock_stash_summary.assert_not_called()

    def test_main_multiple_files_header(self):
        from unittest.mock import patch, MagicMock
        from d2s_parse import main

        with patch('sys.argv', ['d2s_parse.py', '--summary', 'char1.d2s', 'char2.d2s']), \
             patch('d2s_parse.process_file') as mock_proc, \
             patch('builtins.print') as mock_print:
            main()
            self.assertEqual(mock_proc.call_count, 2)
            mock_print.assert_any_call("=== File: char1.d2s ===")
            mock_print.assert_any_call("=== File: char2.d2s ===")


if __name__ == '__main__':
    unittest.main()
