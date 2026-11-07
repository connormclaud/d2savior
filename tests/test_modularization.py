import argparse
import io
import unittest
from unittest.mock import MagicMock, patch

import core.bitstream_debug as bitstream_debug
import core.constants as constants
import core.formatters as formatters
import d2s_parse
from core.d2s_struct import D2SStruct
from core.ibitstream import IBitStream
from core.item import D2Item, ItemInfo, TypeSpecificInfo
from core.stash import SharedStash


class TestModularization(unittest.TestCase):
    def test_constants_module(self):
        self.assertIn("Act I", [act for act, _ in constants.WAYPOINTS_BY_ACT])
        self.assertIn("Act I", [act for act, _ in constants.QUESTS_BY_ACT])
        self.assertEqual(len(constants.CLASS_SKILL_BASES), 8)
        self.assertEqual(constants.TAB_TYPE_NAMES[0], "Normal")
        self.assertEqual(constants.TAB_TYPE_NAMES[1], "Advanced (Currency)")
        self.assertEqual(constants.DIFFICULTY_NAMES, ["Normal", "Nightmare", "Hell"])

    def test_bitstream_debug_module(self):
        data = b"\x4a\x4d\x00\x00\xff"
        bs = IBitStream(data)

        # search_bytes
        results = bitstream_debug.search_bytes(bs, b"\x4a\x4d")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["offset"], 0)
        self.assertIn("4a4d", results[0]["context"])

        # search_bits
        # 'J' is 0x4A = 0b01001010
        results_bits = bitstream_debug.search_bits(bs, "01001010")
        self.assertTrue(len(results_bits) >= 1)

        # debug_bitstream prints without crashing
        with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            bitstream_debug.debug_bitstream(bs, context_bits=16, label="Test")
            self.assertIn("BitStream Debug Test", mock_out.getvalue())

    def test_formatters_module(self):
        self.assertEqual(formatters.format_timestamp(0), "N/A")
        self.assertEqual(formatters.format_timestamp(0xFFFFFFFF), "N/A")
        self.assertEqual(formatters.format_duration(0), "0s")
        self.assertEqual(formatters.format_duration(3665), "1h 1m 5s")

    def test_re_exports_in_d2s_parse(self):
        expected_constants = [
            "TAB_TYPE_NAMES",
            "GEM_TYPE_NAMES",
            "GEM_CODE_MAP",
            "RUNE_CODES_STRIPPED",
            "GEM_CODES_STRIPPED",
            "MATERIAL_CODES_STRIPPED",
            "COMBINED_SLOT_ORDER_STRIPPED",
            "CLASS_SKILL_BASES",
            "DIFFICULTY_NAMES",
            "WAYPOINTS_BY_ACT",
            "QUESTS_BY_ACT",
        ]
        for name in expected_constants:
            self.assertTrue(hasattr(d2s_parse, name), f"Missing re-export {name}")

        expected_debug = [
            "debug_bitstream",
            "search_bits",
            "search_bytes",
            "run_bitstream_searches",
            "_run_bitstream_searches",
        ]
        for name in expected_debug:
            self.assertTrue(hasattr(d2s_parse, name), f"Missing re-export {name}")

        expected_formatters = [
            "ensure_data_loaded",
            "get_char_type_name",
            "get_char_title_name",
            "format_timestamp",
            "format_duration",
            "get_item_display_name",
            "_format_parsed_properties",
            "format_item_summary",
            "format_item_info",
            "format_waypoints_info",
            "format_quests_info",
            "_get_character_skills",
            "format_char_info",
            "format_char_summary",
            "format_stash_info",
            "format_stash_summary",
        ]
        for name in expected_formatters:
            self.assertTrue(hasattr(d2s_parse, name), f"Missing re-export {name}")

    def test_unified_parse_file_and_dispatch(self):
        mock_char = D2SStruct()
        mock_stash = SharedStash()
        mock_item = D2Item()
        mock_bs = MagicMock()

        # Test parse_file with .d2s
        with patch("d2s_parse.parse_d2s_file", return_value=(True, mock_char, mock_bs)):
            kind, data, bs = d2s_parse.parse_file("test.d2s")
            self.assertEqual(kind, "char")
            self.assertIs(data, mock_char)
            self.assertIs(bs, mock_bs)

        # Test parse_file with .d2i stash
        with patch("d2s_parse.parse_d2i_file", return_value=(True, mock_stash, "stash", mock_bs)):
            kind, data, bs = d2s_parse.parse_file("stash.d2i")
            self.assertEqual(kind, "stash")
            self.assertIs(data, mock_stash)
            self.assertIs(bs, mock_bs)

        # Test parse_file with .d2i item
        with patch("d2s_parse.parse_d2i_file", return_value=(True, mock_item, "item", mock_bs)):
            kind, data, bs = d2s_parse.parse_file("item.d2i")
            self.assertEqual(kind, "item")
            self.assertIs(data, mock_item)
            self.assertIs(bs, mock_bs)

        # Test parse_file with invalid file
        kind, data, bs = d2s_parse.parse_file("unknown.txt")
        self.assertIsNone(kind)
        self.assertIsNone(data)
        self.assertIsNone(bs)

    def test_formatters_dispatch_table(self):
        self.assertIn(("char", False), d2s_parse.FORMATTERS)
        self.assertIn(("char", True), d2s_parse.FORMATTERS)
        self.assertIn(("stash", False), d2s_parse.FORMATTERS)
        self.assertIn(("stash", True), d2s_parse.FORMATTERS)
        self.assertIn(("item", False), d2s_parse.FORMATTERS)
        self.assertIn(("item", True), d2s_parse.FORMATTERS)

        mock_item = D2Item()
        mock_item.type_name = b"hp1 "
        item_summary = d2s_parse.FORMATTERS[("item", True)](mock_item)
        self.assertIn("=== Item Summary ===", item_summary)
        self.assertIn("Healing Potion", item_summary)

        item_info = d2s_parse.FORMATTERS[("item", False)](mock_item)
        self.assertIn("=== Item Info ===", item_info)
        self.assertIn("Type: hp1", item_info)

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

        res = formatters._format_parsed_properties(
            mock_prop_list, property_formatter=custom_formatter
        )
        self.assertEqual(len(res), 2)
        self.assertEqual(res[0], "CUSTOM_PROP_7:25")
        self.assertEqual(res[1], "ID 999: raw=10, params=['val']")

        # Also verify format_item_summary with injected property_formatter
        item = D2Item()
        item.type_name = b"amu "
        item.item_info = ItemInfo()
        item.item_info.type_specific_info = TypeSpecificInfo()
        item.item_info.type_specific_info.property_list = mock_prop_list

        summary = formatters.format_item_summary(item, property_formatter=custom_formatter)
        self.assertIn("CUSTOM_PROP_7:25", summary)

    def test_no_sys_modules_d2s_parse_hack(self):
        import inspect

        formatters_source = inspect.getsource(formatters)
        bitstream_source = inspect.getsource(bitstream_debug)

        self.assertNotIn("sys.modules.get('d2s_parse')", formatters_source)
        self.assertNotIn("sys.modules", formatters_source)
        self.assertNotIn("sys.modules.get('d2s_parse')", bitstream_source)
        self.assertNotIn("sys.modules", bitstream_source)

    def test_run_bitstream_searches_delegation(self):
        mock_bs = MagicMock()
        args = argparse.Namespace(search="0101", search_bytes="abcd")

        with (
            patch(
                "core.bitstream_debug.search_bits",
                return_value=[{"offset": 1, "byte": 0, "bit": 1, "context": "c"}],
            ) as mock_sb,
            patch(
                "core.bitstream_debug.search_bytes", return_value=[{"offset": 2, "context": "cb"}]
            ) as mock_sbytes,
            patch("builtins.print"),
        ):
            bitstream_debug.run_bitstream_searches(mock_bs, args)

        mock_sb.assert_called_once_with(mock_bs, "0101")
        mock_sbytes.assert_called_once_with(mock_bs, b"\xab\xcd")

    def test_formatter_return_types_consistent_str(self):
        char = D2SStruct()
        res_wp = formatters.format_waypoints_info(char)
        res_quests = formatters.format_quests_info(char)

        self.assertIsInstance(res_wp, str)
        self.assertIsInstance(res_quests, str)

        item = D2Item()
        item.item_info = ItemInfo()
        item.item_info.type_name = b"rin "
        res_item = formatters.format_item_info(item)
        self.assertIsInstance(res_item, str)

        # Internal line helpers return lists
        self.assertIsInstance(formatters._format_waypoints_lines(char), list)
        self.assertIsInstance(formatters._format_quests_lines(char), list)
        self.assertIsInstance(formatters._format_item_lines(item), list)


if __name__ == "__main__":
    unittest.main()
