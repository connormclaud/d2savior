# D2Savior

A Diablo II: Resurrected save and shared stash parser, originally created by [simshi](https://github.com/simshi/d2savior).

Supports both version 0x63 (v1.x) and 0x69 (v3.x / Reign of the Warlock) save files.

## Features

- Parse character save files (`.d2s`): attributes, progression, skills (with names), waypoints, quests, items, and mercenary gear
- Parse shared stash files (`.d2i`): all normal tabs and the currency tab with stack sizes
- Parse standalone item files (`.d2i`)
- Multi-language item and skill name lookup support (`--lang enUS`, `--lang zhCN`, etc.)
- Bit/byte search capabilities for reverse engineering and debugging

## Requirements

- Python 3.15+

## Usage

### Run with uvx (no installation needed)

Run directly from GitHub without cloning or installing:

```bash
uvx --from git+https://github.com/connormclaud/d2savior d2savior path/to/character.d2s
```

Or once installed / published to PyPI:

```bash
uvx d2savior path/to/character.d2s
```

### Run installed tool or via uv

```bash
# Parse a character save
uv run d2savior path/to/character.d2s

# Parse a shared stash
uv run d2savior path/to/ModernSharedStashSoftCoreV2.d2i

# With language option
uv run d2savior --lang zhCN path/to/character.d2s

# With debug information
uv run d2savior --debug path/to/character.d2s
```

### List Characters

List all characters in your save directory sorted by last played (most recently played on top):

```bash
# List characters in the configured save folder
d2savior list

# Or specify a directory (also remembers the directory in config)
d2savior list "/path/to/Saved Games/Diablo II Resurrected"

# Run without reading or writing config
d2savior list --no-config /path/to/saves
```

Output:

```text
NAME       CLASS      LEVEL  MODE      LAST PLAYED
sork       Sorceress     74  Softcore  2026-11-06 17:31:34 UTC
hammerdin  Paladin       99  Hardcore  2026-11-05 10:15:00 UTC
```

### Save Directory & Automatic Lookup

When pointing `d2savior` to a character file or save folder, it automatically saves that folder to your user configuration (`~/.config/d2savior/config.toml` on Linux):

```bash
# 1. Run once with full path (remembers the save directory)
d2savior "/path/to/Saved Games/Diablo II Resurrected/sork.d2s"

# 2. Later, simply pass character name or filename
d2savior sork.d2s
d2savior sork

# 3. Or summarize all characters and stashes in the folder
d2savior --summary

# 4. Skip reading/writing config for one-offs
d2savior --no-config /path/to/other.d2s
```

When `save_dir` changes in your configuration, `d2savior` prints a confirmation to `stderr`. If multiple files or directories are provided in a single run, the last valid directory is saved.

`d2s-parse` and `python d2s_parse.py` are also available as compatibility aliases.

## Testing

```bash
uv run pytest
```

## License

[MIT](LICENSE)
