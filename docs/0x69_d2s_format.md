# 0x69 (v3.x / Reign of the Warlock) Save Format Specification

## 1. Overall Binary Layout

Save version `0x69` (105 decimal) corresponds to Diablo II: Resurrected v3.x (Reign of the Warlock), which adds the Warlock class (`char_class = 7`). Compared to version `0x63`, the header is overhauled to accommodate the 228-byte `preview_data` block and new class/game modes.

| Offset (Hex) | Size (Bytes) | Field | Description |
|--------------|--------------|-------|-------------|
| 0x0000       | 4            | `magic` | File magic identifier (`0xAA55AA55`) |
| 0x0004       | 4            | `version` | Save format version (`0x69` = 105 decimal) |
| 0x0008       | 4            | `size` | Total file size in bytes (`dwSize`) |
| 0x000C       | 4            | `crc` | 32-bit rotational checksum CRC (`dwCRC`) |
| 0x0010       | 4            | `weapon_set` | Active weapon swap set (0 or 1, `dwWeaponSet`) |
| 0x0014       | 4            | `char_flags` | 32-bit character flags & progression (`charFlags`) |
| 0x0018       | 1            | `char_class` | Character class (0=Amazon .. 7=Warlock, `charClass`) |
| 0x0019       | 1            | `num_stats` | Stat count (constant 16, `numStats`) |
| 0x001A       | 1            | `num_skills` | Skill count (constant 30, `numSkills`) |
| 0x001B       | 1            | `char_level` | Character level (1-99, `charLevel`) |
| 0x001C       | 4            | `create_time` | Creation timestamp (unused/0 in v104+, `createTime`) |
| 0x0020       | 4            | `last_save_time` | Last save timestamp (Unix epoch seconds, `lastSaveTime`) |
| 0x0024       | 4            | `play_time` | Total play time (unused/`0xFFFFFFFF`, `playTime`) |
| 0x0028       | 64           | `skill_keys[16]` | Hotkey skill assignments (16 x 32-bit dwords, `dwSkillKey`) |
| 0x0068       | 4            | `left_skill_1` | Primary left-hand skill ID (`dwLeftSkill1`) |
| 0x006C       | 4            | `right_skill_1` | Primary right-hand skill ID (`dwRightSkill1`) |
| 0x0070       | 4            | `left_skill_2` | Alternate (swap) left-hand skill ID (`dwLeftSkill2`) |
| 0x0074       | 4            | `right_skill_2` | Alternate (swap) right-hand skill ID (`dwRightSkill2`) |
| 0x0078       | 16           | `outfit[16]` | Character appearance configuration |
| 0x0088       | 16           | `colors[16]` | Character color palette settings |
| 0x0098       | 3            | `town[3]` | Current town per difficulty (Normal, NM, Hell, `Town`) |
| 0x009B       | 4            | `map_seed` | Random map generation seed (`dwMapSeed`) |
| 0x009F       | 4            | `merc_flags` | Mercenary state flags (`mercFlags`) |
| 0x00A3       | 4            | `merc_seed` | Mercenary RNG seed (`mercSeed`) |
| 0x00A7       | 2            | `merc_name_index` | Mercenary name table index (`mercNameIndex`) |
| 0x00A9       | 2            | `merc_hireling_id`| Mercenary hireling type / difficulty index (`mercHirelingId`) |
| 0x00AB       | 4            | `merc_experience`| Mercenary accumulated experience points (`mercExperience`) |
| 0x00AF       | 228          | `preview_data` | Modern preview and character metadata block (`previewData`) |
| Variable     | Variable     | `quests` | Quest data block (`QuestInfo`) |
| Variable     | Variable     | `waypoints` | Waypoint activation block (`Waypoints`) |
| Variable     | 52           | `npc` | NPC introduction / talk state flags (0x34 bytes, `NPC`) |
| Variable     | Variable     | `player_stats` | Attributes block (`PlayerStats`) |
| Variable     | 32           | `skills` | Skill allocation block (`CharSkills`) |
| Variable     | Variable     | `item_list` | Inventory, equipped, and stash items (`ItemList`) |
| Variable     | Variable     | `corpse` | Player corpse item block (`Corpse`) |
| Variable     | Variable     | `mercenary` | Mercenary item block (`Mercenary`, expansion only) |
| Variable     | Variable     | `golem` | Iron Golem item data (`Golem`, expansion only) |
| Variable     | Variable     | `demon` | Warlock demon data (`Demon`, if `game_version >= 3`) |

## 2. Key Differences from 0x63

| Feature | Version 0x63 | Version 0x69 |
|---------|--------------|--------------|
| Character Name | Read from `name_ptr` (offset `0x010B`, 64B) or offset `0x0014` (`name`) | Read from `preview_data` at offset `0x00AF` + `0x7C` (96 bytes, UTF-8, `name`) |
| Character Flags | 1 byte at `0x0024` (`char_flags` / `char_type`) | 4 bytes at `0x0014` (`char_flags`) |
| Class ID Offset | Offset `0x0028` (`char_class`) | Offset `0x0018` (`char_class`) |
| Level Offset | Offset `0x002B` (`char_level`) | Offset `0x001B` (`char_level`) |
| Save Timestamp | `dw_time` at offset `0x0030` | `last_save_time` at offset `0x0020` |
| Mercenary Fields | `merc_control`, `merc_name`, etc. (offsets `0x00AF`..`0x00BB`) | `merc_flags`, `merc_seed`, `merc_name_index`, etc. (offsets `0x009F`..`0x00AB`) |
| Expansion Detection | `char_flags & 0x20` | `preview_data[0x49]` (`game_version > 1`) |
| Warlock Demon Section | Not present | Present when `game_version >= 3` (`magic = 0x666C`) |

## 3. The `preview_data` Structure (228 Bytes)

The `preview_data` block is located at offset `0x00AF`:

| Offset | Size (Bytes) | Field | Description |
|--------|--------------|-------|-------------|
| 0x00   | 48           | `save_times[6]` | 6 timestamps (Windows 64-bit FILETIME) |
| 0x30   | 24           | `experiences[6]` | Mode experience values |
| 0x48   | 1            | `guild_emblem_color` | Guild crest / emblem color index |
| 0x49   | 1            | `game_version` | Game mode version selector (see below) |
| 0x4A   | 2            | `preview_padding` | Padding bytes |
| 0x4C   | 48           | `preview_items[4]` | Equipment preview (Left Hand, Right Hand, Torso, Head) |
| 0x7C   | 96           | `name` | Character name (UTF-8, null-terminated) |
| 0xDC   | 8            | `unk1` | Reserved padding |

### `game_version` Values (`preview_data[0x49]`)

| Value | Name | Description |
|-------|------|-------------|
| 0     | None | Unset |
| 1     | Classic | Classic Diablo II (Acts 1-4) |
| 2     | Expansion | Lord of Destruction expansion |
| 3     | ReignOfTheWarlock | Reign of the Warlock expansion (adds Warlock) |

> In v104+, expansion status is determined strictly by `self.game_version > 1`, as the game clears bit 0x20 in `char_flags`.

## 4. Character Flags & Progression (`char_flags`)

| Bit Range | Mask | Name | Description |
|-----------|------|------|-------------|
| 0         | 0x0001 | Init | Initialized flag |
| 1         | 0x0002 | RealmChar | Battle.net realm character |
| 2         | 0x0004 | Hardcore | Hardcore character mode |
| 3         | 0x0008 | Died | Character has died |
| 4         | 0x0010 | SaveProcess | Save in progress flag |
| 5         | 0x0020 | Expansion | Legacy expansion bit (migrated to `gameVersion`) |
| 6         | 0x0040 | Ladder | Ladder character |
| 7         | 0x0080 | NeedsRenaming | Character rename required |
| 8..12     | 0x1F00 | Progression | Acts completed (0 to 15) |
| 13        | 0x2000 | WeaponSwitch | Weapon swap active |

### Progression Values

- `0`: Normal Act I in progress
- `1..4`: Normal Acts I..IV completed
- `5`: Normal completed -> Nightmare unlocked
- `6..9`: Nightmare Acts I..IV completed
- `10`: Nightmare completed -> Hell unlocked
- `11..14`: Hell Acts I..IV completed
- `15`: Hell completed (all acts done)

## 5. Classes & Mercenary Detection

### Character Classes (`char_class`)
- `0`: Amazon
- `1`: Sorceress
- `2`: Necromancer
- `3`: Paladin
- `4`: Barbarian
- `5`: Druid
- `6`: Assassin
- `7`: Warlock

### Mercenary Detection
```python
def has_mercenary(self) -> bool:
    if self.version >= 0x69:
        return self.merc_seed != 0 or self.merc_name_index != 0 or self.merc_experience != 0
    elif self.version >= 0x61:
        return self.merc_control != 0
    return self.merc_name > 0
```

## 6. Warlock Demon Section (`Demon`)

Appears only when `version >= 0x69` and `game_version >= 3`:

| Field | Size (Bytes) | Description |
|-------|--------------|-------------|
| `section_version` | 2 | Section version number (`sectionVersion`) |
| `magic` | 2 | Magic identifier (`0x666C` = ASCII "lf", `wMagic`) |
| `has_demon` | 1 | Boolean (1 = Active Demon, 0 = None, `hasDemon`) |
| `padding` | 1 | Alignment byte |
| `demon_data` | Variable | Demon payload (see table below, only if `has_demon`, `demonData`) |

### Detailed Demon Payload Structure (`has_demon = True`)

When `has_demon` is True, `_read_demon_data` reads the following binary sequence:

| Field | Size (Bytes) | Description |
|-------|--------------|-------------|
| `stat_data_size` | 2 | Byte length of the trailing stat stream |
| `demon_type` | 2 | Demon type code identifier |
| `class_id` | 2 | Class ID word (`value = read_word() - 1`) |
| `name_seed` | 2 | RNG seed used for demon name generation |
| `mon_flags` | 2 | Monster attribute flags |
| `num_stats` | 2 | Number of attributes in demon stat block |
| `unknown_bytes` | 2 | 2 single bytes |
| `unknown_word` | 2 | 1 word |
| `unknown_block1` | 28 | Raw byte block (28 bytes) |
| `unknown_dwords` | 20 | 5 x 32-bit dwords (20 bytes) |
| `unknown_block2` | 16 | Raw byte block (16 bytes) |
| `unknown_block3` | 10 | Raw byte block (10 bytes) |
| `unknown_block4` | 2 | Raw byte block (2 bytes) |
| `stat_data` | `stat_data_size` | Demon attribute stat payload |

## 7. Shared Stash Files (`.d2i`)

D2R shared stash data is stored in separate `.d2i` files:
- `SharedStashSoftCoreV2.d2i` / `SharedStashHardCoreV2.d2i` (Classic)
- `ModernSharedStashSoftCoreV2.d2i` / `ModernSharedStashHardCoreV2.d2i` (Expansion)

A shared stash file consists of sequential tabs (`StashTab`):

### Tab Header (64 Bytes Fixed)
| Offset | Size (Bytes) | Field | Description |
|--------|--------------|-------|-------------|
| 0x00   | 4            | `magic` | Tab magic (`0xAA55AA55`) |
| 0x04   | 4            | `stash_format` | Stash format version (1=Classic, 2=Modern, `StashFormat`) |
| 0x08   | 4            | `item_format` | Item save version (e.g. 105 for 0x69, `ItemFormat`) |
| 0x0C   | 4            | `gold` | Stashed gold on this tab (`Gold`) |
| 0x10   | 2            | `tab_size` | Total byte size of tab including header (`TabSize`) |
| 0x12   | 2            | `season` | Ladder season index (0 = Non-ladder, `Season`) |
| 0x14   | 1            | `tab_type` | Tab type: 0=Normal, 1=Advanced, 2=Chronicle (`TabType`) |
| 0x15   | 43           | `reserved` | Reserved padding |

> **Format Compatibility Note**: When `stash_format < 2`, `tab_type` is forced to `0` (`STASH_TAB_TYPE_NORMAL`) in `StashTab.deserialize`.
>
> **Serialization & Framing**: In `SharedStash.serialize`, `tab_size` (offset `0x10`, 2 bytes) is initially written as `0` and backfilled with the actual total byte length of the tab upon serializing the payload. When reading, each tab advances by `start_pos + tab_size` bytes, ensuring correct tab alignment even if trailing item data is skipped.

### Tab Types (`tab_type`)
- `0` (Normal): Standard 10x10 inventory grid (`ItemList`).
- `1` (AdvancedStash): Dedicated currency tab (`ItemList`):
  - **Gem Tab**: 7 columns x 5 rows grid (`GEM_LAYOUT`).
  - **Rune Tab**: 9 columns x 4 rows grid (`RUNE_LAYOUT`, runes r01..r33).
  - **Material Tab**: 10 columns x 3 rows grid (`MATERIAL_LAYOUT`, potions, keys, essences).
- `2` (Chronicle): Holy Grail collection tracking tab (`magic = 0xC0EAEDC0`).
