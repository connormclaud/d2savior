# 0x69 (v3.x / Reign of the Warlock) Save Format Analysis

## 1. Overview

Save version `0x69` (105 decimal) corresponds to Diablo II: Resurrected v3.x (Reign of the Warlock), which introduced the eighth playable class (Warlock, `charClass = 7`). Compared to version `0x63` (v2.x / Base D2R), the file structure features major changes in the save header, character progression tracking, game mode selection, mercenary data layout, and expansion-specific payload blocks.

## 2. Comprehensive Comparison: 0x63 vs 0x69

### 2.1 Header Differences

| Component | Version 0x63 | Version 0x69 |
|-----------|--------------|--------------|
| Character Name | Read from `name_ptr` (offset `0x010B`, 64B, `NamePTR`) or offset `0x0014` (`name`) | Read from `preview_data` at offset `0x00AF` + `0x7C` (96 bytes, UTF-8, `name`) |
| Character Flags | 1 byte at `0x0024` (`char_flags` / `char_type`) | 4 bytes at `0x0014` (`char_flags`) |
| Act Progression | Stored only in `QuestInfo` | Packed into bits 8-12 (`0x1F00`) of `char_flags` |
| Class ID Offset | Offset `0x0028` (1 byte, 0..6, `char_class`) | Offset `0x0018` (1 byte, 0..7, `char_class`) |
| Level Offset | Offset `0x002B` (1 byte, `char_level`) | Offset `0x001B` (1 byte, `char_level`) |
| Valid Timestamp | `dw_time` at offset `0x0030` (Unix epoch) | `last_save_time` at offset `0x0020` (Unix epoch) |
| Legacy Timestamps | `create_time` = 0, `play_time` = -1 | `create_time` = 0, `play_time` = -1 |
| Mercenary Fields | `merc_control`, `merc_name`, etc. (offsets `0x00AF`..`0x00BB`) | `merc_flags`, `merc_seed`, `merc_name_index`, etc. (offsets `0x009F`..`0x00AB`) |
| Preview Block | `preview_prefix` (76B, `0x00BF`) + `name_ptr` (64B, `0x010B`) + `preview_suffix` (4B, `0x014B`) | Single unified `preview_data` (228 bytes, offset `0x00AF`) |

### 2.2 Item Parsing Differences

| Feature | Version 0x63 | Version 0x69 |
|---------|--------------|--------------|
| Item Type Codes | Huffman encoded (4 characters) | Huffman encoded (4 characters) |
| Quantity Handling | Read 9 bits if `meta.is_stacked` | 1-bit presence flag + 9 bits on any item |
| Compact Item Alignment | No alignment padding | `ipad_bits` read if defined in `itemdata.txt` |
| Stash Stack Size | Stored for `STACKABLE_FOR_STASH` | 1-bit presence flag + 8-bit size |
| Attribute Data | `data/0x63/ItemStatCost.txt` | `data/0x69/ItemStatCost.txt` (Warlock skills & stat 356) |

### 2.3 New Data Blocks

- **Demon Section (`Demon`)**:
  Present in version `0x69` when `game_version >= 3` (`preview_data[0x49] >= 3`), with section magic `0x666C` (ASCII "lf"). Stores demon type, classification ID, name seed, monster flags, and demon attributes.

## 3. Implementation Details & Corrections

1. **Expansion Detection**:
   In older versions (0x63 and below), expansion status is flagged by bit `0x20` in `char_flags`. In 0x69 (v104+), the game migrates this state to `preview_data[0x49]` (`game_version > 1`) and clears bit `0x20`.
2. **Timestamps**:
   Only `dw_time` (at offset `0x0030` in 0x63) and `last_save_time` (at offset `0x0020` in 0x69) store valid Unix timestamps. `create_time` is initialized to 0 and `play_time` to `0xFFFFFFFF` across all official D2R saves.
3. **Runeword Completion Field**:
   Historical reverse-engineering notes sometimes referenced a `bRuneWordComplete` flag in version 0x69; inspection of official files and production code confirms the runeword payload is solely the 16-bit `rune_id`.
4. **Character String Encoding**:
   Both 0x63 and 0x69 use 8-bit UTF-8 character encoding for personalized names, ears, and character names (`is_ptr24_and_above` applies to `version >= 0x62`).
