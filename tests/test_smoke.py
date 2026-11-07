import difflib
import os
import subprocess
import sys

import pytest

from d2s_parse import FORMATTERS, parse_file
from d2savior.core.formatters import ensure_data_loaded

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
GOLDEN_DIR = os.path.join(FIXTURES_DIR, "golden")

SORK_D2S = os.path.join(FIXTURES_DIR, "sork.d2s")
STASH_D2I = os.path.join(FIXTURES_DIR, "ModernSharedStashSoftCoreV2.d2i")

SORK_SUMMARY_GOLDEN = os.path.join(GOLDEN_DIR, "sork_summary.golden.txt")
SORK_FULL_GOLDEN = os.path.join(GOLDEN_DIR, "sork_full.golden.txt")
STASH_SUMMARY_GOLDEN = os.path.join(GOLDEN_DIR, "stash_summary.golden.txt")
STASH_FULL_GOLDEN = os.path.join(GOLDEN_DIR, "stash_full.golden.txt")

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


@pytest.fixture(scope="module", autouse=True)
def load_game_data():
    ensure_data_loaded(lang_key="enUS")


class TestSmokeAPI:
    """Smoke tests validating parsing and formatting via direct API calls."""

    def test_sork_summary(self):
        kind, data, _ = parse_file(SORK_D2S)
        assert kind == "char"
        assert data is not None
        output = FORMATTERS[(kind, True)](data) + "\n"
        assert_matches_golden(output, SORK_SUMMARY_GOLDEN, "sork_summary_api")

    def test_sork_full(self):
        kind, data, _ = parse_file(SORK_D2S)
        assert kind == "char"
        assert data is not None
        output = FORMATTERS[(kind, False)](data) + "\n"
        assert_matches_golden(output, SORK_FULL_GOLDEN, "sork_full_api")

    def test_stash_summary(self):
        kind, data, _ = parse_file(STASH_D2I)
        assert kind == "stash"
        assert data is not None
        output = FORMATTERS[(kind, True)](data) + "\n"
        assert_matches_golden(output, STASH_SUMMARY_GOLDEN, "stash_summary_api")

    def test_stash_full(self):
        kind, data, _ = parse_file(STASH_D2I)
        assert kind == "stash"
        assert data is not None
        output = FORMATTERS[(kind, False)](data) + "\n"
        assert_matches_golden(output, STASH_FULL_GOLDEN, "stash_full_api")


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
