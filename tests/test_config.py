from pathlib import Path

from d2savior.config import get_config_path, get_presets_dir, load_save_dir, update_save_dir


def test_get_config_path():
    cfg_path = get_config_path()
    assert isinstance(cfg_path, Path)
    assert cfg_path.name == "config.toml"


def test_get_presets_dir_tracks_config_path_and_is_isolated(tmp_path: Path):
    import d2savior.config as config_mod
    from d2savior.optimizer.presets import list_presets, resolve_build_expr

    cfg_path = config_mod.get_config_path()
    presets_dir = get_presets_dir()
    assert cfg_path.is_relative_to(tmp_path)
    assert presets_dir == cfg_path.parent / "presets"

    presets_dir.mkdir(parents=True, exist_ok=True)
    (presets_dir / "custom_test.toml").write_text(
        'title = "Custom Isolated"\nclass = "paladin"\nmode = "mf"\nmin_mf = 42\n',
        encoding="utf-8",
    )

    entries = {e.name: e for e in list_presets()}
    assert "custom_test" in entries
    assert entries["custom_test"].source == "user"
    assert entries["custom_test"].path == presets_dir / "custom_test.toml"

    resolved = resolve_build_expr("custom_test", "paladin")
    assert len(resolved) == 1
    assert resolved[0].title == "Custom Isolated"
    assert resolved[0].mode == "mf"
    assert resolved[0].min_mf == 42


def test_load_save_dir_nonexistent(tmp_path: Path):
    cfg_file = tmp_path / "config.toml"
    assert load_save_dir(cfg_file) is None


def test_load_save_dir_invalid_toml(tmp_path: Path):
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text("invalid toml [[[]", encoding="utf-8")
    assert load_save_dir(cfg_file) is None


def test_load_save_dir_missing_key(tmp_path: Path):
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text('lang = "enUS"\n', encoding="utf-8")
    assert load_save_dir(cfg_file) is None


def test_load_save_dir_valid(tmp_path: Path):
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text('save_dir = "/tmp/my_saves"\n', encoding="utf-8")
    loaded = load_save_dir(cfg_file)
    assert loaded == Path("/tmp/my_saves")


def test_update_save_dir_new_file(tmp_path: Path, capsys):
    cfg_file = tmp_path / "subdir" / "config.toml"
    target_dir = tmp_path / "game_saves"
    update_save_dir(target_dir, config_path=cfg_file)

    assert cfg_file.is_file()
    assert load_save_dir(cfg_file) == target_dir
    captured = capsys.readouterr()
    assert f"Saved save_dir = '{target_dir}' in {cfg_file}" in captured.err


def test_update_save_dir_preserves_comments_and_other_keys(tmp_path: Path):
    cfg_file = tmp_path / "config.toml"
    initial_content = """# User configuration
lang = "zhCN"
[custom]
key = "value"
"""
    cfg_file.write_text(initial_content, encoding="utf-8")

    update_save_dir("/path/to/saves", config_path=cfg_file)

    result_text = cfg_file.read_text(encoding="utf-8")
    assert "# User configuration" in result_text
    assert 'lang = "zhCN"' in result_text
    assert 'save_dir = "/path/to/saves"' in result_text
    assert load_save_dir(cfg_file) == Path("/path/to/saves")


def test_update_save_dir_corrupt_config_not_overwritten(tmp_path: Path, capsys):
    cfg_file = tmp_path / "config.toml"
    corrupt_content = "corrupt [[[]]] content"
    cfg_file.write_text(corrupt_content, encoding="utf-8")

    update_save_dir("/new/path", config_path=cfg_file)

    # File must not be overwritten
    assert cfg_file.read_text(encoding="utf-8") == corrupt_content
    captured = capsys.readouterr()
    assert "Warning: Configuration file" in captured.err
    assert "Skipping save_dir update" in captured.err


def test_update_save_dir_noop_when_unchanged(tmp_path: Path, capsys):
    cfg_file = tmp_path / "config.toml"
    update_save_dir("/same/path", config_path=cfg_file)
    captured = capsys.readouterr()
    assert "Saved save_dir" in captured.err
    mtime_first = cfg_file.stat().st_mtime_ns

    # Call again with identical path
    update_save_dir("/same/path", config_path=cfg_file)
    mtime_second = cfg_file.stat().st_mtime_ns
    assert mtime_first == mtime_second
    captured_second = capsys.readouterr()
    assert "Saved save_dir" not in captured_second.err


def test_update_save_dir_if_empty_when_empty(tmp_path: Path, capsys):
    cfg_file = tmp_path / "config.toml"
    res = update_save_dir("/first/path", config_path=cfg_file, if_empty=True)
    assert res is True
    assert load_save_dir(cfg_file) == Path("/first/path")
    captured = capsys.readouterr()
    assert "Saved save_dir" in captured.err


def test_update_save_dir_if_empty_when_already_set(tmp_path: Path, capsys):
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text('save_dir = "/initial/path"\n', encoding="utf-8")

    res = update_save_dir("/second/path", config_path=cfg_file, if_empty=True)
    assert res is False
    assert load_save_dir(cfg_file) == Path("/initial/path")
    captured = capsys.readouterr()
    assert "Saved save_dir" not in captured.err
