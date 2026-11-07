#!/usr/bin/env python3
"""Compatibility shim forwarding to d2savior.cli."""

import sys

import d2savior.cli as _cli
from d2savior.cli import (
    FORMATTERS,
    ensure_data_loaded,
    find_saves_in_dir,
    format_char_info,
    format_char_summary,
    format_item_info,
    format_item_summary,
    format_stash_info,
    format_stash_summary,
    main,
    parse_d2i_file,
    parse_d2s_file,
    parse_file,
    process_file,
    resolve_target_files,
)

__all__ = [
    "FORMATTERS",
    "ensure_data_loaded",
    "find_saves_in_dir",
    "format_char_info",
    "format_char_summary",
    "format_item_info",
    "format_item_summary",
    "format_stash_info",
    "format_stash_summary",
    "main",
    "parse_d2i_file",
    "parse_d2s_file",
    "parse_file",
    "process_file",
    "resolve_target_files",
]

sys.modules[__name__] = _cli

if __name__ == "__main__":
    main()
