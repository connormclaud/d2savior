from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolate_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate every test from the user's real ~/.config/d2savior/config.toml."""
    fake_config = tmp_path / "d2savior" / "config.toml"
    monkeypatch.setattr("d2savior.config.get_config_path", lambda: fake_config)
    return fake_config
