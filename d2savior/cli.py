#!/usr/bin/env python3
import argparse
import os
import sys
from pathlib import Path
from typing import Any

from d2savior.config import load_save_dir, update_save_dir
from d2savior.core.bitstream_debug import _run_bitstream_searches
from d2savior.core.d2data import GameDataResolver
from d2savior.core.d2s_struct import D2SStruct
from d2savior.core.formatters import (
    ensure_data_loaded,
    format_char_info,
    format_char_list,
    format_char_summary,
    format_item_info,
    format_item_summary,
    format_stash_info,
    format_stash_summary,
    format_timestamp,
)
from d2savior.core.ibitstream import IBitStream
from d2savior.core.stash import SharedStash


def parse_d2i_file(
    file_path: str, debug: bool = False
) -> tuple[bool, Any, str | None, IBitStream | None]:
    try:
        with open(file_path, "rb") as f:
            data = f.read()

        ensure_data_loaded()
        from d2savior.core.d2data import get_game_data

        game_data = get_game_data()

        bs = IBitStream(data)
        if data.startswith(b"JM"):
            from d2savior.core.item import D2Item

            item = D2Item()
            item.deserialize(bs, data=game_data)
            return True, item, "item", bs

        stash = SharedStash()
        stash.deserialize(bs, data=game_data)
        if not stash.tabs:
            print(f"Error: '{file_path}' contains no parseable stash tabs", file=sys.stderr)
            return False, None, None, None

        if debug and len(data) >= 4 and data[:4] == b"\x55\xaa\x55\xaa":
            print("\n=== BitStream Final State ===")
            print(f"Total bits: {len(bs)}")
            print(f"Final offset: {bs.get_offset()}")
            print(f"Remaining: {bs.remaining()}")

        return True, stash, "stash", bs
    except Exception as e:
        print(f"Error parsing file: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc(file=sys.stderr)
        return False, None, None, None


def parse_d2s_file(
    file_path: str, debug: bool = False
) -> tuple[bool, D2SStruct | None, IBitStream | None]:
    try:
        with open(file_path, "rb") as f:
            data = f.read()

        ensure_data_loaded()
        from d2savior.core.d2data import get_game_data

        game_data = get_game_data()

        bs = IBitStream(data)
        char_data = D2SStruct()
        char_data.deserialize(bs, data=game_data)

        if debug:
            print("\n=== BitStream Final State ===")
            print(f"Total bits: {len(bs)}")
            print(f"Final offset: {bs.get_offset()}")
            print(f"Remaining: {bs.remaining()}")

        return True, char_data, bs

    except Exception as e:
        print(f"Error parsing file: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc(file=sys.stderr)
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


def process_file(file_path: str, args: Any) -> bool:
    ensure_data_loaded(lang_key=getattr(args, "lang", None) or "enUS")
    if not os.path.exists(file_path):
        print(f"Error: File '{file_path}' does not exist", file=sys.stderr)
        return False

    if not file_path.lower().endswith((".d2s", ".d2i")):
        print(f"Error: File '{file_path}' is not a .d2s or .d2i file", file=sys.stderr)
        return False

    kind, data, bs = parse_file(file_path, getattr(args, "debug", False))
    if not kind or not data:
        return False

    _run_bitstream_searches(bs, args)

    formatter = FORMATTERS.get((kind, getattr(args, "summary", False)))
    if formatter:
        print(formatter(data))
    return True


def find_saves_in_dir(dir_path: Path) -> list[str]:
    """Return sorted list of save files: character files (.d2s) first, then stash files (.d2i)."""
    if not dir_path.is_dir():
        return []
    saves = [p for p in dir_path.iterdir() if p.is_file() and p.suffix.lower() in (".d2s", ".d2i")]
    saves.sort(key=lambda p: (0 if p.suffix.lower() == ".d2s" else 1, p.name.lower()))
    return [str(p) for p in saves]


def resolve_target_files(
    input_paths: list[str], no_config: bool = False
) -> tuple[list[str], Path | None]:
    """Resolve file paths and determine if a directory should be saved to config.

    Returns (files_to_process, dir_to_save).
    """
    configured_dir = None if no_config else load_save_dir()

    if not input_paths:
        if no_config:
            print("Error: No save path provided and --no-config was specified", file=sys.stderr)
            return [], None
        if not configured_dir or not configured_dir.is_dir():
            print(
                "Error: No save path provided and no save directory configured. "
                "Provide a path to a save file or directory.",
                file=sys.stderr,
            )
            return [], None
        files = find_saves_in_dir(configured_dir)
        if not files:
            print(f"Error: No .d2s or .d2i files found in '{configured_dir}'", file=sys.stderr)
            return [], None
        return files, None

    resolved_files: list[str] = []
    dir_to_save: Path | None = None

    for raw_path in input_paths:
        p = Path(raw_path)
        if p.is_dir():
            dir_files = find_saves_in_dir(p)
            if not dir_files:
                print(f"Error: No .d2s or .d2i files found in '{raw_path}'", file=sys.stderr)
            else:
                resolved_files.extend(dir_files)
                dir_to_save = p.resolve()
        elif p.is_file():
            resolved_files.append(str(p))
            dir_to_save = p.resolve().parent
        else:
            found_in_config = False
            if configured_dir and configured_dir.is_dir():
                for candidate in (raw_path, f"{raw_path}.d2s", f"{raw_path}.d2i"):
                    cand_path = configured_dir / candidate
                    if cand_path.is_file():
                        resolved_files.append(str(cand_path))
                        found_in_config = True
                        break
                if not found_in_config:
                    target_names = {
                        raw_path.lower(),
                        f"{raw_path.lower()}.d2s",
                        f"{raw_path.lower()}.d2i",
                    }
                    for item in sorted(configured_dir.iterdir()):
                        if item.is_file() and item.name.lower() in target_names:
                            resolved_files.append(str(item))
                            found_in_config = True
                            break
            if not found_in_config:
                resolved_files.append(raw_path)

    return resolved_files, dir_to_save


def extract_char_row(file_path: str) -> dict[str, Any] | None:
    ok, char_data, _ = parse_d2s_file(file_path, debug=False)
    if not ok or not char_data:
        return None

    name = char_data.get_char_name().strip() or Path(file_path).stem
    resolver = GameDataResolver(char_data.version)
    char_class = resolver.get_localized_class_name(char_data.char_class)
    level = char_data.char_level
    mode = "Hardcore" if char_data.is_hardcore() else "Softcore"

    ts = char_data.last_save_time or char_data.dw_time
    if not ts or ts == 0xFFFFFFFF:
        try:
            ts = int(os.path.getmtime(file_path))
        except OSError:
            ts = 0

    last_played = format_timestamp(ts)
    return {
        "name": name,
        "class": char_class,
        "level": level,
        "mode": mode,
        "last_played": last_played,
        "sort_ts": ts,
        "file_path": file_path,
    }


def list_characters(files: list[str], lang: str | None = None) -> list[dict[str, Any]]:
    ensure_data_loaded(lang_key=lang or "enUS")
    records: list[dict[str, Any]] = []
    for f in files:
        row = extract_char_row(f)
        if row is not None:
            records.append(row)
    records.sort(key=lambda r: (-r["sort_ts"], r["name"].lower()))
    return records


_common_parser = argparse.ArgumentParser(add_help=False)
_common_parser.add_argument(
    "file_path",
    nargs="*",
    help="Path to the .d2s save file(s), directory, or .d2i stash/item file(s)",
)
_common_parser.add_argument(
    "--no-config",
    action="store_true",
    help="Do not read from or write to the configuration file",
)
_common_parser.add_argument(
    "--lang",
    metavar="LANG_KEY",
    help="Set language (e.g. enUS, zhCN, zhTW)",
)


def cmd_list(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="d2savior list",
        description="List Diablo II characters in save directory",
        parents=[_common_parser],
    )
    args = parser.parse_args(argv)
    files_to_process, dir_to_save = resolve_target_files(args.file_path, no_config=args.no_config)

    if not args.no_config and dir_to_save:
        update_save_dir(dir_to_save)

    if not files_to_process:
        return 1

    char_files = [f for f in files_to_process if f.lower().endswith(".d2s")]
    if not char_files:
        print("Error: No .d2s character files found", file=sys.stderr)
        return 1

    records = list_characters(char_files, lang=args.lang)
    if not records:
        print("Error: No characters could be parsed", file=sys.stderr)
        return 1

    print(format_char_list(records))
    return 0


def cmd_stash(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="d2savior stash",
        description="Display Diablo II shared stash in save directory",
        parents=[_common_parser],
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Show compact summary instead of full dump",
    )
    parser.add_argument("-d", "--debug", action="store_true", help="Show debug info")

    args = parser.parse_args(argv)
    files_to_process, dir_to_save = resolve_target_files(args.file_path, no_config=args.no_config)

    if not args.no_config and dir_to_save:
        update_save_dir(dir_to_save)

    if not files_to_process:
        return 1

    stash_files = [f for f in files_to_process if f.lower().endswith(".d2i")]
    if not stash_files:
        print("Error: No .d2i stash files found", file=sys.stderr)
        return 1

    has_error = False
    for idx, path in enumerate(stash_files):
        if len(stash_files) > 1:
            if idx > 0:
                print()
            print(f"=== File: {path} ===")
        if not process_file(path, args):
            has_error = True

    return 1 if has_error else 0


COMMANDS = {
    "list": (
        cmd_list,
        "list [path]       List characters in save directory (sorted by last played)",
    ),
    "stash": (
        cmd_stash,
        "stash [path]      Display shared stash in save directory",
    ),
}


def main(argv: list[str] | None = None) -> None:
    if argv is None:
        argv = sys.argv[1:]

    if argv and argv[0] in COMMANDS:
        code = COMMANDS[argv[0]][0](argv[1:])
        if code != 0:
            sys.exit(code)
        return

    commands_help = "Commands:\n" + "\n".join(f"  {help_str}" for _, help_str in COMMANDS.values())

    parser = argparse.ArgumentParser(
        description="Diablo II Save and Shared Stash File Parser",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
{commands_help}

Examples:
  %(prog)s list
  %(prog)s list /path/to/saves
  %(prog)s stash
  %(prog)s stash --summary
  %(prog)s character.d2s
  %(prog)s --summary character.d2s
  %(prog)s ModernSharedStashSoftCoreV2.d2i
  %(prog)s --summary *.d2s ModernSharedStashSoftCoreV2.d2i
  %(prog)s --debug character.d2s
  %(prog)s --lang zhCN character.d2s
  %(prog)s --search 10110011 character.d2s
  %(prog)s --search-bytes 4a4d character.d2s
        """,
        parents=[_common_parser],
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

    args = parser.parse_args(argv)
    files_to_process, dir_to_save = resolve_target_files(args.file_path, no_config=args.no_config)

    if not args.no_config and dir_to_save:
        update_save_dir(dir_to_save)

    if not files_to_process:
        sys.exit(1)

    ensure_data_loaded(lang_key=args.lang or "enUS")

    has_error = False
    for idx, path in enumerate(files_to_process):
        if len(files_to_process) > 1:
            if idx > 0:
                print()
            print(f"=== File: {path} ===")
        if process_file(path, args) is False:
            has_error = True

    if has_error:
        sys.exit(1)


if __name__ == "__main__":
    main()
