import os
import shutil
import struct
from pathlib import Path
from unittest.mock import patch

from d2savior.cli import (
    cmd_list,
    format_char_list,
    list_characters,
    main,
)
from d2savior.config import load_save_dir


def _create_test_char(
    base_fixture: Path,
    dest_path: Path,
    name: str,
    save_time: int,
    level: int = 74,
    char_class: int = 1,
    hardcore: bool = False,
) -> None:
    data = bytearray(base_fixture.read_bytes())
    old_name = b"sork\x00"
    new_name_bytes = (name.encode("utf-8") + b"\x00").ljust(len(old_name), b"\x00")
    pos = data.find(b"sork")
    data[pos : pos + len(new_name_bytes)] = new_name_bytes
    data[0x18] = char_class
    data[0x1B] = level
    data[0x20:0x24] = struct.pack("<I", save_time)
    if hardcore:
        data[0x14] |= 0x04  # CharStatus.HARDCORE
    else:
        data[0x14] &= ~0x04
    dest_path.write_bytes(data)


def test_format_char_list_empty():
    assert format_char_list([]) == ""


def test_format_char_list_formatting():
    records = [
        {
            "name": "sork",
            "class": "Sorceress",
            "level": 74,
            "mode": "Softcore",
            "last_played": "2026-11-06 17:31:34 UTC",
        },
        {
            "name": "hammerdin",
            "class": "Paladin",
            "level": 99,
            "mode": "Hardcore",
            "last_played": "2026-11-05 10:15:00 UTC",
        },
    ]
    output = format_char_list(records)
    lines = output.splitlines()
    assert len(lines) == 3

    # Check header
    header = lines[0]
    assert "NAME" in header
    assert "CLASS" in header
    assert "LEVEL" in header
    assert "MODE" in header
    assert "LAST PLAYED" in header

    # Ensure no trailing whitespace on lines
    for line in lines:
        assert line == line.rstrip()

    # Check rows
    assert "sork" in lines[1]
    assert "Sorceress" in lines[1]
    assert "Softcore" in lines[1]
    assert "hammerdin" in lines[2]
    assert "Paladin" in lines[2]
    assert "Hardcore" in lines[2]


def test_list_characters_sorting(tmp_path: Path):
    fixture = Path("tests/fixtures/sork.d2s")
    c1 = tmp_path / "char_old.d2s"
    c2 = tmp_path / "char_new.d2s"
    c3 = tmp_path / "char_mid.d2s"

    _create_test_char(fixture, c1, "oldie", save_time=1000)
    _create_test_char(fixture, c2, "newbie", save_time=3000)
    _create_test_char(fixture, c3, "middie", save_time=2000)

    # Pass in arbitrary order
    records = list_characters([str(c1), str(c2), str(c3)])
    names = [r["name"] for r in records]
    assert names == ["newbie", "middie", "oldie"]


def test_list_characters_sorting_same_timestamp_alphabetical(tmp_path: Path):
    fixture = Path("tests/fixtures/sork.d2s")
    c_bob = tmp_path / "bob.d2s"
    c_alice = tmp_path / "alice.d2s"

    _create_test_char(fixture, c_bob, "bob", save_time=1000)
    _create_test_char(fixture, c_alice, "alice", save_time=1000)

    records = list_characters([str(c_bob), str(c_alice)])
    names = [r["name"] for r in records]
    assert names == ["alice", "bob"]


def test_list_characters_fallback_to_mtime(tmp_path: Path):
    fixture = Path("tests/fixtures/sork.d2s")
    c = tmp_path / "fallback.d2s"
    _create_test_char(fixture, c, "fallbk", save_time=0)
    os.utime(c, (1700000000, 1700000000))

    records = list_characters([str(c)])
    assert len(records) == 1
    assert records[0]["sort_ts"] == 1700000000
    assert "1700000000" not in records[0]["last_played"]
    assert "2023-11-14" in records[0]["last_played"]


def test_list_characters_fallback_to_mtime_when_ffffffff(tmp_path: Path):
    fixture = Path("tests/fixtures/sork.d2s")
    c = tmp_path / "fallback_ffff.d2s"
    _create_test_char(fixture, c, "fallbk", save_time=0xFFFFFFFF)
    os.utime(c, (1700000000, 1700000000))

    records = list_characters([str(c)])
    assert len(records) == 1
    assert records[0]["sort_ts"] == 1700000000
    assert records[0]["sort_ts"] != 0xFFFFFFFF
    assert "2023-11-14" in records[0]["last_played"]


def test_cmd_list_skips_stashes(tmp_path: Path, capsys):
    fixture = Path("tests/fixtures/sork.d2s")
    c = tmp_path / "sork.d2s"
    stash = tmp_path / "stash.d2i"
    shutil.copy(fixture, c)
    stash.touch()

    code = cmd_list(["--no-config", str(tmp_path)])
    assert code == 0
    captured = capsys.readouterr()
    assert "sork" in captured.out
    assert "stash" not in captured.out


def test_cmd_list_all_chars_fail_to_parse(tmp_path: Path, capsys):
    corrupt = tmp_path / "corrupt.d2s"
    corrupt.write_bytes(b"invalid data")

    code = cmd_list(["--no-config", str(corrupt)])
    assert code == 1
    captured = capsys.readouterr()
    assert "Error: No characters could be parsed" in captured.err


def test_cmd_list_from_configured_dir(tmp_path: Path, capsys):
    fixture = Path("tests/fixtures/sork.d2s")
    saves_dir = tmp_path / "saves"
    saves_dir.mkdir()
    c = saves_dir / "sork.d2s"
    shutil.copy(fixture, c)

    with patch("d2savior.cli.load_save_dir", return_value=saves_dir):
        code = cmd_list([])
        assert code == 0
        captured = capsys.readouterr()
        assert "NAME" in captured.out
        assert "sork" in captured.out
        assert "Sorceress" in captured.out


def test_cmd_list_explicit_dir_saves_config(tmp_path: Path, capsys):
    cfg_file = tmp_path / "config.toml"
    fixture = Path("tests/fixtures/sork.d2s")
    saves_dir = tmp_path / "saves"
    saves_dir.mkdir()
    c = saves_dir / "sork.d2s"
    shutil.copy(fixture, c)

    with patch("d2savior.config.get_config_path", return_value=cfg_file):
        code = cmd_list([str(saves_dir)])
        assert code == 0
        assert load_save_dir(cfg_file) == saves_dir.resolve()
        captured = capsys.readouterr()
        assert "sork" in captured.out


def test_cmd_list_no_config_flag(tmp_path: Path):
    cfg_file = tmp_path / "config.toml"
    fixture = Path("tests/fixtures/sork.d2s")
    saves_dir = tmp_path / "saves"
    saves_dir.mkdir()
    c = saves_dir / "sork.d2s"
    shutil.copy(fixture, c)

    with patch("d2savior.config.get_config_path", return_value=cfg_file):
        code = cmd_list(["--no-config", str(saves_dir)])
        assert code == 0
        assert not cfg_file.exists()


def test_cmd_list_no_chars_found_only_stashes(tmp_path: Path, capsys):
    saves_dir = tmp_path / "saves"
    saves_dir.mkdir()
    (saves_dir / "stash.d2i").touch()

    with patch("d2savior.cli.load_save_dir", return_value=saves_dir):
        code = cmd_list([])
        assert code == 1
        captured = capsys.readouterr()
        assert "No .d2s character files found" in captured.err


def test_cmd_list_empty_dir(tmp_path: Path, capsys):
    saves_dir = tmp_path / "saves"
    saves_dir.mkdir()

    with patch("d2savior.cli.load_save_dir", return_value=saves_dir):
        code = cmd_list([])
        assert code == 1
        captured = capsys.readouterr()
        assert "No .d2s or .d2i files found" in captured.err


def test_main_dispatch_list_subcommand(tmp_path: Path, capsys):
    fixture = Path("tests/fixtures/sork.d2s")
    c = tmp_path / "sork.d2s"
    shutil.copy(fixture, c)

    with (
        patch("d2savior.cli.load_save_dir", return_value=tmp_path),
        patch("sys.argv", ["d2savior", "list"]),
    ):
        main()
        captured = capsys.readouterr()
        assert "NAME" in captured.out
        assert "sork" in captured.out


def test_main_dispatch_list_with_args(tmp_path: Path, capsys):
    fixture = Path("tests/fixtures/sork.d2s")
    c = tmp_path / "sork.d2s"
    shutil.copy(fixture, c)

    main(["list", "--no-config", str(c)])
    captured = capsys.readouterr()
    assert "NAME" in captured.out
    assert "sork" in captured.out


def test_main_dispatch_list_options_after_subcommand(tmp_path: Path, capsys):
    fixture = Path("tests/fixtures/sork.d2s")
    c = tmp_path / "sork.d2s"
    shutil.copy(fixture, c)

    main(["list", "--lang", "enUS", "--no-config", str(c)])
    captured = capsys.readouterr()
    assert "NAME" in captured.out
    assert "sork" in captured.out
    assert "Sorceress" in captured.out


def test_main_character_named_list(tmp_path: Path, capsys):
    fixture = Path("tests/fixtures/sork.d2s")
    c = tmp_path / "list.d2s"
    shutil.copy(fixture, c)

    # Should run normal parse rather than list subcommand
    main(["--summary", "--no-config", str(c)])
    captured = capsys.readouterr()
    assert "=== Diablo II Character Summary ===" in captured.out
