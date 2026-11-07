# 0x63 Item List and Item Structure Specification

## 1. Item List Structure (`ItemList`)

The item list section begins with a 16-bit magic identifier, followed by the item count and consecutive serialized items:

| Field | Size (Bits) | Description |
|-------|-------------|-------------|
| `magic` | 16 | Section identifier (`0x4D4A` = ASCII "JM") |
| `count` | 16 | Total count of items serialized in this block |
| `items` | Variable | Consecutive serialized `D2Item` objects |

## 2. Individual Item Structure (`D2Item` in D2R)

Save version `0x63` (99 decimal) belongs to D2R (`version >= 0x61`) and parses items via `_read_data_d2r`.

### 2.1 Item Header

| Field | Size (Bits) | Description |
|-------|-------------|-------------|
| `magic` | 16 | Item magic (`0x4D4A`), only read if `version <= 96` |
| `version` | 32 | Item version, only read if `version <= 96` |
| `flags` | 32 | 32-bit packed item status flags (see section 2.2) |

> In version `0x63` (`version > 96`), the item header does not serialize `magic` or `version`; each item inherits the container's version directly.

### 2.2 32-Bit Item Flags

All item status flags are packed into a 32-bit bitmask:

| Flag | Bitmask | Description |
|------|---------|-------------|
| Identified | `0x00000010` | Item is identified (`is_identified`) |
| HasQuantity | `0x00000020` | Quantity field present (`_bHasQuantity`) |
| Socketed | `0x00000800` | Item has sockets (`is_socketed`) |
| IsEar | `0x00010000` | Item is a player ear (`is_ear`) |
| StarterItem | `0x00020000` | Starter equipment (`bNewbie`) |
| CompactSave | `0x00200000` | Compact / simple item format (`is_simple`) |
| Ethereal | `0x00400000` | Item is ethereal (`is_ethereal`) |
| Personalized | `0x01000000` | Personalized by Anya (`is_personalized`) |
| LowQuality / Gamble | `0x02000000` | Low quality or vendor gamble item |
| Runeword | `0x04000000` | Active runeword item (`is_runeword`) |
| Chronicle | `0x10000000` | Chronicle item tracking (`_bChronicle`) |
| ChronicleCompact | `0x20000000` | Compact chronicle data (`_bChronicleCompact`) |

### 2.3 Item Format Version (`wVersion`)

In D2R format (`version > 96`):

| Field | Size (Bits) | Description |
|-------|-------------|-------------|
| `hf` | 1 | High version flag |
| `vv` | 2 | Version offset value |

Decoding logic:
- If `hf == 1`: `wVersion = vv + 99` (codes 99..102)
- If `hf == 0`: `wVersion = vv` (codes 0..3)

### 2.4 Location and Coordinates

| Field | Size (Bits) | Condition | Description |
|-------|-------------|-----------|-------------|
| `mode` | 3 | Always | Location mode index (`iLocation`) |

**Modes 3 and 5 (Ground / Dropping)**:
| Field | Size (Bits) | Description |
|-------|-------------|-------------|
| `GroundX` | 16 | World X coordinate (`iColumn`) |
| `GroundY` | 16 | World Y coordinate (`iRow`) |

**All other modes (Inventory, Equipped, Belt, Stash, Cube)**:
| Field | Size (Bits) | Description |
|-------|-------------|-------------|
| `BodyLocation` | 4 | Equipped body slot (`iPosition`, see `EquipSlot`) |
| `InvX` | 4 | Inventory column 0-9 (`iColumn`) |
| `InvY` | 4 | Inventory row 0-9 (`iRow`) |
| `StorePage` | 3 | Stored page (`iStoredIn = read_bits(3) - 1`) |

#### Location Modes (`ItemLocation`)
- `0`: Stored (Inventory, Stash, Cube)
- `1`: Equipped
- `2`: Belt
- `3`: Ground
- `4`: Cursor
- `5`: Dropping
- `6`: Socketed

#### Storage Pages (`StoredIn`)
- `0`: Inventory
- `1`: Equipped
- `2`: Trade window
- `3`: Horadric Cube
- `4`: Stash
- `5`: Belt

### 2.5 Item Type Code (Huffman Encoded)

In D2R (`version >= 0x61`), 4-character item codes (e.g. `b'hdm '`, `b'rin '`) are **not** stored as raw ASCII. Instead, each character is decoded using a Huffman tree:

```python
if self.is_ear:
    self.ear = Ear()
    self.ear.deserialize(bs, self.version)
    type_name = b'ear '
else:
    type_name = bytes([huffman.read_char(bs) for _ in range(4)])
```

## 3. Compact Items (`is_simple = True`)

Compact items (potions, scrolls, gems, runes, quest items, keys) omit extended properties:

1. **Ear Data** (if `is_ear`):
   - `iEarClass` (3 bits): Class of slain player
   - `iEarLevel` (7 bits): Level of slain player
   - `sEarName`: UTF-8 string terminated by a null character (8 bits per character for `version >= 0x62`).
2. **Quest Difficulty** (if `version > 92` and item has `quest > 0` and `questdiffcheck`):
   - Reads stat 356 (`quest_difficulty`) bit-length from `ItemStatCost.txt`.
3. **Realm Data** (if `version > 86`):
   - 1-bit presence flag; if true, reads 4 x 32-bit dwords (`realm_data`).
4. **Advanced Stash Size** (if `version > 99`):
   - Version 100-101: 8 bits for types in `STACKABLE_FOR_STASH`.
   - Version > 101: 1-bit flag followed by 8 bits (`stash_stack_size`).

## 4. Complete Items (`is_simple = False`)

Complete items contain full extended information and property lists.

### 4.1 Extended Item Info (`ExtItemInfo`)

| Field | Size (Bits) | Description |
|-------|-------------|-------------|
| `gems` | 3 | Number of socketed gems/runes/jewels (0-7) |
| `guid` | 32 | Global unique item ID / RNG seed |
| `drop_level` | 7 | Item drop level / item level (`ilvl`, 1-99) |
| `quality` | 4 | Item quality index (1-8, see `ItemQuality`) |
| `has_var_gfx` | 1 | Variable graphics flag |
| `var_gfx` | 3 | If `has_var_gfx`: graphic variant index |
| `has_class` | 1 | Auto-magic / class-specific affix flag |
| `item_class` | 11 | If `has_class`: auto-affix ID |

### 4.2 Quality-Specific Affix Data

| Quality | Name | Associated Fields |
|---------|------|-------------------|
| 1 | Low / Inferior | `low_quality_id` (3 bits) |
| 2 | Normal | Charm (`charm_id`, 12 bits), Body part (`body_part_file_index`, 10 bits), Scroll/Book (`spell_type`, 5 bits) |
| 3 | High / Superior | `high_quality_id` (3 bits) |
| 4 | Magic | `magic_prefix` (11 bits), `magic_suffix` (11 bits) |
| 5 | Set | `set_id` (12 bits) |
| 6 | Rare | `rare_name` (`LongName`) |
| 7 | Unique | `unique_id` (12 bits) |
| 8 | Crafted | `craft_name` (`LongName`) |

#### Rare and Crafted Name Structure (`LongName`)
- `name_1` (8 bits): Prefix word ID from `rareprefix.txt`
- `name_2` (8 bits): Suffix word ID from `raresuffix.txt`
- 3 pairs of optional affixes (`pref_1`, `suff_1`, `pref_2`, `suff_2`, `pref_3`, `suff_3`):
  - 1-bit flag indicating presence.
  - If set: 11-bit affix ID.

### 4.3 Runewords, Personalization, and Realm Data

- **Runeword ID**: If `is_runeword`, reads `rune_id` (16 bits).
- **Personalized Name**: If `is_personalized`, reads character name string (8 bits per character for `version >= 0x62`, null-terminated, max 16 chars).
- **Realm Data**: 1-bit presence flag; if true, reads 4 x 32-bit dwords (`realm_data`).
- **Gold Quantity**: If item code is `gld `, reads `GoldQuantity` (1 bit non-gold flag + 12 bits gold amount).

### 4.4 Type-Specific Information (`TypeSpecificInfo`)

| Field | Condition | Size (Bits) | Description |
|-------|-----------|-------------|-------------|
| `defence` | Armor (`has_def = True`) | stat 31 `save_bits` (11) | Armor defense (`value = raw - save_add`) |
| `max_durability` | Has durability (`has_dur = True`) | stat 73 `save_bits` (8) | Maximum durability |
| `current_durability`| `max_durability > 0` | stat 72 `save_bits` (9) | Current durability |
| `quantity` | Stackable (`is_stacked = True`) | 9 bits | Stack quantity (for v0x63) |
| `sockets_count` | Socketed (`is_socketed = True`) | stat 194 `save_bits` (3) | Number of base sockets |
| `has_set_prop_list`| Set item (`quality == 5`) | 5 x 1 bit | Set bonus property list bitmask |
| `property_list` | Always | Variable | Base magic/unique properties (see property doc) |
| `set_properties` | If set item | Variable | Up to 5 additional property lists for set bonuses |
| `runeword_property_list` | If `is_runeword` | Variable | Properties granted by the runeword |

### 4.5 Chronicle Data (version > 99)

If `flags & 0x10000000` (`_bChronicle`):
- `chronicle_id` (16 bits)
- If `_bChronicleCompact`: 64 bits compact data
- Else: 32-bit timestamp, 4-bit recipient count, followed by `count * 64` bits recipient records.

## 5. Byte Alignment & Socketed Gems

- **Alignment**: Every item payload is aligned to the nearest byte boundary via `bs.align_byte()`.
- **Nested Socket Items**: If `gems > 0`, the item stream immediately contains `gems` sequentially serialized `D2Item` instances stored in `gem_items`.
