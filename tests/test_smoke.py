import difflib
import os
import subprocess
import sys

import pytest

from d2s_parse import parse_file
from d2savior.core.char_formatter import (
    format_char_find,
    format_char_info,
    format_char_summary,
)
from d2savior.core.stash_formatter import (
    format_stash_find,
    format_stash_info,
    format_stash_summary,
)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
GOLDEN_DIR = os.path.join(FIXTURES_DIR, "golden")

SORK_D2S = os.path.join(FIXTURES_DIR, "sork.d2s")
MULE_UNIQUE_D2S = os.path.join(FIXTURES_DIR, "mule_unique.d2s")
STASH_D2I = os.path.join(FIXTURES_DIR, "ModernSharedStashSoftCoreV2.d2i")

SORK_SUMMARY_GOLDEN = os.path.join(GOLDEN_DIR, "sork_summary.golden.txt")
SORK_FULL_GOLDEN = os.path.join(GOLDEN_DIR, "sork_full.golden.txt")
SORK_FULL_RURU_GOLDEN = os.path.join(GOLDEN_DIR, "sork_full_ruRU.golden.txt")
STASH_SUMMARY_GOLDEN = os.path.join(GOLDEN_DIR, "stash_summary.golden.txt")
STASH_FULL_GOLDEN = os.path.join(GOLDEN_DIR, "stash_full.golden.txt")
STASH_FULL_RURU_GOLDEN = os.path.join(GOLDEN_DIR, "stash_full_ruRU.golden.txt")
STASH_FIND_CHARM_SUMMARY_GOLDEN = os.path.join(GOLDEN_DIR, "stash_find_charm_summary.golden.txt")
STASH_FIND_JEWEL_SUMMARY_GOLDEN = os.path.join(GOLDEN_DIR, "stash_find_jewel_summary.golden.txt")
STASH_FIND_TITAN_SUMMARY_GOLDEN = os.path.join(GOLDEN_DIR, "stash_find_titan_summary.golden.txt")
STASH_FIND_HORAZON_SUMMARY_GOLDEN = os.path.join(
    GOLDEN_DIR, "stash_find_horazon_summary.golden.txt"
)
MULE_UNIQUE_FIND_GRIM_SUMMARY_GOLDEN = os.path.join(
    GOLDEN_DIR, "mule_unique_find_grim_summary.golden.txt"
)

STASH_FIND_CASES = [
    ("Charm", STASH_FIND_CHARM_SUMMARY_GOLDEN),
    ("Jewel", STASH_FIND_JEWEL_SUMMARY_GOLDEN),
    ("Titan", STASH_FIND_TITAN_SUMMARY_GOLDEN),
    ("Horazon", STASH_FIND_HORAZON_SUMMARY_GOLDEN),
]

CHAR_FIND_CASES = [
    ("Grim's Burning Dead", MULE_UNIQUE_D2S, MULE_UNIQUE_FIND_GRIM_SUMMARY_GOLDEN),
]

CLI_SCRIPT = os.path.join(REPO_ROOT, "d2s_parse.py")


def _read_golden(file_path: str) -> str:
    with open(file_path, encoding="utf-8") as f:
        return f.read()


def assert_matches_golden(actual: str, golden_path: str, name: str) -> None:
    expected = _read_golden(golden_path)
    if actual != expected:
        diff = "".join(
            difflib.unified_diff(
                expected.splitlines(keepends=True),
                actual.splitlines(keepends=True),
                fromfile=f"golden/{os.path.basename(golden_path)}",
                tofile=f"actual/{name}",
                n=3,
            )
        )
        if not diff:
            diff = f"(No line diff; length or whitespace differs: expected={len(expected)}, actual={len(actual)})"
        pytest.fail(f"Mismatch against golden for {name}:\n\n{diff}", pytrace=False)


class TestSmokeAPI:
    """Smoke tests validating parsing and formatting via direct API calls."""

    def test_sork_summary(self, game_data_resolver):
        kind, data, _ = parse_file(SORK_D2S, resolver=game_data_resolver)
        assert kind == "char"
        assert data is not None
        output = format_char_summary(data, resolver=game_data_resolver) + "\n"
        assert_matches_golden(output, SORK_SUMMARY_GOLDEN, "sork_summary_api")

    def test_sork_full(self, game_data_resolver):
        kind, data, _ = parse_file(SORK_D2S, resolver=game_data_resolver)
        assert kind == "char"
        assert data is not None
        output = format_char_info(data, resolver=game_data_resolver) + "\n"
        assert_matches_golden(output, SORK_FULL_GOLDEN, "sork_full_api")

    def test_stash_summary(self, game_data_resolver):
        kind, data, _ = parse_file(STASH_D2I, resolver=game_data_resolver)
        assert kind == "stash"
        assert data is not None
        output = format_stash_summary(data, resolver=game_data_resolver) + "\n"
        assert_matches_golden(output, STASH_SUMMARY_GOLDEN, "stash_summary_api")

    def test_stash_full(self, game_data_resolver):
        kind, data, _ = parse_file(STASH_D2I, resolver=game_data_resolver)
        assert kind == "stash"
        assert data is not None
        output = format_stash_info(data, resolver=game_data_resolver) + "\n"
        assert_matches_golden(output, STASH_FULL_GOLDEN, "stash_full_api")

    def test_sork_full_ru(self, game_data_resolver_ru):
        kind, data, _ = parse_file(SORK_D2S, resolver=game_data_resolver_ru)
        assert kind == "char"
        assert data is not None
        output = format_char_info(data, resolver=game_data_resolver_ru) + "\n"
        assert_matches_golden(output, SORK_FULL_RURU_GOLDEN, "sork_full_ru_api")

    def test_stash_full_ru(self, game_data_resolver_ru):
        kind, data, _ = parse_file(STASH_D2I, resolver=game_data_resolver_ru)
        assert kind == "stash"
        assert data is not None
        output = format_stash_info(data, resolver=game_data_resolver_ru) + "\n"
        assert_matches_golden(output, STASH_FULL_RURU_GOLDEN, "stash_full_ru_api")

    @pytest.mark.parametrize(("pattern", "golden_path"), STASH_FIND_CASES)
    def test_stash_find_summary(self, game_data_resolver, pattern, golden_path):
        kind, data, _ = parse_file(STASH_D2I, resolver=game_data_resolver)
        assert kind == "stash"
        assert data is not None
        found = format_stash_find(data, pattern, resolver=game_data_resolver, summary=True)
        assert found is not None
        assert_matches_golden(found + "\n", golden_path, f"stash_find_{pattern.lower()}_api")

    @pytest.mark.parametrize(("pattern", "char_path", "golden_path"), CHAR_FIND_CASES)
    def test_char_find_summary(self, game_data_resolver, pattern, char_path, golden_path):
        kind, data, _ = parse_file(char_path, resolver=game_data_resolver)
        assert kind == "char"
        assert data is not None
        found = format_char_find(data, pattern, resolver=game_data_resolver, summary=True)
        assert found is not None
        assert_matches_golden(found + "\n", golden_path, "char_find_api")


class TestSmokeCLI:
    """Smoke tests validating end-to-end command-line interface execution."""

    def test_cli_sork_summary(self):
        res = subprocess.run(
            [sys.executable, CLI_SCRIPT, "--summary", SORK_D2S],
            capture_output=True,
            text=True,
            check=True,
            cwd=REPO_ROOT,
        )
        assert_matches_golden(res.stdout, SORK_SUMMARY_GOLDEN, "cli_sork_summary")

    def test_cli_sork_full(self):
        res = subprocess.run(
            [sys.executable, CLI_SCRIPT, SORK_D2S],
            capture_output=True,
            text=True,
            check=True,
            cwd=REPO_ROOT,
        )
        assert_matches_golden(res.stdout, SORK_FULL_GOLDEN, "cli_sork_full")

    def test_cli_sork_full_ru(self):
        res = subprocess.run(
            [sys.executable, CLI_SCRIPT, "--lang", "ruRU", SORK_D2S],
            capture_output=True,
            text=True,
            check=True,
            cwd=REPO_ROOT,
        )
        assert_matches_golden(res.stdout, SORK_FULL_RURU_GOLDEN, "cli_sork_full_ru")

    def test_cli_stash_summary(self):
        res = subprocess.run(
            [sys.executable, CLI_SCRIPT, "--summary", STASH_D2I],
            capture_output=True,
            text=True,
            check=True,
            cwd=REPO_ROOT,
        )
        assert_matches_golden(res.stdout, STASH_SUMMARY_GOLDEN, "cli_stash_summary")

    def test_cli_stash_full(self):
        res = subprocess.run(
            [sys.executable, CLI_SCRIPT, STASH_D2I],
            capture_output=True,
            text=True,
            check=True,
            cwd=REPO_ROOT,
        )
        assert_matches_golden(res.stdout, STASH_FULL_GOLDEN, "cli_stash_full")

    def test_cli_stash_full_ru(self):
        res = subprocess.run(
            [sys.executable, CLI_SCRIPT, "--lang", "ruRU", STASH_D2I],
            capture_output=True,
            text=True,
            check=True,
            cwd=REPO_ROOT,
        )
        assert_matches_golden(res.stdout, STASH_FULL_RURU_GOLDEN, "cli_stash_full_ru")

    @pytest.mark.parametrize(("pattern", "golden_path"), STASH_FIND_CASES)
    def test_cli_stash_find_summary(self, pattern, golden_path):
        res = subprocess.run(
            [sys.executable, CLI_SCRIPT, "--summary", "--find", pattern, STASH_D2I],
            capture_output=True,
            text=True,
            check=True,
            cwd=REPO_ROOT,
        )
        assert_matches_golden(res.stdout, golden_path, f"cli_stash_find_{pattern.lower()}_summary")

    @pytest.mark.parametrize(("pattern", "char_path", "golden_path"), CHAR_FIND_CASES)
    def test_cli_char_find_summary(self, pattern, char_path, golden_path):
        res = subprocess.run(
            [sys.executable, CLI_SCRIPT, "--summary", "--find", pattern, char_path],
            capture_output=True,
            text=True,
            check=True,
            cwd=REPO_ROOT,
        )
        assert_matches_golden(res.stdout, golden_path, "cli_char_find_summary")

    def test_cli_multi_file_summary(self):
        res = subprocess.run(
            [sys.executable, CLI_SCRIPT, "--summary", SORK_D2S, STASH_D2I],
            capture_output=True,
            text=True,
            check=True,
            cwd=REPO_ROOT,
        )
        assert f"=== File: {SORK_D2S} ===" in res.stdout
        assert f"=== File: {STASH_D2I} ===" in res.stdout
