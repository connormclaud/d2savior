#!/usr/bin/env python3
import argparse
import signal
import sys

if hasattr(signal, "SIGPIPE"):
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)

lazy import os
lazy import struct
lazy import traceback
lazy from pathlib import Path

lazy from d2savior.config import load_save_dir, update_save_dir
lazy from d2savior.core.bitstream_debug import _run_bitstream_searches
lazy from d2savior.core.char_formatter import (
    CharListRow,
    format_char_find,
    format_char_info,
    format_char_list,
    format_char_summary,
    format_timestamp,
)
lazy from d2savior.core.constants import DIFFICULTY_NAMES
lazy from d2savior.core.d2s_struct import D2SStruct
lazy from d2savior.core.enums import CharClass
lazy from d2savior.core.ibitstream import IBitStream
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
lazy from d2savior.core.stats import get_current_difficulty
lazy from d2savior.optimizer import (
    BUILD_CHOICES,
    PALADIN_BUILD_CHOICES,
    SORC_ONLY_BUILD_CHOICES,
    SUPPORTED_OPTIMIZER_CLASSES,
    CharmSpec,
    ItemSpec,
    extract_pool,
    format_build_report,
    format_paladin_leveling_report,
    optimize_builds,
    optimize_paladin_leveling,
    paladin_primary_skill_info,
    select_paladin_max_res_preset,
    select_sorc_presets,
    validate_supported_class,
)

_PARSE_ERRORS = (OSError, ValueError, LookupError, EOFError, struct.error)


def _report_parse_error(file_path: str, exc: Exception, debug: bool) -> None:
    print(f"Error parsing '{file_path}': {exc}", file=sys.stderr)
    if debug:
        traceback.print_exc(file=sys.stderr)


type ParsedData = D2SStruct | SharedStash | D2Item


def parse_d2i_file(
    file_path: str, resolver: GameDataResolver | None = None, debug: bool = False
) -> tuple[bool, SharedStash | D2Item | None, str | None, IBitStream | None]:
    if resolver is None:
        resolver = GameDataResolver.load()
    try:
        with open(file_path, "rb") as f:
            data = f.read()

        bs = IBitStream(data)
        if data.startswith(b"JM"):
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
    except _PARSE_ERRORS as e:
        _report_parse_error(file_path, e, debug)
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

    except _PARSE_ERRORS as e:
        _report_parse_error(file_path, e, debug)
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


def find_saves_in_dir(dir_path: Path) -> list[str]:
    """Return sorted list of save files: character files (.d2s) first, then stash files (.d2i)."""
    if not dir_path.is_dir():
        return []
    saves = [p for p in dir_path.iterdir() if p.is_file() and p.suffix.lower() in (".d2s", ".d2i")]
    saves.sort(key=lambda p: (0 if p.suffix.lower() == ".d2s" else 1, p.name.lower()))
    return [str(p) for p in saves]


def _resolve_default_dir_files(configured_dir: Path | None, no_config: bool) -> list[str]:
    if no_config:
        print("Error: No save path provided and --no-config was specified", file=sys.stderr)
        return []
    if not configured_dir or not configured_dir.is_dir():
        print(
            "Error: No save path provided and no save directory configured. "
            "Provide a path to a save file or directory.",
            file=sys.stderr,
        )
        return []
    files = find_saves_in_dir(configured_dir)
    if not files:
        print(f"Error: No .d2s or .d2i files found in '{configured_dir}'", file=sys.stderr)
        return []
    return files


def _lookup_in_configured_dir(configured_dir: Path | None, raw_path: str) -> str | None:
    if not (configured_dir and configured_dir.is_dir()):
        return None
    for candidate in (raw_path, f"{raw_path}.d2s", f"{raw_path}.d2i"):
        cand_path = configured_dir / candidate
        if cand_path.is_file():
            return str(cand_path)
    target_names = {raw_path.lower(), f"{raw_path.lower()}.d2s", f"{raw_path.lower()}.d2i"}
    for item in sorted(configured_dir.iterdir()):
        if item.is_file() and item.name.lower() in target_names:
            return str(item)
    return None


def resolve_target_files(
    input_paths: list[str], no_config: bool = False
) -> tuple[list[str], Path | None]:
    """Resolve file paths and determine if a directory should be saved to config (if empty).

    Returns (files_to_process, dir_to_save).
    """
    configured_dir = None if no_config else load_save_dir()

    if not input_paths:
        return _resolve_default_dir_files(configured_dir, no_config), None

    resolved_files: list[str] = []
    dir_to_save: Path | None = None
    should_remember = configured_dir is None and not no_config

    for raw_path in input_paths:
        p = Path(raw_path)
        if p.is_dir():
            if dir_files := find_saves_in_dir(p):
                resolved_files.extend(dir_files)
                if should_remember and dir_to_save is None:
                    dir_to_save = p.resolve()
            else:
                print(f"Error: No .d2s or .d2i files found in '{raw_path}'", file=sys.stderr)
        elif p.is_file():
            resolved_files.append(str(p))
            if should_remember and dir_to_save is None:
                dir_to_save = p.resolve().parent
        else:
            matched = _lookup_in_configured_dir(configured_dir, raw_path)
            resolved_files.append(matched or raw_path)

    return resolved_files, dir_to_save


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


def _resolve_and_save_targets(args: argparse.Namespace) -> list[str]:
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


def _resolve_primary_optimize_char(
    chars: list[D2SStruct], target_name: str | None, build: str
) -> tuple[D2SStruct | None, str | None]:
    build_lower = build.lower()
    if target_name is not None:
        for ch in chars:
            if ch.get_char_name().lower() == target_name.lower():
                return ch, None
        return None, f"Error: Character '{target_name}' not found in target saves"

    allowed_classes: tuple[CharClass, ...]
    if build_lower in SORC_ONLY_BUILD_CHOICES:
        allowed_classes, class_label = (CharClass.SORCERESS,), "Sorceress"
    elif build_lower in PALADIN_BUILD_CHOICES:
        allowed_classes, class_label = (CharClass.PALADIN,), "Paladin"
    else:
        allowed_classes, class_label = SUPPORTED_OPTIMIZER_CLASSES, "optimizable"
    candidates = [ch for ch in chars if ch.char_class in allowed_classes]
    if not candidates:
        no_cls_msg = (
            "Sorceress or Paladin"
            if allowed_classes == SUPPORTED_OPTIMIZER_CLASSES
            else class_label
        )
        return None, f"Error: No {no_cls_msg} character found in target saves"
    if len(candidates) > 1:
        names = ", ".join(ch.get_char_name() for ch in candidates)
        return (
            None,
            f"Error: Multiple {class_label} characters found ({names}); specify a character name",
        )
    return candidates[0], None


def _load_optimize_pool(
    files_to_process: list[str],
    target_name: str | None,
    resolver: GameDataResolver,
    *,
    build: str = "all",
) -> tuple[D2SStruct | None, list[D2SStruct], list[SharedStash], str | None]:
    chars: list[D2SStruct] = []
    stashes: list[SharedStash] = []
    for f in files_to_process:
        lower = f.lower()
        if lower.endswith(".d2s"):
            ok, char_data, _ = parse_d2s_file(f, resolver=resolver)
            if ok and char_data is not None:
                chars.append(char_data)
        elif lower.endswith(".d2i"):
            ok, stash_data, kind, _ = parse_d2i_file(f, resolver=resolver)
            if ok and kind == "stash" and isinstance(stash_data, SharedStash):
                stashes.append(stash_data)

    primary, err = _resolve_primary_optimize_char(chars, target_name, build)
    if primary is None:
        return None, [], stashes, err

    try:
        validate_supported_class(primary)
    except ValueError as exc:
        return None, [], stashes, f"Error: {exc}"

    build_lower = build.lower()
    if primary.char_class == CharClass.SORCERESS and build_lower in PALADIN_BUILD_CHOICES:
        return (
            None,
            [],
            stashes,
            f"Error: Build preset '{build}' is only supported for Paladin; '{primary.get_char_name()}' is Sorceress",
        )
    if primary.char_class == CharClass.PALADIN and build_lower in SORC_ONLY_BUILD_CHOICES:
        return (
            None,
            [],
            stashes,
            f"Error: Build preset '{build}' is only supported for Sorceress; '{primary.get_char_name()}' is Paladin",
        )

    extras = [ch for ch in chars if ch is not primary]
    return primary, extras, stashes, None


def _run_sorc_optimize(
    primary: D2SStruct,
    extras: list[D2SStruct],
    stashes: list[SharedStash],
    items: list[ItemSpec],
    charms: list[CharmSpec],
    resolver: GameDataResolver,
    args: argparse.Namespace,
    primary_inv_loc: str,
) -> None:
    for title, constraints in select_sorc_presets(
        primary,
        build=args.build,
        max_charm_slots=args.charm_slots,
        limit=args.limit,
        extra_chars=extras,
        stashes=stashes,
        resolver=resolver,
        keep_equipped=args.keep_gear,
    ):
        results = optimize_builds(items, charms, constraints)
        print(format_build_report(title, results, charms, primary_inv_loc=primary_inv_loc))
        print()


def _run_paladin_optimize(
    primary: D2SStruct,
    extras: list[D2SStruct],
    stashes: list[SharedStash],
    items: list[ItemSpec],
    charms: list[CharmSpec],
    resolver: GameDataResolver,
    args: argparse.Namespace,
    primary_inv_loc: str,
) -> None:
    if args.build.lower() == "max-res":
        title, constraints, resolved_spec = select_paladin_max_res_preset(
            primary,
            max_charm_slots=args.charm_slots,
            limit=args.limit,
            extra_chars=extras,
            stashes=stashes,
            resolver=resolver,
            keep_equipped=args.keep_gear,
            targets=args.targets,
        )
        diff_name = DIFFICULTY_NAMES[get_current_difficulty(primary)]
        skill_name, base_skill_lvl = paladin_primary_skill_info(primary, resolved_spec)
        report = format_build_report(
            title,
            optimize_builds(items, charms, constraints),
            charms,
            char_class=primary.char_class,
            diff_name=diff_name,
            primary_skill_name=skill_name,
            primary_skill_base=base_skill_lvl,
            primary_inv_loc=primary_inv_loc,
        )
    else:
        title, options, resolved_spec, diff_name = optimize_paladin_leveling(
            primary,
            items,
            charms,
            max_charm_slots=args.charm_slots,
            limit=args.limit,
            extra_chars=extras,
            stashes=stashes,
            resolver=resolver,
            keep_equipped=args.keep_gear,
            targets=args.targets,
        )
        skill_name, base_skill_lvl = paladin_primary_skill_info(primary, resolved_spec)
        report = format_paladin_leveling_report(
            title,
            options,
            charms,
            diff_name=diff_name,
            primary_skill_name=skill_name,
            primary_skill_base=base_skill_lvl,
            primary_inv_loc=primary_inv_loc,
        )
    print(report)
    print()


def _split_optimize_targets(
    raw_targets: list[str], explicit_char: str | None
) -> tuple[str | None, list[str]]:
    """Separate an optional positional character name from explicit save paths."""
    char_name = explicit_char
    paths: list[str] = []
    for entry in raw_targets:
        p = Path(entry)
        if p.exists() or entry.lower().endswith((".d2s", ".d2i")):
            paths.append(entry)
            if char_name is None and entry.lower().endswith(".d2s"):
                char_name = p.stem
        elif char_name is None:
            char_name = entry
        else:
            paths.append(entry)
    return char_name, paths


def cmd_optimize(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="d2savior optimize",
        description="Optimize Sorceress or Paladin leveling builds across characters and shared stash",
        parents=[_common_parser],
    )
    parser.add_argument(
        "--char",
        default=None,
        help="Target character name (Sorceress or Paladin; can also be passed positionally)",
    )
    parser.add_argument(
        "-b",
        "--build",
        choices=BUILD_CHOICES,
        default="all",
        help="Build preset to optimize (default: all)",
    )
    parser.add_argument(
        "--charm-slots",
        type=int,
        default=23,
        help="Maximum inventory charm slots to allocate (default: 23)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=3,
        help="Maximum top options to show per build preset (default: 3)",
    )
    parser.add_argument(
        "--keep-gear",
        action="store_true",
        help="Keep currently equipped active gear and optimize inventory charms only",
    )
    parser.add_argument(
        "--targets",
        type=int,
        default=1,
        help="Number of simultaneous targets for AoE DPS (e.g. 1=boss, 3=pack; default: 1)",
    )
    args = parser.parse_args(argv)
    if args.targets < 1:
        parser.error("--targets must be >= 1")
    target_char, args.file_path = _split_optimize_targets(args.file_path, args.char)
    files_to_process = _resolve_and_save_targets(args)
    if not files_to_process:
        return 1

    resolver = GameDataResolver.load(lang_key=args.lang or "enUS")
    primary, extras, stashes, err = _load_optimize_pool(
        files_to_process, target_char, resolver, build=args.build
    )
    if primary is None:
        print(err or "Error: Character not found in target saves", file=sys.stderr)
        return 1

    primary_inv_loc = f"{primary.get_char_name()} Inv"
    try:
        items, charms = extract_pool(
            primary,
            extra_chars=extras,
            stashes=stashes,
            resolver=resolver,
            keep_equipped=args.keep_gear,
        )
        if primary.char_class == CharClass.SORCERESS:
            _run_sorc_optimize(
                primary, extras, stashes, items, charms, resolver, args, primary_inv_loc
            )
        else:
            _run_paladin_optimize(
                primary, extras, stashes, items, charms, resolver, args, primary_inv_loc
            )
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


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
            "optimize [name]   Optimize Sorceress or Paladin leveling builds (-b ...)",
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
