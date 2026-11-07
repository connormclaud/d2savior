# Waypoints Format Specification

## 1. Overview

The waypoint data section tracks unlocked waypoints across all three difficulties (Normal, Nightmare, and Hell). Both save versions `0x63` and `0x69` use the identical 80-byte binary format.

## 2. Waypoints Block (`Waypoints`, 80 Bytes)

| Field | Size (Bytes) | Description |
|-------|--------------|-------------|
| `magic` | 2 | Magic identifier (`0x5357` = ASCII "WS") |
| `unknown` | 4 | Section version identifier (constant `1`) |
| `size` | 2 | Total section length in bytes (`0x0050` = 80 decimal) |
| `wp[0]` | 24 | Normal difficulty waypoint data (`WaypointData`) |
| `wp[1]` | 24 | Nightmare difficulty waypoint data (`WaypointData`) |
| `wp[2]` | 24 | Hell difficulty waypoint data (`WaypointData`) |

## 3. Per-Difficulty Waypoint Data (`WaypointData`, 24 Bytes)

| Field | Size (Bytes) | Description |
|-------|--------------|-------------|
| `unknown` | 2 | Header constant (`0x0102`) |
| `Waypoints[5]` | 5 | 40-bit bitfield (39 active waypoints + 1 padding bit) |
| `unknown2[17]`| 17 | Trailing reserved bytes (zeroed) |

## 4. Waypoint Bitfield Mapping (39 Waypoints)

The 5-byte `Waypoints` array stores a 39-bit mask of unlocked waypoints in order across Acts I through V:

```
Byte 0: Act I waypoints 0..7
Byte 1: Act I waypoint 8 + Act II waypoints 0..6
Byte 2: Act II waypoints 7..8 + Act III waypoints 0..5
Byte 3: Act III waypoints 6..8 + Act IV waypoints 0..2 + Act V waypoints 0..1
Byte 4: Act V waypoints 2..8 (bit 7 is unused padding)
```

### Complete Waypoint Directory (`WAYPOINTS_BY_ACT`)

#### Act I (9 Waypoints, Global Indices 0 - 8)
| Bit (Act) | Global Index | Waypoint Name |
|-----------|--------------|---------------|
| 0 | 0 | Rogue Encampment |
| 1 | 1 | Cold Plains |
| 2 | 2 | Stony Field |
| 3 | 3 | Dark Wood |
| 4 | 4 | Black Marsh |
| 5 | 5 | Outer Cloister |
| 6 | 6 | Jail Level 1 |
| 7 | 7 | Inner Cloister |
| 8 | 8 | Catacombs Level 2 |

#### Act II (9 Waypoints, Global Indices 9 - 17)
| Bit (Act) | Global Index | Waypoint Name |
|-----------|--------------|---------------|
| 0 | 9 | Lut Gholein |
| 1 | 10 | Sewers Level 2 |
| 2 | 11 | Dry Hills |
| 3 | 12 | Halls of the Dead Level 2 |
| 4 | 13 | Far Oasis |
| 5 | 14 | Lost City |
| 6 | 15 | Palace Cellar Level 1 |
| 7 | 16 | Arcane Sanctuary |
| 8 | 17 | Canyon of the Magi |

#### Act III (9 Waypoints, Global Indices 18 - 26)
| Bit (Act) | Global Index | Waypoint Name |
|-----------|--------------|---------------|
| 0 | 18 | Kurast Docks |
| 1 | 19 | Spider Forest |
| 2 | 20 | Great Marsh |
| 3 | 21 | Flayer Jungle |
| 4 | 22 | Lower Kurast |
| 5 | 23 | Kurast Bazaar |
| 6 | 24 | Upper Kurast |
| 7 | 25 | Travincal |
| 8 | 26 | Durance of Hate Level 2 |

#### Act IV (3 Waypoints, Global Indices 27 - 29)
| Bit (Act) | Global Index | Waypoint Name |
|-----------|--------------|---------------|
| 0 | 27 | The Pandemonium Fortress |
| 1 | 28 | City of the Damned |
| 2 | 29 | River of Flame |

#### Act V (9 Waypoints, Global Indices 30 - 38)
| Bit (Act) | Global Index | Waypoint Name |
|-----------|--------------|---------------|
| 0 | 30 | Harrogath |
| 1 | 31 | Frigid Highlands |
| 2 | 32 | Arreat Plateau |
| 3 | 33 | Crystalline Passage |
| 4 | 34 | Glacial Trail |
| 5 | 35 | Halls of Pain |
| 6 | 36 | Frozen Tundra |
| 7 | 37 | The Ancients' Way |
| 8 | 38 | Worldstone Keep Level 2 |

## 5. Bitwise Verification and Progress Check

### Bit Index Calculation
To check or modify any waypoint by its global index (0 to 38):

```python
def is_waypoint_unlocked(wp_data: WaypointData, global_idx: int) -> bool:
    if not (0 <= global_idx <= 38):
        return False
    byte_idx = global_idx // 8
    bit_idx = global_idx % 8
    return bool(wp_data.Waypoints[byte_idx] & (1 << bit_idx))

def unlock_waypoint(wp_data: WaypointData, global_idx: int) -> None:
    byte_idx = global_idx // 8
    bit_idx = global_idx % 8
    wp_data.Waypoints[byte_idx] |= (1 << bit_idx)
```

### Difficulty Progress Detection
Because the Rogue Encampment waypoint (bit 0) is default-enabled on newly created characters, detection of real progression beyond the starter town checks:

```python
has_wp_progress = (wp_data.Waypoints[0] & ~1) != 0 or any(b != 0 for b in wp_data.Waypoints[1:])
```

## 6. Relation to Act Travel Flags

Transitioning between acts also updates the transition flags in `QuestInfoData`:
- `travel_1`: Traveled from Act I to Act II
- `travel_2`: Traveled from Act II to Act III
- `travel_3`: Traveled from Act III to Act IV
- `travel_4`: Traveled from Act IV to Act V
