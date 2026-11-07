# Item Flags Format Specification

## 1. Overview

Diablo II and Diablo II: Resurrected items store status and behavior flags in their header. The deserialization mechanism depends on the format version:

- **D2R Format (`version >= 0x61`)**: Reads a 32-bit `flags` dword at once, extracting individual flags via bitwise masking.
- **Classic Format (`version < 0x61`)**: Reads individual bitfields sequentially from the bitstream.

## 2. D2R 32-Bit Flags (`version >= 0x61`)

In D2R save versions `0x63` and `0x69`, the 32-bit `flags` dword is unpacked with bitwise AND operations:

| Bit | Hex Mask | Field | Description |
|-----|----------|-------|-------------|
| 0   | `0x00000001` | `new_item` | Newly generated item flag |
| 1   | `0x00000002` | `target` | Target state |
| 2   | `0x00000004` | `targeting` | Targeting state |
| 3   | `0x00000008` | `deleted` | Marked for deletion |
| 4   | `0x00000010` | `is_identified` | Item is identified |
| 5   | `0x00000020` | `_has_quantity` | Stack quantity is present (`_bHasQuantity`) |
| 6   | `0x00000040` | `switch_in` | Active during weapon swap set 1 |
| 7   | `0x00000080` | `switch_out` | Active during weapon swap set 2 |
| 8   | `0x00000100` | `is_disabled` | Broken / zero durability (`Broken` / `bDisabled`) |
| 9   | `0x00000200` | `repaired` | Repaired state |
| 10  | `0x00000400` | (undefined) | Reserved |
| 11  | `0x00000800` | `is_socketed` | Item contains or can hold sockets |
| 12  | `0x00001000` | `is_no_sell` | Cannot be sold to vendors (`bNoSell`) |
| 13  | `0x00002000` | `is_new` | In vendor store inventory (`bNew` / `InStore`) |
| 14  | `0x00004000` | `is_bad_equipped` | Cannot be equipped (`bBadEquipped` / `NoEquip`) |
| 15  | `0x00008000` | `is_named` | Personalized / named item (`bNamed`) |
| 16  | `0x00010000` | `is_ear` | Item is a player PvP ear |
| 17  | `0x00020000` | `is_newbie` | Starter character equipment (`bNewbie` / `StarterItem`) |
| 18  | `0x00040000` | (undefined) | Reserved |
| 19  | `0x00080000` | `init` | Engine initialization flag |
| 20  | `0x00100000` | (undefined) | Reserved |
| 21  | `0x00200000` | `is_simple` | Compact save format (no ext info / props, `CompactSave`) |
| 22  | `0x00400000` | `is_ethereal` | Ethereal item (cannot be repaired) |
| 23  | `0x00800000` | `is_just_saved` | Save state marker (`bJustSaved`) |
| 24  | `0x01000000` | `is_personalized` | Personalized by Anya |
| 25  | `0x02000000` | `is_low_quality` | Low quality or gamble item (`bLowQuality` / `Gamble`) |
| 26  | `0x04000000` | `is_runeword` | Active runeword with extra properties |
| 27  | `0x08000000` | `duplicated` | Duplicated item flag |
| 28  | `0x10000000` | `_is_chronicle` | Holy Grail chronicle tracking flag (`_bChronicle`) |
| 29  | `0x20000000` | `_is_chronicle_compact` | Compact chronicle entry (`_bChronicleCompact`) |
| 30  | `0x40000000` | (undefined) | Reserved |
| 31  | `0x80000000` | (undefined) | Reserved |

### D2R Deserialization Logic
```python
flags = bs.read_bits(32)
self._flags = flags
self.is_identified = bool(flags & 0x00000010)
self._has_quantity = bool(flags & 0x00000020)
self.is_socketed = bool(flags & 0x00000800)
self.is_ear = bool(flags & 0x00010000)
self.is_newbie = bool(flags & 0x00020000)
self.is_simple = bool(flags & 0x00200000)
self.is_ethereal = bool(flags & 0x00400000)
self.is_personalized = bool(flags & 0x01000000)
self.is_runeword = bool(flags & 0x04000000)
self._is_chronicle = bool(flags & 0x10000000)
self._is_chronicle_compact = bool(flags & 0x20000000)
```

## 3. Classic Sequential Bitstream Flags (`version < 0x61`)

In legacy Classic saves (`_read_data_classic`), flags are read one bitfield at a time in exact order:

| Order | Bit Width | Field | Description |
|-------|-----------|-------|-------------|
| 1     | 1 | `is_quest` | Quest item flag (`bQuest`) |
| 2     | 3 | `target_del_flags` | Target / deletion state (`iTargetDelFlags`) |
| 3     | 1 | `is_identified` | Identified flag |
| 4     | 3 | `switch_in_out_flags` | Weapon swap state (`iSwitchInOutFlags`) |
| 5     | 1 | `is_disabled` | Broken / zero durability (`bDisabled`) |
| 6     | 2 | `repair_flags` | Repair state (`iRepairFlags`) |
| 7     | 1 | `is_socketed` | Socketed flag |
| 8     | 1 | `is_no_sell` | Cannot sell (`bNoSell`) |
| 9     | 1 | `is_new` | Vendor shop item (`bNew`) |
| 10    | 1 | `is_bad_equipped` | Cannot equip (`bBadEquipped`) |
| 11    | 1 | `is_named` | Named / personalized (`bNamed`) |
| 12    | 1 | `is_ear` | PvP ear |
| 13    | 1 | `is_newbie` | Starter equipment (`bNewbie`) |
| 14    | 3 | `init_flags` | Init flags (`iInitFlags`) |
| 15    | 1 | `is_simple` | Compact format |
| 16    | 1 | `is_ethereal` | Ethereal |
| 17    | 1 | `is_just_saved` | Saved state (`bJustSaved`) |
| 18    | 1 | `is_personalized` | Personalized |
| 19    | 1 | `is_low_quality` | Low quality / gamble (`bLowQuality`) |
| 20    | 1 | `is_runeword` | Runeword |
| 21    | 5 | `duplicate_chronicle` | Duplicate / chronicle bits (`iDuplicateChronicle`) |
| 22    | 10| `item_version` | Classic item format version (`wVersion`) |

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
    ("is_quest", "Quest"),
    ("is_no_sell", "NoSell"),
    ("is_named", "Named"),
    ("is_just_saved", "JustSaved"),
    ("is_low_quality", "LowQuality"),
    ("is_disabled", "Broken"),
    ("is_new", "InStore"),
    ("is_bad_equipped", "NoEquip"),
    ("is_newbie", "StarterItem"),
]
```
