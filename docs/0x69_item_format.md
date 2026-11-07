# 0x69 (v3.x / Reign of the Warlock) Item Format Specification

## 1. Item List Structure

The item list retains the same container format as earlier versions, beginning with the 16-bit `0x4D4A` ("JM") magic word and total item count:

| Field | Size (Bits) | Description |
|-------|-------------|-------------|
| `magic` | 16 | Magic identifier (`0x4D4A` = ASCII "JM") |
| `count` | 16 | Number of items in this section |
| `items` | Variable | Sequentially serialized `D2Item` objects |

## 2. Individual Item Structure (`D2Item`)

Because version `0x69` (105 decimal) is greater than 96, individual items omit the redundant 16-bit magic and 32-bit version prefix. Deserialization starts directly with the 32-bit `flags` word.

### 2.1 Item Header

| Field | Size (Bits) | Description |
|-------|-------------|-------------|
| `flags` | 32 | Packed 32-bit status flags |
| `hf` | 1 | High version flag |
| `vv` | 2 | Version value offset (`wVersion = vv + 99` if `hf` else `vv`) |
| `mode` | 3 | Location mode (`iLocation`) |
| Coordinates | Variable | Depending on `mode` (Ground vs Stored/Equipped) |
| `type_name` | Huffman | 4 characters decoded via Huffman coding tree |

### 2.2 Huffman Encoding for Item Type Codes

In version `0x69`, 4-character item codes (e.g. `b'am01'`, `b'hdm '`, `b'r01 '`) are decoded using Huffman decompression:

```python
huffman = get_huffman()
if self.is_ear:
    self.ear = Ear()
    self.ear.deserialize(bs, self.version)
    type_name = b'ear '
else:
    type_name = bytes([huffman.read_char(bs) for _ in range(4)])
```

## 3. Key Differences Between 0x63 and 0x69 Items

### 3.1 Universal Quantity Flag

In version `0x63`, the 9-bit stack quantity is read only if the item type is marked as stackable (`meta.is_stacked`).

In version `0x69` (`version >= 0x69` or `version > 104`), quantity serialization is universal:
1. Reads a 1-bit presence flag (`bs.read_bits(1)`).
2. If true, reads a 9-bit quantity value (`bs.read_bits(9)`).

```python
if version >= 0x69:
    if bs.read_bits(1):
        self.quantity = bs.read_bits(9)
elif bIsStacked:
    self.quantity = bs.read_bits(9)
```

### 3.2 Compact Item Padding (`ipad_bits`)

In version `0x69`, compact items (`is_simple = True`) check `itemdata.txt` for trailing alignment padding. If `meta.ipad_bits > 0`, the stream reads those padding bits:

```python
if is_d2r and version >= 0x69 and meta and meta.ipad_bits > 0:
    self.pad = bs.read_bits(meta.ipad_bits)
```

### 3.3 Advanced Stash Stack Size

For shared stash tabs in version `0x69` (`version > 101`), stack size tracking uses a 1-bit presence flag:

```python
if version > 101:
    if bs.read_bits(1):
        self.item_info.stash_stack_size = bs.read_bits(8)
        self.item_info.has_stash_stack_size = True
```

### 3.4 Version-Specific `ItemStatCost.txt`

Version `0x69` uses `data/0x69/ItemStatCost.txt`, which includes:
- Attributes for Warlock skills and masteries.
- Stat 356 (`quest_difficulty`) for quest difficulty tracking.
- Updated `save_bits`, `save_add`, and `save_param_bits` for new and rebalanced properties.

## 4. Complete Item Layout Breakdown

When `is_simple = False`, complete items parse:

1. **Extended Info (`ExtItemInfo`)**:
   - `gems` (3 bits)
   - `guid` (32 bits)
   - `drop_level` (7 bits)
   - `quality` (4 bits: Low=1, Normal=2, High=3, Magic=4, Set=5, Rare=6, Unique=7, Crafted=8)
   - `has_var_gfx` (1 bit) + optional `var_gfx` (3 bits)
   - `has_class` (1 bit) + optional `item_class` (11 bits)
   - Quality-specific affixes (affix IDs, `LongName` for Rare/Crafted, etc.)
   - Runeword ID (16 bits if `is_runeword`)
   - Personalized character name (8-bit characters, null-terminated, if `is_personalized`)
2. **Realm Data**:
   - 1-bit presence flag + 4 x 32-bit dwords (`realm_data`).
3. **Gold Quantity**:
   - If item code is `b'gld '`, reads 1-bit non-gold flag + 12-bit quantity.
4. **Type-Specific Info (`TypeSpecificInfo`)**:
   - Defense: stat 31 (bits from `ItemStatCost.txt`)
   - Durability: max durability (stat 73) and current durability (stat 72)
   - Quantity flag (1 bit) + 9-bit value
   - Sockets count: stat 194
   - Set property list flags (5 x 1-bit flags, `has_set_prop_list`, if set item)
   - Base magical property list (`PropertyList`)
   - Set property lists (up to 5 additional property lists, each read if the corresponding `has_set_prop_list[i]` flag is True)
   - Optional runeword property list (read if `is_runeword`)
5. **Chronicle Tracking**:
   - Deserialized if `flags & 0x10000000`.
6. **Advanced Stash Stack Size**:
   - 1-bit flag + 8-bit stack size.
7. **Byte Alignment & Nested Items**:
   - Byte alignment (`bs.align_byte()`).
   - `gems` nested socketed `D2Item` objects.
