#!/usr/bin/env python3
import argparse
import signal
import sys

if hasattr(signal, "SIGPIPE"):
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)

lazy import os
lazy from pathlib import Path

lazy from d2savior.cli_common import (
    common_parser,
    report_parse_error,
    resolve_and_save_targets,
)
lazy from d2savior.cli_common import (
    find_saves_in_dir as find_saves_in_dir,
)
lazy from d2savior.cli_common import (
    resolve_target_files as resolve_target_files,
)
lazy from d2savior.cli_optimize import cmd_optimize
lazy from d2savior.core.bitstream_debug import _run_bitstream_searches
lazy from d2savior.core.char_formatter import (
    CharListRow,
    format_char_find,
    format_char_info,
    format_char_list,
    format_char_summary,
    format_timestamp,
)
lazy from d2savior.core.d2s_struct import D2SStruct
lazy from d2savior.core.ibitstream import IBitStream
lazy from d2savior.core.io import PARSE_ERRORS, ParsedData, load_d2i, load_d2s
lazy from d2savior.core.item import D2Item
lazy from d2savior.core.item_formatter import (
    format_item_find,
    format_item_info,
    format_item_summary,
)
lazy from d2savior.core.resolver import GameDataResolver
lazy from d2savior.core.stash import SharedStash
lazy from d2savior.core.stash_formatter import (
    format_stash_find,
    format_stash_info,
    format_stash_summary,
)


def parse_d2i_file(
    file_path: str, resolver: GameDataResolver | None = None, debug: bool = False
) -> tuple[bool, SharedStash | D2Item | None, str | None, IBitStream | None]:
    if resolver is None:
        resolver = GameDataResolver.load()
    try:
        parsed, kind, bs = load_d2i(file_path, resolver=resolver)
        if (
            debug
            and kind == "stash"
            and isinstance(parsed, SharedStash)
            and bs.data[:4] == b"\x55\xaa\x55\xaa"
        ):
            print("\n=== BitStream Final State ===")
            print(f"Total bits: {len(bs)}")
            print(f"Final offset: {bs.get_offset()}")
            print(f"Remaining: {bs.remaining()}")

        return True, parsed, kind, bs
    except PARSE_ERRORS as e:
        report_parse_error(file_path, e, debug)
        return False, None, None, None


def parse_d2s_file(
    file_path: str, resolver: GameDataResolver | None = None, debug: bool = False
) -> tuple[bool, D2SStruct | None, IBitStream | None]:
    if resolver is None:
        resolver = GameDataResolver.load()
    try:
        char_data, bs = load_d2s(file_path, resolver=resolver)

        if debug:
            print("\n=== BitStream Final State ===")
            print(f"Total bits: {len(bs)}")
            print(f"Final offset: {bs.get_offset()}")
            print(f"Remaining: {bs.remaining()}")

        return True, char_data, bs

    except PARSE_ERRORS as e:
        report_parse_error(file_path, e, debug)
        return False, None, None


def parse_file(
    file_path: str, resolver: GameDataResolver | None = None, debug: bool = False
) -> tuple[str | None, ParsedData | None, IBitStream | None]:
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


FORMATTERS = frozendict(
    {
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
)


def format_output(
    kind: str,
    data: ParsedData,
    summary: bool,
    resolver: GameDataResolver,
    find_pattern: str | None = None,
) -> str | None:
    if find_pattern:
        if kind == "char" and isinstance(data, D2SStruct):
            return format_char_find(data, find_pattern, resolver=resolver, summary=summary)
        elif kind == "stash" and isinstance(data, SharedStash):
            return format_stash_find(data, find_pattern, resolver=resolver, summary=summary)
        elif kind == "item" and isinstance(data, D2Item):
            return format_item_find(data, find_pattern, resolver=resolver, summary=summary)
        return None
    formatter = FORMATTERS.get((kind, summary))
    if formatter:
        return formatter(data, resolver)
    return None


def _evaluate_file(
    file_path: str, args: argparse.Namespace, resolver: GameDataResolver
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


def process_file(file_path: str, args: argparse.Namespace, resolver: GameDataResolver) -> bool:
    ok, output = _evaluate_file(file_path, args, resolver)
    if not ok:
        return False
    if output:
        print(output)
    return True


def _process_files(files: list[str], args: argparse.Namespace, resolver: GameDataResolver) -> int:
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


def extract_char_row(
    file_path: str, resolver: GameDataResolver | None = None
) -> CharListRow | None:
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
) -> list[CharListRow]:
    if resolver is None:
        resolver = GameDataResolver.load(lang_key=lang or "enUS")
    records: list[CharListRow] = []
    for f in files:
        row = extract_char_row(f, resolver=resolver)
        if row is not None:
            records.append(row)
    records.sort(key=lambda r: (-r["sort_ts"], r["name"].lower()))
    return records


def cmd_list(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="d2savior list",
        description="List Diablo II characters in save directory",
        parents=[common_parser],
    )
    args = parser.parse_args(argv)
    files_to_process = resolve_and_save_targets(args)

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
        parents=[common_parser],
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Show compact summary instead of full dump",
    )
    parser.add_argument("-d", "--debug", action="store_true", help="Show debug info")

    args = parser.parse_args(argv)
    files_to_process = resolve_and_save_targets(args)

    if not files_to_process:
        return 1

    stash_files = [f for f in files_to_process if f.lower().endswith(".d2i")]
    if not stash_files:
        print("Error: No .d2i stash files found", file=sys.stderr)
        return 1

    resolver = GameDataResolver.load(lang_key=args.lang or "enUS")
    return _process_files(stash_files, args, resolver)


COMMANDS = frozendict(
    {
        "list": (
            cmd_list,
            "list [path]       List characters in save directory (sorted by last played)",
        ),
        "stash": (
            cmd_stash,
            "stash [path]      Display shared stash in save directory",
        ),
        "optimize": (
            cmd_optimize,
            "optimize [socket] [name]  Optimize builds or Socket Quest candidates (-b ...)",
        ),
    }
)


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
        parents=[common_parser],
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
    files_to_process = resolve_and_save_targets(args)

    if not files_to_process:
        sys.exit(1)

    resolver = GameDataResolver.load(lang_key=args.lang or "enUS")
    if _process_files(files_to_process, args, resolver) != 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
