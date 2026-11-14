import argparse
import io
from unittest.mock import MagicMock, patch

import d2s_parse
import d2savior.core.bitstream_debug as bitstream_debug
import d2savior.core.char_formatter as char_formatter
import d2savior.core.constants as constants
import d2savior.core.item_formatter as item_formatter
import d2savior.core.stash_formatter as stash_formatter
from d2savior.core.d2s_struct import D2SStruct
from d2savior.core.ibitstream import IBitStream
from d2savior.core.item import D2Item, ItemInfo, TypeSpecificInfo
from d2savior.core.stash import SharedStash


class TestModularization:
    def test_constants_module(self):
        assert "Act I" in [act for act, _ in constants.WAYPOINTS_BY_ACT]
        assert "Act I" in [act for act, _ in constants.QUESTS_BY_ACT]
        assert len(constants.CLASS_SKILL_BASES) == 8
        assert constants.TAB_TYPE_NAMES[0] == "Normal"
        assert constants.TAB_TYPE_NAMES[1] == "Advanced (Currency)"
        assert constants.DIFFICULTY_NAMES == ["Normal", "Nightmare", "Hell"]

    def test_bitstream_debug_module(self):
        data = b"\x4a\x4d\x00\x00\xff"
        bs = IBitStream(data)

        # search_bytes
        results = bitstream_debug.search_bytes(bs, b"\x4a\x4d")
        assert len(results) == 1
        assert results[0]["offset"] == 0
        assert "4a4d" in results[0]["context"]

        # search_bits
        # 'J' is 0x4A = 0b01001010
        results_bits = bitstream_debug.search_bits(bs, "01001010")
        assert len(results_bits) >= 1

        # debug_bitstream prints without crashing
        with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            bitstream_debug.debug_bitstream(bs, context_bits=16, label="Test")
            assert "BitStream Debug Test" in mock_out.getvalue()

    def test_formatters_module(self):
        assert char_formatter.format_timestamp(0) == "N/A"
        assert char_formatter.format_timestamp(4294967295) == "N/A"
        assert char_formatter.format_duration(0) == "0s"
        assert char_formatter.format_duration(3665) == "1h 1m 5s"

    def test_unified_parse_file_and_dispatch(self):
        mock_char = D2SStruct()
        mock_stash = SharedStash()
        mock_item = D2Item()
        mock_bs = MagicMock()

        # Test parse_file with .d2s
        with patch("d2s_parse.parse_d2s_file", return_value=(True, mock_char, mock_bs)):
            kind, data, bs = d2s_parse.parse_file("test.d2s")
            assert kind == "char"
            assert data is mock_char
            assert bs is mock_bs

        # Test parse_file with .d2i stash
        with patch("d2s_parse.parse_d2i_file", return_value=(True, mock_stash, "stash", mock_bs)):
            kind, data, bs = d2s_parse.parse_file("stash.d2i")
            assert kind == "stash"
            assert data is mock_stash
            assert bs is mock_bs

        # Test parse_file with .d2i item
        with patch("d2s_parse.parse_d2i_file", return_value=(True, mock_item, "item", mock_bs)):
            kind, data, bs = d2s_parse.parse_file("item.d2i")
            assert kind == "item"
            assert data is mock_item
            assert bs is mock_bs

        # Test parse_file with invalid file
        kind, data, bs = d2s_parse.parse_file("unknown.txt")
        assert kind is None
        assert data is None
        assert bs is None

    def test_formatters_dispatch_table(self, game_data_resolver):
        assert ("char", False) in d2s_parse.FORMATTERS
        assert ("char", True) in d2s_parse.FORMATTERS
        assert ("stash", False) in d2s_parse.FORMATTERS
        assert ("stash", True) in d2s_parse.FORMATTERS
        assert ("item", False) in d2s_parse.FORMATTERS
        assert ("item", True) in d2s_parse.FORMATTERS

        mock_item = D2Item()
        mock_item.type_name = b"hp1 "
        item_summary = d2s_parse.FORMATTERS[("item", True)](mock_item, game_data_resolver)
        assert "=== Item Summary ===" in item_summary
        assert "Healing Potion" in item_summary

        item_info = d2s_parse.FORMATTERS[("item", False)](mock_item, game_data_resolver)
        assert "=== Item Info ===" in item_info
        assert "Type: hp1" in item_info

    def test_property_formatter_dependency_injection(self):
        mock_prop_list = MagicMock()
        mock_prop_list.properties = [1]
        mock_prop_list.ext_sockets.return_value = 0
        mock_prop_list.get_parsed_properties.return_value = [
            (7, 25, [25]),
            (999, 10, ["val"]),
        ]

        # Custom injected formatter
        def custom_formatter(pid, params, ver):
            return f"CUSTOM_PROP_{pid}:{params[0]}" if pid == 7 else None

        res = item_formatter._format_parsed_properties(
            mock_prop_list, resolver=MagicMock(), property_formatter=custom_formatter
        )
        assert len(res) == 2
        assert res[0] == "CUSTOM_PROP_7:25"
        assert res[1] == "ID 999: raw=10, params=['val']"

        # Also verify format_item_summary with injected property_formatter
        item = D2Item()
        item.type_name = b"amu "
        item.item_info = ItemInfo()
        item.item_info.type_specific_info = TypeSpecificInfo()
        item.item_info.type_specific_info.property_list = mock_prop_list

        summary = item_formatter.format_item_summary(
            item, resolver=MagicMock(), property_formatter=custom_formatter
        )
        assert "CUSTOM_PROP_7:25" in summary

    def test_no_sys_modules_d2s_parse_hack(self):
        import inspect

        for mod in (char_formatter, item_formatter, stash_formatter, bitstream_debug):
            source = inspect.getsource(mod)
            assert "sys.modules.get('d2s_parse')" not in source
            assert "sys.modules" not in source

    def test_run_bitstream_searches_delegation(self):
        mock_bs = MagicMock()
        args = argparse.Namespace(search="0101", search_bytes="abcd")

        with (
            patch(
                "d2savior.core.bitstream_debug.search_bits",
                return_value=[{"offset": 1, "byte": 0, "bit": 1, "context": "c"}],
            ) as mock_sb,
            patch(
                "d2savior.core.bitstream_debug.search_bytes",
                return_value=[{"offset": 2, "context": "cb"}],
            ) as mock_sbytes,
            patch("builtins.print"),
        ):
            bitstream_debug.run_bitstream_searches(mock_bs, args)

        mock_sb.assert_called_once_with(mock_bs, "0101")
        mock_sbytes.assert_called_once_with(mock_bs, b"\xab\xcd")

    def test_formatter_return_types_consistent_str(self, game_data_resolver):
        char = D2SStruct()
        res_wp = char_formatter.format_waypoints_info(char, resolver=game_data_resolver)
        res_quests = char_formatter.format_quests_info(char, resolver=game_data_resolver)

        assert isinstance(res_wp, str)
        assert isinstance(res_quests, str)

        item = D2Item()
        item.item_info = ItemInfo()
        item.item_info.type_name = b"rin "
        res_item = item_formatter.format_item_info(item, resolver=game_data_resolver)
        assert isinstance(res_item, str)

        # Internal line helpers return lists
        assert isinstance(char_formatter._format_waypoints_lines(char, game_data_resolver), list)
        assert isinstance(char_formatter._format_quests_lines(char, game_data_resolver), list)
        assert isinstance(
            item_formatter._format_item_lines(item, resolver=game_data_resolver), list
        )
