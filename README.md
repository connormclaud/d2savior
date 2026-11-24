# D2Savior

A Diablo II: Resurrected save and shared stash parser, originally created by [simshi](https://github.com/simshi/d2savior).

Supports both version 0x63 (v1.x) and 0x69 (v3.x / Reign of the Warlock) save files.

## Features

- Parse character save files (`.d2s`): attributes, progression, skills (with names), waypoints, quests, items, and mercenary gear
- Parse shared stash files (`.d2i`): all normal tabs and the currency tab with stack sizes
- Parse standalone item files (`.d2i`)
- Search for items across characters and shared stashes (`-f` / `--find`)
- Multi-language item and skill name lookup support (`--lang enUS`, `--lang zhCN`, etc.)
- Optional Sorceress & Paladin leveling build & charm loadout optimizer across character saves and shared stashes (`d2savior optimize`, enabled via `[optimize]`)
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

# Search for items across saves and stashes
uv run d2savior --find "Shako" path/to/saves/
uv run d2savior stash --find "Runes" --summary

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

### Shared Stash

Display shared stash contents or summary from your save directory:

```bash
# Show full stash contents in the configured save folder
d2savior stash

# Show compact stash summary
d2savior stash --summary

# Or specify a directory or stash file
d2savior stash "/path/to/Saved Games/Diablo II Resurrected"
d2savior stash --summary /path/to/SharedStashSoftCoreV2.d2i

# Run without reading or writing config
d2savior stash --no-config
```

### Build Optimizer (Optional)

`d2savior optimize` evaluates Blizzard Sorceress and Paladin leveling gear and charm loadouts across your characters and shared stash. Optimization is an optional feature and is off by default:

```bash
# Install with the optional optimizer extra
pip install "d2savior[optimize]"
# or with uvx
uvx "d2savior[optimize]" optimize
```

When running from a source checkout, build the Rust native extension first:

```bash
make build-rust
```

Usage examples:

```bash
# Optimize a character in the configured save folder across all saves & stashes
d2savior optimize

# Optimize a specific Sorceress build preset
# Sorceress presets: base, mf, mf-speed, mf-pure, tz, power, max-res, all (default)
d2savior optimize sork -b tz

# Optimize a leveling Paladin (auto-detects highest damage skill, evaluates set bonuses)
# Paladin presets: leveling, max-res, all (default)
d2savior optimize smite -b leveling

# Keep currently equipped active gear and optimize inventory charms only
d2savior optimize smite --keep-gear

# Keep only specific equipped gear groups (all, weapon, jewelry, armor, or '+' combinations)
d2savior optimize smite --keep-gear weapon+jewelry

# Customize charm inventory budget and number of options shown
d2savior optimize sork -b mf --charm-slots 23 --limit 5

# Pass explicit save/stash files without modifying config
d2savior optimize --no-config /path/to/sork.d2s /path/to/mule.d2s /path/to/ModernSharedStashSoftCoreV2.d2i

# Find the best item for Larzuk's Socket Quest (owned gems/runes/jewels & craftable runewords)
d2savior optimize socket sork -b tz

# Include theoretical/ideal runes, perfect gems, and runewords for a lvl 99 respec (unbound level & Str/Dex reqs)
d2savior optimize socket sork --theoretical
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
# Run Python test suite (native optimizer tests are skipped unless built)
uv run pytest

# Build and test the optional Rust optimizer extension from source
make build-rust
make test-rust
uv run pytest
```

## License

The `d2savior` source code is licensed under the [MIT License](LICENSE).

The bundled game data tables and localized strings in [`d2savior/data/`](d2savior/data/README.md) are **© Blizzard Entertainment, Inc.** (*Diablo II: Resurrected*), are **not** covered by the MIT License, and are included solely for interoperability with *Diablo II: Resurrected* save and stash files.
