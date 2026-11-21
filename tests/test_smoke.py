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
from d2savior.core.constants import DIFFICULTY_NAMES
from d2savior.core.d2s_struct import D2SStruct
from d2savior.core.stash import SharedStash
from d2savior.core.stash_formatter import (
    format_stash_find,
    format_stash_info,
    format_stash_summary,
)
from d2savior.core.stats import get_current_difficulty
from d2savior.optimizer import (
    extract_pool,
    format_build_report,
    format_paladin_leveling_report,
    optimize_builds,
    optimize_paladin_leveling,
    paladin_primary_skill_info,
    select_paladin_max_res_preset,
    select_sorc_presets,
)
from d2savior.optimizer.skill_tables import build_sorc_dps_tables

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
GOLDEN_DIR = os.path.join(FIXTURES_DIR, "golden")

SORK_D2S = os.path.join(FIXTURES_DIR, "sork.d2s")
MULE_UNIQUE_D2S = os.path.join(FIXTURES_DIR, "mule_unique.d2s")
STASH_D2I = os.path.join(FIXTURES_DIR, "ModernSharedStashSoftCoreV2.d2i")
PALADIN_SNAPSHOT_DIR = os.path.join(FIXTURES_DIR, "paladin_snapshot")
SMITE_D2S = os.path.join(PALADIN_SNAPSHOT_DIR, "smite.d2s")
PALADIN_EXTRA_D2S = (
    os.path.join(PALADIN_SNAPSHOT_DIR, "mule_charms.d2s"),
    os.path.join(PALADIN_SNAPSHOT_DIR, "mule_leveling.d2s"),
    os.path.join(PALADIN_SNAPSHOT_DIR, "mule_sets.d2s"),
    os.path.join(PALADIN_SNAPSHOT_DIR, "mule_unique.d2s"),
)
PALADIN_STASH_D2I = os.path.join(PALADIN_SNAPSHOT_DIR, "ModernSharedStashSoftCoreV2.d2i")

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
SORK_OPTIMIZE_GOLDEN = os.path.join(GOLDEN_DIR, "sork_optimize.golden.txt")
SMITE_SUMMARY_GOLDEN = os.path.join(GOLDEN_DIR, "smite_summary.golden.txt")
SMITE_OPTIMIZE_LEVELING_GOLDEN = os.path.join(GOLDEN_DIR, "smite_optimize_leveling.golden.txt")
SMITE_OPTIMIZE_KEEP_GEAR_GOLDEN = os.path.join(GOLDEN_DIR, "smite_optimize_keep_gear.golden.txt")
SMITE_OPTIMIZE_MAX_RES_GOLDEN = os.path.join(GOLDEN_DIR, "smite_optimize_max_res.golden.txt")
SMITE_OPTIMIZE_CBF_FRW30_GOLDEN = os.path.join(GOLDEN_DIR, "smite_optimize_cbf_frw30.golden.txt")

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
        assert isinstance(data, D2SStruct)
        output = format_char_summary(data, resolver=game_data_resolver) + "\n"
        assert_matches_golden(output, SORK_SUMMARY_GOLDEN, "sork_summary_api")

    def test_sork_full(self, game_data_resolver):
        kind, data, _ = parse_file(SORK_D2S, resolver=game_data_resolver)
        assert kind == "char"
        assert isinstance(data, D2SStruct)
        output = format_char_info(data, resolver=game_data_resolver) + "\n"
        assert_matches_golden(output, SORK_FULL_GOLDEN, "sork_full_api")

    def test_stash_summary(self, game_data_resolver):
        kind, data, _ = parse_file(STASH_D2I, resolver=game_data_resolver)
        assert kind == "stash"
        assert isinstance(data, SharedStash)
        output = format_stash_summary(data, resolver=game_data_resolver) + "\n"
        assert_matches_golden(output, STASH_SUMMARY_GOLDEN, "stash_summary_api")

    def test_stash_full(self, game_data_resolver):
        kind, data, _ = parse_file(STASH_D2I, resolver=game_data_resolver)
        assert kind == "stash"
        assert isinstance(data, SharedStash)
        output = format_stash_info(data, resolver=game_data_resolver) + "\n"
        assert_matches_golden(output, STASH_FULL_GOLDEN, "stash_full_api")

    def test_sork_full_ru(self, game_data_resolver_ru):
        kind, data, _ = parse_file(SORK_D2S, resolver=game_data_resolver_ru)
        assert kind == "char"
        assert isinstance(data, D2SStruct)
        output = format_char_info(data, resolver=game_data_resolver_ru) + "\n"
        assert_matches_golden(output, SORK_FULL_RURU_GOLDEN, "sork_full_ru_api")

    def test_stash_full_ru(self, game_data_resolver_ru):
        kind, data, _ = parse_file(STASH_D2I, resolver=game_data_resolver_ru)
        assert kind == "stash"
        assert isinstance(data, SharedStash)
        output = format_stash_info(data, resolver=game_data_resolver_ru) + "\n"
        assert_matches_golden(output, STASH_FULL_RURU_GOLDEN, "stash_full_ru_api")

    @pytest.mark.parametrize(("pattern", "golden_path"), STASH_FIND_CASES)
    def test_stash_find_summary(self, game_data_resolver, pattern, golden_path):
        kind, data, _ = parse_file(STASH_D2I, resolver=game_data_resolver)
        assert kind == "stash"
        assert isinstance(data, SharedStash)
        found = format_stash_find(data, pattern, resolver=game_data_resolver, summary=True)
        assert found is not None
        assert_matches_golden(found + "\n", golden_path, f"stash_find_{pattern.lower()}_api")

    @pytest.mark.parametrize(("pattern", "char_path", "golden_path"), CHAR_FIND_CASES)
    def test_char_find_summary(self, game_data_resolver, pattern, char_path, golden_path):
        kind, data, _ = parse_file(char_path, resolver=game_data_resolver)
        assert kind == "char"
        assert isinstance(data, D2SStruct)
        found = format_char_find(data, pattern, resolver=game_data_resolver, summary=True)
        assert found is not None
        assert_matches_golden(found + "\n", golden_path, "char_find_api")

    def test_sork_optimize(self, game_data_resolver):
        pytest.importorskip("d2savior._native")
        s_kind, sork, _ = parse_file(SORK_D2S, resolver=game_data_resolver)
        m_kind, mule, _ = parse_file(MULE_UNIQUE_D2S, resolver=game_data_resolver)
        st_kind, stash, _ = parse_file(STASH_D2I, resolver=game_data_resolver)
        assert s_kind == "char"
        assert isinstance(sork, D2SStruct)
        assert m_kind == "char"
        assert isinstance(mule, D2SStruct)
        assert st_kind == "stash"
        assert isinstance(stash, SharedStash)

        items, charms = extract_pool(
            sork, extra_chars=[mule], stashes=[stash], resolver=game_data_resolver
        )
        filler_name = build_sorc_dps_tables(sork).filler_skill_name
        diff_name = DIFFICULTY_NAMES[get_current_difficulty(sork)]
        sections = [
            format_build_report(
                title,
                optimize_builds(items, charms, constraints),
                charms,
                diff_name=diff_name,
                filler_skill_name=filler_name,
            )
            for title, constraints in select_sorc_presets(
                sork,
                extra_chars=[mule],
                stashes=[stash],
                resolver=game_data_resolver,
            )
        ]
        output = "\n\n".join(sections) + "\n\n"
        assert_matches_golden(output, SORK_OPTIMIZE_GOLDEN, "sork_optimize_api")

    @staticmethod
    def _load_paladin_snapshot(resolver):
        sm_kind, smite, _ = parse_file(SMITE_D2S, resolver=resolver)
        assert sm_kind == "char"
        assert isinstance(smite, D2SStruct)
        extras: list[D2SStruct] = []
        for path in PALADIN_EXTRA_D2S:
            ex_kind, extra, _ = parse_file(path, resolver=resolver)
            assert ex_kind == "char"
            assert isinstance(extra, D2SStruct)
            extras.append(extra)
        st_kind, stash, _ = parse_file(PALADIN_STASH_D2I, resolver=resolver)
        assert st_kind == "stash"
        assert isinstance(stash, SharedStash)
        return smite, extras, [stash]

    def test_smite_summary(self, game_data_resolver):
        kind, data, _ = parse_file(SMITE_D2S, resolver=game_data_resolver)
        assert kind == "char"
        assert isinstance(data, D2SStruct)
        output = format_char_summary(data, resolver=game_data_resolver) + "\n"
        assert_matches_golden(output, SMITE_SUMMARY_GOLDEN, "smite_summary_api")

    def test_smite_optimize_leveling(self, game_data_resolver):
        pytest.importorskip("d2savior._native")
        smite, extras, stashes = self._load_paladin_snapshot(game_data_resolver)
        items, charms = extract_pool(
            smite, extra_chars=extras, stashes=stashes, resolver=game_data_resolver
        )
        title, options, resolved_spec, diff_name = optimize_paladin_leveling(
            smite,
            items,
            charms,
            extra_chars=extras,
            stashes=stashes,
            resolver=game_data_resolver,
        )
        skill_name, base_skill_lvl = paladin_primary_skill_info(smite, resolved_spec)
        report = format_paladin_leveling_report(
            title,
            options,
            charms,
            diff_name=diff_name,
            primary_skill_name=skill_name,
            primary_skill_base=base_skill_lvl,
            primary_inv_loc="smite Inv",
        )
        assert_matches_golden(
            report + "\n\n", SMITE_OPTIMIZE_LEVELING_GOLDEN, "smite_optimize_leveling_api"
        )

    def test_smite_optimize_keep_gear(self, game_data_resolver):
        pytest.importorskip("d2savior._native")
        smite, extras, stashes = self._load_paladin_snapshot(game_data_resolver)
        items, charms = extract_pool(
            smite,
            extra_chars=extras,
            stashes=stashes,
            resolver=game_data_resolver,
            keep_equipped=True,
        )
        title, options, resolved_spec, diff_name = optimize_paladin_leveling(
            smite,
            items,
            charms,
            max_charm_slots=26,
            extra_chars=extras,
            stashes=stashes,
            resolver=game_data_resolver,
            keep_equipped=True,
        )
        skill_name, base_skill_lvl = paladin_primary_skill_info(smite, resolved_spec)
        report = format_paladin_leveling_report(
            title,
            options,
            charms,
            diff_name=diff_name,
            primary_skill_name=skill_name,
            primary_skill_base=base_skill_lvl,
            primary_inv_loc="smite Inv",
        )
        assert_matches_golden(
            report + "\n\n", SMITE_OPTIMIZE_KEEP_GEAR_GOLDEN, "smite_optimize_keep_gear_api"
        )

    def test_smite_optimize_max_res(self, game_data_resolver):
        pytest.importorskip("d2savior._native")
        smite, extras, stashes = self._load_paladin_snapshot(game_data_resolver)
        items, charms = extract_pool(
            smite, extra_chars=extras, stashes=stashes, resolver=game_data_resolver
        )
        title, constraints, resolved_spec = select_paladin_max_res_preset(
            smite,
            extra_chars=extras,
            stashes=stashes,
            resolver=game_data_resolver,
        )
        diff_name = DIFFICULTY_NAMES[get_current_difficulty(smite)]
        skill_name, base_skill_lvl = paladin_primary_skill_info(smite, resolved_spec)
        report = format_build_report(
            title,
            optimize_builds(items, charms, constraints),
            charms,
            char_class=smite.char_class,
            diff_name=diff_name,
            primary_skill_name=skill_name,
            primary_skill_base=base_skill_lvl,
            primary_inv_loc="smite Inv",
        )
        assert_matches_golden(
            report + "\n\n", SMITE_OPTIMIZE_MAX_RES_GOLDEN, "smite_optimize_max_res_api"
        )

    def test_smite_optimize_cbf_frw30(self, game_data_resolver):
        """Leveling optimize with --cbf and --min-frw 30: every option must satisfy both floors."""
        pytest.importorskip("d2savior._native")
        from d2savior.optimizer import ConstraintOverrides

        smite, extras, stashes = self._load_paladin_snapshot(game_data_resolver)
        items, charms = extract_pool(
            smite, extra_chars=extras, stashes=stashes, resolver=game_data_resolver
        )
        overrides = ConstraintOverrides(require_cbf=True, min_frw=30)
        title, options, resolved_spec, diff_name = optimize_paladin_leveling(
            smite,
            items,
            charms,
            extra_chars=extras,
            stashes=stashes,
            resolver=game_data_resolver,
            overrides=overrides,
        )
        # Every returned option must satisfy the floors.
        for _label, res in options:
            assert res.cbf, "CBF floor violated"
            assert res.frw >= 30, f"FRW floor violated: {res.frw} < 30"
        skill_name, base_skill_lvl = paladin_primary_skill_info(smite, resolved_spec)
        report = format_paladin_leveling_report(
            title,
            options,
            charms,
            diff_name=diff_name,
            primary_skill_name=skill_name,
            primary_skill_base=base_skill_lvl,
            primary_inv_loc="smite Inv",
        )
        assert_matches_golden(
            report + "\n\n", SMITE_OPTIMIZE_CBF_FRW30_GOLDEN, "smite_optimize_cbf_frw30_api"
        )


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

    def test_cli_sork_optimize(self):
        pytest.importorskip("d2savior._native")
        res = subprocess.run(
            [
                sys.executable,
                CLI_SCRIPT,
                "optimize",
                "--no-config",
                SORK_D2S,
                MULE_UNIQUE_D2S,
                STASH_D2I,
            ],
            capture_output=True,
            text=True,
            check=True,
            cwd=REPO_ROOT,
        )
        assert_matches_golden(res.stdout, SORK_OPTIMIZE_GOLDEN, "cli_sork_optimize")

    def test_cli_smite_summary(self):
        res = subprocess.run(
            [sys.executable, CLI_SCRIPT, "--summary", SMITE_D2S],
            capture_output=True,
            text=True,
            check=True,
            cwd=REPO_ROOT,
        )
        assert_matches_golden(res.stdout, SMITE_SUMMARY_GOLDEN, "cli_smite_summary")

    @pytest.mark.parametrize(
        ("extra_args", "golden_path", "case_name"),
        [
            (["-b", "leveling"], SMITE_OPTIMIZE_LEVELING_GOLDEN, "cli_smite_optimize_leveling"),
            (
                ["--keep-gear", "--charm-slots", "26"],
                SMITE_OPTIMIZE_KEEP_GEAR_GOLDEN,
                "cli_smite_optimize_keep_gear",
            ),
            (["-b", "max-res"], SMITE_OPTIMIZE_MAX_RES_GOLDEN, "cli_smite_optimize_max_res"),
            (
                ["--cbf", "--min-frw", "30"],
                SMITE_OPTIMIZE_CBF_FRW30_GOLDEN,
                "cli_smite_optimize_cbf_frw30",
            ),
        ],
    )
    def test_cli_smite_optimize(self, extra_args, golden_path, case_name):
        pytest.importorskip("d2savior._native")
        res = subprocess.run(
            [
                sys.executable,
                CLI_SCRIPT,
                "optimize",
                "--no-config",
                *extra_args,
                "smite",
                PALADIN_SNAPSHOT_DIR,
            ],
            capture_output=True,
            text=True,
            check=True,
            cwd=REPO_ROOT,
        )
        assert_matches_golden(res.stdout, golden_path, case_name)

    def test_cli_list_builds(self):
        """--list-builds prints all built-in presets without requiring a save file."""
        res = subprocess.run(
            [sys.executable, CLI_SCRIPT, "optimize", "--list-builds", "--no-config"],
            capture_output=True,
            text=True,
            check=True,
            cwd=REPO_ROOT,
        )
        for name in ("base", "tz", "mf", "mf-speed", "mf-pure", "max-res", "leveling"):
            assert name in res.stdout, f"preset '{name}' missing from --list-builds output"
