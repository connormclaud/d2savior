import shutil
from pathlib import Path
from unittest.mock import patch

from d2savior.cli import (
    COMMANDS,
    cmd_stash,
    main,
)
from d2savior.config import load_save_dir


def test_cmd_stash_from_configured_dir(tmp_path: Path, capsys):
    fixture = Path("tests/fixtures/ModernSharedStashSoftCoreV2.d2i")
    saves_dir = tmp_path / "saves"
    saves_dir.mkdir()
    shutil.copy(fixture, saves_dir / "ModernSharedStashSoftCoreV2.d2i")

    with patch("d2savior.cli.load_save_dir", return_value=saves_dir):
        code = cmd_stash([])
        assert code == 0
        captured = capsys.readouterr()
        assert "=== Diablo II Shared Stash ===" in captured.out
        assert "Total Tabs: 7" in captured.out


def test_cmd_stash_with_explicit_file(capsys):
    fixture = Path("tests/fixtures/ModernSharedStashSoftCoreV2.d2i")
    code = cmd_stash(["--no-config", str(fixture)])
    assert code == 0
    captured = capsys.readouterr()
    assert "=== Diablo II Shared Stash ===" in captured.out
    assert "Total Tabs: 7" in captured.out


def test_cmd_stash_with_summary(capsys):
    fixture = Path("tests/fixtures/ModernSharedStashSoftCoreV2.d2i")
    code = cmd_stash(["--summary", "--no-config", str(fixture)])
    assert code == 0
    captured = capsys.readouterr()
    assert "=== Diablo II Shared Stash Summary ===" in captured.out
    assert "Total Tabs: 7" in captured.out


def test_cmd_stash_skips_character_files(tmp_path: Path, capsys):
    stash_fixture = Path("tests/fixtures/ModernSharedStashSoftCoreV2.d2i")
    char_fixture = Path("tests/fixtures/sork.d2s")
    shutil.copy(stash_fixture, tmp_path / "stash.d2i")
    shutil.copy(char_fixture, tmp_path / "sork.d2s")

    code = cmd_stash(["--no-config", str(tmp_path)])
    assert code == 0
    captured = capsys.readouterr()
    assert "=== Diablo II Shared Stash ===" in captured.out
    assert "=== Diablo II Character ===" not in captured.out
    assert "sork" not in captured.out


def test_cmd_stash_no_stash_files_found(tmp_path: Path, capsys):
    char_fixture = Path("tests/fixtures/sork.d2s")
    shutil.copy(char_fixture, tmp_path / "sork.d2s")

    code = cmd_stash(["--no-config", str(tmp_path)])
    assert code == 1
    captured = capsys.readouterr()
    assert "Error: No .d2i stash files found" in captured.err


def test_cmd_stash_all_stashes_fail_to_parse(tmp_path: Path, capsys):
    corrupt = tmp_path / "corrupt.d2i"
    corrupt.write_bytes(b"invalid data")

    code = cmd_stash(["--no-config", str(corrupt)])
    assert code == 1
    captured = capsys.readouterr()
    assert f"Error: '{corrupt}' contains no parseable stash tabs" in captured.err


def test_cmd_stash_one_good_one_corrupt(tmp_path: Path, capsys):
    fixture = Path("tests/fixtures/ModernSharedStashSoftCoreV2.d2i")
    good = tmp_path / "good.d2i"
    corrupt = tmp_path / "corrupt.d2i"
    shutil.copy(fixture, good)
    corrupt.write_bytes(b"invalid data")

    code = cmd_stash(["--no-config", str(good), str(corrupt)])
    assert code == 1
    captured = capsys.readouterr()
    assert "=== Diablo II Shared Stash ===" in captured.out
    assert f"Error: '{corrupt}' contains no parseable stash tabs" in captured.err


def test_cmd_stash_one_missing_one_corrupt(tmp_path: Path, capsys):
    missing = tmp_path / "missing.d2i"
    corrupt = tmp_path / "corrupt.d2i"
    corrupt.write_bytes(b"invalid data")

    code = cmd_stash(["--no-config", str(missing), str(corrupt)])
    assert code == 1
    captured = capsys.readouterr()
    assert f"Error: File '{missing}' does not exist" in captured.err
    assert f"Error: '{corrupt}' contains no parseable stash tabs" in captured.err


def test_default_command_corrupt_stash_prints_error_and_exits_one(tmp_path: Path, capsys):
    import pytest

    corrupt = tmp_path / "corrupt.d2i"
    corrupt.write_bytes(b"invalid data")

    with pytest.raises(SystemExit) as exc_info:
        main(["--no-config", str(corrupt)])
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert f"Error: '{corrupt}' contains no parseable stash tabs" in captured.err


def test_cmd_stash_missing_file(capsys):
    code = cmd_stash(["--no-config", "nonexistent.d2i"])
    assert code == 1
    captured = capsys.readouterr()
    assert "Error: File 'nonexistent.d2i' does not exist" in captured.err


def test_cmd_stash_explicit_dir_saves_config(tmp_path: Path, capsys):
    cfg_file = tmp_path / "config.toml"
    fixture = Path("tests/fixtures/ModernSharedStashSoftCoreV2.d2i")
    saves_dir = tmp_path / "saves"
    saves_dir.mkdir()
    shutil.copy(fixture, saves_dir / "stash.d2i")

    with patch("d2savior.config.get_config_path", return_value=cfg_file):
        code = cmd_stash([str(saves_dir)])
        assert code == 0
        assert load_save_dir(cfg_file) == saves_dir.resolve()
        captured = capsys.readouterr()
        assert "=== Diablo II Shared Stash ===" in captured.out


def test_cmd_stash_multiple_stashes(tmp_path: Path, capsys):
    fixture = Path("tests/fixtures/ModernSharedStashSoftCoreV2.d2i")
    s1 = tmp_path / "stash1.d2i"
    s2 = tmp_path / "stash2.d2i"
    shutil.copy(fixture, s1)
    shutil.copy(fixture, s2)

    code = cmd_stash(["--no-config", str(tmp_path)])
    assert code == 0
    captured = capsys.readouterr()
    assert f"=== File: {s1} ===" in captured.out
    assert f"=== File: {s2} ===" in captured.out


def test_main_dispatch_stash(capsys):
    fixture = Path("tests/fixtures/ModernSharedStashSoftCoreV2.d2i")
    main(["stash", "--no-config", str(fixture)])
    captured = capsys.readouterr()
    assert "=== Diablo II Shared Stash ===" in captured.out


def test_main_dispatch_stash_with_summary(capsys):
    fixture = Path("tests/fixtures/ModernSharedStashSoftCoreV2.d2i")
    main(["stash", "--summary", "--no-config", str(fixture)])
    captured = capsys.readouterr()
    assert "=== Diablo II Shared Stash Summary ===" in captured.out


def test_main_dispatch_stash_options_after_subcommand(capsys):
    fixture = Path("tests/fixtures/ModernSharedStashSoftCoreV2.d2i")
    main(["stash", "--lang", "enUS", "--no-config", str(fixture)])
    captured = capsys.readouterr()
    assert "=== Diablo II Shared Stash ===" in captured.out


def test_commands_table_and_epilog_in_sync(capsys):
    import pytest

    assert "list" in COMMANDS
    assert "stash" in COMMANDS

    from d2savior.cli import cmd_list, cmd_stash

    assert COMMANDS["list"][0] == cmd_list
    assert COMMANDS["stash"][0] == cmd_stash
    assert "list [path]" in COMMANDS["list"][1]
    assert "stash [path]" in COMMANDS["stash"][1]

    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "Commands:" in captured.out
    assert "list [path]" in captured.out
    assert "stash [path]" in captured.out
