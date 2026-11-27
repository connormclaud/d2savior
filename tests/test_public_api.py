from pathlib import Path

import pytest

import d2savior
from d2savior import (
    D2Item,
    D2SStruct,
    GameDataResolver,
    IBitStream,
    OBitStream,
    SharedStash,
    format_char_summary,
    format_stash_summary,
    load_d2i,
    load_d2s,
)


def test_public_api_exports_complete():
    for name in d2savior.__all__:
        assert hasattr(d2savior, name)
    assert isinstance(d2savior.__version__, str)


def test_public_api_parse_character(game_data_resolver: GameDataResolver):
    char = D2SStruct()
    char.deserialize(
        IBitStream(Path("tests/fixtures/sork.d2s").read_bytes()), data=game_data_resolver
    )
    assert char.get_char_name() == "sork"
    summary = format_char_summary(char, resolver=game_data_resolver)
    assert "Sorceress" in summary


def test_public_api_parse_stash(game_data_resolver: GameDataResolver):
    stash = SharedStash()
    stash.deserialize(
        IBitStream(Path("tests/fixtures/ModernSharedStashSoftCoreV2.d2i").read_bytes()),
        data=game_data_resolver,
    )
    assert stash.get_tab_count() > 0
    summary = format_stash_summary(stash, resolver=game_data_resolver)
    assert "Shared Stash Summary" in summary


def test_public_api_parse_item_with_resolver(game_data_resolver: GameDataResolver):
    stash = SharedStash()
    stash.deserialize(
        IBitStream(Path("tests/fixtures/ModernSharedStashSoftCoreV2.d2i").read_bytes()),
        data=game_data_resolver,
    )
    tab_item = stash.get_tab_items(2)[0]

    out = OBitStream()
    tab_item.serialize(out, version=tab_item.version, data=game_data_resolver)

    reparsed = D2Item()
    reparsed.deserialize(
        IBitStream(out.get_data()), version=tab_item.version, data=game_data_resolver
    )
    assert reparsed.code_str == tab_item.code_str


def test_load_d2s_and_load_d2i_pure_loaders(tmp_path: Path, game_data_resolver: GameDataResolver):
    char_data, char_bs = load_d2s("tests/fixtures/sork.d2s", resolver=game_data_resolver)
    assert isinstance(char_data, D2SStruct)
    assert char_data.get_char_name() == "sork"
    assert len(char_bs) > 0

    stash_data, kind, stash_bs = load_d2i(
        "tests/fixtures/ModernSharedStashSoftCoreV2.d2i", resolver=game_data_resolver
    )
    assert kind == "stash"
    assert isinstance(stash_data, SharedStash)
    assert stash_data.get_tab_count() > 0
    assert len(stash_bs) > 0

    tab_item = stash_data.get_tab_items(2)[0]
    out = OBitStream()
    tab_item.serialize(out, version=tab_item.version, data=game_data_resolver)
    item_path = tmp_path / "single.d2i"
    item_path.write_bytes(out.get_data())

    item_data, item_kind, _ = load_d2i(item_path, resolver=game_data_resolver)
    assert item_kind == "item"
    assert isinstance(item_data, D2Item)
    assert item_data.code_str == tab_item.code_str

    with pytest.raises(FileNotFoundError):
        load_d2s(tmp_path / "missing.d2s", resolver=game_data_resolver)

    corrupt_stash = tmp_path / "empty_stash.d2i"
    corrupt_stash.write_bytes(b"invalid data")
    with pytest.raises(ValueError, match="contains no parseable stash tabs"):
        load_d2i(corrupt_stash, resolver=game_data_resolver)


def test_cli_optimize_decoupled_from_cli_and_private_actions():
    import ast

    source = Path("d2savior/cli_optimize.py").read_text(encoding="utf-8")
    assert "_actions" not in source

    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("d2savior.cli") or alias.name.startswith(
                    "d2savior.cli_common"
                )
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            assert node.module != "d2savior.cli"
            if node.module == "d2savior":
                assert all(alias.name != "cli" for alias in node.names)
