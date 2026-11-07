# Item Flags Format Specification

## 1. Overview

Diablo II and Diablo II: Resurrected items store status and behavior flags in their header. The deserialization mechanism depends on the format version:

- **D2R Format (`version >= 0x61`)**: Reads a 32-bit `flags` dword at once, extracting individual flags via bitwise masking.
- **Classic Format (`version < 0x61`)**: Reads individual bitfields sequentially from the bitstream.

## 2. D2R 32-Bit Flags (`version >= 0x61`)

In D2R save versions `0x63` and `0x69`, the 32-bit `flags` dword is unpacked with bitwise AND operations:

| Bit | Hex Mask | Field | Description |
|-----|----------|-------|-------------|
| 0   | `0x00000001` | `NewItem` | Newly generated item flag |
| 1   | `0x00000002` | `Target` | Target state |
| 2   | `0x00000004` | `Targeting` | Targeting state |
| 3   | `0x00000008` | `Deleted` | Marked for deletion |
| 4   | `0x00000010` | `is_identified` | Item is identified |
| 5   | `0x00000020` | `_bHasQuantity` | Stack quantity is present |
| 6   | `0x00000040` | `SwitchIn` | Active during weapon swap set 1 |
| 7   | `0x00000080` | `SwitchOut` | Active during weapon swap set 2 |
| 8   | `0x00000100` | `Broken` / `bDisabled` | Broken / zero durability |
| 9   | `0x00000200` | `Repaired` | Repaired state |
| 10  | `0x00000400` | (undefined) | Reserved |
| 11  | `0x00000800` | `is_socketed` | Item contains or can hold sockets |
| 12  | `0x00001000` | `bNoSell` | Cannot be sold to vendors |
| 13  | `0x00002000` | `bNew` / `InStore` | In vendor store inventory |
| 14  | `0x00004000` | `bBadEquipped` / `NoEquip` | Cannot be equipped |
| 15  | `0x00008000` | `bNamed` | Personalized / named item |
| 16  | `0x00010000` | `is_ear` | Item is a player PvP ear |
| 17  | `0x00020000` | `bNewbie` / `StarterItem` | Starter character equipment |
| 18  | `0x00040000` | (undefined) | Reserved |
| 19  | `0x00080000` | `Init` | Engine initialization flag |
| 20  | `0x00100000` | (undefined) | Reserved |
| 21  | `0x00200000` | `is_simple` / `CompactSave` | Compact save format (no ext info / props) |
| 22  | `0x00400000` | `is_ethereal` | Ethereal item (cannot be repaired) |
| 23  | `0x00800000` | `bJustSaved` | Save state marker |
| 24  | `0x01000000` | `is_personalized` | Personalized by Anya |
| 25  | `0x02000000` | `bLowQuality` / `Gamble` | Low quality or gamble item |
| 26  | `0x04000000` | `is_runeword` | Active runeword with extra properties |
| 27  | `0x08000000` | `Duplicated` | Duplicated item flag |
| 28  | `0x10000000` | `_bChronicle` | Holy Grail chronicle tracking flag |
| 29  | `0x20000000` | `_bChronicleCompact` | Compact chronicle entry |
| 30  | `0x40000000` | (undefined) | Reserved |
| 31  | `0x80000000` | (undefined) | Reserved |

### D2R Deserialization Logic
```python
flags = bs.read_bits(32)
self._flags = flags
self.is_identified = bool(flags & 0x00000010)
self._bHasQuantity = bool(flags & 0x00000020)
self.is_socketed = bool(flags & 0x00000800)
self.is_ear = bool(flags & 0x00010000)
self.bNewbie = bool(flags & 0x00020000)
self.is_simple = bool(flags & 0x00200000)
self.is_ethereal = bool(flags & 0x00400000)
self.is_personalized = bool(flags & 0x01000000)
self.is_runeword = bool(flags & 0x04000000)
self._bChronicle = bool(flags & 0x10000000)
self._bChronicleCompact = bool(flags & 0x20000000)
```

## 3. Classic Sequential Bitstream Flags (`version < 0x61`)

In legacy Classic saves (`_read_data_classic`), flags are read one bitfield at a time in exact order:

| Order | Bit Width | Field | Description |
|-------|-----------|-------|-------------|
| 1     | 1 | `bQuest` | Quest item flag |
| 2     | 3 | `iTargetDelFlags` | Target / deletion state |
| 3     | 1 | `is_identified` | Identified flag |
| 4     | 3 | `iSwitchInOutFlags` | Weapon swap state |
| 5     | 1 | `bDisabled` | Broken / zero durability |
| 6     | 2 | `iRepairFlags` | Repair state |
| 7     | 1 | `is_socketed` | Socketed flag |
| 8     | 1 | `bNoSell` | Cannot sell |
| 9     | 1 | `bNew` | Vendor shop item |
| 10    | 1 | `bBadEquipped` | Cannot equip |
| 11    | 1 | `bNamed` | Named / personalized |
| 12    | 1 | `is_ear` | PvP ear |
| 13    | 1 | `bNewbie` | Starter equipment |
| 14    | 3 | `iInitFlags` | Init flags |
| 15    | 1 | `is_simple` | Compact format |
| 16    | 1 | `is_ethereal` | Ethereal |
| 17    | 1 | `bJustSaved` | Saved state |
| 18    | 1 | `is_personalized` | Personalized |
| 19    | 1 | `bLowQuality` | Low quality / gamble |
| 20    | 1 | `is_runeword` | Runeword |
| 21    | 5 | `iDuplicateChronicle` | Duplicate / chronicle bits |
| 22    | 10| `wVersion` | Classic item format version |

The 21 flag bitfields total 32 bits (`1+3+1+3+1+2+1+1+1+1+1+1+1+3+1+1+1+1+1+1+5 = 32`), directly mirroring the D2R packed word layout.

## 4. Human-Readable Flag Reporting

The `D2Item.get_flag_names()` method returns human-readable labels matching `ITEM_FLAG_LABELS`:

```python
ITEM_FLAG_LABELS = [
    ("is_identified", "Identified"),
    ("is_socketed", "Socketed"),
    ("is_ethereal", "Ethereal"),
    ("is_runeword", "RuneWord"),
    ("is_personalized", "Personalized"),
    ("bQuest", "Quest"),
    ("bNoSell", "NoSell"),
    ("bNamed", "Named"),
    ("bJustSaved", "JustSaved"),
    ("bLowQuality", "LowQuality"),
    ("bDisabled", "Broken"),
    ("bNew", "InStore"),
    ("bBadEquipped", "NoEquip"),
    ("bNewbie", "StarterItem"),
]
```
