import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from d2s_parse import main
from d2savior.core.char_formatter import (
    format_char_summary,
    get_char_status_summary,
)
from d2savior.core.d2s_struct import D2SStruct
from d2savior.core.enums import EquipSlot, ItemLocation, StoredIn
from d2savior.core.item import (
    D2Item,
    ExtItemInfo,
    ItemInfo,
    ItemList,
    TypeSpecificInfo,
)
from d2savior.core.item_formatter import (
    format_item_info,
    format_item_summary,
)
from d2savior.core.item_name import GoldQuantity, LongName
from d2savior.core.property_list import PropertyList
from d2savior.core.resolver import GameDataResolver
from d2savior.core.stash import (
    STASH_TAB_TYPE_ADVANCED,
    STASH_TAB_TYPE_NORMAL,
    SharedStash,
    StashTab,
)
from d2savior.core.stash_formatter import format_stash_summary


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

    def test_item_summary_rare_and_crafted(self, game_data_resolver):
        # Rare belt: Bitter Buckle (Rare Belt)
        item = D2Item()
        item.is_simple = False
        item.type_name = b"mbl "  # Belt
        item.item_info = ItemInfo()
        item.item_info.ext_info = ExtItemInfo()
        item.item_info.ext_info.quality = 6  # RARE
        item.item_info.ext_info.rare_name = LongName()
        item.item_info.ext_info.rare_name.name_1 = 194  # Bitter
        item.item_info.ext_info.rare_name.name_2 = 112  # buckle
        item.item_info.type_specific_info = TypeSpecificInfo()
        item.item_info.type_specific_info.defence = 15

        summary = format_item_summary(item, resolver=game_data_resolver)
        assert "Bitter Buckle (Rare Belt)" in summary

        # Detailed view
        detailed = format_item_info(item, resolver=game_data_resolver)
        assert "Rare Name: 194-112 (Bitter Buckle)" in detailed

        # Crafted belt: Demon Clasp (Crafted Sharkskin Belt)
        crafted_item = D2Item()
        crafted_item.is_simple = False
        crafted_item.type_name = b"zvb "  # Sharkskin Belt
        crafted_item.item_info = ItemInfo()
        crafted_item.item_info.ext_info = ExtItemInfo()
        crafted_item.item_info.ext_info.quality = 8  # CRAFTED
        crafted_item.item_info.ext_info.craft_name = LongName()
        crafted_item.item_info.ext_info.craft_name.name_1 = 176  # Demon
        crafted_item.item_info.ext_info.craft_name.name_2 = 111  # clasp
        crafted_item.item_info.type_specific_info = TypeSpecificInfo()

        c_summary = format_item_summary(crafted_item, resolver=game_data_resolver)
        assert "Demon Clasp (Crafted Sharkskin Belt)" in c_summary
        c_detailed = format_item_info(crafted_item, resolver=game_data_resolver)
        assert "Craft Name: 176-111 (Demon Clasp)" in c_detailed

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

        from d2savior.core.item_formatter import _format_parsed_properties

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
        from d2savior.core.char_formatter import _get_character_skills

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
        from d2savior.core.resolver import GameDataResolver

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
        from d2savior.core.char_formatter import format_char_summary
        from d2savior.core.d2s_struct import D2SStruct, ItemList
        from d2savior.core.item import D2Item, ExtItemInfo, ItemInfo, TypeSpecificInfo
        from d2savior.core.stash import (
            STASH_TAB_TYPE_ADVANCED,
            STASH_TAB_TYPE_NORMAL,
            SharedStash,
            StashTab,
        )
        from d2savior.core.stash_formatter import format_stash_summary

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
        from d2savior.core.item import D2Item, ExtItemInfo, ItemInfo
        from d2savior.core.item_formatter import format_item_info

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

    def test_mercenary_formatting(self):
        from d2savior.core.char_formatter import format_char_info

        resolver = GameDataResolver.load(lang_key="enUS")

        # Resolved mercenary (0x69 expansion): Name Index 10, Type 34 -> Jemali
        char = D2SStruct()
        char.version = 0x69
        char.game_version = 3
        char.merc_seed = 0x12345678
        char.merc_name_index = 10
        char.merc_hireling_id = 34
        char._merc_experience = 67_392_000  # Level 80 (130 * 80^2 * 81)

        summary = format_char_summary(char, resolver=resolver)
        assert "Mercenary: Jemali (Act II Desert Mercenary, Hell, Holy Freeze)" in summary
        assert "Level: 80 | Attributes: Str: 181, Dex: 146" in summary
        assert (
            "Resistances (Normal): Fire: 75% (+147%), Cold: 75% (+147%), Lightning: 75% (+147%), Poison: 75% (+147%)"
            in summary
        )

        full = format_char_info(char, resolver=resolver)
        assert (
            "Has mercenary: Jemali (Act II Desert Mercenary, Hell, Holy Freeze; Name: 10, Type: 34)"
            in full
        )
        assert "Mercenary Level: 80" in full
        assert "Mercenary Strength: 181" in full
        assert "Mercenary Dexterity: 146" in full
        assert (
            "Mercenary Resistances (Normal): Fire: 75% (+147%), Cold: 75% (+147%), Lightning: 75% (+147%), Poison: 75% (+147%)"
            in full
        )

        # Dead flag preserved in summary (0x63)
        char_dead = D2SStruct()
        char_dead.version = 0x63
        char_dead.char_flags = 0x20
        char_dead.merc_control = 1
        char_dead.merc_name = 19
        char_dead.merc_type = 10
        char_dead.merc_dead = 1
        assert (
            "Mercenary: Waheed (Act II Desert Mercenary, Nightmare, Holy Freeze) (Dead)"
            in format_char_summary(char_dead, resolver=resolver)
        )

        # Out-of-range name index omits name cleanly
        char.merc_name_index = 999
        assert "Mercenary: Act II Desert Mercenary, Hell, Holy Freeze" in format_char_summary(
            char, resolver=resolver
        )
        assert (
            "Has mercenary: Act II Desert Mercenary, Hell, Holy Freeze (Name: 999, Type: 34)"
            in format_char_info(char, resolver=resolver)
        )

        # Unknown type falls back to raw IDs without stat lines
        char.merc_name_index = 10
        char.merc_hireling_id = 999
        unknown_summary = format_char_summary(char, resolver=resolver)
        unknown_full = format_char_info(char, resolver=resolver)
        assert "Mercenary: Name Index 10, Type 999" in unknown_summary
        assert "Attributes: Str:" not in unknown_summary.split("=== Mercenary ===")[1]
        assert "Has mercenary (Name: 10, Type: 999)" in unknown_full
        assert "Mercenary Level:" not in unknown_full

    def test_summary_properties_collapse_damage_variants(self, game_data_resolver):
        from d2savior.core.item_formatter import _format_summary_properties

        # Max damage only (1H/2H/Throw identical)
        max_only = _format_summary_properties(
            [(19, 33, [33]), (22, 6, [6]), (24, 6, [6]), (160, 6, [6])],
            resolver=game_data_resolver,
        )
        assert max_only == ["+33 to Attack Rating", "+6 to Maximum Damage"]

        # Min damage only (1H/2H/Throw identical)
        min_only = _format_summary_properties(
            [(2, 8, [8]), (21, 2, [2]), (23, 2, [2]), (159, 2, [2])],
            resolver=game_data_resolver,
        )
        assert min_only == ["+8 to Dexterity", "+2 to Minimum Damage"]

        # Matching min + max (1H + Throw) combines into Adds X-Y damage
        t_revenge = _format_summary_properties(
            [(21, 25, [25]), (22, 50, [50]), (159, 25, [25]), (160, 50, [50])],
            resolver=game_data_resolver,
        )
        assert t_revenge == ["Adds 25-50 damage"]

        # Matching min + max (all 6 stats) and reverse max-before-min order
        all_six = _format_summary_properties(
            [
                (21, 3, [3]),
                (23, 3, [3]),
                (159, 3, [3]),
                (22, 8, [8]),
                (24, 8, [8]),
                (160, 8, [8]),
            ],
            resolver=game_data_resolver,
        )
        assert all_six == ["Adds 3-8 damage"]

        reversed_pair = _format_summary_properties(
            [(22, 25, [25]), (21, 15, [15])],
            resolver=game_data_resolver,
        )
        assert reversed_pair == ["Adds 15-25 damage"]

        # Distinct throw values remain visible
        diff_throw = _format_summary_properties(
            [(21, 10, [10]), (22, 20, [20]), (159, 12, [12]), (160, 25, [25])],
            resolver=game_data_resolver,
        )
        assert diff_throw == [
            "Adds 10-20 damage",
            "+12 to Minimum Throw Damage",
            "+25 to Maximum Throw Damage",
        ]

        # Pre-summed 1H + dmg-min on one property list collapses to canonical 1H total
        diff_2h = _format_summary_properties(
            [(21, 14, [14]), (23, 5, [5]), (159, 5, [5])],
            resolver=game_data_resolver,
        )
        assert diff_2h == ["+14 to Minimum Damage"]

        # Pre-summed 1H dmg-norm + dmg-max on one property list collapses duplicate 2H/Throw max
        mixed_1h = _format_summary_properties(
            [(21, 12, [12]), (22, 53, [53]), (24, 8, [8]), (160, 8, [8])],
            resolver=game_data_resolver,
        )
        assert mixed_1h == ["Adds 12-53 damage"]

        # Pre-summed 2H dmg-norm + dmg-min on one property list collapses duplicate 1H/Throw min
        mixed_2h = _format_summary_properties(
            [(21, 6, [6]), (23, 15, [15]), (24, 30, [30]), (159, 6, [6])],
            resolver=game_data_resolver,
        )
        assert mixed_2h == ["Adds 15-30 damage"]

        # 2H min (23) + 1H max (22, e.g. Ith Rune) combine cleanly
        bow_plus_ith = _format_summary_properties(
            [(23, 10, [10]), (22, 15, [15])],
            resolver=game_data_resolver,
        )
        assert bow_plus_ith == ["Adds 10-15 damage"]

        # Inverted min > max does not emit nonsensical "Adds 9-4 damage"
        min_gt_max = _format_summary_properties(
            [
                (21, 9, [9]),
                (23, 9, [9]),
                (159, 9, [9]),
                (22, 4, [4]),
                (24, 4, [4]),
                (160, 4, [4]),
            ],
            resolver=game_data_resolver,
        )
        assert min_gt_max == ["+9 to Minimum Damage", "+4 to Maximum Damage"]

        # Localized damage range formatting (ruRU)
        resolver_ru = GameDataResolver.load(lang_key="ruRU")
        assert _format_summary_properties(
            [(21, 25, [25]), (22, 50, [50])],
            resolver=resolver_ru,
        ) == ["+25–50 урона"]

    def test_stash_find_summary_collapses_damage_stats(self, game_data_resolver):
        from d2s_parse import parse_file
        from d2savior.core.stash_formatter import format_stash_find

        stash_path = os.path.join(
            os.path.dirname(__file__), "fixtures", "ModernSharedStashSoftCoreV2.d2i"
        )
        kind, stash, _ = parse_file(stash_path, resolver=game_data_resolver)
        assert kind == "stash"
        assert stash is not None

        fine_gc = format_stash_find(stash, "Fine Grand Charm", resolver=game_data_resolver)
        assert fine_gc is not None
        assert "Fine Grand Charm (+33 to Attack Rating, +6 to Maximum Damage)" in fine_gc
        assert "Throw Damage" not in fine_gc

        scarlet_jewel = format_stash_find(
            stash, "Scarlet Jewel of Daring", resolver=game_data_resolver
        )
        assert scarlet_jewel is not None
        assert "Scarlet Jewel of Daring (+8 to Dexterity, +2 to Minimum Damage)" in scarlet_jewel
        assert "Throw Damage" not in scarlet_jewel

        razortail = format_stash_find(stash, "Razortail", resolver=game_data_resolver)
        assert razortail is not None
        assert razortail.count("+10 to Maximum Damage") == 1
        assert "Throw Damage" not in razortail

        titans = format_stash_find(stash, "Titan's Revenge", resolver=game_data_resolver)
        assert titans is not None
        assert "Adds 25-50 damage" in titans
        assert "Throw Damage" not in titans
        assert "to Minimum Damage" not in titans
        assert "to Maximum Damage" not in titans

    def test_item_summary_socketed_flat_damage_sources(self, game_data_resolver):
        class _StaticPropertyList(PropertyList):
            def __init__(self, props):
                self.properties = [(0, 0, 0)]
                self._props = props

            def get_parsed_properties(self, version=0x63, data=None):
                return self._props

        def _make_item(type_name: bytes, props, gems=None):
            item = D2Item()
            item.type_name = type_name
            item.item_info = ItemInfo()
            item.item_info.type_specific_info = TypeSpecificInfo()
            if props:
                item.item_info.type_specific_info.property_list = _StaticPropertyList(props)
            if gems:
                item.gem_items = gems
            return item

        # 1H weapon (Bloodletter-like) socketed with flat +max damage jewel
        jewel_max = _make_item(b"jew ", [(22, 8, [8]), (24, 8, [8]), (160, 8, [8])])
        sword_jewel = _make_item(b"9ss ", [(21, 12, [12]), (22, 45, [45])], gems=[jewel_max])
        sword_summary = format_item_summary(sword_jewel, resolver=game_data_resolver)
        assert "Adds 12-53 damage" in sword_summary
        assert "+8 to Maximum Damage" not in sword_summary

        # 2H bow (Cliffkiller-like) socketed with flat +min damage jewel
        jewel_min = _make_item(b"jew ", [(21, 6, [6]), (23, 6, [6]), (159, 6, [6])])
        bow_jewel = _make_item(b"8l8 ", [(23, 9, [9]), (24, 30, [30])], gems=[jewel_min])
        bow_jewel_summary = format_item_summary(bow_jewel, resolver=game_data_resolver)
        assert "Adds 15-30 damage" in bow_jewel_summary
        assert "+6 to Minimum Damage" not in bow_jewel_summary

        # 2H bow (Cliffkiller-like) socketed with Sol Rune (+9 min via stat 21)
        sol_rune = _make_item(b"r12 ", [])
        bow_sol = _make_item(b"8l8 ", [(23, 9, [9]), (24, 30, [30])], gems=[sol_rune])
        bow_sol_summary = format_item_summary(bow_sol, resolver=game_data_resolver)
        assert "Adds 18-30 damage" in bow_sol_summary
        assert "+9 to Minimum Damage" not in bow_sol_summary
        assert "+30 to Maximum Damage" not in bow_sol_summary

    def test_elemental_and_poison_grouping(self, game_data_resolver):
        from d2savior.core.item_formatter import (
            _format_property_entries,
            _format_summary_properties,
        )

        # Poison equal rate (Tal Rune: 154 rate * 125 frames / 256 = 75 over 5s)
        tal_props = [(57, 154, [154]), (58, 154, [154]), (59, 125, [125])]
        assert _format_summary_properties(tal_props, resolver=game_data_resolver) == [
            "+75 poison damage over 5 seconds"
        ]
        assert _format_property_entries(tal_props, resolver=game_data_resolver) == [
            "+75 poison damage over 5 seconds"
        ]

        # Foul Small Charm (128 rate * 100 frames / 256 = 50 over 4s), no stat 88
        foul_props = [(57, 128, [128]), (58, 128, [128]), (59, 100, [100])]
        assert _format_summary_properties(foul_props, resolver=game_data_resolver) == [
            "+50 poison damage over 4 seconds"
        ]

        # Asymmetric poison range (min_rate=103, max_rate=205, 50 frames -> 20-40 over 2s)
        range_poison = [(57, 103, [103]), (58, 205, [205]), (59, 50, [50])]
        assert _format_summary_properties(range_poison, resolver=game_data_resolver) == [
            "Adds 20-40 poison damage over 2 seconds"
        ]

        # Legacy 0x60 single-tuple poison format [min_rate, max_rate, frames]
        legacy_poison = [(57, 0, [128, 128, 100, 0])]
        assert _format_summary_properties(legacy_poison, resolver=game_data_resolver) == [
            "+50 poison damage over 4 seconds"
        ]

        # Fire, Lightning, Cold (consuming duration 56), and equal elemental values
        elem_props = [
            (48, 5, [5]),
            (49, 30, [30]),
            (50, 1, [1]),
            (51, 50, [50]),
            (54, 3, [3]),
            (55, 14, [14]),
            (56, 75, [75]),
        ]
        expected_elem = [
            "Adds 5-30 fire damage",
            "Adds 1-50 lightning damage",
            "Adds 3-14 cold damage",
        ]
        assert _format_summary_properties(elem_props, resolver=game_data_resolver) == expected_elem
        assert _format_property_entries(elem_props, resolver=game_data_resolver) == expected_elem
        assert _format_summary_properties(
            [(48, 12, [12]), (49, 12, [12])], resolver=game_data_resolver
        ) == ["+12 fire damage"]

        # Two socketed Tal Runes average duration rather than squaring damage/duration
        sword = D2Item()
        sword.type_name = b"crs "
        tal1 = D2Item()
        tal1.type_name = b"r07 "
        tal2 = D2Item()
        tal2.type_name = b"r07 "
        sword.item_info = ItemInfo()
        sword.item_info.type_specific_info = TypeSpecificInfo()
        sword.gem_items = [tal1, tal2]
        assert "+150 poison damage over 5 seconds" in format_item_summary(
            sword, resolver=game_data_resolver
        )

        # Localized ruRU poison and elemental range formatting
        resolver_ru = GameDataResolver.load(lang_key="ruRU")
        assert _format_summary_properties(tal_props, resolver=resolver_ru) == [
            "+75 урона от яда за 5 сек."
        ]
        assert _format_summary_properties(elem_props, resolver=resolver_ru) == [
            "+5–30 урона от огня",
            "+1–50 урона от молнии",
            "+3–14 урона от льда",
        ]

    def test_enhanced_damage_collapse_and_ohm_rune(self, game_data_resolver):
        from d2savior.core.item_formatter import (
            _format_property_entries,
            _format_summary_properties,
        )

        # Equal 17 + 18 collapse into +% Enhanced Damage in both summary and full modes
        equal_ed = [(17, 64, [64]), (18, 64, [64])]
        assert _format_summary_properties(equal_ed, resolver=game_data_resolver) == [
            "+64% Enhanced Damage"
        ]
        assert _format_property_entries(equal_ed, resolver=game_data_resolver) == [
            "+64% Enhanced Damage"
        ]

        # Unequal 17 + 18 remain separate
        assert _format_summary_properties(
            [(17, 64, [64]), (18, 30, [30])], resolver=game_data_resolver
        ) == ["+64% Enhanced Maximum Damage", "+30% Enhanced Minimum Damage"]

        # Legacy 0x60 single-tuple [max%, min%] when equal
        assert _format_summary_properties(
            [(17, 0, [64, 64, 0, 0])], resolver=game_data_resolver
        ) == ["+64% Enhanced Damage"]

        # Localized ruRU
        resolver_ru = GameDataResolver.load(lang_key="ruRU")
        assert _format_summary_properties(equal_ed, resolver=resolver_ru) == ["+64% к урону"]

        # Ohm Rune (r27) in weapon contributes both stat 17 (+50%) and stat 18 (+50%)
        class _StaticPropertyList(PropertyList):
            def __init__(self, props):
                self.properties = [(0, 0, 0)]
                self._props = props

            def get_parsed_properties(self, version=0x63, data=None):
                return self._props

        cta = D2Item()
        cta.type_name = b"crs "
        ohm = D2Item()
        ohm.type_name = b"r27 "
        assert game_data_resolver.get_socket_properties(cta, ohm) == [
            (17, 50, [50]),
            (18, 50, [50]),
        ]

        cta.item_info = ItemInfo()
        cta.item_info.type_specific_info = TypeSpecificInfo()
        cta.item_info.type_specific_info.runeword_property_list = _StaticPropertyList(
            [(17, 218, [218]), (18, 218, [218])]
        )
        cta.gem_items = [ohm]
        cta_summary = format_item_summary(cta, resolver=game_data_resolver)
        assert "+268% Enhanced Damage" in cta_summary
        assert "Enhanced Maximum Damage" not in cta_summary
        assert "Enhanced Minimum Damage" not in cta_summary

    def test_effective_armor_defence(self, game_data_resolver):
        from d2savior.core.item_formatter import format_item_info

        def _make_prop_list(props):
            pl = PropertyList()
            pl._version = 0x69
            pl._use_stat_cost = True
            pl._data = game_data_resolver.data
            pl.properties = props
            return pl

        # Que-Hegan's Wisdom (Mage Plate): base 262 + 160% ED -> 681
        armor = D2Item()
        armor.type_name = b"xtp "
        armor.version = 0x69
        armor.item_info = ItemInfo()
        armor.item_info.ext_info = ExtItemInfo()
        armor.item_info.ext_info.quality = 7
        armor.item_info.ext_info.unique_id = 223
        armor.item_info.type_specific_info = TypeSpecificInfo()
        armor.item_info.type_specific_info.defence = 272  # save_add=10 -> base 262
        armor.item_info.type_specific_info.property_list = _make_prop_list([(16, 0, 160)])

        assert "[Def: 681]" in format_item_summary(armor, resolver=game_data_resolver, version=0x69)
        assert "[Def: 681]" in format_item_summary(
            armor, resolver=game_data_resolver, version=0x69, include_properties=False
        )
        assert "Defence: 262 (effective: 681)" in format_item_info(
            armor, resolver=game_data_resolver, version=0x69
        )

        # Combined %ED (stat 16) + flat +Defense (stat 31) + socketed Pul Rune (+30% ED)
        pul = D2Item()
        pul.type_name = b"r21 "
        armor.item_info.type_specific_info.property_list = _make_prop_list(
            [(16, 0, 160), (31, 0, 40)]
        )
        armor.gem_items = [pul]
        # 262 * (100 + 160 + 30) // 100 + 40 = 262 * 290 // 100 + 40 = 759 + 40 = 799
        assert "[Def: 799," in format_item_summary(armor, resolver=game_data_resolver, version=0x69)
        assert "Defence: 262 (effective: 799)" in format_item_info(
            armor, resolver=game_data_resolver, version=0x69
        )

        # Plain armor without ED or +Defense keeps plain Defence output
        plain = D2Item()
        plain.type_name = b"xtp "
        plain.item_info = ItemInfo()
        plain.item_info.type_specific_info = TypeSpecificInfo()
        plain.item_info.type_specific_info.defence = 260  # base 250
        full_plain = format_item_info(plain, resolver=game_data_resolver)
        assert "Defence: 250" in full_plain
        assert "(effective:" not in full_plain

    def test_char_summary_play_time_sentinel(self, game_data_resolver):
        char = D2SStruct()
        char.name = b"TestChar"
        char.char_class = 1
        char.char_level = 80
        char.last_save_time = 1700000000

        # Sentinel 0xFFFFFFFF (D2R v0x69) and 0 should not display Play Time: N/A
        for sentinel in (0, 0xFFFFFFFF):
            char.play_time = sentinel
            summary = format_char_summary(char, resolver=game_data_resolver)
            assert "Play Time" not in summary
            assert "Last Saved:" in summary

        # Valid positive play_time displays formatted duration
        char.play_time = 3665
        summary = format_char_summary(char, resolver=game_data_resolver)
        assert "Play Time: 1h 1m 5s" in summary
