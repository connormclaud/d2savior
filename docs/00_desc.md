# Game Versions and Architecture Overview

## 1. Supported Game and Save Versions

D2Savior supports parsing and manipulating Diablo II and Diablo II: Resurrected save files across legacy and modern formats:

### Classic Diablo II (v1.x)
- Save versions `< 0x61`
- Common versions: `0x47` (v1.07), `0x57` (v1.09), `0x59`, `0x5C`, `0x60` (v1.10 - v1.14d)
- Item types and names stored as raw ASCII, item flags read sequentially bit-by-bit.

### Diablo II: Resurrected (D2R) (`version >= 0x61`)
- **v2.x (Base D2R)**: Save versions `0x61` ~ `0x63`
  - `0x61`: D2R Launch / Patch 2.3
  - `0x62`: D2R Patch 2.4 / PTR 2.4 (switches character name strings to UTF-8 and 8-bit character encoding)
  - `0x63`: D2R Patch 2.5+
- **v3.x (Reign of the Warlock)**: Save version `0x69` (105 decimal)
  - Expansion release introducing the Warlock class (`charClass = 7`)
  - Substantial header revisions: introduction of the 228-byte `preview_data` structure containing character names and game mode versioning, dedicated `Demon` data section (`magic = 0x666C`), and shared stash tabs support (`ModernSharedStash*.d2i`).

## 2. Version Detection Helpers

```python
def is_d2r(version: int) -> bool:
    """Return True if save version corresponds to Diablo II: Resurrected."""
    return version >= 0x61

def is_ptr24_and_above(version: int) -> bool:
    """Return True if version supports PTR 2.4+ features (8-bit name encodings)."""
    return version >= 0x62
```

- `version < 0x61`: Classic Diablo II
- `0x61 <= version < 0x69`: D2R Base (2.x)
- `version >= 0x69`: D2R Expansion - Reign of the Warlock (3.x)

## 3. Core Architecture

The project consists of modular components in the `core/` package and the CLI entry point `d2s_parse.py`:

- **Bitstream Engine** (`core/ibitstream.py`, `core/obitstream.py`):
  Direct byte buffering and bit-level stream readers/writers.
- **Huffman Coding** (`core/huffman.py`):
  Tree-based bitwise decompression used in D2R for 4-character item type codes.
- **Save File Structure** (`core/d2s_struct.py`):
  Structures representing headers, quests (`QuestInfo`), waypoints (`Waypoints`), player stats (`PlayerStats`), character skills (`CharSkills`), item lists (`ItemList`), corpses (`Corpse`), mercenaries (`Mercenary`), golem items (`Golem`), and warlock demons (`Demon`).
- **Item System** (`core/item.py`):
  Data models for items (`D2Item`), item lists (`ItemList`), extended information (`ExtItemInfo`), type-specific data (`TypeSpecificInfo`), ear data (`Ear`), rare/crafted names (`LongName`), and gold quantities (`GoldQuantity`).
- **Shared Stash System** (`core/stash.py`):
  Shared stash tab parsing (`SharedStash`, `StashTab`) supporting standard tabs and advanced currency tabs (Gems, Runes, Materials).
- **Game Data & Resolution** (`core/d2data.py`, `core/localized_data.py`, `core/property.py`):
  Multi-version game data management (`D2DataManager`, `GameDataResolver`), localized strings loader (`LocalizedData`), and property formula evaluation.
- **Formatters & CLI** (`core/formatters.py`, `core/constants.py`, `d2s_parse.py`):
  Output formatting for summary views, item inspection, quest progression, waypoints, and stash reports.
