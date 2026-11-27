"""Shared CLI target resolution, common arguments, and error reporting helpers."""

import argparse
import sys
lazy import traceback
lazy from pathlib import Path

lazy from d2savior.config import load_save_dir, update_save_dir
lazy from d2savior.core.io import EmptyStashError

COMMON_VALUE_OPTS: frozenset[str] = frozenset({"--lang", "-f", "--find"})


def report_parse_error(file_path: str, exc: Exception, debug: bool = False) -> None:
    """Print a standardized parse error to stderr, optionally including traceback."""
    if isinstance(exc, EmptyStashError):
        print(f"Error: {exc}", file=sys.stderr)
    else:
        print(f"Error parsing '{file_path}': {exc}", file=sys.stderr)
    if debug:
        traceback.print_exc(file=sys.stderr)


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


def resolve_and_save_targets(args: argparse.Namespace) -> list[str]:
    """Resolve input targets and persist the inferred save directory if not yet configured."""
    files_to_process, dir_to_save = resolve_target_files(args.file_path, no_config=args.no_config)
    if not args.no_config and dir_to_save:
        update_save_dir(dir_to_save, if_empty=True)
    return files_to_process


common_parser = argparse.ArgumentParser(add_help=False)
common_parser.add_argument(
    "file_path",
    nargs="*",
    help="Path to the .d2s save file(s), directory, or .d2i stash/item file(s)",
)
common_parser.add_argument(
    "--no-config",
    action="store_true",
    help="Do not read from or write to the configuration file",
)
common_parser.add_argument(
    "--lang",
    metavar="LANG_KEY",
    help="Set language (e.g. enUS, zhCN, zhTW)",
)
common_parser.add_argument(
    "-f",
    "--find",
    metavar="PATTERN",
    help="Find items matching pattern in name or type",
)
