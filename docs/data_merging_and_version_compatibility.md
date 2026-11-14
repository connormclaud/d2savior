# Game Data Loading and Version Compatibility

## 1. Directory Structure

Game data tables are segregated by save format version, with root-level fallbacks:

```
data/
├── 0x63/                      # Version 0x63 specific data tables
│   ├── Armor.txt              # Armor definitions
│   ├── Weapons.txt            # Weapon definitions
│   ├── Misc.txt               # Miscellaneous item definitions
│   ├── ItemStatCost.txt       # Attribute bitfield costs & shifts
│   ├── itemtypes.txt          # Item type hierarchy
│   ├── itemdata.txt           # Item metadata (iPadBits, equip slots)
│   └── property.txt           # Property encoding definitions
│
├── 0x69/                      # Version 0x69 (v3.x / Reign of the Warlock) tables
│   ├── Armor.txt
│   ├── Weapons.txt
│   ├── Misc.txt
│   ├── ItemStatCost.txt       # Includes Warlock stats and stat 356
│   ├── Properties.txt
│   ├── itemtypes.txt
│   ├── itemdata.txt
│   ├── property.txt
│   ├── magicprefix.txt        # Magic prefixes
│   ├── magicsuffix.txt        # Magic suffixes
│   ├── uniqueitems.txt        # Unique items list
│   ├── runewords.txt          # Runeword definitions
│   ├── skills.txt             # Skill definitions (including Warlock)
│   └── sets.txt               # Set item definitions
│
├── local/                     # Multi-language string dictionaries
│   ├── item-modifiers.json    # Property formatting templates
│   ├── item-names.json        # Base, unique, and set item names
│   ├── item-nameaffixes.json  # Magic and rare affix names
│   ├── item-runes.json        # Rune and runeword localized names
│   ├── skills.json            # Localized skill names
│   ├── levels.json            # Localized area / waypoint names
│   └── quests.json            # Localized quest names
│
├── Armor.txt                  # Root-level fallback tables
├── Weapons.txt
├── ItemStatCost.txt
└── ... (other shared txt tables)
```

## 2. Multi-Version Loading Pipeline

Data initialization is lazy and explicit via `init_d2data()` or `ensure_data_loaded()`:

```python
def init_d2data(data_dir: str) -> bool:
    """Initialize versioned game data and manager."""
    mgr = D2DataManager()
    result = mgr.load_all_versions(data_dir)
    return result
```

### Path Resolution with Version Fallback

When loading a specific version (such as `0x63` or `0x69`), files are resolved from the version-specific directory first; if a file does not exist there, the loader falls back to the root `data/` directory:

```python
def _resolve_path(self, filename: str, data_dir: str, fallback_dir: str = None) -> str:
    path = os.path.join(data_dir, filename)
    if os.path.exists(path):
        return path
    if fallback_dir:
        fallback_path = os.path.join(fallback_dir, filename)
        if os.path.exists(fallback_path):
            return fallback_path
    return path
```

## 3. Data Structures

### `VersionData`
Stores all parsed tables for a single game version:
- `stats`: `Dict[int, StatInfo]` (`ItemStatCost.txt`)
- `properties`: `Dict[int, PropertyInfo]` (`Properties.txt`)
- `items`: `Dict[str, ItemTypeInfo]` (`Armor.txt`, `Weapons.txt`, `Misc.txt`)
- `magic_prefixes`, `magic_suffixes`: `Dict[int, MagicAffixInfo]`
- `unique_items`: `Dict[int, UniqueItemInfo]`
- `runewords`: `Dict[int, RuneWordInfo]`
- `skills`: `Dict[int, str]` (`skills.txt`)
- `type_ancestors`, `type_descendants`: Type hierarchy graphs (`itemtypes.txt`)
- `item_manager`: `ItemMetaDataManager` (`itemdata.txt`)
- `prop_meta`: Property bitfield models (`property.txt`)
- `stat_cost`: `StatCostItem` definitions for bitstream property parsing

### `D2DataManager`
Maintains versioned instances:
- `version_data`: Map of `version -> VersionData`
- Dispatches lookups (`get_item()`, `get_stat()`, `get_property()`, etc.) based on the requested save file version.

## 4. `GameDataResolver` Facade

The `GameDataResolver` class provides a unified interface across versioned data, legacy wrappers, and localized strings:

```python
from d2savior.core.resolver import GameDataResolver

resolver = GameDataResolver(version=char_data.version)

# Lookups with automatic version resolution
item_info = resolver.get_item("hdm ")
stat_info = resolver.get_stat(31)
unique_info = resolver.get_unique_item(unique_id)

# Localized names based on the active language (--lang zhCN, --lang enUS, etc.)
localized_name = resolver.get_localized_item_name("hdm ", fallback="Cap")
unique_name = resolver.get_localized_unique_name(unique_id)
skill_name = resolver.get_skill_name(skill_id)
```

## 5. Localization (`LocalizedData`)

Localized JSON dictionaries in `data/local/` support multi-language output:

- **CLI Flag**: `python d2s_parse.py --lang zhCN character.d2s`
- **Supported Languages**: `enUS`, `zhCN`, `zhTW`, `deDE`, `esES`, `frFR`, `itIT`, `koKR`, `plPL`, `ruRU`, etc.
- **Tables Handled**:
  - `item-names.json`: Base item names, unique item names, set names
  - `item-nameaffixes.json`: Magic prefixes/suffixes and rare name components
  - `item-runes.json`: Rune names (`El`, `Eld`, ...) and runewords (`Enigma`, `Grief`, ...)
  - `item-modifiers.json`: Formatted affix templates (e.g. `+10 to Strength`)
  - `skills.json`: Class skill names
  - `levels.json`: Area and waypoint names
  - `quests.json`: Quest titles
