lazy import sys
lazy from pathlib import Path

lazy import platformdirs
lazy import tomlkit
lazy from tomlkit.exceptions import TOMLKitError


def get_config_path() -> Path:
    """Return the platform-specific path to config.toml."""
    return platformdirs.user_config_path("d2savior") / "config.toml"


def load_save_dir(config_path: Path | None = None) -> Path | None:
    """Load the save_dir path from config.toml if present and valid."""
    path = config_path or get_config_path()
    if not path.is_file():
        return None

    try:
        content = path.read_text(encoding="utf-8")
        doc = tomlkit.parse(content)
        val = doc.get("save_dir")
        if isinstance(val, str) and val.strip():
            return Path(val.strip()).expanduser()
    except OSError, TOMLKitError:
        return None
    return None


def update_save_dir(
    save_dir: Path | str,
    config_path: Path | None = None,
    if_empty: bool = False,
) -> bool:
    """Update or set save_dir in config.toml, preserving other keys and comments.

    If if_empty is True, save_dir is only written if it is not already set in config.
    Returns True if written, False otherwise.
    """
    path = config_path or get_config_path()
    save_dir_str = str(save_dir)

    if if_empty and load_save_dir(path) is not None:
        return False

    if path.is_file():
        try:
            content = path.read_text(encoding="utf-8")
            doc = tomlkit.parse(content)
            if doc.get("save_dir") == save_dir_str:
                return False
        except (OSError, TOMLKitError) as e:
            print(
                f"Warning: Configuration file {path} could not be parsed: {e}. "
                "Skipping save_dir update.",
                file=sys.stderr,
            )
            return False
    else:
        doc = tomlkit.document()

    doc["save_dir"] = save_dir_str

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(tomlkit.dumps(doc), encoding="utf-8")
        print(f"Saved save_dir = '{save_dir_str}' in {path}", file=sys.stderr)
        return True
    except OSError as e:
        print(f"Warning: Could not write configuration to {path}: {e}", file=sys.stderr)
        return False
