from pathlib import Path

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
