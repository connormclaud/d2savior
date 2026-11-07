import os
from collections.abc import Buffer, Iterator
from dataclasses import dataclass, field
from itertools import batched
from typing import Any, ClassVar

from core.enums import ITEM_LIST_MAGIC
from core.huffman import get_huffman
from core.ibitstream import IBitStream
from core.obitstream import OBitStream

type RawProperty = tuple[int, int, int]
type ItemTypeId = Buffer | str


def is_d2r(version: int) -> bool:
    return version >= 0x61


def _convert_item_type_to_meta(type_info: Any, d2data: Any = None) -> ItemMetaData | None:
    if type_info is None:
        return None

    meta = ItemMetaData()
    meta.type_id = type_info.code.encode("ascii").ljust(4)[:4]
    meta.name = type_info.name

    meta.simple = type_info.compactsave
    meta.normal = type_info.spawnable
    meta.white = not type_info.rarity or type_info.rarity == 1

    meta.has_def = type_info.item_type == "armor"
    meta.has_dur = not type_info.nodurability and type_info.durability > 0
    meta.is_stacked = type_info.stackable

    meta.is_charm = type_info.item_type2 in ["char", "charmed"]
    meta.spell_id = type_info.spell_id if type_info.spell_id > 0 else 0

    meta.is_gem = type_info.item_type2 in ["gem", "gem2"]
    meta.is_unique = type_info.rarity == 7
    meta.is_craft = type_info.item_type2 == "craft"

    if d2data is not None and type_info.item_type2:
        meta.is_scroll_or_book = d2data.is_descendant(
            type_info.item_type2, "scro"
        ) or d2data.is_descendant(type_info.item_type2, "book")
        meta.is_body_part = d2data.is_descendant(type_info.item_type2, "body")
        meta.is_player_body_part = d2data.is_descendant(type_info.item_type2, "play")
        if d2data.is_descendant(type_info.item_type2, "armo"):
            meta.has_def = True

    meta.dmg1_min = type_info.mindam
    meta.dmg1_max = type_info.maxdam
    meta.dmg2_min = type_info.minmisdam
    meta.dmg2_max = type_info.maxmisdam

    return meta


def is_ptr24_and_above(version: int) -> bool:
    return version >= 0x62


VALID_VERSIONS = [0x69, 0x63, 0x62, 0x61, 0x60, 0x5C, 0x59, 0x57, 0x47]


def is_valid_version(version: int) -> bool:
    return version in VALID_VERSIONS


@dataclass(slots=True)
class PropertyField:
    bits: int = 0
    base: int = 0
    min_val: int = 0
    max_val: int = 0


@dataclass(slots=True)
class PropertyMetaDataItem:
    ver_min: int = 0
    fields: list[PropertyField] = field(default_factory=list)
    default_value: int = 0
    bits_sum: int = 0

    def parse(self, value: int) -> list[int]:
        result = []
        remaining = value
        for f in self.fields:
            if f.bits > 0:
                mask = (1 << f.bits) - 1
                v = remaining & mask
                result.append(v + f.base)
                remaining >>= f.bits
            else:
                result.append(0)
        return result

    def get_value(self, params: list[int]) -> tuple[bool, int]:
        if len(params) != len(self.fields):
            return False, 0
        value = 0
        bit_pos = 0
        for i, f in enumerate(self.fields):
            if f.bits > 0:
                v = params[i] - f.base
                if v < 0 or v >= (1 << f.bits):
                    return False, 0
                value += v << bit_pos
                bit_pos += f.bits
        return True, value


class PropertyMetaData:
    def __init__(self) -> None:
        self._data: list[PropertyMetaDataItem] = []

    def add_item(self, item: PropertyMetaDataItem) -> None:
        self._data.append(item)

    def find_data(self, version: int) -> PropertyMetaDataItem | None:
        best_match = None
        best_ver_min = -1
        for item in self._data:
            if item.ver_min <= version and item.ver_min > best_ver_min:
                best_match = item
                best_ver_min = item.ver_min
        # If no match found, return the last item (matching C++ behavior)
        if best_match is None and self._data:
            return self._data[-1]
        return best_match


@dataclass(slots=True)
class ItemMetaData:
    type_id: bytes = b"    "
    ver_min: int = 0
    name: str = ""
    pic_index: int = 0
    name_index: int = 0
    equip: int = 0
    range_val: int = 0
    simple: bool = False
    normal: bool = False
    white: bool = False
    is_new: bool = False
    has_def: bool = False
    has_dur: bool = False
    is_stacked: bool = False
    has_monster_id: bool = False
    is_charm: bool = False
    is_scroll_or_book: bool = False
    is_body_part: bool = False
    is_player_body_part: bool = False
    spell_id: int = 0
    is_unique: bool = False
    is_craft: bool = False
    is_gem: bool = False
    dmg1_min: int = 0
    dmg1_max: int = 0
    dmg2_min: int = 0
    dmg2_max: int = 0
    ipad_bits: int = 0
    ipad: int = 0

    @property
    def type_name(self) -> str:
        return self.type_id.decode("ascii", errors="replace").strip()


class ItemMetaDataManager:
    def __init__(self) -> None:
        self._items: dict[bytes, list[ItemMetaData]] = {}

    def add_item(self, item: ItemMetaData) -> None:
        if item.type_id not in self._items:
            self._items[item.type_id] = []
        self._items[item.type_id].append(item)

    def get_item(self, type_id: ItemTypeId, version: int = 0) -> ItemMetaData | None:
        items = self._items.get(type_id)
        if not items:
            return None

        best_match = None
        best_ver_min = -1
        for item in items:
            if item.ver_min <= version and item.ver_min > best_ver_min:
                best_match = item
                best_ver_min = item.ver_min

        if best_match is None and items:
            return items[-1]
        return best_match

    def get_item_by_name(self, name: str, version: int = 0) -> ItemMetaData | None:
        padded_name = name.ljust(4)[:4].encode("ascii")
        return self.get_item(padded_name, version)


def parse_property_txt(filepath: str) -> dict[int, PropertyMetaData]:
    properties: dict[int, PropertyMetaData] = {}

    if not os.path.exists(filepath):
        return properties

    with open(filepath, encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    for line in lines:
        line = line.strip()
        if not line or line.startswith("*"):
            continue

        parts = line.split("\t")
        if len(parts) < 1:
            continue

        try:
            prop_id = int(parts[0])
        except ValueError:
            continue

        ver_min = 0
        if len(parts) > 1 and parts[1]:
            if parts[1].startswith("0x"):
                ver_min = int(parts[1], 16)
            else:
                try:
                    ver_min = int(parts[1])
                except ValueError:
                    ver_min = 0

        default_value = 0
        if len(parts) > 2 and parts[2]:
            if parts[2].startswith("0x"):
                default_value = int(parts[2], 16)
            else:
                try:
                    default_value = int(parts[2])
                except ValueError:
                    default_value = 0

        fields: list[PropertyField] = []
        bits_sum = 0

        for chunk in batched(parts[3:], 4, strict=False):
            bits_str = chunk[0]
            if not bits_str:
                break

            try:
                bits = int(bits_str)
                base_str = chunk[1] if len(chunk) > 1 else ""
                min_str = chunk[2] if len(chunk) > 2 else ""
                max_str = chunk[3] if len(chunk) > 3 else ""

                base = int(base_str) if base_str else 0
                min_val = int(min_str) if min_str else 0
                max_val = int(max_str) if max_str else 0

                fields.append(PropertyField(bits, base, min_val, max_val))
                bits_sum += bits
            except ValueError:
                break

        while len(fields) < 4:
            fields.append(PropertyField())

        item = PropertyMetaDataItem(ver_min, fields, default_value, bits_sum)

        if prop_id not in properties:
            properties[prop_id] = PropertyMetaData()
        properties[prop_id].add_item(item)

    return properties


def parse_itemdata_txt(filepath: str) -> ItemMetaDataManager:
    manager = ItemMetaDataManager()

    if not os.path.exists(filepath):
        return manager

    with open(filepath, encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    has_version_min = False
    for line in lines:
        if line.strip().startswith("*ID"):
            if "VersionMin" in line:
                has_version_min = True
            break

    for line in lines:
        line = line.strip()
        if not line or line.startswith("*"):
            continue

        parts = line.split("\t")
        if len(parts) < 2:
            continue

        type_id = parts[0].ljust(4)[:4].encode("ascii")

        def parse_int(s: str, default: int = 0) -> int:
            if not s:
                return default
            try:
                return int(s)
            except ValueError:
                return default

        def parse_bool(s: str) -> bool:
            return s == "1"

        def parse_version(s: str) -> int:
            if not s:
                return 0
            if s.startswith("0x"):
                return int(s, 16)
            try:
                return int(s)
            except ValueError:
                return 0

        idx_offset = 1 if has_version_min else 0

        ver_min = parse_version(parts[1]) if has_version_min and len(parts) > 1 else 0

        item = ItemMetaData(
            type_id=type_id,
            ver_min=ver_min,
            pic_index=parse_int(parts[1 + idx_offset]) if len(parts) > 1 + idx_offset else 0,
            name_index=parse_int(parts[2 + idx_offset]) if len(parts) > 2 + idx_offset else 0,
            range_val=parse_int(parts[3 + idx_offset]) if len(parts) > 3 + idx_offset else 0,
            equip=parse_int(parts[4 + idx_offset]) if len(parts) > 4 + idx_offset else 0,
            simple=parse_bool(parts[5 + idx_offset]) if len(parts) > 5 + idx_offset else False,
            normal=parse_bool(parts[6 + idx_offset]) if len(parts) > 6 + idx_offset else False,
            white=parse_bool(parts[7 + idx_offset]) if len(parts) > 7 + idx_offset else False,
            is_new=parse_bool(parts[8 + idx_offset]) if len(parts) > 8 + idx_offset else False,
            has_def=parse_bool(parts[9 + idx_offset]) if len(parts) > 9 + idx_offset else False,
            has_dur=parse_bool(parts[10 + idx_offset]) if len(parts) > 10 + idx_offset else False,
            is_stacked=parse_bool(parts[11 + idx_offset])
            if len(parts) > 11 + idx_offset
            else False,
            has_monster_id=parse_bool(parts[12 + idx_offset])
            if len(parts) > 12 + idx_offset
            else False,
            is_charm=parse_bool(parts[13 + idx_offset]) if len(parts) > 13 + idx_offset else False,
            spell_id=parse_int(parts[14 + idx_offset]) if len(parts) > 14 + idx_offset else 0,
            is_unique=parse_bool(parts[15 + idx_offset]) if len(parts) > 15 + idx_offset else False,
            is_craft=parse_bool(parts[16 + idx_offset]) if len(parts) > 16 + idx_offset else False,
            is_gem=parse_bool(parts[17 + idx_offset]) if len(parts) > 17 + idx_offset else False,
            dmg1_min=parse_int(parts[18 + idx_offset]) if len(parts) > 18 + idx_offset else 0,
            dmg1_max=parse_int(parts[19 + idx_offset]) if len(parts) > 19 + idx_offset else 0,
            dmg2_min=parse_int(parts[20 + idx_offset]) if len(parts) > 20 + idx_offset else 0,
            dmg2_max=parse_int(parts[21 + idx_offset]) if len(parts) > 21 + idx_offset else 0,
            ipad_bits=parse_int(parts[22 + idx_offset]) if len(parts) > 22 + idx_offset else 0,
            ipad=parse_int(parts[23 + idx_offset]) if len(parts) > 23 + idx_offset else 0,
        )

        manager.add_item(item)

    return manager


_g_item_manager: ItemMetaDataManager | None = None
_g_properties: dict[int, PropertyMetaData] | None = None
_g_stat_cost: dict[int, StatCostItem] | None = None


PAIRED_STATS = {
    17: [18],
    48: [49],
    50: [51],
    52: [53],
    54: [55, 56],
    57: [58, 59],
}


@dataclass(slots=True)
class StatCostItem:
    stat_id: int = 0
    stat_name: str = ""
    save_bits: int = 0
    save_add: int = 0
    save_param_bits: int = 0
    val_shift: int = 0
    op: int = 0
    op_param: int = 0
    op_base: int = 0
    op_stat1: int = 0
    op_stat2: int = 0
    op_stat3: int = 0


def parse_itemstatcost_txt(filepath: str) -> dict[int, StatCostItem]:
    result: dict[int, StatCostItem] = {}
    if not os.path.exists(filepath):
        return result

    with open(filepath, encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    header = None
    col_idx = {}
    for line in lines:
        line = line.strip()
        if not line or line.startswith("*"):
            continue
        parts = line.split("\t")
        if header is None:
            header = parts
            for i, h in enumerate(header):
                col_idx[h.strip().lower()] = i
            continue

        def get_col(name: str, default: str = "", _parts: list[str] = parts) -> str:
            idx = col_idx.get(name.strip().lower(), -1)
            return _parts[idx].strip() if 0 <= idx < len(_parts) else default

        try:
            stat_id = int(get_col("*id", "-1"))
        except ValueError:
            continue
        if stat_id < 0:
            continue

        def parse_int_safe(s: str, default: int = 0) -> int:
            if not s:
                return default
            try:
                return int(s)
            except ValueError:
                return default

        item = StatCostItem(
            stat_id=stat_id,
            stat_name=get_col("stat", ""),
            save_bits=parse_int_safe(get_col("save bits")),
            save_add=parse_int_safe(get_col("save add")),
            save_param_bits=parse_int_safe(get_col("save param bits")),
            val_shift=parse_int_safe(get_col("valshift")),
            op=parse_int_safe(get_col("op")),
            op_param=parse_int_safe(get_col("op param")),
            op_base=parse_int_safe(get_col("op base")),
            op_stat1=parse_int_safe(get_col("op stat1")),
            op_stat2=parse_int_safe(get_col("op stat2")),
            op_stat3=parse_int_safe(get_col("op stat3")),
        )
        result[stat_id] = item

    return result


def init_item_data(
    itemdata_path: str | None = None,
    property_path: str | None = None,
    statcost_path: str | None = None,
) -> None:
    global _g_item_manager, _g_properties, _g_stat_cost

    if itemdata_path:
        _g_item_manager = parse_itemdata_txt(itemdata_path)
    if property_path:
        _g_properties = parse_property_txt(property_path)
    if statcost_path:
        _g_stat_cost = parse_itemstatcost_txt(statcost_path)


def get_item_meta(type_id: ItemTypeId, version: int = 0) -> ItemMetaData | None:
    global _g_item_manager

    from core.d2data import get_d2data, get_d2data_manager

    d2data_manager = get_d2data_manager()
    d2data = get_d2data()

    if d2data_manager is not None:
        meta = d2data_manager.get_item_meta(type_id, version)
        if meta is not None:
            if d2data is not None:
                _supplement_meta_from_d2data(meta, d2data)
            return meta

    if _g_item_manager is not None:
        meta = _g_item_manager.get_item(type_id, version)
        if meta is not None and d2data is not None:
            _supplement_meta_from_d2data(meta, d2data)
        return meta

    if d2data is None:
        return None

    code = type_id.decode("ascii", errors="replace").strip()
    type_info = d2data.get_item(code)
    return _convert_item_type_to_meta(type_info, d2data)


def _supplement_meta_from_d2data(meta: ItemMetaData, d2data: Any) -> None:
    code = meta.type_id.decode("ascii", errors="replace").strip()
    type_info = d2data.get_item(code)
    if type_info is None or not type_info.item_type2:
        return
    if not meta.is_scroll_or_book:
        meta.is_scroll_or_book = d2data.is_descendant(
            type_info.item_type2, "scro"
        ) or d2data.is_descendant(type_info.item_type2, "book")
    if not meta.is_body_part:
        meta.is_body_part = d2data.is_descendant(type_info.item_type2, "body")
    if not meta.is_player_body_part:
        meta.is_player_body_part = d2data.is_descendant(type_info.item_type2, "play")
    if not meta.has_def and d2data.is_descendant(type_info.item_type2, "armo"):
        meta.has_def = True


def get_property_meta(prop_id: int, version: int) -> PropertyMetaDataItem | None:
    from core.d2data import get_d2data_manager

    d2data_manager = get_d2data_manager()
    if d2data_manager is not None:
        result = d2data_manager.get_property_meta(prop_id, version)
        if result is not None:
            return result
    global _g_properties
    if _g_properties is None or prop_id not in _g_properties:
        return None
    return _g_properties[prop_id].find_data(version)


def get_stat_cost(stat_id: int) -> StatCostItem | None:
    from core.d2data import get_d2data_manager

    d2data_manager = get_d2data_manager()
    if d2data_manager is not None:
        result = d2data_manager.get_stat_cost(stat_id)
        if result is not None:
            return result
    global _g_stat_cost
    if _g_stat_cost is None:
        return None
    return _g_stat_cost.get(stat_id)


class Ear:
    def __init__(self, name: str = "") -> None:
        self.ear_class = 0
        self.ear_level = 1
        self.ear_name = name

    def deserialize(self, bs: IBitStream, version: int) -> None:
        self.ear_class = bs.read_bits(3)
        self.ear_level = bs.read_bits(7)
        bits_per_char = 8 if is_ptr24_and_above(version) else 7
        max_len = 15 if not is_ptr24_and_above(version) else 60
        name_bytes = []
        for _ in range(max_len):
            c = bs.read_bits(bits_per_char)
            if c == 0:
                break
            name_bytes.append(c)
        try:
            self.ear_name = bytes(name_bytes).decode("utf-8")
        except UnicodeDecodeError:
            self.ear_name = bytes(name_bytes).decode("latin-1", errors="replace")

    def is_valid(self) -> bool:
        return self.ear_level > 0

    def serialize(self, bs: OBitStream, version: int) -> None:
        bs.write_bits(3, self.ear_class)
        bs.write_bits(7, self.ear_level)
        bits_per_char = 8 if is_ptr24_and_above(version) else 7
        name_bytes = (
            self.ear_name.encode("utf-8") if isinstance(self.ear_name, str) else self.ear_name
        )
        for c in name_bytes:
            bs.write_bits(bits_per_char, c)
        bs.write_bits(bits_per_char, 0)


class LongName:
    def __init__(self) -> None:
        self.name_1: int = 0
        self.name_2: int = 0
        self.pref_1: int | None = None
        self.suff_1: int | None = None
        self.pref_2: int | None = None
        self.suff_2: int | None = None
        self.pref_3: int | None = None
        self.suff_3: int | None = None

    def deserialize(self, bs: IBitStream) -> None:
        self.name_1 = bs.read_bits(8)
        self.name_2 = bs.read_bits(8)
        if bs.read_bits(1):
            self.pref_1 = bs.read_bits(11)
        if bs.read_bits(1):
            self.suff_1 = bs.read_bits(11)
        if bs.read_bits(1):
            self.pref_2 = bs.read_bits(11)
        if bs.read_bits(1):
            self.suff_2 = bs.read_bits(11)
        if bs.read_bits(1):
            self.pref_3 = bs.read_bits(11)
        if bs.read_bits(1):
            self.suff_3 = bs.read_bits(11)

    def serialize(self, bs: OBitStream) -> None:
        bs.write_bits(8, self.name_1)
        bs.write_bits(8, self.name_2)
        bs.write_bits(1, 1 if self.pref_1 is not None else 0)
        if self.pref_1 is not None:
            bs.write_bits(11, self.pref_1)
        bs.write_bits(1, 1 if self.suff_1 is not None else 0)
        if self.suff_1 is not None:
            bs.write_bits(11, self.suff_1)
        bs.write_bits(1, 1 if self.pref_2 is not None else 0)
        if self.pref_2 is not None:
            bs.write_bits(11, self.pref_2)
        bs.write_bits(1, 1 if self.suff_2 is not None else 0)
        if self.suff_2 is not None:
            bs.write_bits(11, self.suff_2)
        bs.write_bits(1, 1 if self.pref_3 is not None else 0)
        if self.pref_3 is not None:
            bs.write_bits(11, self.pref_3)
        bs.write_bits(1, 1 if self.suff_3 is not None else 0)
        if self.suff_3 is not None:
            bs.write_bits(11, self.suff_3)


class GoldQuantity:
    def __init__(self) -> None:
        self.is_not_gold = False
        self.quantity = 0

    def deserialize(self, bs: IBitStream) -> None:
        self.is_not_gold = bs.read_bits(1) != 0
        self.quantity = bs.read_bits(12)


_TRACE_PROPERTY = False
_TRACE_ITEM = False
_TRACE_ITEM_IDX = -1


class PropertyList:
    def __init__(self) -> None:
        self.properties: list[RawProperty] = []
        self.end_flag = 0
        self._version: int = 0
        self._use_stat_cost: bool = False

    def deserialize(self, bs: IBitStream, version: int) -> None:
        self._version = version
        self.properties = []
        self._use_stat_cost = _g_stat_cost is not None and is_d2r(version)

        while True:
            bit_pos = bs.get_offset() if _TRACE_PROPERTY else 0
            self.end_flag = bs.read_bits(9)
            if self.end_flag >= 0x1FF:
                break

            if self._use_stat_cost:
                stat_cost = get_stat_cost(self.end_flag)
                if stat_cost is None or stat_cost.save_bits == 0:
                    continue

                layer = 0
                if stat_cost.save_param_bits > 0:
                    layer = bs.read_bits(stat_cost.save_param_bits)

                raw_value = bs.read_bits(stat_cost.save_bits)
                value = (raw_value - stat_cost.save_add) << stat_cost.val_shift
                self.properties.append((self.end_flag, layer, value))

                if _TRACE_PROPERTY:
                    print(
                        f"  stat {self.end_flag}: bit_pos={bit_pos}, layer={layer}, raw_value={raw_value}, value={value}, save_bits={stat_cost.save_bits}, save_param_bits={stat_cost.save_param_bits}"
                    )

                for paired_id in PAIRED_STATS.get(self.end_flag, []):
                    paired_cost = get_stat_cost(paired_id)
                    if paired_cost and paired_cost.save_bits > 0:
                        paired_raw = bs.read_bits(paired_cost.save_bits)
                        paired_value = (paired_raw - paired_cost.save_add) << paired_cost.val_shift
                        self.properties.append((paired_id, 0, paired_value))
                        if _TRACE_PROPERTY:
                            print(
                                f"    paired stat {paired_id}: raw={paired_raw}, value={paired_value}"
                            )

                if self.end_flag == 57:
                    self.properties.append((88, 0, 1))
            else:
                prop_meta = get_property_meta(self.end_flag, version)
                if prop_meta and prop_meta.bits_sum > 0:
                    value = bs.read_bits(prop_meta.bits_sum)
                    self.properties.append((self.end_flag, 0, value))

    def ext_sockets(self) -> int:
        r = 0
        for prop_id, _layer, value in self.properties:
            if prop_id == 194:
                r += value
        return r

    def is_indestructible(self) -> bool:
        return any(prop_id == 152 and value != 0 for prop_id, layer, value in self.properties)

    def get_parsed_properties(self, version: int | None = None) -> list[tuple[int, int, list[int]]]:
        ver = version if version is not None else self._version
        result = []
        for prop_id, layer, value in self.properties:
            if self._use_stat_cost:
                params = self._isc_to_params(prop_id, layer, value, ver)
                result.append((prop_id, value, params))
            else:
                prop_meta = get_property_meta(prop_id, ver)
                if prop_meta:
                    params = prop_meta.parse(value)
                    result.append((prop_id, value, params))
                else:
                    result.append((prop_id, value, []))
        return result

    def _isc_to_params(self, prop_id: int, layer: int, value: int, version: int) -> list[int]:
        prop_meta = get_property_meta(prop_id, version)
        stat_cost = get_stat_cost(prop_id)
        display_value = (
            value >> stat_cost.val_shift if stat_cost and stat_cost.val_shift > 0 else value
        )

        if not prop_meta or prop_meta.bits_sum == 0:
            if stat_cost and stat_cost.save_param_bits > 0:
                return self._isc_layer_to_params(prop_id, layer, display_value, version)
            return [display_value, 0, 0, 0]

        fields = prop_meta.fields
        active_fields = [f for f in fields if f.bits > 0]

        isc_bits = stat_cost.save_bits + stat_cost.save_param_bits if stat_cost else 0
        if (
            len(active_fields) <= 1
            and stat_cost
            and stat_cost.save_param_bits > 0
            and isc_bits > prop_meta.bits_sum
        ):
            return self._isc_layer_to_params(prop_id, layer, display_value, version)

        if len(active_fields) <= 1:
            return [display_value, 0, 0, 0]

        if prop_meta.bits_sum > isc_bits and isc_bits > 0:
            return [display_value, 0, 0, 0]

        param_fields = active_fields[:-1]

        params = [0, 0, 0, 0]
        remaining_layer = layer
        for i, f in enumerate(param_fields):
            mask = (1 << f.bits) - 1
            params[i] = remaining_layer & mask
            remaining_layer >>= f.bits

        params[len(param_fields)] = display_value

        return params

    def _isc_layer_to_params(
        self, prop_id: int, layer: int, display_value: int, version: int
    ) -> list[int]:
        base_meta = get_property_meta(prop_id, 0x63)
        if base_meta:
            active_fields = [f for f in base_meta.fields if f.bits > 0]
            if len(active_fields) > 1:
                param_fields = active_fields[:-1]
                params = [0, 0, 0, 0]
                remaining_layer = layer
                for i, f in enumerate(param_fields):
                    mask = (1 << f.bits) - 1
                    params[i] = remaining_layer & mask
                    remaining_layer >>= f.bits
                params[len(param_fields)] = display_value
                return params
        return [layer, display_value, 0, 0]

    IMPLICIT_STATS: ClassVar[set[int]] = {88}

    def serialize(self, bs: OBitStream, version: int) -> None:
        self._use_stat_cost = _g_stat_cost is not None and is_d2r(version)

        all_paired_ids = set()
        for paired_list in PAIRED_STATS.values():
            all_paired_ids.update(paired_list)

        for prop_id, layer, value in self.properties:
            if prop_id in all_paired_ids:
                continue

            if prop_id in PropertyList.IMPLICIT_STATS:
                continue

            bs.write_bits(9, prop_id)

            if self._use_stat_cost:
                stat_cost = get_stat_cost(prop_id)
                if stat_cost is None or stat_cost.save_bits == 0:
                    continue

                if stat_cost.save_param_bits > 0:
                    bs.write_bits(stat_cost.save_param_bits, layer)

                raw_value = (value >> stat_cost.val_shift) + stat_cost.save_add
                bs.write_bits(stat_cost.save_bits, raw_value)

                for paired_id in PAIRED_STATS.get(prop_id, []):
                    paired_cost = get_stat_cost(paired_id)
                    if paired_cost and paired_cost.save_bits > 0:
                        paired_found = False
                        for pid, _pl, pv in self.properties:
                            if pid == paired_id:
                                paired_raw = (pv >> paired_cost.val_shift) + paired_cost.save_add
                                bs.write_bits(paired_cost.save_bits, paired_raw)
                                paired_found = True
                                break
                        if not paired_found:
                            bs.write_bits(paired_cost.save_bits, 0)
            else:
                prop_meta = get_property_meta(prop_id, version)
                if prop_meta and prop_meta.bits_sum > 0:
                    bs.write_bits(prop_meta.bits_sum, value)

        bs.write_bits(9, 0x1FF)


class ExtItemInfo:
    def __init__(self, meta: ItemMetaData = None) -> None:
        self.gems: int = 0
        self.guid: int = 0
        self.drop_level: int = 99
        self.quality: int = 2
        self.has_var_gfx: bool = False
        self.var_gfx: int | None = None
        self.has_class: bool = False
        self.item_class: int | None = None
        self.low_quality_id: int | None = None
        self.high_quality_id: int | None = None
        self.magic_prefix: int | None = None
        self.magic_suffix: int | None = None
        self.set_id: int | None = None
        self.rare_name: LongName | None = None
        self.unique_id: int | None = None
        self.craft_name: LongName | None = None
        self.rune_id: int | None = None
        self.person_name: list[int] = []
        self.monster_id: int | None = None
        self.charm_id: int | None = None
        self.spell_id: int | None = None
        self.body_part_file_index: int | None = None
        self.spell_type: int | None = None

    def is_set(self) -> bool:
        return self.quality == 5

    def rune_word_id(self) -> int:
        return self.rune_id if self.rune_id is not None else 0

    def deserialize(
        self,
        bs: IBitStream,
        version: int,
        is_charm: bool,
        is_runeword: bool,
        is_personalized: bool,
        has_monster_id: bool,
        has_spell_id: bool,
        is_body_part: bool = False,
        is_scroll_or_book: bool = False,
    ) -> None:
        self.gems = bs.read_bits(3)
        self.guid = bs.read_bits(32)
        self.drop_level = bs.read_bits(7)
        self.quality = bs.read_bits(4)
        self.has_var_gfx = bs.read_bits(1) != 0
        if self.has_var_gfx:
            self.var_gfx = bs.read_bits(3)
        self.has_class = bs.read_bits(1) != 0
        if self.has_class:
            self.item_class = bs.read_bits(11)

        match self.quality:
            case 1:
                self.low_quality_id = bs.read_bits(3)
            case 2:
                if is_charm:
                    self.charm_id = bs.read_bits(12)
                elif is_body_part:
                    self.body_part_file_index = bs.read_bits(10)
                elif is_scroll_or_book:
                    self.spell_type = bs.read_bits(5)
            case 3:
                self.high_quality_id = bs.read_bits(3)
            case 4:
                self.magic_prefix = bs.read_bits(11)
                self.magic_suffix = bs.read_bits(11)
            case 5:
                self.set_id = bs.read_bits(12)
            case 6:
                self.rare_name = LongName()
                self.rare_name.deserialize(bs)
            case 7:
                self.unique_id = bs.read_bits(12)
            case 8:
                self.craft_name = LongName()
                self.craft_name.deserialize(bs)

        if is_runeword:
            self.rune_id = bs.read_bits(16)

        if is_personalized:
            bits_per_char = 8 if is_ptr24_and_above(version) else 7
            for _ in range(16):
                c = bs.read_bits(bits_per_char)
                if c == 0:
                    break
                self.person_name.append(c)

        if has_monster_id:
            self.monster_id = bs.read_bits(10)
        elif has_spell_id:
            self.spell_id = bs.read_bits(5)

    def serialize(
        self,
        bs: OBitStream,
        version: int,
        is_charm: bool,
        is_runeword: bool,
        is_personalized: bool,
        has_monster_id: bool,
        has_spell_id: bool,
        is_body_part: bool = False,
        is_scroll_or_book: bool = False,
    ) -> None:
        bs.write_bits(3, self.gems)
        bs.write_bits(32, self.guid)
        bs.write_bits(7, self.drop_level)
        bs.write_bits(4, self.quality)

        bs.write_bits(1, 1 if self.has_var_gfx else 0)
        if self.has_var_gfx:
            bs.write_bits(3, self.var_gfx if self.var_gfx is not None else 0)

        bs.write_bits(1, 1 if self.has_class else 0)
        if self.has_class:
            bs.write_bits(11, self.item_class if self.item_class is not None else 0)

        match self.quality:
            case 1:
                bs.write_bits(3, self.low_quality_id if self.low_quality_id is not None else 0)
            case 2:
                if is_charm:
                    bs.write_bits(12, self.charm_id if self.charm_id is not None else 0)
                elif is_body_part:
                    bs.write_bits(
                        10,
                        self.body_part_file_index if self.body_part_file_index is not None else 0,
                    )
                elif is_scroll_or_book:
                    bs.write_bits(5, self.spell_type if self.spell_type is not None else 0)
            case 3:
                bs.write_bits(3, self.high_quality_id if self.high_quality_id is not None else 0)
            case 4:
                bs.write_bits(11, self.magic_prefix if self.magic_prefix is not None else 0)
                bs.write_bits(11, self.magic_suffix if self.magic_suffix is not None else 0)
            case 5:
                bs.write_bits(12, self.set_id if self.set_id is not None else 0)
            case 6:
                if self.rare_name:
                    self.rare_name.serialize(bs)
            case 7:
                bs.write_bits(12, self.unique_id if self.unique_id is not None else 0)
            case 8:
                if self.craft_name:
                    self.craft_name.serialize(bs)

        if is_runeword:
            bs.write_bits(16, self.rune_id if self.rune_id is not None else 0)

        if is_personalized:
            bits_per_char = 8 if is_ptr24_and_above(version) else 7
            for c in self.person_name:
                bs.write_bits(bits_per_char, c)
            bs.write_bits(bits_per_char, 0)

        if has_monster_id:
            bs.write_bits(10, self.monster_id if self.monster_id is not None else 0)
        elif has_spell_id:
            bs.write_bits(5, self.spell_id if self.spell_id is not None else 0)


class TypeSpecificInfo:
    def __init__(self, meta: ItemMetaData = None) -> None:
        self.defence: int | None = None
        self.max_durability: int | None = None
        self.current_durability: int | None = None
        self.sockets_count: int | None = None
        self.quantity: int | None = None
        self.has_set_prop_list: list[bool] = []
        self.property_list: PropertyList = PropertyList()
        self.set_properties: list[PropertyList | None] = []
        self.runeword_property_list: PropertyList | None = None

    def sockets(self) -> tuple[int, int]:
        base = self.sockets_count if self.sockets_count is not None else 0
        ext = self.property_list.ext_sockets()
        return (base, ext)

    def total_sockets(self) -> int:
        b, e = self.sockets()
        return min(7, b + e)

    def get_defence(self) -> int:
        if self.defence is None:
            return 0
        ac_stat = get_stat_cost(31)
        save_add = ac_stat.save_add if ac_stat else 10
        return self.defence - save_add

    def is_indestructible(self) -> bool:
        return self.max_durability == 0 or self.property_list.is_indestructible()

    def deserialize(
        self,
        bs: IBitStream,
        version: int,
        has_def: bool,
        has_dur: bool,
        is_socketed: bool,
        is_stacked: bool,
        is_set: bool,
        is_runeword: bool,
        use_stat_cost: bool = False,
        d2r_order: bool = False,
    ) -> None:
        if has_def:
            if use_stat_cost:
                ac_stat = get_stat_cost(31)
                def_bits = ac_stat.save_bits if ac_stat else 11
            else:
                def_bits = 11
            self.defence = bs.read_bits(def_bits)
        if has_dur:
            if use_stat_cost:
                max_dur_stat = get_stat_cost(73)
                max_dur_bits = max_dur_stat.save_bits if max_dur_stat else 8
                dur_stat = get_stat_cost(72)
                dur_bits = dur_stat.save_bits if dur_stat else 9
            else:
                max_dur_bits = 8
                dur_bits = 9
            self.max_durability = bs.read_bits(max_dur_bits)
            if self.max_durability > 0:
                self.current_durability = bs.read_bits(dur_bits)
        if d2r_order:
            if version >= 0x69:
                if bs.read_bits(1):
                    self.quantity = bs.read_bits(9)
            elif is_stacked:
                self.quantity = bs.read_bits(9)
            if is_socketed:
                if use_stat_cost:
                    sock_stat = get_stat_cost(194)
                    sock_bits = sock_stat.save_bits if sock_stat else 3
                else:
                    sock_bits = 4
                self.sockets_count = bs.read_bits(sock_bits)
                if self.sockets_count < 1:
                    self.sockets_count = 1
        else:
            if is_socketed:
                if use_stat_cost:
                    sock_stat = get_stat_cost(194)
                    sock_bits = sock_stat.save_bits if sock_stat else 3
                else:
                    sock_bits = 4
                self.sockets_count = bs.read_bits(sock_bits)
                if self.sockets_count < 1:
                    self.sockets_count = 1
            if version >= 0x69:
                if bs.read_bits(1):
                    self.quantity = bs.read_bits(9)
            elif is_stacked:
                self.quantity = bs.read_bits(9)
        if is_set:
            self.has_set_prop_list = [bs.read_bits(1) != 0 for _ in range(5)]
        else:
            self.has_set_prop_list = [False] * 5

        self.property_list.deserialize(bs, version)

        self.set_properties = []
        if is_set:
            for i in range(5):
                if self.has_set_prop_list[i]:
                    prop_list = PropertyList()
                    prop_list.deserialize(bs, version)
                    self.set_properties.append(prop_list)
                else:
                    self.set_properties.append(None)

        if is_runeword:
            self.runeword_property_list = PropertyList()
            self.runeword_property_list.deserialize(bs, version)

    def serialize(
        self,
        bs: OBitStream,
        version: int,
        has_def: bool,
        has_dur: bool,
        is_socketed: bool,
        is_stacked: bool,
        is_set: bool,
        is_runeword: bool,
        use_stat_cost: bool = False,
        d2r_order: bool = False,
    ) -> None:
        if has_def:
            if use_stat_cost:
                ac_stat = get_stat_cost(31)
                def_bits = ac_stat.save_bits if ac_stat else 11
            else:
                def_bits = 11
            bs.write_bits(def_bits, self.defence if self.defence is not None else 0)

        if has_dur:
            if use_stat_cost:
                max_dur_stat = get_stat_cost(73)
                max_dur_bits = max_dur_stat.save_bits if max_dur_stat else 8
                dur_stat = get_stat_cost(72)
                dur_bits = dur_stat.save_bits if dur_stat else 9
            else:
                max_dur_bits = 8
                dur_bits = 9
            bs.write_bits(
                max_dur_bits, self.max_durability if self.max_durability is not None else 0
            )
            if self.max_durability is not None and self.max_durability > 0:
                bs.write_bits(
                    dur_bits, self.current_durability if self.current_durability is not None else 0
                )

        if d2r_order:
            if version >= 0x69:
                has_quantity = self.quantity is not None
                bs.write_bits(1, 1 if has_quantity else 0)
                if has_quantity:
                    bs.write_bits(9, self.quantity)
            elif is_stacked:
                bs.write_bits(9, self.quantity if self.quantity is not None else 0)
            if is_socketed:
                if use_stat_cost:
                    sock_stat = get_stat_cost(194)
                    sock_bits = sock_stat.save_bits if sock_stat else 3
                else:
                    sock_bits = 4
                bs.write_bits(
                    sock_bits, self.sockets_count if self.sockets_count is not None else 1
                )
        else:
            if is_socketed:
                if use_stat_cost:
                    sock_stat = get_stat_cost(194)
                    sock_bits = sock_stat.save_bits if sock_stat else 3
                else:
                    sock_bits = 4
                bs.write_bits(
                    sock_bits, self.sockets_count if self.sockets_count is not None else 1
                )
            if version >= 0x69:
                has_quantity = self.quantity is not None
                bs.write_bits(1, 1 if has_quantity else 0)
                if has_quantity:
                    bs.write_bits(9, self.quantity)
            elif is_stacked:
                bs.write_bits(9, self.quantity if self.quantity is not None else 0)

        if is_set:
            for has_prop in self.has_set_prop_list:
                bs.write_bits(1, 1 if has_prop else 0)

        self.property_list.serialize(bs, version)

        if is_set:
            for i, prop_list in enumerate(self.set_properties):
                if i < len(self.has_set_prop_list) and self.has_set_prop_list[i] and prop_list:
                    prop_list.serialize(bs, version)

        if is_runeword and self.runeword_property_list:
            self.runeword_property_list.serialize(bs, version)


class ItemInfo:
    STACKABLE_FOR_STASH: ClassVar[set[bytes]] = {
        b"rvs ",
        b"rvl ",
        b"gcv ",
        b"gfv ",
        b"gsv ",
        b"gzv ",
        b"gpv ",
        b"gcy ",
        b"gfy ",
        b"gsy ",
        b"gly ",
        b"gpy ",
        b"gcb ",
        b"gfb ",
        b"gsb ",
        b"glb ",
        b"gpb ",
        b"gcg ",
        b"gfg ",
        b"gsg ",
        b"glg ",
        b"gpg ",
        b"gcr ",
        b"gfr ",
        b"gsr ",
        b"glr ",
        b"gpr ",
        b"gcw ",
        b"gfw ",
        b"gsw ",
        b"glw ",
        b"gpw ",
        b"skc ",
        b"skf ",
        b"sku ",
        b"skl ",
        b"skz ",
        b"r01 ",
        b"r02 ",
        b"r03 ",
        b"r04 ",
        b"r05 ",
        b"r06 ",
        b"r07 ",
        b"r08 ",
        b"r09 ",
        b"r10 ",
        b"r11 ",
        b"r12 ",
        b"r13 ",
        b"r14 ",
        b"r15 ",
        b"r16 ",
        b"r17 ",
        b"r18 ",
        b"r19 ",
        b"r20 ",
        b"r21 ",
        b"r22 ",
        b"r23 ",
        b"r24 ",
        b"r25 ",
        b"r26 ",
        b"r27 ",
        b"r28 ",
        b"r29 ",
        b"r30 ",
        b"r31 ",
        b"r32 ",
        b"r33 ",
        b"pk1 ",
        b"pk2 ",
        b"pk3 ",
        b"dhn ",
        b"bey ",
        b"mbr ",
        b"toa ",
        b"tes ",
        b"ceh ",
        b"bet ",
        b"fed ",
    }

    def __init__(self, meta: ItemMetaData = None) -> None:
        self.type_name: bytes = b"    "
        self.ext_info: ExtItemInfo | None = None
        self.gold: GoldQuantity | None = None
        self.has_rand: bool = False
        self.timestamp_flag: list[int] = []
        self.realm_data: list[int] = []
        self.stash_stack_size: int = 0
        self.has_stash_stack_size: bool = False
        self.quest_difficulty: int = 0
        self.type_specific_info: TypeSpecificInfo | None = None
        self.pad: int = 0
        self._meta = meta

    def is_gold(self) -> bool:
        return self.type_name == b"gld "

    def is_box(self) -> bool:
        return self.type_name == b"box "

    def is_set(self) -> bool:
        return self.ext_info is not None and self.ext_info.is_set()

    def rune_word_id(self) -> int:
        return self.ext_info.rune_word_id() if self.ext_info else 0

    def gems(self) -> int:
        return self.ext_info.gems if self.ext_info else 0

    def sockets(self) -> int:
        if self.type_specific_info:
            return self.type_specific_info.total_sockets()
        return 0

    def _is_stackable_for_stash(self) -> bool:
        return self.type_name in self.STACKABLE_FOR_STASH

    def deserialize(
        self,
        bs: IBitStream,
        version: int,
        is_simple: bool,
        is_runeword: bool,
        is_personalized: bool,
        is_socketed: bool,
    ) -> ItemMetaData | None:
        is_d2r_ = is_d2r(version)
        huffman = get_huffman()

        if is_d2r_:
            self.type_name = bytes([huffman.read_char(bs) for _ in range(4)])
        else:
            # 读取4个字节，注意小端序
            self.type_name = bytes([bs.read_byte() for _ in range(4)])

        meta = get_item_meta(self.type_name, version)
        if meta is None:
            meta = self._meta

        if not is_simple and meta:
            self.ext_info = ExtItemInfo(meta)
            self.ext_info.deserialize(
                bs,
                version,
                meta.is_charm if meta else False,
                is_runeword,
                is_personalized,
                meta.has_monster_id if meta else False,
                (meta.spell_id > 0) if meta else False,
            )

        if self.is_gold():
            self.gold = GoldQuantity()
            self.gold.deserialize(bs)

        self.has_rand = bs.read_bits(1) != 0
        if self.has_rand:
            if is_d2r_ and version > 86:
                realm_count = 4 if version > 96 else (3 if version > 93 else 2)
                self.realm_data = [bs.read_bits(32) for _ in range(realm_count)]
            elif not is_simple:
                self.timestamp_flag = [bs.read_bits(32) for _ in range(4)]

        if is_d2r_ and version > 99:
            if version <= 101:
                if self._is_stackable_for_stash():
                    self.stash_stack_size = bs.read_bits(8)
                    self.has_stash_stack_size = True
            else:
                if bs.read_bits(1):
                    self.stash_stack_size = bs.read_bits(8)
                    self.has_stash_stack_size = True

        if not is_simple and meta:
            self.type_specific_info = TypeSpecificInfo(meta)
            self.type_specific_info.deserialize(
                bs,
                version,
                meta.has_def if meta else False,
                meta.has_dur if meta else False,
                is_socketed,
                meta.is_stacked if meta else False,
                self.is_set(),
                is_runeword,
            )
        elif is_d2r_ and version >= 0x69 and meta and meta.ipad_bits > 0:
            self.pad = bs.read_bits(meta.ipad_bits)

        return meta


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


class D2Item:
    def __init__(self, meta: ItemMetaData = None) -> None:
        self.version = 0
        self.magic = ITEM_LIST_MAGIC
        self.is_quest = False
        self.target_del_flags = 0
        self.is_identified = True
        self.switch_in_out_flags = 0
        self.is_disabled = False
        self.repair_flags = 0
        self.is_socketed = False
        self.is_no_sell = False
        self.is_new = False
        self.is_bad_equipped = False
        self.is_named = False
        self.is_ear = False
        self.is_newbie = False
        self.init_flags = 0
        self.is_simple = True
        self.is_ethereal = False
        self.is_just_saved = True
        self.is_personalized = False
        self.is_low_quality = False
        self.is_runeword = False
        self.duplicate_chronicle = 0
        self.item_version = 101
        self.version_high = 0xA0
        self.location = 0
        self.position = 0
        self.column = 0
        self.row = 0
        self.stored_in = 1

        self._flags = 0
        self._has_quantity = False
        self._is_chronicle = False
        self._is_chronicle_compact = False

        self.ear: Ear | None = None
        self.item_info: ItemInfo | None = None
        self.gem_items: list[D2Item] = []

        self._meta = meta

    @property
    def type_name(self) -> bytes:
        if self.item_info and self.item_info.type_name.strip():
            return self.item_info.type_name
        if self.is_ear:
            return b"ear "
        if self._meta:
            return self._meta.type_id
        if self.item_info:
            return self.item_info.type_name
        return b"    "

    @type_name.setter
    def type_name(self, value: bytes) -> None:
        if self.item_info:
            self.item_info.type_name = value
        if self._meta:
            self._meta.type_id = value
        else:
            self._meta = ItemMetaData(type_id=value)

    def quality(self) -> int:
        if self.is_ear or self.is_simple:
            if self._meta and self._meta.is_unique:
                return 7
            return 2
        if self.item_info and self.item_info.ext_info:
            return self.item_info.ext_info.quality
        return 2

    def get_flag_names(self) -> list[str]:
        """Return list of human-readable flag names that are set on this item."""
        return [label for attr, label in ITEM_FLAG_LABELS if getattr(self, attr, False)]

    def is_set(self) -> bool:
        return self.item_info is not None and self.item_info.is_set()

    def is_rune_word(self) -> bool:
        return self.is_runeword

    def rune_word_id(self) -> int:
        if self.is_runeword and self.item_info:
            return self.item_info.rune_word_id()
        return 0

    def gems(self) -> int:
        if self.item_info:
            return self.item_info.gems()
        return 0

    def sockets(self) -> int:
        if self.is_socketed and self.item_info:
            return self.item_info.sockets()
        return 0

    def is_box(self) -> bool:
        return self.item_info is not None and self.item_info.is_box()

    def has_property_list(self) -> bool:
        return self.item_info is not None and self.item_info.type_specific_info is not None

    def deserialize(self, bs: IBitStream, version: int, read_magic: bool = True) -> None:
        if is_d2r(version):
            self._read_data_d2r(bs, version, read_magic)
        else:
            self._read_data_classic(bs, version, read_magic)

    def _read_data_d2r(self, bs: IBitStream, version: int, read_magic: bool = True) -> None:
        if read_magic:
            bs.align_byte()
            self.magic = bs.read_word()
            if self.magic != ITEM_LIST_MAGIC:
                bs.seek_back_bytes(2)
                self.magic = ITEM_LIST_MAGIC
            self.version = bs.read_dword()
            if not is_valid_version(self.version):
                bs.seek_back_bytes(4)
                self.version = version
        else:
            self.magic = ITEM_LIST_MAGIC
            self.version = version

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

        hf = bs.read_bits(1)
        vv = bs.read_bits(2)
        self.item_version = (vv + 99) if hf else vv

        mode = bs.read_bits(3)
        self.location = mode
        if mode == 3 or mode == 5:
            self.position = 0
            self.column = bs.read_bits(16)
            self.row = bs.read_bits(16)
            self.stored_in = 0
        else:
            self.position = bs.read_bits(4)
            self.column = bs.read_bits(4)
            self.row = bs.read_bits(4)
            self.stored_in = bs.read_bits(3) - 1

        huffman = get_huffman()
        if self.is_ear:
            self.ear = Ear()
            self.ear.deserialize(bs, self.version)
            self._meta = get_item_meta(b"ear ", self.version)
            type_name = b"ear "
        else:
            type_name = bytes([huffman.read_char(bs) for _ in range(4)])
            self._meta = get_item_meta(type_name, self.version)
            self.item_info = ItemInfo(self._meta)
            self.item_info.type_name = type_name

        if self.is_simple:
            self._read_compact_d2r(
                bs, version, type_name, self._is_chronicle, self._is_chronicle_compact
            )
        else:
            self._read_complete_d2r(
                bs, version, type_name, self._is_chronicle, self._is_chronicle_compact
            )

        bs.align_byte()

        gem_count = self.gems()
        self.gem_items = []
        for _ in range(gem_count):
            item = D2Item()
            item.deserialize(bs, self.version, self.version <= 96)
            self.gem_items.append(item)

    def _read_compact_d2r(
        self,
        bs: IBitStream,
        version: int,
        type_name: bytes,
        is_chronicle: bool,
        is_chronicle_compact: bool,
    ) -> None:
        if self.is_ear:
            return

        if version > 92:
            from core.d2data import get_d2data

            d2data = get_d2data()
            code = type_name.decode("ascii", errors="replace").strip()
            type_info = d2data.get_item(code) if d2data else None
            if type_info and type_info.quest > 0 and type_info.questdiffcheck:
                quest_diff_stat = get_stat_cost(356)
                if quest_diff_stat and quest_diff_stat.save_bits > 0:
                    raw = bs.read_bits(quest_diff_stat.save_bits)
                    if self.item_info:
                        self.item_info.quest_difficulty = (
                            raw - quest_diff_stat.save_add
                        ) << quest_diff_stat.val_shift

        realm_flag = bs.read_bits(1)
        if realm_flag:
            realm_count = 4 if version > 96 else (3 if version > 93 else 2)
            if self.item_info:
                self.item_info.realm_data = [bs.read_bits(32) for _ in range(realm_count)]

        self._read_advanced_stash_size(bs, version, type_name)

    def _read_complete_d2r(
        self,
        bs: IBitStream,
        version: int,
        type_name: bytes,
        is_chronicle: bool,
        is_chronicle_compact: bool,
    ) -> None:
        if self.is_ear:
            return

        meta = self._meta

        ext = ExtItemInfo(meta)
        ext.deserialize(
            bs,
            version,
            meta.is_charm if meta else False,
            self.is_runeword,
            self.is_personalized,
            False,
            False,
            (meta.is_body_part and not meta.is_player_body_part) if meta else False,
            meta.is_scroll_or_book if meta else False,
        )
        if self.item_info:
            self.item_info.ext_info = ext

        realm_flag = bs.read_bits(1)
        if realm_flag:
            realm_count = 4 if version > 96 else (3 if version > 93 else 2)
            if self.item_info:
                self.item_info.realm_data = [bs.read_bits(32) for _ in range(realm_count)]

        if self.item_info and self.item_info.is_gold():
            self.item_info.gold = GoldQuantity()
            self.item_info.gold.deserialize(bs)

        tp = TypeSpecificInfo(meta)
        tp.deserialize(
            bs,
            version,
            meta.has_def if meta else False,
            meta.has_dur if meta else False,
            self.is_socketed,
            meta.is_stacked if meta else False,
            self.is_set(),
            self.is_runeword,
            use_stat_cost=True,
            d2r_order=True,
        )
        if self.item_info:
            self.item_info.type_specific_info = tp

        if is_chronicle:
            _chronicle_id = bs.read_bits(16)
            if is_chronicle_compact:
                bs.read_bits(64)
            else:
                bs.read_bits(32)
                count = bs.read_bits(4)
                for _ in range(count):
                    bs.read_bits(64)

        self._read_advanced_stash_size(bs, version, type_name)

    def _read_advanced_stash_size(self, bs: IBitStream, version: int, type_name: bytes) -> None:
        if version <= 99 or not self.item_info:
            return
        if version <= 101:
            if type_name in ItemInfo.STACKABLE_FOR_STASH:
                self.item_info.stash_stack_size = bs.read_bits(8)
                self.item_info.has_stash_stack_size = True
        else:
            if bs.read_bits(1):
                self.item_info.stash_stack_size = bs.read_bits(8)
                self.item_info.has_stash_stack_size = True

    def _read_data_classic(self, bs: IBitStream, version: int, read_magic: bool = True) -> None:
        if read_magic:
            bs.align_byte()
            self.magic = bs.read_word()
            if self.magic != ITEM_LIST_MAGIC:
                bs.seek_back_bytes(2)
                self.magic = ITEM_LIST_MAGIC
            self.version = bs.read_dword()
            if not is_valid_version(self.version):
                bs.seek_back_bytes(4)
                self.version = version
        else:
            self.magic = ITEM_LIST_MAGIC
            self.version = version

        self.is_quest = bs.read_bits(1) != 0
        self.target_del_flags = bs.read_bits(3)
        self.is_identified = bs.read_bits(1) != 0
        self.switch_in_out_flags = bs.read_bits(3)
        self.is_disabled = bs.read_bits(1) != 0
        self.repair_flags = bs.read_bits(2)
        self.is_socketed = bs.read_bits(1) != 0
        self.is_no_sell = bs.read_bits(1) != 0
        self.is_new = bs.read_bits(1) != 0
        self.is_bad_equipped = bs.read_bits(1) != 0
        self.is_named = bs.read_bits(1) != 0
        self.is_ear = bs.read_bits(1) != 0
        self.is_newbie = bs.read_bits(1) != 0
        self.init_flags = bs.read_bits(3)
        self.is_simple = bs.read_bits(1) != 0
        self.is_ethereal = bs.read_bits(1) != 0
        self.is_just_saved = bs.read_bits(1) != 0
        self.is_personalized = bs.read_bits(1) != 0
        self.is_low_quality = bs.read_bits(1) != 0
        self.is_runeword = bs.read_bits(1) != 0

        self.duplicate_chronicle = bs.read_bits(5)
        self.item_version = bs.read_bits(10)

        self.location = bs.read_bits(3)
        self.position = bs.read_bits(4)
        self.column = bs.read_bits(4)
        self.row = bs.read_bits(4)
        self.stored_in = bs.read_bits(3)

        if self.is_ear:
            self.ear = Ear()
            self.ear.deserialize(bs, self.version)
            self._meta = get_item_meta(b"ear ", self.version)
        else:
            self.item_info = ItemInfo(self._meta)
            self._meta = self.item_info.deserialize(
                bs,
                self.version,
                self.is_simple,
                self.is_runeword,
                self.is_personalized,
                self.is_socketed,
            )

        bs.align_byte()

        gem_count = self.gems()
        self.gem_items = []
        for _ in range(gem_count):
            item = D2Item()
            item.deserialize(bs, self.version, True)
            self.gem_items.append(item)

    def serialize(self, bs: OBitStream, version: int, write_magic: bool = True) -> None:
        if is_d2r(version):
            self._serialize_d2r(bs, version, write_magic and version <= 96)
        else:
            self._serialize_classic(bs, version, write_magic)

    def _serialize_d2r(self, bs: OBitStream, version: int, write_magic: bool = True) -> None:
        if write_magic:
            bs.align_byte()
            bs.write_word(self.magic)
            bs.write_dword(self.version)

        bs.write_bits(32, self._flags)

        if self.item_version >= 99:
            bs.write_bits(1, 1)
            bs.write_bits(2, self.item_version - 99)
        else:
            bs.write_bits(1, 0)
            bs.write_bits(2, self.item_version)

        bs.write_bits(3, self.location)
        if self.location == 3 or self.location == 5:
            bs.write_bits(16, self.column)
            bs.write_bits(16, self.row)
        else:
            bs.write_bits(4, self.position)
            bs.write_bits(4, self.column)
            bs.write_bits(4, self.row)
            bs.write_bits(3, self.stored_in + 1)

        huffman = get_huffman()
        if self.is_ear:
            if self.ear:
                self.ear.serialize(bs, self.version)
        else:
            type_name = self.type_name
            for c in type_name:
                huffman.write_char(bs, c)

        if self.is_simple and self.item_info:
            self._write_compact_d2r(bs, version)
        elif not self.is_simple and self.item_info:
            self._write_complete_d2r(bs, version)

        bs.align_byte()

        for gem_item in self.gem_items:
            gem_item.serialize(bs, self.version, True)

    def _write_compact_d2r(self, bs: OBitStream, version: int) -> None:
        if not self.item_info:
            return

        if version > 92 and self.item_info.quest_difficulty > 0:
            quest_diff_stat = get_stat_cost(356)
            if quest_diff_stat and quest_diff_stat.save_bits > 0:
                raw = (
                    self.item_info.quest_difficulty >> quest_diff_stat.val_shift
                ) + quest_diff_stat.save_add
                bs.write_bits(quest_diff_stat.save_bits, raw)

        realm_flag = len(self.item_info.realm_data) > 0 if self.item_info.realm_data else False
        bs.write_bits(1, 1 if realm_flag else 0)
        if realm_flag:
            realm_count = 4 if version > 96 else (3 if version > 93 else 2)
            for i in range(realm_count):
                if i < len(self.item_info.realm_data):
                    bs.write_bits(32, self.item_info.realm_data[i])
                else:
                    bs.write_bits(32, 0)

        self._write_advanced_stash_size(bs, version)

    def _write_complete_d2r(self, bs: OBitStream, version: int) -> None:
        if not self.item_info or not self.item_info.ext_info:
            return

        ext = self.item_info.ext_info
        meta = self._meta

        ext.serialize(
            bs,
            version,
            meta.is_charm if meta else False,
            self.is_runeword,
            self.is_personalized,
            False,
            False,
            (meta.is_body_part and not meta.is_player_body_part) if meta else False,
            meta.is_scroll_or_book if meta else False,
        )

        realm_flag = len(self.item_info.realm_data) > 0 if self.item_info.realm_data else False
        bs.write_bits(1, 1 if realm_flag else 0)
        if realm_flag:
            realm_count = 4 if version > 96 else (3 if version > 93 else 2)
            for i in range(realm_count):
                if i < len(self.item_info.realm_data):
                    bs.write_bits(32, self.item_info.realm_data[i])
                else:
                    bs.write_bits(32, 0)

        if self.item_info.type_specific_info:
            tp = self.item_info.type_specific_info
            tp.serialize(
                bs,
                version,
                meta.has_def if meta else False,
                meta.has_dur if meta else False,
                self.is_socketed,
                meta.is_stacked if meta else False,
                self.is_set(),
                self.is_runeword,
                use_stat_cost=True,
                d2r_order=True,
            )

        self._write_advanced_stash_size(bs, version)

    def _write_advanced_stash_size(self, bs: OBitStream, version: int) -> None:
        if version <= 99 or not self.item_info:
            return

        if version <= 101:
            type_name = self.type_name
            if type_name in ItemInfo.STACKABLE_FOR_STASH:
                stash_size = self.item_info.stash_stack_size
                bs.write_bits(8, stash_size)
        else:
            has_stash_size = self.item_info.has_stash_stack_size
            bs.write_bits(1, 1 if has_stash_size else 0)
            if has_stash_size:
                bs.write_bits(8, self.item_info.stash_stack_size)

    def _serialize_classic(self, bs: OBitStream, version: int, write_magic: bool = True) -> None:
        if write_magic:
            bs.align_byte()
            bs.write_word(self.magic)
            bs.write_dword(self.version)

        bs.write_bits(1, 1 if self.is_quest else 0)
        bs.write_bits(3, self.target_del_flags)
        bs.write_bits(1, 1 if self.is_identified else 0)
        bs.write_bits(3, self.switch_in_out_flags)
        bs.write_bits(1, 1 if self.is_disabled else 0)
        bs.write_bits(2, self.repair_flags)
        bs.write_bits(1, 1 if self.is_socketed else 0)
        bs.write_bits(1, 1 if self.is_no_sell else 0)
        bs.write_bits(1, 1 if self.is_new else 0)
        bs.write_bits(1, 1 if self.is_bad_equipped else 0)
        bs.write_bits(1, 1 if self.is_named else 0)
        bs.write_bits(1, 1 if self.is_ear else 0)
        bs.write_bits(1, 1 if self.is_newbie else 0)
        bs.write_bits(3, self.init_flags)
        bs.write_bits(1, 1 if self.is_simple else 0)
        bs.write_bits(1, 1 if self.is_ethereal else 0)
        bs.write_bits(1, 1 if self.is_just_saved else 0)
        bs.write_bits(1, 1 if self.is_personalized else 0)
        bs.write_bits(1, 1 if self.is_low_quality else 0)
        bs.write_bits(1, 1 if self.is_runeword else 0)

        bs.write_bits(5, self.duplicate_chronicle)
        bs.write_bits(10, self.item_version)

        bs.write_bits(3, self.location)
        bs.write_bits(4, self.position)
        bs.write_bits(4, self.column)
        bs.write_bits(4, self.row)
        bs.write_bits(3, self.stored_in)

        if self.is_ear:
            if self.ear:
                self.ear.serialize(bs, self.version)
        else:
            if self.item_info and self.item_info.ext_info:
                ext = self.item_info.ext_info
                meta = self._meta
                ext.serialize(
                    bs,
                    version,
                    meta.is_charm if meta else False,
                    self.is_runeword,
                    self.is_personalized,
                    False,
                    False,
                    (meta.is_body_part and not meta.is_player_body_part) if meta else False,
                    meta.is_scroll_or_book if meta else False,
                )

            if self.item_info and self.item_info.type_specific_info:
                tp = self.item_info.type_specific_info
                tp.serialize(
                    bs,
                    version,
                    meta.has_def if meta else False,
                    meta.has_dur if meta else False,
                    self.is_socketed,
                    meta.is_stacked if meta else False,
                    self.is_set(),
                    self.is_runeword,
                )

        bs.align_byte()

        for gem_item in self.gem_items:
            gem_item.serialize(bs, self.version, True)


class ItemList:
    def __init__(self) -> None:
        self.magic = ITEM_LIST_MAGIC
        self.count = 0
        self.items: list[D2Item] = []

    def __len__(self) -> int:
        return len(self.items)

    def __bool__(self) -> bool:
        return True

    def __iter__(self) -> Iterator[D2Item]:
        return iter(self.items)

    def __getitem__(self, index: int) -> D2Item:
        return self.items[index]

    def deserialize(self, bs: IBitStream, version: int) -> None:
        self.magic = bs.read_word()
        self.count = bs.read_word()
        if self.magic != ITEM_LIST_MAGIC:
            return

        self.items = []
        for i in range(self.count):
            if bs.is_end():
                break
            if bs.remaining() < 16 * 8:
                break
            import core.item as _self_mod

            old_trace = _self_mod._TRACE_ITEM
            old_trace_prop = _self_mod._TRACE_PROPERTY
            if _self_mod._TRACE_ITEM_IDX >= 0 and i == _self_mod._TRACE_ITEM_IDX:
                _self_mod._TRACE_ITEM = True
                _self_mod._TRACE_PROPERTY = True
            item = D2Item()
            start_offset = bs.get_offset()
            try:
                if is_d2r(version):
                    item.deserialize(bs, version, False)
                else:
                    item.deserialize(bs, version, True)
            except ValueError:
                bs._offset = start_offset
                continue
            _self_mod._TRACE_ITEM = old_trace
            _self_mod._TRACE_PROPERTY = old_trace_prop
            self.items.append(item)

    def serialize(self, bs: OBitStream, version: int) -> None:
        bs.align_byte()
        bs.write_word(self.magic)
        bs.write_word(len(self.items))

        for item in self.items:
            item.serialize(bs, version, False)

    def get_items(self) -> list[D2Item]:
        return self.items
