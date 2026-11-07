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

`d2s-parse` and `python d2s_parse.py` are also available as compatibility aliases.

## Testing

```bash
uv run pytest
```

## License

[MIT](LICENSE)
