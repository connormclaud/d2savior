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

- Python 3.10+

## Usage

```bash
# Parse a character save
uv run python d2s_parse.py path/to/character.d2s

# Parse a shared stash
uv run python d2s_parse.py path/to/ModernSharedStashSoftCoreV2.d2i

# With language option
uv run python d2s_parse.py --lang zhCN path/to/character.d2s

# With debug information
uv run python d2s_parse.py --debug path/to/character.d2s
```

## Testing

```bash
uv run pytest
```

## License

[MIT](LICENSE)
