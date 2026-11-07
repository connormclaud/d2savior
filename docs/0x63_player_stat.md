# Player Stats Block Format (0x63 and 0x69)

## 1. Structure Overview

Player attributes and resources are stored in a compressed bitstream block in the character save file (`.d2s`), marked by a 16-bit magic number:

| Field | Size | Description |
|-------|------|-------------|
| `magic` | 16 bits | Section identifier (`0x6667` = ASCII "gf") |
| Attribute Data | Variable | Sequential (9-bit ID + variable-length value) pairs |
| Terminator | 9 bits | Stop marker (`stat_id >= 0x10`, typically `0x1FF`) |
| Alignment | 0-7 bits | Byte boundary alignment (`bs.align_byte()`) |

> Note: Both version 0x63 and 0x69 use the exact same player stats block format and attribute IDs.

## 2. Attribute IDs and Bit Widths

Attributes are stored in ascending order of their 9-bit ID. Unallocated or zeroed attributes may be omitted from the stream.

The bit lengths are defined by `PLAYER_STATS_BITS_COUNT`:

```python
PLAYER_STATS_BITS_COUNT = [
    10,  # 0:  Strength
    10,  # 1:  Energy
    10,  # 2:  Dexterity
    10,  # 3:  Vitality
    10,  # 4:  Stat points remaining
    8,   # 5:  Skill points remaining
    21,  # 6:  Current Life (fixed-point 256ths)
    21,  # 7:  Max Life (fixed-point 256ths)
    21,  # 8:  Current Mana (fixed-point 256ths)
    21,  # 9:  Max Mana (fixed-point 256ths)
    21,  # 10: Current Stamina (fixed-point 256ths)
    21,  # 11: Max Stamina (fixed-point 256ths)
    7,   # 12: Level (1 - 99)
    32,  # 13: Experience
    25,  # 14: Gold (Inventory)
    25,  # 15: Gold (Personal Stash)
]
```

### Table of Attributes

| ID | Attribute Name | Bit Width | Description |
|----|----------------|-----------|-------------|
| 0  | Strength | 10 | Base strength attribute |
| 1  | Energy | 10 | Base energy attribute |
| 2  | Dexterity | 10 | Base dexterity attribute |
| 3  | Vitality | 10 | Base vitality attribute |
| 4  | Stat Points | 10 | Unspent attribute stat points |
| 5  | Skill Points | 8 | Unspent skill points |
| 6  | Current HP | 21 | Current life (`display_value = raw_value >> 8`) |
| 7  | Max HP | 21 | Maximum life (`display_value = raw_value >> 8`) |
| 8  | Current Mana | 21 | Current mana (`display_value = raw_value >> 8`) |
| 9  | Max Mana | 21 | Maximum mana (`display_value = raw_value >> 8`) |
| 10 | Current Stamina| 21 | Current stamina (`display_value = raw_value >> 8`) |
| 11 | Max Stamina | 21 | Maximum stamina (`display_value = raw_value >> 8`) |
| 12 | Level | 7 | Character level (1 - 99) |
| 13 | Experience | 32 | Total accumulated experience |
| 14 | Gold (Inventory)| 25 | Gold carried on character |
| 15 | Gold (Stash) | 25 | Gold in personal character stash |

## 3. Fixed-Point HP, Mana, and Stamina Representation

Life, Mana, and Stamina are stored as 21-bit fixed-point integers representing 256ths of a point (8 fractional bits). To calculate the integer display value visible in game:

```
display_value = raw_value >> 8
```

For example, a raw current life value of `0x1400` (5120 decimal) yields `5120 >> 8 = 20` HP.

## 4. Deserialization & Serialization Reference

```python
class PlayerStats:
    def deserialize(self, bs):
        self.magic = bs.read_word()
        if self.magic != PLAYER_STATS_MAGIC:
            return
        self.stat_values = [0] * 0x10
        while True:
            try:
                stat_id = bs.read_bits(9)
                if stat_id >= 0x10:
                    break
                self.stat_values[stat_id] = bs.read_bits(PLAYER_STATS_BITS_COUNT[stat_id])
            except ValueError:
                break
        bs.align_byte()

    def serialize(self, bs):
        bs.write_word(self.magic)
        for i in range(0x10):
            if self.stat_values[i] != 0:
                bs.write_bits(9, i)
                bs.write_bits(PLAYER_STATS_BITS_COUNT[i], self.stat_values[i])
        bs.write_bits(9, 0x1FF)
        bs.align_byte()
```

## 5. Model Properties

The `PlayerStats` class exposes Python properties for direct attribute access:

- `strength`, `energy`, `dexterity`, `vitality`
- `stat_points_remaining`, `skill_points_remaining`
- `current_life`, `max_life` (auto-shifted `>> 8`)
- `current_mana`, `max_mana` (auto-shifted `>> 8`)
- `current_stamina`, `max_stamina` (auto-shifted `>> 8`)
- `level`, `experience`
- `gold`, `gold_stash`
