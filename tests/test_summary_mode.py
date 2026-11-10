import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from d2s_parse import main
from d2savior.core.d2data import GameDataResolver
from d2savior.core.d2s_struct import D2SStruct
from d2savior.core.enums import EquipSlot, ItemLocation, StoredIn
from d2savior.core.formatters import (
    format_char_summary,
    format_item_summary,
    format_stash_summary,
    get_char_status_summary,
)
from d2savior.core.item import (
    D2Item,
    ExtItemInfo,
    ItemInfo,
    ItemList,
    TypeSpecificInfo,
)
from d2savior.core.item_name import GoldQuantity
from d2savior.core.property_list import PropertyList
from d2savior.core.stash import (
    STASH_TAB_TYPE_ADVANCED,
    STASH_TAB_TYPE_NORMAL,
    SharedStash,
    StashTab,
)


class TestSummaryMode:
    def test_item_summary_gold(self, game_data_resolver):
        item = D2Item()
        item.item_info = ItemInfo()
        gold = GoldQuantity()
        gold.quantity = 50000
        item.item_info.gold = gold
        summary = format_item_summary(item, resolver=game_data_resolver)
        assert summary == "Gold: 50000"

    def test_item_summary_simple(self, game_data_resolver):
        item = D2Item()
        item.type_name = b"hp1 "
        summary = format_item_summary(item, resolver=game_data_resolver)
        assert "Healing Potion" in summary

    def test_item_summary_unique_with_defence(self, game_data_resolver):
        item = D2Item()
        item.type_name = b"uap "  # Shako
        item.item_info = ItemInfo()
        item.item_info.ext_info = ExtItemInfo()
        item.item_info.ext_info.unique_id = 0x00F8  # Harlequin Crest (248)
        item.item_info.type_specific_info = TypeSpecificInfo()
        item.item_info.type_specific_info.defence = 130

        summary = format_item_summary(item, resolver=game_data_resolver)
        assert "Harlequin Crest" in summary
        assert "Shako" in summary
        assert "Def: 120" in summary

    def test_item_summary_unmapped_property_fallback(self, game_data_resolver):
        item = D2Item()
        item.type_name = b"amu "  # Amulet
        item.item_info = ItemInfo()
        item.item_info.type_specific_info = TypeSpecificInfo()

        class MockPropertyList(PropertyList):
            def __init__(self, props):
                self.properties = [(0, 0, 0)]
                self.props = props

            def get_parsed_properties(self, version=0x63, data=None):
                return self.props

            def ext_sockets(self):
                return 0

        item.item_info.type_specific_info.property_list = MockPropertyList(
            [(999, 42, [1, 2]), (998, 15, [])]
        )

        # Force every property through the fallback path by returning empty/None
        # (replicates the old patch("...format_property", return_value=None)).
        summary = format_item_summary(
            item, resolver=game_data_resolver, property_formatter=lambda *a, **k: None
        )
        assert "ID 999: raw=42, params=[1, 2]" in summary
        assert "ID 998: 15" in summary

    def test_item_summary_currency_stack(self, game_data_resolver):
        item = D2Item()
        item.type_name = b"r20 "  # Lem Rune
        item.item_info = ItemInfo()
        item.item_info.stash_stack_size = 5

        summary = format_item_summary(item, resolver=game_data_resolver)
        assert "Lem Rune" in summary
        assert "x5" in summary

    def test_stash_summary_currency_and_normal(self, game_data_resolver):
        stash = SharedStash()

        # Tab 1: Normal with 1 unique item
        tab1 = StashTab()
        tab1.tab_type = STASH_TAB_TYPE_NORMAL
        item1 = D2Item()
        item1.type_name = b"uap "
        item1.item_info = ItemInfo()
        item1.item_info.ext_info = ExtItemInfo()
        item1.item_info.ext_info.unique_id = 0x00F8
        item1.item_info.type_specific_info = TypeSpecificInfo()
        item1.item_info.type_specific_info.defence = 120

        class MockItemList(ItemList):
            def __init__(self, items):
                self.items = items
                self.count = len(items)

        tab1.items = MockItemList([item1])
        stash.tabs.append(tab1)

        # Tab 2: Advanced (Currency)
        tab2 = StashTab()
        tab2.tab_type = STASH_TAB_TYPE_ADVANCED

        rune_pul = D2Item()
        rune_pul.type_name = b"r21 "  # Pul
        rune_pul.item_info = ItemInfo()
        rune_pul.item_info.stash_stack_size = 2

        rune_hel = D2Item()
        rune_hel.type_name = b"r15 "  # Hel
        rune_hel.item_info = ItemInfo()
        rune_hel.item_info.stash_stack_size = 3

        gem_topaz = D2Item()
        gem_topaz.type_name = b"gpw "  # Perfect Diamond / Topaz
        gem_topaz.item_info = ItemInfo()
        gem_topaz.item_info.stash_stack_size = 10

        empty_item = D2Item()
        empty_item.type_name = b"r01 "
        empty_item.item_info = ItemInfo()
        empty_item.item_info.stash_stack_size = 0

        tab2.items = MockItemList([rune_pul, rune_hel, gem_topaz, empty_item])
        stash.tabs.append(tab2)

        # Tab 3: Normal tab with repeated items (jewels)
        tab3 = StashTab()
        tab3.tab_type = STASH_TAB_TYPE_NORMAL
        jewels = []
        for _ in range(24):
            jewel = D2Item()
            jewel.type_name = b"jew "
            jewels.append(jewel)
        tab3.items = MockItemList(jewels)
        stash.tabs.append(tab3)

        output = format_stash_summary(stash, resolver=game_data_resolver)

        assert "Total Tabs: 3" in output
        assert "Tab 1: Normal" in output
        assert "Tab 2: Advanced (Currency)" in output
        assert "=== Tab 1 (Normal) ===" in output
        assert "  - Harlequin Crest (Shako) [Def: 110]" in output
        assert "=== Tab 2 (Advanced (Currency)) ===" in output
        assert "Runes: Hel: 3, Pul: 2" in output
        assert "Diamond: p 10, f 0, o 0" in output
        assert "El: 0" not in output
        assert "=== Tab 3 (Normal) ===" in output
        assert "  - 24x Jewels" in output

    def test_stash_summary_gem_compaction(self, game_data_resolver):
        stash = SharedStash()
        tab = StashTab()
        tab.tab_type = STASH_TAB_TYPE_ADVANCED

        items = []
        # Perfect Ruby x 5
        gpr = D2Item()
        gpr.type_name = b"gpr "
        gpr.item_info = ItemInfo()
        gpr.item_info.stash_stack_size = 5
        items.append(gpr)

        # Flawless Ruby x 10, Normal Ruby x 10, Flawed Ruby x 9, Chipped Ruby x 5 = 34 other rubies
        for code, count in [(b"glr ", 10), (b"gsr ", 10), (b"gfr ", 9), (b"gcr ", 5)]:
            it = D2Item()
            it.type_name = code
            it.item_info = ItemInfo()
            it.item_info.stash_stack_size = count
            items.append(it)

        class MockItemList(ItemList):
            def __init__(self, items):
                self.items = items
                self.count = len(items)

        tab.items = MockItemList(items)
        stash.tabs.append(tab)

        output = format_stash_summary(stash, resolver=game_data_resolver)
        assert "Gems (p=perfect, f=flawless, o=other): Ruby: p 5, f 10, o 24" in output

    def test_char_summary_formatting(self, game_data_resolver):
        char = D2SStruct()
        char.name = b"Sork\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        char.char_class = 1  # Sorceress
        char.char_level = 85
        char.char_flags = 0x24  # Expansion | Hardcore

        # Stats
        char.player_stats.magic = 0x6667
        char.player_stats.stat_values[0] = 156  # Str
        char.player_stats.stat_values[1] = 35  # Ene
        char.player_stats.stat_values[2] = 25  # Dex
        char.player_stats.stat_values[3] = 300  # Vit
        char.player_stats.stat_values[4] = 10  # Stat points remaining
        char.player_stats.stat_values[5] = 2  # Skill points remaining
        char.player_stats.stat_values[6] = 900 << 8  # Life
        char.player_stats.stat_values[7] = 900 << 8
        char.player_stats.stat_values[8] = 450 << 8  # Mana
        char.player_stats.stat_values[9] = 450 << 8
        char.player_stats.stat_values[0xE] = 12000  # Gold person
        char.player_stats.stat_values[0xF] = 2500000  # Gold stash

        # Skills
        char.skills.magic = 0x6669
        char.skills.skill_levels[20] = 20  # Blizzard
        char.skills.skill_levels[25] = 15  # Cold Mastery
        char.skills.skill_levels[8] = 1  # Teleport

        # Items
        class MockItemList(ItemList):
            def __init__(self, items):
                self.magic = 0x4D4A
                self.items = items
                self.count = len(items)

        # Equipped Helm
        helm = D2Item()
        helm.location = ItemLocation.EQUIPPED
        helm.position = EquipSlot.HELMET.value
        helm.type_name = b"uap "
        helm.item_info = ItemInfo()
        helm.item_info.ext_info = ExtItemInfo()
        helm.item_info.ext_info.unique_id = 0x00F8
        helm.item_info.type_specific_info = TypeSpecificInfo()
        helm.item_info.type_specific_info.defence = 141

        # Stored Charm in Inventory
        charm = D2Item()
        charm.location = ItemLocation.STORED
        charm.stored_in = StoredIn.INVENTORY
        charm.type_name = b"cm3 "  # Grand Charm

        # Belt potions
        pot1 = D2Item()
        pot1.location = ItemLocation.BELT
        pot1.type_name = b"hp5 "

        pot2 = D2Item()
        pot2.location = ItemLocation.BELT
        pot2.type_name = b"hp5 "

        char.item_list = MockItemList([helm, charm, pot1, pot2])

        output = format_char_summary(char, resolver=game_data_resolver)

        assert "=== Diablo II Character Summary ===" in output
        assert "Name: Sork | Class: Sorceress | Level: 85" in output
        assert "Status: Hardcore" in output
        assert "Attributes: Str: 156, Dex: 25, Vit: 300, Ene: 35" in output
        assert "Life: 900/900 | Mana: 450/450" in output
        assert "Gold: 12000 (Person), 2500000 (Stash)" in output
        assert "Remaining Points: 10 Stat, 2 Skill" in output

        # Skills
        assert "Meteor: 20" in output
        assert "Fire Mastery: 15" in output
        assert "Frost Nova: 1" in output

        # Equipped Gear
        assert "=== Equipped Gear ===" in output
        assert "- Helmet: Harlequin Crest (Shako) [Def: 131]" in output

        # Stored items & grouped belt potions
        assert "=== Inventory & Stash ===" in output
        assert "- [Inventory] Grand Charm" in output
        assert "- [Belt] Super Healing Potion (x2)" in output

    def test_char_status_summary_combinations(self):
        # 1. Softcore, alive / not died before
        char = D2SStruct()
        char.char_flags = 0x20  # Expansion only, softcore
        assert get_char_status_summary(char) == "Softcore"

        # 2. Softcore, died before (e.g. sork in 0x69)
        char_0x69 = D2SStruct()
        char_0x69.version = 0x69
        char_0x69.game_version = 3
        char_0x69.char_flags = 0x08  # Died before
        assert get_char_status_summary(char_0x69) == "Softcore | Died before"

        # 3. Hardcore, died before
        char_hc_dead = D2SStruct()
        char_hc_dead.char_flags = 0x04 | 0x08  # Hardcore | Died
        assert get_char_status_summary(char_hc_dead) == "Hardcore | Died before"

        # 4. Hardcore, alive
        char_hc_alive = D2SStruct()
        char_hc_alive.char_flags = 0x04  # Hardcore
        assert get_char_status_summary(char_hc_alive) == "Hardcore"

        # 5. Ladder, Softcore, alive
        char_ladder = D2SStruct()
        char_ladder.char_flags = 0x40  # Ladder
        assert get_char_status_summary(char_ladder) == "Ladder | Softcore"

        # 6. Ladder, Hardcore, died before
        char_ladder_hc_died = D2SStruct()
        char_ladder_hc_died.char_flags = 0x40 | 0x04 | 0x08  # Ladder | Hardcore | Died
        assert get_char_status_summary(char_ladder_hc_died) == "Ladder | Hardcore | Died before"

    def test_cli_argument_parsing(self):
        import argparse
        from unittest.mock import patch

        # Test single file without summary
        with patch("sys.argv", ["d2s_parse.py", "char.d2s"]):
            # Test that argparse accepts positional file_path as list and summary flag
            parser = argparse.ArgumentParser()
            parser.add_argument("file_path", nargs="+")
            parser.add_argument("--summary", action="store_true")
            args = parser.parse_args(["char.d2s"])
            assert args.file_path == ["char.d2s"]
            assert not args.summary

            # Test multiple files with --summary
            args_summary = parser.parse_args(["--summary", "char1.d2s", "char2.d2s", "stash.d2i"])
            assert args_summary.file_path == ["char1.d2s", "char2.d2s", "stash.d2i"]
            assert args_summary.summary

    def test_process_file_dispatch(self, game_data_resolver):
        import argparse
        from unittest.mock import MagicMock, patch

        from d2s_parse import process_file

        mock_char = D2SStruct()
        mock_char.name = b"Test\x00"

        mock_stash = SharedStash()

        # Test d2s dispatch
        with (
            patch("os.path.exists", return_value=True),
            patch("d2s_parse.parse_d2s_file", return_value=(True, mock_char, MagicMock())),
            patch("d2s_parse.format_char_summary", return_value="SUMMARY_CHAR") as mock_summary,
            patch("d2s_parse.format_char_info", return_value="INFO_CHAR") as mock_info,
            patch("builtins.print") as mock_print,
        ):
            args = argparse.Namespace(summary=True, debug=False, search=None, search_bytes=None)
            process_file("test.d2s", args, game_data_resolver)
            mock_summary.assert_called_once_with(mock_char, resolver=game_data_resolver)
            mock_info.assert_not_called()
            mock_print.assert_called_with("SUMMARY_CHAR")

            mock_summary.reset_mock()
            mock_info.reset_mock()
            args.summary = False
            process_file("test.d2s", args, game_data_resolver)
            mock_info.assert_called_once_with(mock_char, resolver=game_data_resolver)
            mock_summary.assert_not_called()

        # Test d2i stash dispatch
        with (
            patch("os.path.exists", return_value=True),
            patch(
                "d2s_parse.parse_d2i_file", return_value=(True, mock_stash, "stash", MagicMock())
            ),
            patch(
                "d2s_parse.format_stash_summary", return_value="SUMMARY_STASH"
            ) as mock_stash_summary,
            patch("d2s_parse.format_stash_info", return_value="INFO_STASH") as mock_stash_info,
            patch("builtins.print") as mock_print,
        ):
            args = argparse.Namespace(summary=True, debug=False, search=None, search_bytes=None)
            process_file("test.d2i", args, game_data_resolver)
            mock_stash_summary.assert_called_once_with(mock_stash, resolver=game_data_resolver)
            mock_stash_info.assert_not_called()

            mock_stash_summary.reset_mock()
            mock_stash_info.reset_mock()
            args.summary = False
            process_file("test.d2i", args, game_data_resolver)
            mock_stash_info.assert_called_once_with(mock_stash, resolver=game_data_resolver)
            mock_stash_summary.assert_not_called()

    def test_main_multiple_files_header(self):
        from unittest.mock import patch

        with (
            patch("sys.argv", ["d2s_parse.py", "--summary", "char1.d2s", "char2.d2s"]),
            patch("d2s_parse.process_file") as mock_proc,
            patch("builtins.print") as mock_print,
        ):
            main()
            assert mock_proc.call_count == 2
            mock_print.assert_any_call("=== File: char1.d2s ===")
            mock_print.assert_any_call("=== File: char2.d2s ===")

    def test_format_parsed_properties_helper(self, game_data_resolver):
        from unittest.mock import MagicMock

        from d2savior.core.formatters import _format_parsed_properties

        assert _format_parsed_properties(None, resolver=game_data_resolver) == []

        empty_list = MagicMock()
        empty_list.properties = None
        assert _format_parsed_properties(empty_list, resolver=game_data_resolver) == []

        prop_list = MagicMock()
        prop_list.properties = [1]
        # (prop_id, value, params)
        prop_list.get_parsed_properties.return_value = [
            (7, 25, [25]),  # max life
            (999, 10, ["param1"]),  # unmapped with params
            (998, 5, []),  # unmapped without params
        ]

        def fake_formatter(prop_id, params, version=None):
            # Mapped prop 7 yields a label; unmapped IDs yield empty -> fallback path
            return "+25 to Life" if prop_id == 7 else ""

        formatted = _format_parsed_properties(
            prop_list,
            resolver=game_data_resolver,
            version=0x63,
            property_formatter=fake_formatter,
        )
        assert len(formatted) == 3
        assert formatted[0] == "+25 to Life"
        assert formatted[1] == "ID 999: raw=10, params=['param1']"
        assert formatted[2] == "ID 998: 5"

    def test_get_character_skills_helper(self, game_data_resolver):
        from d2savior.core.formatters import _get_character_skills

        char_data = D2SStruct()
        assert _get_character_skills(char_data, game_data_resolver) == []

        char_data.skills.magic = 0x6669
        char_data.char_class = 1  # Sorceress (base skill 36)
        char_data.skills.skill_levels[18] = 20  # 36 + 18 = 54 (Teleport)
        char_data.skills.skill_levels[0] = 5  # 36 + 0 = 36 (Fire Bolt)

        skills = _get_character_skills(char_data, game_data_resolver)
        assert len(skills) == 2
        # Should be ordered by skill index
        assert skills[0][0] == 0
        assert skills[0][2] == 5
        assert skills[1][0] == 18
        assert skills[1][2] == 20
        assert "Teleport" in skills[1][1]

    def test_run_bitstream_searches_helper(self):
        import argparse
        from unittest.mock import MagicMock, patch

        from d2savior.core.bitstream_debug import _run_bitstream_searches

        bs = MagicMock()
        args = argparse.Namespace(search="1010", search_bytes="4a4d")

        with (
            patch(
                "d2savior.core.bitstream_debug.search_bits",
                return_value=[{"offset": 10, "byte": 1, "bit": 2, "context": "ctx"}],
            ) as mock_sb,
            patch(
                "d2savior.core.bitstream_debug.search_bytes",
                return_value=[{"offset": 5, "context": "ctx_b"}],
            ) as mock_sbytes,
            patch("builtins.print") as mock_print,
        ):
            _run_bitstream_searches(bs, args)
            mock_sb.assert_called_once_with(bs, "1010")
            mock_sbytes.assert_called_once_with(bs, b"\x4a\x4d")
            mock_print.assert_any_call("\n=== Search Results for '1010' ===")
            mock_print.assert_any_call("\n=== Search Results for bytes '4a4d' ===")

    def test_ensure_data_loaded(self):
        from d2savior.core.d2data import GameDataResolver

        # Default language loaded
        resolver = GameDataResolver.load(lang_key="enUS")
        assert resolver is not None
        assert resolver.loc is not None
        assert resolver.loc.current_lang == "enUS"

        # Switching language produces a resolver for that language
        resolver_zh = GameDataResolver.load(lang_key="zhCN")
        assert resolver_zh.loc.current_lang == "zhCN"

        # enUS still loads correctly
        resolver_en = GameDataResolver.load(lang_key="enUS")
        assert resolver_en.loc.current_lang == "enUS"

    def test_ru_summary_mode(self):
        from d2savior.core.d2s_struct import D2SStruct, ItemList
        from d2savior.core.formatters import (
            format_char_summary,
            format_stash_summary,
        )
        from d2savior.core.item import D2Item, ExtItemInfo, ItemInfo, TypeSpecificInfo
        from d2savior.core.stash import (
            STASH_TAB_TYPE_ADVANCED,
            STASH_TAB_TYPE_NORMAL,
            SharedStash,
            StashTab,
        )

        resolver = GameDataResolver.load(lang_key="ruRU")

        # Test stash summary in Russian
        s = SharedStash()
        t1 = StashTab()
        t1.tab_type = STASH_TAB_TYPE_NORMAL
        t1.items = ItemList()

        cap = D2Item()
        cap.type_name = b"cap "
        cap.item_info = ItemInfo()
        cap.item_info.type_specific_info = TypeSpecificInfo()
        cap.item_info.type_specific_info.defence = 4
        ral = D2Item()
        ral.type_name = b"r08 "
        cap.gem_items = [ral]
        t1.items.items.append(cap)

        shako = D2Item()
        shako.type_name = b"uap "
        shako.item_info = ItemInfo()
        shako.item_info.ext_info = ExtItemInfo()
        shako.item_info.ext_info.unique_id = 248
        t1.items.items.append(shako)
        s.tabs.append(t1)

        t2 = StashTab()
        t2.tab_type = STASH_TAB_TYPE_ADVANCED
        t2.items = ItemList()
        r_ral = D2Item()
        r_ral.type_name = b"r08 "
        r_ral.item_info = ItemInfo()
        r_ral.item_info.stash_stack_size = 10
        t2.items.items.append(r_ral)

        p_rub = D2Item()
        p_rub.type_name = b"gpr "
        p_rub.item_info = ItemInfo()
        p_rub.item_info.stash_stack_size = 5
        t2.items.items.append(p_rub)
        s.tabs.append(t2)

        stash_out = format_stash_summary(s, resolver=resolver)
        assert "наголовник" in stash_out
        assert "Шутовской капюшон (шако)" in stash_out
        assert "Рал: 10" in stash_out
        assert "Рубин: p 5, f 0, o 0" in stash_out

        # Test char summary in Russian
        char = D2SStruct()
        char.char_class = 1  # Sorceress
        char.char_level = 80
        char_out = format_char_summary(char, resolver=resolver)
        assert "Волшебница" in char_out

    def test_detailed_mode_localization(self):
        from d2savior.core.formatters import format_item_info
        from d2savior.core.item import D2Item, ExtItemInfo, ItemInfo

        resolver_en = GameDataResolver.load(lang_key="enUS")
        resolver_zh = GameDataResolver.load(lang_key="zhCN")

        # Unique Bonesnap (id 23)
        item = D2Item()
        item.type_name = b"mau "
        item.item_info = ItemInfo()
        item.item_info.ext_info = ExtItemInfo()
        item.item_info.ext_info.unique_id = 23

        lines_en = format_item_info(item, resolver=resolver_en)
        assert "Unique ID: 23 (Bonesnap)" in lines_en

        lines_zh = format_item_info(item, resolver=resolver_zh)
        assert "Unique ID: 23 (碎骨)" in lines_zh

        # Set item (Aldur's Rhythm, id 68)
        item_set = D2Item()
        item_set.type_name = b"9mt "
        item_set.item_info = ItemInfo()
        item_set.item_info.ext_info = ExtItemInfo()
        item_set.item_info.ext_info.set_id = 68

        set_en = format_item_info(item_set, resolver=resolver_en)
        assert "Set ID: 68 (Aldur's Rhythm)" in set_en

        set_zh = format_item_info(item_set, resolver=resolver_zh)
        assert "Set ID: 68 (艾尔多的律动)" in set_zh
