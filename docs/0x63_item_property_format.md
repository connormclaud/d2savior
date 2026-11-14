# 0x63 Item Property Format Specification

## 1. Property List Structure

Magical properties on items are stored as a continuous bitstream sequence of 9-bit stat IDs and attribute values, ending with a reserved termination marker:

```
[9-bit stat_id][param / layer bits][value bits] ... [0x1FF Terminator]
```

### 1.1 D2R Format (ItemStatCost Driven)

In D2R (`version >= 0x61`), property serialization and bit lengths are dynamically defined by `ItemStatCost.txt`:

| Field | Size (Bits) | Description |
|-------|-------------|-------------|
| `stat_id` | 9 | Unique stat identifier (0 - 511) |
| `layer` | `save_param_bits` | Parameter or sub-stat layer (if `save_param_bits > 0`) |
| `raw_value` | `save_bits` | Raw integer attribute value |
| Terminator | 9 | `0x1FF` (511 decimal), signals end of property list |

The final gameplay value is calculated as:
```
value = (raw_value - save_add) << val_shift
```

### 1.2 Role of property.txt Across Versions

- **Classic Saves (`version < 0x61`)**: Classic saves historically used composite field definitions from `property.txt` where each property ID had a fixed bit sum (`bits_sum`).
- **D2R Saves (`version >= 0x61`)**: While raw bitstream serialization is governed by `ItemStatCost.txt` (`save_bits`, `save_param_bits`, `save_add`, `val_shift`), D2R saves still consult `property.txt` via `get_property_meta()` in `PropertyList._isc_to_params` and `_isc_layer_to_params`. The field widths defined in `property.txt` allow unpacking multi-parameter `layer` bitfields into the 4-element `params` tuple required by display formatters.

## 2. ItemStatCost Metadata Fields

The `ItemStatCost.txt` table defines the binary serialization rules for each stat ID:

| Column | Field | Purpose |
|--------|-------|---------|
| `*ID` | `stat_id` | Unique attribute ID |
| `Stat` | `stat_name` | Name string (e.g. `strength`, `item_addskills`) |
| `Save Bits` | `save_bits` | Bit width allocated for the raw value |
| `Save Add` | `save_add` | Integer offset added to the value before encoding |
| `Save Param Bits` | `save_param_bits` | Bit width allocated for parameters / skill IDs |
| `ValShift` | `val_shift` | Left/right bit shift applied to the value |
| `descfunc` | `desc_func` | Formatter function selector (1-24) |
| `descval` | `desc_val` | Number display format (0=Hide, 1=Show +, 2=Show no +) |
| `descstrpos` | `desc_str_pos` | Positive description lookup key |
| `descstrneg` | `desc_str_neg` | Negative description lookup key |

## 3. Paired Stats Handling

Certain primary stats automatically encode secondary stats immediately following the primary value without an additional 9-bit stat ID:

| Primary Stat ID | Secondary Stat ID(s) | Description |
|-----------------|----------------------|-------------|
| 17 (`item_maxdamage_percent`) | 18 (`item_mindamage_percent`) | Enhanced Damage range |
| 48 (`firemindam`) | 49 (`firemaxdam`) | Fire minimum & maximum damage |
| 50 (`lightmindam`) | 51 (`lightmaxdam`) | Lightning minimum & maximum damage |
| 52 (`magicmindam`) | 53 (`magicmaxdam`) | Magic minimum & maximum damage |
| 54 (`coldmindam`) | 55 (`coldmaxdam`), 56 (`coldlength`) | Cold damage range and freeze duration |
| 57 (`poisonmindam`) | 58 (`poisonmaxdam`), 59 (`poisonlength`) | Poison damage range and duration |

### Special Rules for Poison Damage:
- When deserializing stat 57 (`poisonmindam`), an implicit stat 88 (`poisoncount`) with value `1` is automatically registered.
- Stat 88 is an internal engine flag and is omitted during serialization.

## 4. Layer Parameter Deconstruction

For stats with `save_param_bits > 0`, the `layer` field packs extra context such as skill IDs or class indices:

### Stat 83 (`item_addclassskills` - e.g. +2 to Sorceress Skill Levels)
- `save_param_bits`: 3
- `layer` (3 bits): `class_id` (0=Amazon, 1=Sorceress, ..., 6=Assassin)
- `value`: Skill bonus points (`params = [class_id, value, 0, 0]`)

### Stat 97 (`item_nonclassskill` - e.g. +1 to Teleport)
- `save_param_bits`: 9
- `layer` (9 bits): `skill_id` (e.g. 54 for Teleport)
- `value`: Skill bonus points (`params = [skill_id, value, 0, 0]`)

### Stat 107 (`item_singleskill` - e.g. +3 to Warmth)
- `layer`: `skill_id`
- `value`: Skill bonus points (`params = [skill_id, value, 0, 0]`)

### Stat 126 (`item_elemskill` - e.g. +1 to Fire Skills)
- `save_param_bits`: 3
- `layer` (3 bits): Element type index
- `value`: Skill bonus points

### Stat 188 (`item_addskill_tab` - e.g. +2 to Lightning Skills)
- `save_param_bits`: 16
- `layer`:
  - Bits 0..2 (3 bits): Skill tab index within class (0..2)
  - Bits 3..5 (3 bits): Character class index (0..6)
- `value`: Skill bonus points (`params = [tab_id, class_id, value, 0]`)

## 5. Non-List Type-Specific Field Widths

The bit lengths and offsets of several fixed item fields are also defined in `ItemStatCost.txt` rather than hardcoded:

| Field | Stat ID | Stat Name | Description |
|-------|---------|-----------|-------------|
| Defense | 31 | `armorclass` | Raw defense on armor (`value = raw - save_add`) |
| Current Durability | 72 | `durability` | Current durability (`save_bits` = 9) |
| Max Durability | 73 | `maxdurability` | Maximum durability (`save_bits` = 8) |
| Sockets | 194 | `item_numsockets` | Number of sockets (`save_bits` = 3 in D2R) |
| Quest Difficulty | 356 | `quest_difficulty`| Quest difficulty requirement (compact items) |

## 6. Property Formatting & Localization

Property string formatting is implemented in `core/property.py` (`format_property` and `init_item_modifiers`), which evaluates string templates using `descfunc` selectors (supporting functions 1 through 24):

1. The stat metadata specifies a `descfunc` selector:
   - `1`: `+[value] [desc]` (e.g. `+10 to Strength`)
   - `2`: `[value]% [desc]` (e.g. `30% Fire Resist`)
   - `3`: `[value] [desc]` (e.g. `50 to Life`)
   - `4`: `+[value]% [desc]` (e.g. `+100% Enhanced Defense`)
   - `5`: `[value]% [desc] (class only)`
   - `6`: `[value] [desc]` (e.g. `25% Crushing Blow`)
   - `7`: `[value]% [desc]` (e.g. `50% Deadly Strike`)
   - `8`: `+[value] to [skill]`
   - `9`: `+[value] to [tab] ([class] Only)`
   - `11`: `Repairs 1 Durability in [time] Seconds`
   - `12-24`: Chance to cast, elemental absorption, charged skills, level-based scaling, etc.
2. Template strings are loaded from `data/local/item-modifiers.json` via `init_item_modifiers()`, supporting multi-language output in coordination with `GameDataResolver` and `core/item_formatter.py`.
