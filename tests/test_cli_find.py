from pathlib import Path

from d2savior.cli import cmd_stash, main, parse_d2i_file, parse_d2s_file
from d2savior.core.char_formatter import format_char_find
from d2savior.core.item_formatter import item_matches_pattern
from d2savior.core.resolver import GameDataResolver
from d2savior.core.stash_formatter import format_stash_find


def test_item_matches_pattern(game_data_resolver: GameDataResolver):
    stash_fixture = Path("tests/fixtures/ModernSharedStashSoftCoreV2.d2i")
    ok, stash, _kind, _ = parse_d2i_file(str(stash_fixture), resolver=game_data_resolver)
    assert ok
    assert stash is not None
    tab3 = stash.tabs[2]

    # Find Horazon's Hold item in tab 3
    horazon = None
    for it in tab3.items.items:
        if item_matches_pattern(it, "Horazon's Hold", resolver=game_data_resolver):
            horazon = it
            break

    assert horazon is not None
    # Case-insensitive substring on unique name
    assert item_matches_pattern(horazon, "hold", resolver=game_data_resolver)
    assert item_matches_pattern(horazon, "HORAZON", resolver=game_data_resolver)
    # Case-insensitive substring on base type
    assert item_matches_pattern(horazon, "demonhide", resolver=game_data_resolver)
    assert item_matches_pattern(horazon, "gloves", resolver=game_data_resolver)
    # Non-match
    assert not item_matches_pattern(horazon, "crystal sword", resolver=game_data_resolver)


def test_socketed_item_matches_pattern(game_data_resolver: GameDataResolver):
    char_fixture = Path("tests/fixtures/sork.d2s")
    ok, char_data, _ = parse_d2s_file(str(char_fixture), resolver=game_data_resolver)
    assert ok
    assert char_data is not None

    # Lore (Cap) contains Ort Rune and Sol Rune
    lore_item = None
    for it in char_data.item_list.items:
        if it.position == 1:  # Helmet
            lore_item = it
            break

    assert lore_item is not None
    assert item_matches_pattern(lore_item, "Lore", resolver=game_data_resolver)
    assert item_matches_pattern(lore_item, "Cap", resolver=game_data_resolver)
    assert item_matches_pattern(lore_item, "Ort Rune", resolver=game_data_resolver)
    assert item_matches_pattern(lore_item, "Sol Rune", resolver=game_data_resolver)


def test_format_char_find_summary(game_data_resolver: GameDataResolver):
    char_fixture = Path("tests/fixtures/sork.d2s")
    ok, char_data, _ = parse_d2s_file(str(char_fixture), resolver=game_data_resolver)
    assert ok
    assert char_data is not None

    out = format_char_find(char_data, "Tal Rasha", resolver=game_data_resolver, summary=True)
    assert out is not None
    assert "=== Diablo II Character Summary: sork" in out
    assert "=== Mercenary ===" in out
    assert "Tal Rasha's Horadric Crest" in out
    assert "=== Inventory & Stash ===" in out
    assert "Tal Rasha's Fine-Spun Cloth" in out
    assert "Tal Rasha's Lidless Eye" in out
    # Skills and waypoints shouldn't be present
    assert "=== Skills ===" not in out
    assert "=== Waypoints ===" not in out


def test_format_char_find_detailed(game_data_resolver: GameDataResolver):
    char_fixture = Path("tests/fixtures/sork.d2s")
    ok, char_data, _ = parse_d2s_file(str(char_fixture), resolver=game_data_resolver)
    assert ok
    assert char_data is not None

    out = format_char_find(char_data, "Visceratuant", resolver=game_data_resolver, summary=False)
    assert out is not None
    assert "=== Diablo II Character Info: sork" in out
    assert "=== Equipped Gear ===" in out
    assert "--- Equipped: Shield I ---" in out
    assert "Defender" in out
    assert "Visceratuant" in out


def test_format_char_find_no_match(game_data_resolver: GameDataResolver):
    char_fixture = Path("tests/fixtures/sork.d2s")
    ok, char_data, _ = parse_d2s_file(str(char_fixture), resolver=game_data_resolver)
    assert ok
    assert char_data is not None

    out = format_char_find(char_data, "nonexistent_item", resolver=game_data_resolver, summary=True)
    assert out is None


def test_format_stash_find_summary(game_data_resolver: GameDataResolver):
    stash_fixture = Path("tests/fixtures/ModernSharedStashSoftCoreV2.d2i")
    ok, stash, _kind, _ = parse_d2i_file(str(stash_fixture), resolver=game_data_resolver)
    assert ok
    assert stash is not None

    out = format_stash_find(stash, "hold", resolver=game_data_resolver, summary=True)
    assert out is not None
    assert "=== Diablo II Shared Stash Summary ===" in out
    assert "=== Tab 3 (Normal) ===" in out
    assert "Horazon's Hold (Demonhide Gloves) [Def: 30]" in out
    assert "+11 to Dexterity, +35 to Life" in out
    # Tabs without matches shouldn't be listed
    assert "=== Tab 1 (" not in out
    assert "=== Tab 2 (" not in out


def test_format_stash_find_detailed(game_data_resolver: GameDataResolver):
    stash_fixture = Path("tests/fixtures/ModernSharedStashSoftCoreV2.d2i")
    ok, stash, _kind, _ = parse_d2i_file(str(stash_fixture), resolver=game_data_resolver)
    assert ok
    assert stash is not None

    out = format_stash_find(stash, "hold", resolver=game_data_resolver, summary=False)
    assert out is not None
    assert "=== Diablo II Shared Stash ===" in out
    assert "=== Tab 3 (Normal) ===" in out
    assert "--- Item 0 ---" in out
    assert "Type: xlg  (Demonhide Gloves)" in out


def test_cli_find_single_file_summary(capsys):
    stash_fixture = "tests/fixtures/ModernSharedStashSoftCoreV2.d2i"
    main(["--no-config", "--find", "hold", "--summary", stash_fixture])
    captured = capsys.readouterr()
    assert "=== Diablo II Shared Stash Summary ===" in captured.out
    assert "=== Tab 3 (Normal) ===" in captured.out
    assert "Horazon's Hold (Demonhide Gloves)" in captured.out
    # Single file should not have the "=== File: ... ===" header
    assert "=== File:" not in captured.out


def test_cli_find_multi_file_suppression(capsys):
    char_fixture = "tests/fixtures/sork.d2s"
    stash_fixture = "tests/fixtures/ModernSharedStashSoftCoreV2.d2i"
    # sork has no "hold", stash has "hold"
    main(["--no-config", "-f", "hold", "--summary", char_fixture, stash_fixture])
    captured = capsys.readouterr()
    # Stash file header printed because multi-file
    assert f"=== File: {stash_fixture} ===" in captured.out
    assert "Horazon's Hold (Demonhide Gloves)" in captured.out
    # sork has no match, so its header should be completely suppressed
    assert f"=== File: {char_fixture} ===" not in captured.out
    assert "sork" not in captured.out


def test_cli_find_no_matches_message(capsys):
    char_fixture = "tests/fixtures/sork.d2s"
    stash_fixture = "tests/fixtures/ModernSharedStashSoftCoreV2.d2i"
    main(["--no-config", "--find", "super_rare_unobtainable_xyz", char_fixture, stash_fixture])
    captured = capsys.readouterr()
    assert captured.out == "No matching items found\n"


def test_cmd_stash_find(capsys):
    stash_fixture = "tests/fixtures/ModernSharedStashSoftCoreV2.d2i"
    code = cmd_stash(["--no-config", "--find", "hold", "--summary", stash_fixture])
    assert code == 0
    captured = capsys.readouterr()
    assert "=== Diablo II Shared Stash Summary ===" in captured.out
    assert "=== Tab 3 (Normal) ===" in captured.out
    assert "Horazon's Hold (Demonhide Gloves)" in captured.out
