"""Pure save (.d2s) and shared stash / item (.d2i) file loaders."""

import struct
from pathlib import Path

from d2savior.core.d2s_struct import D2SStruct
from d2savior.core.ibitstream import IBitStream
from d2savior.core.item import D2Item
from d2savior.core.resolver import GameDataResolver
from d2savior.core.stash import SharedStash

PARSE_ERRORS = (OSError, ValueError, LookupError, EOFError, struct.error)


class EmptyStashError(ValueError):
    """Raised when a shared stash file contains no parseable tabs."""


type ParsedData = D2SStruct | SharedStash | D2Item


def load_d2s(
    file_path: str | Path, resolver: GameDataResolver | None = None
) -> tuple[D2SStruct, IBitStream]:
    """Load and deserialize a `.d2s` character save file."""
    if resolver is None:
        resolver = GameDataResolver.load()
    with open(file_path, "rb") as f:
        data = f.read()
    bs = IBitStream(data)
    char_data = D2SStruct()
    char_data.deserialize(bs, data=resolver)
    return char_data, bs


def load_d2i(
    file_path: str | Path, resolver: GameDataResolver | None = None
) -> tuple[SharedStash | D2Item, str, IBitStream]:
    """Load and deserialize a `.d2i` item (`\"item\"`) or shared stash (`\"stash\"`) file."""
    if resolver is None:
        resolver = GameDataResolver.load()
    with open(file_path, "rb") as f:
        data = f.read()
    bs = IBitStream(data)
    if data.startswith(b"JM"):
        item = D2Item()
        item.deserialize(bs, data=resolver.game_data)
        return item, "item", bs

    stash = SharedStash()
    stash.deserialize(bs, data=resolver)
    if not stash.tabs:
        raise EmptyStashError(f"'{file_path}' contains no parseable stash tabs")
    return stash, "stash", bs
