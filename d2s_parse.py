#!/usr/bin/env python3
import argparse
import os
from typing import Any

from core.bitstream_debug import _run_bitstream_searches
from core.d2s_struct import D2SStruct
from core.formatters import (
    ensure_data_loaded,
    format_char_info,
    format_char_summary,
    format_item_info,
    format_item_summary,
    format_stash_info,
    format_stash_summary,
)
from core.ibitstream import IBitStream
from core.stash import SharedStash


def parse_d2i_file(
    file_path: str, debug: bool = False
) -> tuple[bool, Any, str | None, IBitStream | None]:
    try:
        with open(file_path, "rb") as f:
            data = f.read()

        bs = IBitStream(data)
        if len(data) >= 4 and data[:4] == b"\x55\xaa\x55\xaa":
            stash = SharedStash()
            stash.deserialize(bs)
            if debug:
                print("\n=== BitStream Final State ===")
                print(f"Total bits: {len(bs)}")
                print(f"Final offset: {bs.get_offset()}")
                print(f"Remaining: {bs.remaining()}")
            return True, stash, "stash", bs
        elif data.startswith(b"JM"):
            from core.item import D2Item

            item = D2Item()
            item.deserialize(bs)
            return True, item, "item", bs
        else:
            stash = SharedStash()
            stash.deserialize(bs)
            return True, stash, "stash", bs
    except Exception as e:
        print(f"Error parsing file: {e}")
        import traceback

        traceback.print_exc()
        return False, None, None, None


def parse_d2s_file(
    file_path: str, debug: bool = False
) -> tuple[bool, D2SStruct | None, IBitStream | None]:
    try:
        with open(file_path, "rb") as f:
            data = f.read()

        bs = IBitStream(data)
        char_data = D2SStruct()
        char_data.deserialize(bs)

        if debug:
            print("\n=== BitStream Final State ===")
            print(f"Total bits: {len(bs)}")
            print(f"Final offset: {bs.get_offset()}")
            print(f"Remaining: {bs.remaining()}")

        return True, char_data, bs

    except Exception as e:
        print(f"Error parsing file: {e}")
        import traceback

        traceback.print_exc()
        return False, None, None


def parse_file(file_path: str, debug: bool = False) -> tuple[str | None, Any, IBitStream | None]:
    """Dispatch file parsing based on extension, returning (kind, data, bs) or (None, None, None)."""
    if file_path.endswith(".d2i"):
        res = parse_d2i_file(file_path, debug)
        if res[0]:
            _, data, kind, bs = res
            return kind, data, bs
    elif file_path.endswith(".d2s"):
        res = parse_d2s_file(file_path, debug)
        if res[0]:
            _, data, bs = res
            return "char", data, bs
    return None, None, None


FORMATTERS = {
    ("char", False): lambda d: format_char_info(d),
    ("char", True): lambda d: format_char_summary(d),
    ("stash", False): lambda d: format_stash_info(d),
    ("stash", True): lambda d: format_stash_summary(d),
    ("item", False): lambda it: "=== Item Info ===\n" + format_item_info(it),
    ("item", True): lambda it: f"=== Item Summary ===\n- {format_item_summary(it)}",
}


def process_file(file_path: str, args: Any) -> None:
    ensure_data_loaded(lang_key=getattr(args, "lang", None) or "enUS")
    if not os.path.exists(file_path):
        print(f"Error: File '{file_path}' does not exist")
        return

    if not file_path.endswith((".d2s", ".d2i")):
        print(f"Error: File '{file_path}' is not a .d2s or .d2i file")
        return

    kind, data, bs = parse_file(file_path, getattr(args, "debug", False))
    if not kind or not data:
        return

    _run_bitstream_searches(bs, args)

    formatter = FORMATTERS.get((kind, getattr(args, "summary", False)))
    if formatter:
        print(formatter(data))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Diablo II Save and Shared Stash File Parser",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s character.d2s
  %(prog)s --summary character.d2s
  %(prog)s ModernSharedStashSoftCoreV2.d2i
  %(prog)s --summary *.d2s ModernSharedStashSoftCoreV2.d2i
  %(prog)s --debug character.d2s
  %(prog)s --lang zhCN character.d2s
  %(prog)s --search 10110011 character.d2s
  %(prog)s --search-bytes 4a4d character.d2s
        """,
    )

    parser.add_argument(
        "file_path", nargs="+", help="Path to the .d2s save file(s) or .d2i stash/item file(s)"
    )
    parser.add_argument(
        "--summary", action="store_true", help="Show compact summary instead of full dump"
    )
    parser.add_argument("-d", "--debug", action="store_true", help="Show debug info")
    parser.add_argument(
        "-s", "--search", metavar="PATTERN", help='Search bit pattern (e.g. "10110011")'
    )
    parser.add_argument(
        "-sb", "--search-bytes", metavar="HEX", help='Search byte pattern (e.g. "4a4d")'
    )
    parser.add_argument("--lang", metavar="LANG_KEY", help="Set language (e.g. enUS, zhCN, zhTW)")

    args = parser.parse_args()
    ensure_data_loaded(lang_key=args.lang or "enUS")

    for idx, path in enumerate(args.file_path):
        if len(args.file_path) > 1:
            if idx > 0:
                print()
            print(f"=== File: {path} ===")
        process_file(path, args)


if __name__ == "__main__":
    main()
