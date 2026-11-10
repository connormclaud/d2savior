import importlib.resources
from pathlib import Path

import pytest

from d2savior.core.d2data import GameData, GameDataResolver, VersionData


@pytest.fixture(autouse=True)
def isolate_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate every test from the user's real ~/.config/d2savior/config.toml."""
    fake_config = tmp_path / "d2savior" / "config.toml"
    monkeypatch.setattr("d2savior.config.get_config_path", lambda: fake_config)
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
