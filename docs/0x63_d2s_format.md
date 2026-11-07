# 0x63 (v1.x/v2.x) D2S Save Format Specification

## 1. Overall Binary Layout

Version `0x63` (Patch 2.5+) of Diablo II: Resurrected save files (`.d2s`) uses a binary structure with little-endian integer byte order. The fixed header occupies 335 bytes (`0x014F`).

| Offset (Hex) | Size (Bytes) | Field | Description |
|--------------|--------------|-------|-------------|
| 0x0000       | 4            | `magic` | File magic identifier (`0xAA55AA55`) |
| 0x0004       | 4            | `version` | Save format version (`0x63` = 99 decimal) |
| 0x0008       | 4            | `size` | Total file size in bytes (`dwSize`) |
| 0x000C       | 4            | `crc` | 32-bit rotational checksum CRC (`dwCRC`) |
| 0x0010       | 4            | `weapon_set` | Active weapon swap set (0 or 1, `dwWeaponSet`) |
| 0x0014       | 16           | `name` | Legacy character name (ASCII, null-padded, `Name`) |
| 0x0024       | 1            | `char_flags` / `char_type` | Character type bitmask flags (`charFlags`) |
| 0x0025       | 1            | `char_title` | Character title index (0=None, 5=Slayer, etc., `charTitle`) |
| 0x0026       | 2            | `num_stats_num_skills` | High 8 bits: stat count; Low 8 bits: skill count |
| 0x0028       | 1            | `char_class` | Character class (0=Amazon .. 6=Assassin, `charClass`) |
| 0x0029       | 2            | `padding1` | Constant padding (`0x101E`) |
| 0x002B       | 1            | `char_level` | Character level (1-99, `charLevel`) |
| 0x002C       | 4            | `create_time` | Creation timestamp (unused/0 in 0x63, `createTime`) |
| 0x0030       | 4            | `dw_time` / `last_save_time` | Last save timestamp (Unix epoch seconds, `dwTime`) |
| 0x0034       | 4            | `play_time` | Total play time (unused/`0xFFFFFFFF`, `playTime`) |
| 0x0038       | 64           | `skill_keys[16]` | Hotkey skill assignments (16 x 32-bit dwords, `dwSkillKey`) |
| 0x0078       | 4            | `left_skill_1` | Primary left-hand skill ID (`dwLeftSkill1`) |
| 0x007C       | 4            | `right_skill_1` | Primary right-hand skill ID (`dwRightSkill1`) |
| 0x0080       | 4            | `left_skill_2` | Alternate (swap) left-hand skill ID (`dwLeftSkill2`) |
| 0x0084       | 4            | `right_skill_2` | Alternate (swap) right-hand skill ID (`dwRightSkill2`) |
| 0x0088       | 16           | `outfit[16]` | Character appearance configuration |
| 0x0098       | 16           | `colors[16]` | Character color palette settings |
| 0x00A8       | 3            | `town[3]` | Current town per difficulty (Normal, NM, Hell, `Town`) |
| 0x00AB       | 4            | `map_seed` | Random map generation seed (`dwMapSeed`) |
| 0x00AF       | 2            | `merc_flags_low` | Mercenary flags lower 16 bits (`mercFlagsLow`) |
| 0x00B1       | 1            | `merc_dead` | Mercenary dead flag (1=Dead, 0=Alive, `bMercDead`) |
| 0x00B2       | 1            | `merc_flags_high` | Mercenary flags upper 8 bits (`mercFlagsHigh`) |
| 0x00B3       | 4            | `merc_control` | Mercenary control seed/flag (`dwMercControl`) |
| 0x00B7       | 2            | `merc_name` | Mercenary name ID table index (`wMercName`) |
| 0x00B9       | 2            | `merc_type` | Mercenary hireling type / difficulty index (`wMercType`) |
| 0x00BB       | 4            | `merc_exp` | Mercenary accumulated experience points (`dwMercExp`) |
| 0x00BF       | 76           | `preview_prefix` | Preview metadata (equipment, guild emblem, XP, `previewPrefix`) |
| 0x010B       | 64           | `name_ptr` | D2R character name (UTF-8, null-terminated, `NamePTR`) |
| 0x014B       | 4            | `preview_suffix` | Preview metadata suffix (`previewSuffix`) |
| Variable     | Variable     | `quests` | Quest data block (`QuestInfo`) |
| Variable     | Variable     | `waypoints` | Waypoint activation block (`Waypoints`) |
| Variable     | 52           | `npc` | NPC introduction / talk state flags (0x34 bytes, `NPC`) |
| Variable     | Variable     | `player_stats` | Attributes block (`PlayerStats`) |
| Variable     | 32           | `skills` | Skill allocation block (`CharSkills`) |
| Variable     | Variable     | `item_list` | Inventory, equipped, and stash items (`ItemList`) |
| Variable     | Variable     | `corpse` | Player corpse item block (`Corpse`) |
| Variable     | Variable     | `mercenary` | Mercenary item block (`Mercenary`, expansion only) |
| Variable     | Variable     | `golem` | Iron Golem item data (`Golem`, expansion only) |

## 2. Character Type Flags (`char_flags` / `char_type`)

The character type byte at offset `0x0024` stores boolean gameplay flags:

| Bit | Mask | Flag | Description |
|-----|------|------|-------------|
| 0   | 0x01 | Init | Character initialized |
| 1   | 0x02 | RealmChar | Battle.net realm character |
| 2   | 0x04 | Hardcore | Hardcore character mode (permadeath) |
| 3   | 0x08 | Died | Character has died at least once |
| 4   | 0x10 | SaveProcess | Active save flag |
| 5   | 0x20 | Expansion | Lord of Destruction expansion character |
| 6   | 0x40 | Ladder | Ladder character |
| 7   | 0x80 | NeedsRenaming | Renaming required flag |

> In save version 0x63, character type flags fit in 1 byte (`charType`). In version 0x69, this is expanded to a 4-byte `charFlags` dword that incorporates progression in bits 8-12.

## 3. Character Class Identifiers (`charClass`)

| Value | Class |
|-------|-------|
| 0     | Amazon |
| 1     | Sorceress |
| 2     | Necromancer |
| 3     | Paladin |
| 4     | Barbarian |
| 5     | Druid |
| 6     | Assassin |

## 4. Character Name Resolution

In save version `0x63` (and any version `>= 0x62`), the game reads the character name from `NamePTR` (offset `0x010B`, 64 bytes) decoded as **UTF-8** rather than the legacy 16-byte ASCII field at offset `0x0014`:

```python
def get_char_name(self) -> str:
    if self.version >= 0x69:
        name_data = self.Name
    elif self.version >= 0x62:
        name_data = self.NamePTR
    else:
        name_data = self.Name
    null_pos = name_data.find(b'\x00')
    name_bytes = name_data[:null_pos] if null_pos != -1 else name_data
    if self.version >= 0x62:
        return name_bytes.decode('utf-8', errors='replace')
    return name_bytes.decode('ascii', errors='replace')
```

## 5. Quest Information (`QuestInfo`)

The quest block starts immediately after `preview_suffix` (offset `0x014F`):

| Field | Size (Bytes) | Description |
|-------|--------------|-------------|
| `magic` | 4 | Magic header (`0x21666F57` = ASCII "Woo!") |
| `acts` | 4 | Number of unlocked acts (typically 5 for expansion) |
| `size` | 2 | Quest data payload length (typically 298 bytes: `10 + 3 * 96`) |
| `qi_data[3]` | 96 x 3 | Per-difficulty quest data (Normal, Nightmare, Hell) |

### Per-Difficulty Quest Data (`QuestInfoData`, 96 Bytes)

| Field | Size (Bytes) | Description |
|-------|--------------|-------------|
| `introduced_1` | 2 | Act I intro dialogue flag (`wIntroduced1`) |
| `act_1[6]` | 12 | Act I quest state words (6 quests, `wActI`) |
| `travel_1` | 2 | Act I -> Act II transition flag |
| `introduced_2` | 2 | Act II intro dialogue flag (`wIntroduced2`) |
| `act_2[6]` | 12 | Act II quest state words (6 quests, `wActII`) |
| `travel_2` | 2 | Act II -> Act III transition flag |
| `introduced_3` | 2 | Act III intro dialogue flag (`wIntroduced3`) |
| `act_3[6]` | 12 | Act III quest state words (6 quests, `wActIII`) |
| `travel_3` | 2 | Act III -> Act IV transition flag |
| `introduced_4` | 2 | Act IV intro dialogue flag (`wIntroduced4`) |
| `act_4[3]` | 6 | Act IV quest state words (3 quests, `wActIV`) |
| `travel_4` | 2 | Act IV -> Act V transition flag |
| `unknown1[3]` | 6 | Padding / reserved |
| `introduced_5` | 2 | Act V intro dialogue flag (`wIntroduced5`) |
| `unknown2[2]` | 4 | Padding / reserved |
| `act_5[6]` | 12 | Act V quest state words (6 quests, `wActV`) |
| `reset_stats` | 1 | Akara stat/skill reset available flag (`bResetStats`) |
| `unknown3` | 1 | Padding / reserved |
| `unknown4[6]` | 12 | Reserved trailing words |

## 6. Waypoints (`Waypoints`)

Refer to [waypoint_format.md](waypoint_format.md) for full bitmask details.

| Field | Size (Bytes) | Description |
|-------|--------------|-------------|
| `magic` | 2 | Magic identifier (`0x5357` = ASCII "WS") |
| `unknown` | 4 | Section version (always `1`) |
| `size` | 2 | Section size (`0x0050` = 80 bytes) |
| `wp[3]` | 72 | 3 difficulty waypoint structures (24 bytes each, `WaypointData`) |

## 7. Player Attributes (`PlayerStats`)

Refer to [0x63_player_stat.md](0x63_player_stat.md) for full attribute unpacking details.

- Magic identifier: `0x6667` (ASCII "gf")
- Bitstream sequence of 9-bit stat IDs and variable-length values.
- Terminated by a 9-bit ID `>= 0x10`.

## 8. Character Skills (`CharSkills`)

| Field | Size (Bytes) | Description |
|-------|--------------|-------------|
| `magic` | 2 | Magic identifier (`0x6669` = ASCII "if", `wMagic`) |
| `skill_levels[30]` | 30 | Base skill points allocated per skill (1 byte each, `bSkillLevel`) |

## 9. Items Block (`ItemList`)

Refer to [0x63_itemlist_format.md](0x63_itemlist_format.md).

- Magic identifier: `0x4D4A` (ASCII "JM")
- `count` (2 bytes): Number of items in list
- Followed by sequentially serialized items (`D2Item`).

## 10. Corpse Items (`Corpse`)

| Field | Size (Bytes) | Description |
|-------|--------------|-------------|
| `magic` | 2 | Magic identifier (`0x4D4A` = ASCII "JM", `wMagic`) |
| `count` | 2 | Corpse count (0 or 1, `wCount`) |
| `corpse_data` | Variable | If `count > 0`: 12-byte header + `ItemList` (`pCorpseData`) |

## 11. Mercenary Gear (`Mercenary`)

Present only when `is_expansion()` is True:

| Field | Size (Bytes) | Description |
|-------|--------------|-------------|
| `magic` | 2 | Magic identifier (`0x666A` = ASCII "jf", `wMagic`) |
| `items` | Variable | `ItemList` containing mercenary equipped items (`stItems`) |

Presence detection in 0x63:
```python
def has_mercenary(self) -> bool:
    if self.version >= 0x61:
        return self.merc_control != 0
    return self.merc_name > 0
```

## 12. Iron Golem Item (`Golem`)

Present only when `is_expansion()` is True:

| Field | Size (Bytes) | Description |
|-------|--------------|-------------|
| `magic` | 2 | Magic identifier (`0x666B` or `0x6669`, `wMagic`) |
| `has_golem` | 1 | Boolean flag (1 = Active Golem, 0 = None, `bHasGolem`) |
| `item` | Variable | If `has_golem`: serialized `D2Item` (`pItem`) |

## 13. CRC Checksum Calculation

Diablo II uses a 32-bit rotational checksum algorithm over the entire save file bytes, skipping the 4 checksum bytes at offsets `0x000C..0x000F`:

```python
def calculate_checksum(self, data: bytes) -> int:
    checksum = 0
    for i, b in enumerate(data):
        if 0x0C <= i < 0x10:
            b = 0
        checksum = ((checksum << 1) | (checksum >> 31)) + b
        checksum &= 0xFFFFFFFF
    return checksum
```
