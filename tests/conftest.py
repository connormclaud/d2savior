import importlib.resources
import sys
from pathlib import Path

import pytest

from d2savior import load_d2i, load_d2s
from d2savior.core.d2s_struct import D2SStruct
from d2savior.core.loader import GameData
from d2savior.core.models import VersionData
from d2savior.core.resolver import GameDataResolver
from d2savior.core.stash import SharedStash

FIXTURES_DIR = Path(__file__).parent / "fixtures"
PALADIN_SNAPSHOT_DIR = FIXTURES_DIR / "paladin_snapshot"


@pytest.fixture(autouse=True)
def isolate_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate every test from the user's real ~/.config/d2savior/ (config.toml and presets/)."""
    fake_config = tmp_path / "d2savior" / "config.toml"
    monkeypatch.setattr("d2savior.config.get_config_path", lambda: fake_config)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    if sys.platform == "win32":
        monkeypatch.setenv("APPDATA", str(tmp_path))
    return fake_config


@pytest.fixture(scope="session")
def game_data() -> GameData:
    data_dir = str(importlib.resources.files("d2savior").joinpath("data"))
    return GameData.load(data_dir)


@pytest.fixture(scope="session")
def version_data_63(game_data: GameData) -> VersionData:
    return game_data.for_version(0x63)


@pytest.fixture(scope="session")
def version_data_69(game_data: GameData) -> VersionData:
    return game_data.for_version(0x69)


@pytest.fixture(scope="session")
def game_data_resolver() -> GameDataResolver:
    return GameDataResolver.load(lang_key="enUS")


@pytest.fixture(scope="session")
def game_data_resolver_ru() -> GameDataResolver:
    return GameDataResolver.load(lang_key="ruRU")


@pytest.fixture(scope="session")
def parsed_sork(game_data_resolver: GameDataResolver) -> D2SStruct:
    char_data, _ = load_d2s(FIXTURES_DIR / "sork.d2s", resolver=game_data_resolver)
    return char_data


@pytest.fixture(scope="session")
def parsed_mule_unique(game_data_resolver: GameDataResolver) -> D2SStruct:
    char_data, _ = load_d2s(FIXTURES_DIR / "mule_unique.d2s", resolver=game_data_resolver)
    return char_data


@pytest.fixture(scope="session")
def parsed_shared_stash(game_data_resolver: GameDataResolver) -> SharedStash:
    stash, kind, _ = load_d2i(
        FIXTURES_DIR / "ModernSharedStashSoftCoreV2.d2i", resolver=game_data_resolver
    )
    assert kind == "stash"
    assert isinstance(stash, SharedStash)
    return stash


@pytest.fixture(scope="session")
def parsed_paladin_smite(game_data_resolver: GameDataResolver) -> D2SStruct:
    char_data, _ = load_d2s(PALADIN_SNAPSHOT_DIR / "smite.d2s", resolver=game_data_resolver)
    return char_data


@pytest.fixture(scope="session")
def parsed_paladin_mule_sets(game_data_resolver: GameDataResolver) -> D2SStruct:
    char_data, _ = load_d2s(PALADIN_SNAPSHOT_DIR / "mule_sets.d2s", resolver=game_data_resolver)
    return char_data


@pytest.fixture(scope="session")
def parsed_paladin_stash(game_data_resolver: GameDataResolver) -> SharedStash:
    stash, kind, _ = load_d2i(
        PALADIN_SNAPSHOT_DIR / "ModernSharedStashSoftCoreV2.d2i", resolver=game_data_resolver
    )
    assert kind == "stash"
    assert isinstance(stash, SharedStash)
    return stash


@pytest.fixture(scope="session")
def parsed_paladin_extra_chars(game_data_resolver: GameDataResolver) -> list[D2SStruct]:
    return [
        load_d2s(p, resolver=game_data_resolver)[0]
        for p in sorted(PALADIN_SNAPSHOT_DIR.glob("*.d2s"))
        if p.name != "smite.d2s"
    ]
