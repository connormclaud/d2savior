#!/usr/bin/env python3
import argparse
import os
import signal
import sys
from pathlib import Path
from typing import Any

if hasattr(signal, "SIGPIPE"):
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)

from d2savior.config import load_save_dir, update_save_dir
from d2savior.core.bitstream_debug import _run_bitstream_searches
from d2savior.core.char_formatter import (
    format_char_find,
    format_char_info,
    format_char_list,
    format_char_summary,
    format_timestamp,
)
from d2savior.core.d2s_struct import D2SStruct
from d2savior.core.ibitstream import IBitStream
from d2savior.core.item_formatter import (
    format_item_find,
    format_item_info,
    format_item_summary,
)
from d2savior.core.resolver import GameDataResolver
from d2savior.core.stash import SharedStash
from d2savior.core.stash_formatter import (
    format_stash_find,
    format_stash_info,
    format_stash_summary,
)


def parse_d2i_file(
    file_path: str, resolver: GameDataResolver | None = None, debug: bool = False
) -> tuple[bool, Any, str | None, IBitStream | None]:
    if resolver is None:
        resolver = GameDataResolver.load()
    try:
        with open(file_path, "rb") as f:
            data = f.read()

        bs = IBitStream(data)
        if data.startswith(b"JM"):
            from d2savior.core.item import D2Item

            item = D2Item()
            item.deserialize(bs, data=resolver.game_data)
            return True, item, "item", bs

        stash = SharedStash()
        stash.deserialize(bs, data=resolver)
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
    file_path: str, resolver: GameDataResolver | None = None, debug: bool = False
) -> tuple[bool, D2SStruct | None, IBitStream | None]:
    if resolver is None:
        resolver = GameDataResolver.load()
    try:
        with open(file_path, "rb") as f:
            data = f.read()

        bs = IBitStream(data)
        char_data = D2SStruct()
        char_data.deserialize(bs, data=resolver)

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


def parse_file(
    file_path: str, resolver: GameDataResolver | None = None, debug: bool = False
) -> tuple[str | None, Any, IBitStream | None]:
    """Dispatch file parsing based on extension, returning (kind, data, bs) or (None, None, None)."""
    if resolver is None:
        resolver = GameDataResolver.load()
    lower_path = file_path.lower()
    if lower_path.endswith(".d2i"):
        res = parse_d2i_file(file_path, resolver=resolver, debug=debug)
        if res[0]:
            _, data, kind, bs = res
            return kind, data, bs
    elif lower_path.endswith(".d2s"):
        res = parse_d2s_file(file_path, resolver=resolver, debug=debug)
        if res[0]:
            _, data, bs = res
            return "char", data, bs
    return None, None, None


FORMATTERS = {
    ("char", False): lambda d, resolver: format_char_info(d, resolver=resolver),
    ("char", True): lambda d, resolver: format_char_summary(d, resolver=resolver),
    ("stash", False): lambda d, resolver: format_stash_info(d, resolver=resolver),
    ("stash", True): lambda d, resolver: format_stash_summary(d, resolver=resolver),
    ("item", False): lambda it, resolver: (
        "=== Item Info ===\n" + format_item_info(it, resolver=resolver)
    ),
    ("item", True): lambda it, resolver: (
        f"=== Item Summary ===\n- {format_item_summary(it, resolver=resolver)}"
    ),
}


def format_output(
    kind: str,
    data: Any,
    summary: bool,
    resolver: GameDataResolver,
    find_pattern: str | None = None,
) -> str | None:
    if find_pattern:
        if kind == "char":
            return format_char_find(data, find_pattern, resolver=resolver, summary=summary)
        elif kind == "stash":
            return format_stash_find(data, find_pattern, resolver=resolver, summary=summary)
        elif kind == "item":
            return format_item_find(data, find_pattern, resolver=resolver, summary=summary)
        return None
    formatter = FORMATTERS.get((kind, summary))
    if formatter:
        return formatter(data, resolver)
    return None


def _evaluate_file(
    file_path: str, args: Any, resolver: GameDataResolver
) -> tuple[bool, str | None]:
    """Validate, parse, search, and format a single save or stash file."""
    if not os.path.exists(file_path):
        print(f"Error: File '{file_path}' does not exist", file=sys.stderr)
        return False, None

    if not file_path.lower().endswith((".d2s", ".d2i")):
        print(f"Error: File '{file_path}' is not a .d2s or .d2i file", file=sys.stderr)
        return False, None

    kind, data, bs = parse_file(file_path, resolver=resolver, debug=getattr(args, "debug", False))
    if not kind or not data:
        return False, None

    _run_bitstream_searches(bs, args)

    output = format_output(
        kind,
        data,
        getattr(args, "summary", False),
        resolver=resolver,
        find_pattern=getattr(args, "find", None),
    )
    return True, output


def process_file(file_path: str, args: Any, resolver: GameDataResolver) -> bool:
    ok, output = _evaluate_file(file_path, args, resolver)
    if not ok:
        return False
    if output:
        print(output)
    return True


def _process_files(files: list[str], args: Any, resolver: GameDataResolver) -> int:
    """Process multiple save/stash files in either search (--find) or normal display mode."""
    has_error = False
    if getattr(args, "find", None):
        printed_count = 0
        for path in files:
            ok, output = _evaluate_file(path, args, resolver)
            if not ok:
                has_error = True
                continue
            if output:
                if len(files) > 1:
                    if printed_count > 0:
                        print()
                    print(f"=== File: {path} ===")
                print(output)
                printed_count += 1
        if printed_count == 0 and not has_error:
            print("No matching items found")
        return 1 if has_error else 0

    for idx, path in enumerate(files):
        if len(files) > 1:
            if idx > 0:
                print()
            print(f"=== File: {path} ===")
        if process_file(path, args, resolver=resolver) is False:
            has_error = True
    return 1 if has_error else 0


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
    """Resolve file paths and determine if a directory should be saved to config (if empty).

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
                if configured_dir is None and not no_config and dir_to_save is None:
                    dir_to_save = p.resolve()
        elif p.is_file():
            resolved_files.append(str(p))
            if configured_dir is None and not no_config and dir_to_save is None:
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


def extract_char_row(
    file_path: str, resolver: GameDataResolver | None = None
) -> dict[str, Any] | None:
    if resolver is None:
        resolver = GameDataResolver.load()
    ok, char_data, _ = parse_d2s_file(file_path, resolver=resolver, debug=False)
    if not ok or not char_data:
        return None

    name = char_data.get_char_name().strip() or Path(file_path).stem
    char_resolver = resolver.for_version(char_data.version)
    char_class = char_resolver.get_localized_class_name(char_data.char_class)
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


def list_characters(
    files: list[str], lang: str | None = None, resolver: GameDataResolver | None = None
) -> list[dict[str, Any]]:
    if resolver is None:
        resolver = GameDataResolver.load(lang_key=lang or "enUS")
    records: list[dict[str, Any]] = []
    for f in files:
        row = extract_char_row(f, resolver=resolver)
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
_common_parser.add_argument(
    "-f",
    "--find",
    metavar="PATTERN",
    help="Find items matching pattern in name or type",
)


def _resolve_and_save_targets(args: Any) -> list[str]:
    """Resolve input targets and persist the inferred save directory if not yet configured."""
    files_to_process, dir_to_save = resolve_target_files(args.file_path, no_config=args.no_config)
    if not args.no_config and dir_to_save:
        update_save_dir(dir_to_save, if_empty=True)
    return files_to_process


def cmd_list(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="d2savior list",
        description="List Diablo II characters in save directory",
        parents=[_common_parser],
    )
    args = parser.parse_args(argv)
    files_to_process = _resolve_and_save_targets(args)

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
    files_to_process = _resolve_and_save_targets(args)

    if not files_to_process:
        return 1

    stash_files = [f for f in files_to_process if f.lower().endswith(".d2i")]
    if not stash_files:
        print("Error: No .d2i stash files found", file=sys.stderr)
        return 1

    resolver = GameDataResolver.load(lang_key=args.lang or "enUS")
    return _process_files(stash_files, args, resolver)


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
  %(prog)s stash --find "hold"
  %(prog)s character.d2s
  %(prog)s --summary character.d2s
  %(prog)s --find "hold"
  %(prog)s --find "hold" --summary
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
    files_to_process = _resolve_and_save_targets(args)

    if not files_to_process:
        sys.exit(1)

    resolver = GameDataResolver.load(lang_key=args.lang or "enUS")
    if _process_files(files_to_process, args, resolver) != 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
