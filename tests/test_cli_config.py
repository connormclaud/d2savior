import shutil
from pathlib import Path
from unittest.mock import patch

import pytest

from d2savior.cli import find_saves_in_dir, main, resolve_target_files
from d2savior.config import load_save_dir


def test_find_saves_in_dir(tmp_path: Path):
    assert find_saves_in_dir(tmp_path) == []

    f_stash = tmp_path / "a_stash.d2i"
    f_char1 = tmp_path / "char1.d2s"
    f_char2 = tmp_path / "char2.D2S"
    f_char_z = tmp_path / "z_char.d2s"
    f_other = tmp_path / "backup.key"
    f_stash.touch()
    f_char1.touch()
    f_char2.touch()
    f_char_z.touch()
    f_other.touch()

    sub = tmp_path / "backup"
    sub.mkdir()
    (sub / "nested.d2s").touch()

    saves = find_saves_in_dir(tmp_path)
    # Characters first (.d2s sorted), then stashes (.d2i sorted)
    assert saves == [str(f_char1), str(f_char2), str(f_char_z), str(f_stash)]


def test_resolve_target_files_no_args_no_config(capsys):
    with patch("d2savior.cli.load_save_dir", return_value=None):
        files, to_save = resolve_target_files([], no_config=False)
        assert files == []
        assert to_save is None
        captured = capsys.readouterr()
        assert "No save path provided and no save directory configured" in captured.err


def test_resolve_target_files_no_args_with_no_config_flag(capsys):
    files, to_save = resolve_target_files([], no_config=True)
    assert files == []
    assert to_save is None
    captured = capsys.readouterr()
    assert "No save path provided and --no-config was specified" in captured.err


def test_resolve_target_files_no_args_with_configured_dir(tmp_path: Path):
    saves_dir = tmp_path / "saves"
    saves_dir.mkdir()
    char1 = saves_dir / "sork.d2s"
    char1.touch()

    with patch("d2savior.cli.load_save_dir", return_value=saves_dir):
        files, to_save = resolve_target_files([], no_config=False)
        assert files == [str(char1)]
        assert to_save is None


def test_resolve_target_files_with_existing_file(tmp_path: Path):
    saves_dir = tmp_path / "saves"
    saves_dir.mkdir()
    char = saves_dir / "sork.d2s"
    char.touch()

    with patch("d2savior.cli.load_save_dir", return_value=None):
        files, to_save = resolve_target_files([str(char)], no_config=False)
        assert files == [str(char)]
        assert to_save == saves_dir.resolve()


def test_resolve_target_files_with_directory(tmp_path: Path):
    saves_dir = tmp_path / "saves"
    saves_dir.mkdir()
    char = saves_dir / "sork.d2s"
    stash = saves_dir / "a_stash.d2i"
    char.touch()
    stash.touch()

    with patch("d2savior.cli.load_save_dir", return_value=None):
        files, to_save = resolve_target_files([str(saves_dir)], no_config=False)
        # Characters first, then stashes
        assert files == [str(char), str(stash)]
        assert to_save == saves_dir.resolve()


def test_resolve_target_files_with_existing_file_when_config_exists(tmp_path: Path):
    configured_dir = tmp_path / "configured"
    configured_dir.mkdir()
    other_dir = tmp_path / "other"
    other_dir.mkdir()
    char = other_dir / "sork.d2s"
    char.touch()

    with patch("d2savior.cli.load_save_dir", return_value=configured_dir):
        files, to_save = resolve_target_files([str(char)], no_config=False)
        assert files == [str(char)]
        assert to_save is None


def test_resolve_target_files_with_directory_when_config_exists(tmp_path: Path):
    configured_dir = tmp_path / "configured"
    configured_dir.mkdir()
    other_dir = tmp_path / "other"
    other_dir.mkdir()
    char = other_dir / "sork.d2s"
    char.touch()

    with patch("d2savior.cli.load_save_dir", return_value=configured_dir):
        files, to_save = resolve_target_files([str(other_dir)], no_config=False)
        assert files == [str(char)]
        assert to_save is None


def test_resolve_target_files_lookup_by_name_in_config(tmp_path: Path):
    saves_dir = tmp_path / "saves"
    saves_dir.mkdir()
    char = saves_dir / "sork.D2S"
    char.touch()

    with patch("d2savior.cli.load_save_dir", return_value=saves_dir):
        # 1. Lookup with exact filename
        files1, _ = resolve_target_files(["sork.D2S"], no_config=False)
        assert files1 == [str(char)]

        # 2. Lookup with stem only
        files2, _ = resolve_target_files(["sork"], no_config=False)
        assert files2 == [str(char)]

        # 3. Lookup case-insensitively
        files3, _ = resolve_target_files(["sork.d2s"], no_config=False)
        assert files3 == [str(char)]


def test_main_stores_directory_into_config(tmp_path: Path):
    cfg_file = tmp_path / "config.toml"
    saves_dir = tmp_path / "saves"
    saves_dir.mkdir()
    char_file = saves_dir / "sork.d2s"
    shutil.copy("tests/fixtures/sork.d2s", char_file)

    with (
        patch("d2savior.config.get_config_path", return_value=cfg_file),
        patch("sys.argv", ["d2savior", "--summary", str(char_file)]),
    ):
        main()
        assert load_save_dir(cfg_file) == saves_dir.resolve()


def test_main_uses_config_to_find_bare_filename(tmp_path: Path):
    cfg_file = tmp_path / "config.toml"
    saves_dir = tmp_path / "saves"
    saves_dir.mkdir()
    char_file = saves_dir / "sork.d2s"
    shutil.copy("tests/fixtures/sork.d2s", char_file)

    from d2savior.config import update_save_dir

    update_save_dir(saves_dir, config_path=cfg_file)

    with (
        patch("d2savior.config.get_config_path", return_value=cfg_file),
        patch("sys.argv", ["d2savior", "--summary", "sork.d2s"]),
        patch("d2savior.cli.process_file") as mock_proc,
    ):
        main()
        mock_proc.assert_called_once()
        assert mock_proc.call_args[0][0] == str(char_file)


def test_main_no_config_flag_bypasses_config(tmp_path: Path):
    cfg_file = tmp_path / "config.toml"
    fixture = Path("tests/fixtures/sork.d2s").resolve()

    with (
        patch("d2savior.config.get_config_path", return_value=cfg_file),
        patch("sys.argv", ["d2savior", "--no-config", "--summary", str(fixture)]),
    ):
        main()
        assert not cfg_file.exists()


def test_main_exits_with_error_code_when_no_config(capsys):
    with (
        patch("d2savior.cli.load_save_dir", return_value=None),
        patch("sys.argv", ["d2savior"]),
        pytest.raises(SystemExit) as exc_info,
    ):
        main()
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "No save path provided and no save directory configured" in captured.err


def test_main_exits_with_error_code_on_missing_file(capsys):
    with (
        patch("d2savior.cli.load_save_dir", return_value=None),
        patch("sys.argv", ["d2savior", "nonexistent_file.d2s"]),
        pytest.raises(SystemExit) as exc_info,
    ):
        main()
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "Error: File 'nonexistent_file.d2s' does not exist" in captured.err


def test_main_does_not_overwrite_existing_config(tmp_path: Path, capsys):
    cfg_file = tmp_path / "config.toml"
    initial_dir = tmp_path / "initial_saves"
    initial_dir.mkdir()
    other_dir = tmp_path / "other_saves"
    other_dir.mkdir()
    char_file = other_dir / "sork.d2s"
    shutil.copy("tests/fixtures/sork.d2s", char_file)

    cfg_file.write_text(f'save_dir = "{initial_dir}"\n', encoding="utf-8")

    with (
        patch("d2savior.config.get_config_path", return_value=cfg_file),
        patch("sys.argv", ["d2savior", "--summary", str(char_file)]),
    ):
        main()
        assert load_save_dir(cfg_file) == initial_dir.resolve()

    captured = capsys.readouterr()
    assert "Saved save_dir" not in captured.err


def test_cmd_list_does_not_overwrite_existing_config(tmp_path: Path, capsys):
    from d2savior.cli import cmd_list

    cfg_file = tmp_path / "config.toml"
    initial_dir = tmp_path / "initial_saves"
    initial_dir.mkdir()
    other_dir = tmp_path / "other_saves"
    other_dir.mkdir()
    char_file = other_dir / "sork.d2s"
    shutil.copy("tests/fixtures/sork.d2s", char_file)

    cfg_file.write_text(f'save_dir = "{initial_dir}"\n', encoding="utf-8")

    with patch("d2savior.config.get_config_path", return_value=cfg_file):
        code = cmd_list([str(other_dir)])
        assert code == 0
        assert load_save_dir(cfg_file) == initial_dir.resolve()

    captured = capsys.readouterr()
    assert "Saved save_dir" not in captured.err


def test_cmd_stash_does_not_overwrite_existing_config(tmp_path: Path, capsys):
    from d2savior.cli import cmd_stash

    cfg_file = tmp_path / "config.toml"
    initial_dir = tmp_path / "initial_saves"
    initial_dir.mkdir()
    other_dir = tmp_path / "other_saves"
    other_dir.mkdir()
    stash_file = other_dir / "ModernSharedStashSoftCoreV2.d2i"
    shutil.copy("tests/fixtures/ModernSharedStashSoftCoreV2.d2i", stash_file)

    cfg_file.write_text(f'save_dir = "{initial_dir}"\n', encoding="utf-8")

    with patch("d2savior.config.get_config_path", return_value=cfg_file):
        code = cmd_stash(["--summary", str(stash_file)])
        assert code == 0
        assert load_save_dir(cfg_file) == initial_dir.resolve()

    captured = capsys.readouterr()
    assert "Saved save_dir" not in captured.err
