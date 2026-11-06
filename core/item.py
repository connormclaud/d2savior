import os
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from core.huffman import HuffmanDecoder, get_huffman
from core.enums import ITEM_LIST_MAGIC


def is_d2r(version: int) -> bool:
    return version >= 0x61


def _convert_item_type_to_meta(type_info, d2data=None) -> Optional['ItemMetaData']:
    if type_info is None:
        return None
    
    meta = ItemMetaData()
    meta.type_id = type_info.code.encode('ascii').ljust(4)[:4]
    meta.name = type_info.name
    
    meta.simple = type_info.compactsave
    meta.normal = type_info.spawnable
    meta.white = not type_info.rarity or type_info.rarity == 1
    
    meta.has_def = type_info.item_type == 'armor'
    meta.has_dur = not type_info.nodurability and type_info.durability > 0
    meta.is_stacked = type_info.stackable
    
    meta.is_charm = type_info.item_type2 in ['char', 'charmed']
    meta.spell_id = type_info.spell_id if type_info.spell_id > 0 else 0
    
    meta.is_gem = type_info.item_type2 in ['gem', 'gem2']
    meta.is_unique = type_info.rarity == 7
    meta.is_craft = type_info.item_type2 == 'craft'
    
    if d2data is not None and type_info.item_type2:
        meta.is_scroll_or_book = (d2data.is_descendant(type_info.item_type2, 'scro') or
                                  d2data.is_descendant(type_info.item_type2, 'book'))
        meta.is_body_part = d2data.is_descendant(type_info.item_type2, 'body')
        meta.is_player_body_part = d2data.is_descendant(type_info.item_type2, 'play')
        if d2data.is_descendant(type_info.item_type2, 'armo'):
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


@dataclass
class PropertyField:
    bits: int = 0
    base: int = 0
    min_val: int = 0
    max_val: int = 0


@dataclass
class PropertyMetaDataItem:
    ver_min: int = 0
    fields: List[PropertyField] = field(default_factory=list)
    default_value: int = 0
    bits_sum: int = 0

    def parse(self, value: int) -> List[int]:
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

    def get_value(self, params: List[int]) -> Tuple[bool, int]:
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
    def __init__(self):
        self._data: List[PropertyMetaDataItem] = []

    def add_item(self, item: PropertyMetaDataItem):
        self._data.append(item)

    def find_data(self, version: int) -> Optional[PropertyMetaDataItem]:
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


@dataclass
class ItemMetaData:
    type_id: bytes = b'    '
    ver_min: int = 0
    name: str = ''
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
        return self.type_id.decode('ascii', errors='replace').strip()


class ItemMetaDataManager:
    def __init__(self):
        self._items: Dict[bytes, List[ItemMetaData]] = {}

    def add_item(self, item: ItemMetaData):
        if item.type_id not in self._items:
            self._items[item.type_id] = []
        self._items[item.type_id].append(item)

    def get_item(self, type_id: bytes, version: int = 0) -> Optional[ItemMetaData]:
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

    def get_item_by_name(self, name: str, version: int = 0) -> Optional[ItemMetaData]:
        padded_name = name.ljust(4)[:4].encode('ascii')
        return self.get_item(padded_name, version)



def parse_property_txt(filepath: str) -> Dict[int, PropertyMetaData]:
    properties: Dict[int, PropertyMetaData] = {}
    
    if not os.path.exists(filepath):
        return properties
    
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        lines = f.readlines()
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith('*'):
            continue
        
        parts = line.split('\t')
        if len(parts) < 1:
            continue
        
        try:
            prop_id = int(parts[0])
        except ValueError:
            continue
        
        ver_min = 0
        if len(parts) > 1 and parts[1]:
            if parts[1].startswith('0x'):
                ver_min = int(parts[1], 16)
            else:
                try:
                    ver_min = int(parts[1])
                except ValueError:
                    ver_min = 0
        
        default_value = 0
        if len(parts) > 2 and parts[2]:
            if parts[2].startswith('0x'):
                default_value = int(parts[2], 16)
            else:
                try:
                    default_value = int(parts[2])
                except ValueError:
                    default_value = 0
        
        fields: List[PropertyField] = []
        bits_sum = 0
        
        field_col_idx = 3
        while field_col_idx < len(parts):
            bits_str = parts[field_col_idx] if field_col_idx < len(parts) else ''
            if not bits_str:
                break
            
            try:
                bits = int(bits_str)
                base_str = parts[field_col_idx + 1] if field_col_idx + 1 < len(parts) else ''
                min_str = parts[field_col_idx + 2] if field_col_idx + 2 < len(parts) else ''
                max_str = parts[field_col_idx + 3] if field_col_idx + 3 < len(parts) else ''
                
                base = int(base_str) if base_str else 0
                min_val = int(min_str) if min_str else 0
                max_val = int(max_str) if max_str else 0
                
                fields.append(PropertyField(bits, base, min_val, max_val))
                bits_sum += bits
            except ValueError:
                break
            
            field_col_idx += 4
        
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
    
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        lines = f.readlines()
    
    has_version_min = False
    for line in lines:
        if line.strip().startswith('*ID'):
            if 'VersionMin' in line:
                has_version_min = True
            break
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith('*'):
            continue
        
        parts = line.split('\t')
        if len(parts) < 2:
            continue
        
        type_id = parts[0].ljust(4)[:4].encode('ascii')
        
        def parse_int(s: str, default: int = 0) -> int:
            if not s:
                return default
            try:
                return int(s)
            except ValueError:
                return default
        
        def parse_bool(s: str) -> bool:
            return s == '1'
        
        def parse_version(s: str) -> int:
            if not s:
                return 0
            if s.startswith('0x'):
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
            is_stacked=parse_bool(parts[11 + idx_offset]) if len(parts) > 11 + idx_offset else False,
            has_monster_id=parse_bool(parts[12 + idx_offset]) if len(parts) > 12 + idx_offset else False,
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


_g_item_manager: Optional[ItemMetaDataManager] = None
_g_properties: Optional[Dict[int, PropertyMetaData]] = None
_g_stat_cost: Optional[Dict[int, 'StatCostItem']] = None


PAIRED_STATS = {
    17: [18],
    48: [49],
    50: [51],
    52: [53],
    54: [55, 56],
    57: [58, 59],
}


@dataclass
class StatCostItem:
    stat_id: int = 0
    stat_name: str = ''
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


def parse_itemstatcost_txt(filepath: str) -> Dict[int, StatCostItem]:
    result: Dict[int, StatCostItem] = {}
    if not os.path.exists(filepath):
        return result

    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        lines = f.readlines()

    header = None
    col_idx = {}
    for line in lines:
        line = line.strip()
        if not line or line.startswith('*'):
            continue
        parts = line.split('\t')
        if header is None:
            header = parts
            for i, h in enumerate(header):
                col_idx[h.strip().lower()] = i
            continue

        def get_col(name: str, default: str = '') -> str:
            idx = col_idx.get(name.strip().lower(), -1)
            return parts[idx].strip() if 0 <= idx < len(parts) else default

        try:
            stat_id = int(get_col('*id', '-1'))
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
            stat_name=get_col('stat', ''),
            save_bits=parse_int_safe(get_col('save bits')),
            save_add=parse_int_safe(get_col('save add')),
            save_param_bits=parse_int_safe(get_col('save param bits')),
            val_shift=parse_int_safe(get_col('valshift')),
            op=parse_int_safe(get_col('op')),
            op_param=parse_int_safe(get_col('op param')),
            op_base=parse_int_safe(get_col('op base')),
            op_stat1=parse_int_safe(get_col('op stat1')),
            op_stat2=parse_int_safe(get_col('op stat2')),
            op_stat3=parse_int_safe(get_col('op stat3')),
        )
        result[stat_id] = item

    return result


def init_item_data(itemdata_path: str = None, property_path: str = None,
                   statcost_path: str = None):
    global _g_item_manager, _g_properties, _g_stat_cost

    if itemdata_path:
        _g_item_manager = parse_itemdata_txt(itemdata_path)
    if property_path:
        _g_properties = parse_property_txt(property_path)
    if statcost_path:
        _g_stat_cost = parse_itemstatcost_txt(statcost_path)


def get_item_meta(type_id: bytes, version: int = 0) -> Optional[ItemMetaData]:
    global _g_item_manager
    
    from core.d2data import get_d2data_manager, get_d2data
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
    
    code = type_id.decode('ascii', errors='replace').strip()
    type_info = d2data.get_item(code)
    return _convert_item_type_to_meta(type_info, d2data)


def _supplement_meta_from_d2data(meta: ItemMetaData, d2data):
    code = meta.type_id.decode('ascii', errors='replace').strip()
    type_info = d2data.get_item(code)
    if type_info is None or not type_info.item_type2:
        return
    if not meta.is_scroll_or_book:
        meta.is_scroll_or_book = (d2data.is_descendant(type_info.item_type2, 'scro') or
                                  d2data.is_descendant(type_info.item_type2, 'book'))
    if not meta.is_body_part:
        meta.is_body_part = d2data.is_descendant(type_info.item_type2, 'body')
    if not meta.is_player_body_part:
        meta.is_player_body_part = d2data.is_descendant(type_info.item_type2, 'play')
    if not meta.has_def:
        if d2data.is_descendant(type_info.item_type2, 'armo'):
            meta.has_def = True


def get_property_meta(prop_id: int, version: int) -> Optional[PropertyMetaDataItem]:
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


def get_stat_cost(stat_id: int) -> Optional[StatCostItem]:
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


class MayExist:
    """Compatibility wrapper during migration from MayExist to Optional[T]."""
    def __init__(self, owner_or_type=int, attr_or_bits=0):
        if isinstance(owner_or_type, str) or hasattr(owner_or_type, '__dict__'):
            self._owner = owner_or_type
            self._attr = attr_or_bits
            self._standalone = False
        else:
            self._owner = None
            self._attr = None
            self._standalone = True
            self._exists = False
            self._value = None

    def exist(self) -> bool:
        if self._standalone:
            return self._exists
        return getattr(self._owner, self._attr) is not None

    def ensure(self, value=None):
        if self._standalone:
            self._exists = True
            self._value = value if value is not None else 0
        else:
            if value is not None:
                setattr(self._owner, self._attr, value)
            elif getattr(self._owner, self._attr) is None:
                setattr(self._owner, self._attr, 0)
        return self

    @property
    def value(self):
        if self._standalone:
            return self._value if self._value is not None else 0
        val = getattr(self._owner, self._attr)
        return val if val is not None else 0

    @value.setter
    def value(self, v):
        if self._standalone:
            self._value = v
            self._exists = True
        else:
            setattr(self._owner, self._attr, v)

    def __int__(self):
        return int(self.value)

    def __bool__(self):
        return self.exist()

    def __eq__(self, other):
        if isinstance(other, MayExist):
            return self.value == other.value and self.exist() == other.exist()
        return self.value == other if self.exist() else (other is None)

    def __repr__(self):
        val = self.value if self.exist() else None
        return f"MayExist({val})"


class Ear:
    def __init__(self, name: str = ""):
        self.iEarClass = 0
        self.iEarLevel = 1
        self.sEarName = name

    def deserialize(self, bs, version: int):
        self.iEarClass = bs.read_bits(3)
        self.iEarLevel = bs.read_bits(7)
        bits_per_char = 8 if is_ptr24_and_above(version) else 7
        max_len = 15 if not is_ptr24_and_above(version) else 60
        name_bytes = []
        for _ in range(max_len):
            c = bs.read_bits(bits_per_char)
            if c == 0:
                break
            name_bytes.append(c)
        try:
            self.sEarName = bytes(name_bytes).decode('utf-8')
        except:
            self.sEarName = bytes(name_bytes).decode('latin-1', errors='replace')

    def is_valid(self) -> bool:
        return self.iEarLevel > 0
    
    def serialize(self, bs, version: int):
        bs.write_bits(3, self.iEarClass)
        bs.write_bits(7, self.iEarLevel)
        bits_per_char = 8 if is_ptr24_and_above(version) else 7
        name_bytes = self.sEarName.encode('utf-8') if isinstance(self.sEarName, str) else self.sEarName
        for c in name_bytes:
            bs.write_bits(bits_per_char, c)
        bs.write_bits(bits_per_char, 0)


class LongName:
    def __init__(self):
        self.name_1: int = 0
        self.name_2: int = 0
        self.pref_1: Optional[int] = None
        self.suff_1: Optional[int] = None
        self.pref_2: Optional[int] = None
        self.suff_2: Optional[int] = None
        self.pref_3: Optional[int] = None
        self.suff_3: Optional[int] = None


    def deserialize(self, bs):
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
    
    def serialize(self, bs):
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
    def __init__(self):
        self.is_not_gold = False
        self.quantity = 0

    def deserialize(self, bs):
        self.is_not_gold = bs.read_bits(1) != 0
        self.quantity = bs.read_bits(12)


_TRACE_PROPERTY = False
_TRACE_ITEM = False
_TRACE_ITEM_IDX = -1

class PropertyList:
    def __init__(self):
        self.mProperty: List[Tuple[int, int, int]] = []
        self.iEndFlag = 0
        self._version: int = 0
        self._use_stat_cost: bool = False

    def deserialize(self, bs, version: int):
        self._version = version
        self.mProperty = []
        self._use_stat_cost = _g_stat_cost is not None and is_d2r(version)

        while True:
            bit_pos = bs.getOffset() if _TRACE_PROPERTY else 0
            self.iEndFlag = bs.read_bits(9)
            if self.iEndFlag >= 0x1FF:
                break

            if self._use_stat_cost:
                stat_cost = get_stat_cost(self.iEndFlag)
                if stat_cost is None or stat_cost.save_bits == 0:
                    continue

                layer = 0
                if stat_cost.save_param_bits > 0:
                    layer = bs.read_bits(stat_cost.save_param_bits)

                raw_value = bs.read_bits(stat_cost.save_bits)
                value = (raw_value - stat_cost.save_add) << stat_cost.val_shift
                self.mProperty.append((self.iEndFlag, layer, value))

                if _TRACE_PROPERTY:
                    print(f'  stat {self.iEndFlag}: bit_pos={bit_pos}, layer={layer}, raw_value={raw_value}, value={value}, save_bits={stat_cost.save_bits}, save_param_bits={stat_cost.save_param_bits}')

                for paired_id in PAIRED_STATS.get(self.iEndFlag, []):
                    paired_cost = get_stat_cost(paired_id)
                    if paired_cost and paired_cost.save_bits > 0:
                        paired_raw = bs.read_bits(paired_cost.save_bits)
                        paired_value = (paired_raw - paired_cost.save_add) << paired_cost.val_shift
                        self.mProperty.append((paired_id, 0, paired_value))
                        if _TRACE_PROPERTY:
                            print(f'    paired stat {paired_id}: raw={paired_raw}, value={paired_value}')

                if self.iEndFlag == 57:
                    self.mProperty.append((88, 0, 1))
            else:
                prop_meta = get_property_meta(self.iEndFlag, version)
                if prop_meta and prop_meta.bits_sum > 0:
                    value = bs.read_bits(prop_meta.bits_sum)
                    self.mProperty.append((self.iEndFlag, 0, value))

    def ext_sockets(self) -> int:
        r = 0
        for prop_id, layer, value in self.mProperty:
            if prop_id == 194:
                r += value
        return r

    def is_indestructible(self) -> bool:
        for prop_id, layer, value in self.mProperty:
            if prop_id == 152 and value != 0:
                return True
        return False

    def get_parsed_properties(self, version: int = None) -> List[Tuple[int, int, List[int]]]:
        ver = version if version is not None else self._version
        result = []
        for prop_id, layer, value in self.mProperty:
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

    def _isc_to_params(self, prop_id: int, layer: int, value: int, version: int) -> List[int]:
        prop_meta = get_property_meta(prop_id, version)
        stat_cost = get_stat_cost(prop_id)
        display_value = value >> stat_cost.val_shift if stat_cost and stat_cost.val_shift > 0 else value

        if not prop_meta or prop_meta.bits_sum == 0:
            if stat_cost and stat_cost.save_param_bits > 0:
                return self._isc_layer_to_params(prop_id, layer, display_value, version)
            return [display_value, 0, 0, 0]

        fields = prop_meta.fields
        active_fields = [f for f in fields if f.bits > 0]

        isc_bits = stat_cost.save_bits + stat_cost.save_param_bits if stat_cost else 0
        if len(active_fields) <= 1 and stat_cost and stat_cost.save_param_bits > 0 and isc_bits > prop_meta.bits_sum:
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

    def _isc_layer_to_params(self, prop_id: int, layer: int, display_value: int, version: int) -> List[int]:
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

    IMPLICIT_STATS = {88}

    def serialize(self, bs, version: int):
        self._use_stat_cost = _g_stat_cost is not None and is_d2r(version)
        
        all_paired_ids = set()
        for paired_list in PAIRED_STATS.values():
            all_paired_ids.update(paired_list)
        
        for prop_id, layer, value in self.mProperty:
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
                        for pid, pl, pv in self.mProperty:
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
    def __init__(self, meta: ItemMetaData = None):
        self.gems: int = 0
        self.guid: int = 0
        self.drop_level: int = 99
        self.quality: int = 2
        self.has_var_gfx: bool = False
        self.var_gfx: Optional[int] = None
        self.has_class: bool = False
        self.item_class: Optional[int] = None
        self.low_quality_id: Optional[int] = None
        self.high_quality_id: Optional[int] = None
        self.magic_prefix: Optional[int] = None
        self.magic_suffix: Optional[int] = None
        self.set_id: Optional[int] = None
        self.rare_name: Optional[LongName] = None
        self.unique_id: Optional[int] = None
        self.craft_name: Optional[LongName] = None
        self.rune_id: Optional[int] = None
        self.person_name: List[int] = []
        self.monster_id: Optional[int] = None
        self.charm_id: Optional[int] = None
        self.spell_id: Optional[int] = None
        self.body_part_file_index: Optional[int] = None
        self.spell_type: Optional[int] = None

    # Transitional property aliases
    @property
    def nGems(self) -> int: return self.gems
    @nGems.setter
    def nGems(self, v: int): self.gems = v

    @property
    def dwGUID(self) -> int: return self.guid
    @dwGUID.setter
    def dwGUID(self, v: int): self.guid = v

    @property
    def iDropLevel(self) -> int: return self.drop_level
    @iDropLevel.setter
    def iDropLevel(self, v: int): self.drop_level = v

    @property
    def iQuality(self) -> int: return self.quality
    @iQuality.setter
    def iQuality(self, v: int): self.quality = v

    @property
    def bVarGfx(self) -> bool: return self.has_var_gfx
    @bVarGfx.setter
    def bVarGfx(self, v: bool): self.has_var_gfx = v

    @property
    def iVarGfx(self): return MayExist(self, 'var_gfx')
    @iVarGfx.setter
    def iVarGfx(self, v): self.var_gfx = v.value if isinstance(v, MayExist) else v

    @property
    def bClass(self) -> bool: return self.has_class
    @bClass.setter
    def bClass(self, v: bool): self.has_class = v

    @property
    def wClass(self): return MayExist(self, 'item_class')
    @wClass.setter
    def wClass(self, v): self.item_class = v.value if isinstance(v, MayExist) else v

    @property
    def loQual(self): return MayExist(self, 'low_quality_id')
    @loQual.setter
    def loQual(self, v): self.low_quality_id = v.value if isinstance(v, MayExist) else v

    @property
    def hiQual(self): return MayExist(self, 'high_quality_id')
    @hiQual.setter
    def hiQual(self, v): self.high_quality_id = v.value if isinstance(v, MayExist) else v

    @property
    def wPrefix(self): return MayExist(self, 'magic_prefix')
    @wPrefix.setter
    def wPrefix(self, v): self.magic_prefix = v.value if isinstance(v, MayExist) else v

    @property
    def wSuffix(self): return MayExist(self, 'magic_suffix')
    @wSuffix.setter
    def wSuffix(self, v): self.magic_suffix = v.value if isinstance(v, MayExist) else v

    @property
    def wSetID(self): return MayExist(self, 'set_id')
    @wSetID.setter
    def wSetID(self, v): self.set_id = v.value if isinstance(v, MayExist) else v

    @property
    def pRareName(self) -> Optional[LongName]: return self.rare_name
    @pRareName.setter
    def pRareName(self, v: Optional[LongName]): self.rare_name = v

    @property
    def wUniID(self): return MayExist(self, 'unique_id')
    @wUniID.setter
    def wUniID(self, v): self.unique_id = v.value if isinstance(v, MayExist) else v

    @property
    def pCraftName(self) -> Optional[LongName]: return self.craft_name
    @pCraftName.setter
    def pCraftName(self, v: Optional[LongName]): self.craft_name = v

    @property
    def wRune(self): return MayExist(self, 'rune_id')
    @wRune.setter
    def wRune(self, v): self.rune_id = v.value if isinstance(v, MayExist) else v

    @property
    def sPersonName(self) -> List[int]: return self.person_name
    @sPersonName.setter
    def sPersonName(self, v: List[int]): self.person_name = v

    @property
    def wMonsterID(self): return MayExist(self, 'monster_id')
    @wMonsterID.setter
    def wMonsterID(self, v): self.monster_id = v.value if isinstance(v, MayExist) else v

    @property
    def wCharm(self): return MayExist(self, 'charm_id')
    @wCharm.setter
    def wCharm(self, v): self.charm_id = v.value if isinstance(v, MayExist) else v

    @property
    def iSpellID(self): return MayExist(self, 'spell_id')
    @iSpellID.setter
    def iSpellID(self, v): self.spell_id = v.value if isinstance(v, MayExist) else v

    @property
    def iBodyPartFileIndex(self): return MayExist(self, 'body_part_file_index')
    @iBodyPartFileIndex.setter
    def iBodyPartFileIndex(self, v): self.body_part_file_index = v.value if isinstance(v, MayExist) else v

    @property
    def iSpellType(self): return MayExist(self, 'spell_type')
    @iSpellType.setter
    def iSpellType(self, v): self.spell_type = v.value if isinstance(v, MayExist) else v

    def is_set(self) -> bool:
        return self.quality == 5

    def rune_word_id(self) -> int:
        return self.rune_id if self.rune_id is not None else 0

    def deserialize(self, bs, version: int, bIsCharm: bool, bRuneWord: bool,
                  bPersonalized: bool, bHasMonsterID: bool, bHasSpellId: bool,
                  bIsBodyPart: bool = False, bIsScrollOrBook: bool = False):
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

        if self.quality == 1:
            self.low_quality_id = bs.read_bits(3)
        elif self.quality == 2:
            if bIsCharm:
                self.charm_id = bs.read_bits(12)
            elif bIsBodyPart:
                self.body_part_file_index = bs.read_bits(10)
            elif bIsScrollOrBook:
                self.spell_type = bs.read_bits(5)
        elif self.quality == 3:
            self.high_quality_id = bs.read_bits(3)
        elif self.quality == 4:
            self.magic_prefix = bs.read_bits(11)
            self.magic_suffix = bs.read_bits(11)
        elif self.quality == 5:
            self.set_id = bs.read_bits(12)
        elif self.quality == 6:
            self.rare_name = LongName()
            self.rare_name.deserialize(bs)
        elif self.quality == 7:
            self.unique_id = bs.read_bits(12)
        elif self.quality == 8:
            self.craft_name = LongName()
            self.craft_name.deserialize(bs)

        if bRuneWord:
            self.rune_id = bs.read_bits(16)

        if bPersonalized:
            bits_per_char = 8 if is_ptr24_and_above(version) else 7
            for _ in range(16):
                c = bs.read_bits(bits_per_char)
                if c == 0:
                    break
                self.person_name.append(c)

        if bHasMonsterID:
            self.monster_id = bs.read_bits(10)
        elif bHasSpellId:
            self.spell_id = bs.read_bits(5)
    
    def serialize(self, bs, version: int, bIsCharm: bool, bRuneWord: bool,
                   bPersonalized: bool, bHasMonsterID: bool, bHasSpellId: bool,
                   bIsBodyPart: bool = False, bIsScrollOrBook: bool = False):
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
        
        if self.quality == 1:
            bs.write_bits(3, self.low_quality_id if self.low_quality_id is not None else 0)
        elif self.quality == 2:
            if bIsCharm:
                bs.write_bits(12, self.charm_id if self.charm_id is not None else 0)
            elif bIsBodyPart:
                bs.write_bits(10, self.body_part_file_index if self.body_part_file_index is not None else 0)
            elif bIsScrollOrBook:
                bs.write_bits(5, self.spell_type if self.spell_type is not None else 0)
        elif self.quality == 3:
            bs.write_bits(3, self.high_quality_id if self.high_quality_id is not None else 0)
        elif self.quality == 4:
            bs.write_bits(11, self.magic_prefix if self.magic_prefix is not None else 0)
            bs.write_bits(11, self.magic_suffix if self.magic_suffix is not None else 0)
        elif self.quality == 5:
            bs.write_bits(12, self.set_id if self.set_id is not None else 0)
        elif self.quality == 6:
            if self.rare_name:
                self.rare_name.serialize(bs)
        elif self.quality == 7:
            bs.write_bits(12, self.unique_id if self.unique_id is not None else 0)
        elif self.quality == 8:
            if self.craft_name:
                self.craft_name.serialize(bs)
        
        if bRuneWord:
            bs.write_bits(16, self.rune_id if self.rune_id is not None else 0)
        
        if bPersonalized:
            bits_per_char = 8 if is_ptr24_and_above(version) else 7
            for c in self.person_name:
                bs.write_bits(bits_per_char, c)
            bs.write_bits(bits_per_char, 0)
        
        if bHasMonsterID:
            bs.write_bits(10, self.monster_id if self.monster_id is not None else 0)
        elif bHasSpellId:
            bs.write_bits(5, self.spell_id if self.spell_id is not None else 0)


class TypeSpecificInfo:
    def __init__(self, meta: ItemMetaData = None):
        self.defence: Optional[int] = None
        self.max_durability: Optional[int] = None
        self.current_durability: Optional[int] = None
        self.sockets_count: Optional[int] = None
        self.quantity: Optional[int] = None
        self.has_set_prop_list: List[bool] = []
        self.property_list: PropertyList = PropertyList()
        self.set_properties: List[Optional[PropertyList]] = []
        self.runeword_property_list: Optional[PropertyList] = None


    def sockets(self) -> Tuple[int, int]:
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
        if self.max_durability == 0:
            return True
        if self.property_list.is_indestructible():
            return True
        return False

    def deserialize(self, bs, version: int, bHasDef: bool, bHasDur: bool,
                  bSocketed: bool, bIsStacked: bool, bIsSet: bool, bRuneWord: bool,
                  use_stat_cost: bool = False, d2r_order: bool = False):
        if bHasDef:
            if use_stat_cost:
                ac_stat = get_stat_cost(31)
                def_bits = ac_stat.save_bits if ac_stat else 11
            else:
                def_bits = 11
            self.defence = bs.read_bits(def_bits)
        if bHasDur:
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
            elif bIsStacked:
                self.quantity = bs.read_bits(9)
            if bSocketed:
                if use_stat_cost:
                    sock_stat = get_stat_cost(194)
                    sock_bits = sock_stat.save_bits if sock_stat else 3
                else:
                    sock_bits = 4
                self.sockets_count = bs.read_bits(sock_bits)
                if self.sockets_count < 1:
                    self.sockets_count = 1
        else:
            if bSocketed:
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
            elif bIsStacked:
                self.quantity = bs.read_bits(9)
        if bIsSet:
            self.has_set_prop_list = [bs.read_bits(1) != 0 for _ in range(5)]
        else:
            self.has_set_prop_list = [False] * 5

        self.property_list.deserialize(bs, version)

        self.set_properties = []
        if bIsSet:
            for i in range(5):
                if self.has_set_prop_list[i]:
                    prop_list = PropertyList()
                    prop_list.deserialize(bs, version)
                    self.set_properties.append(prop_list)
                else:
                    self.set_properties.append(None)

        if bRuneWord:
            self.runeword_property_list = PropertyList()
            self.runeword_property_list.deserialize(bs, version)
    
    def serialize(self, bs, version: int, bHasDef: bool, bHasDur: bool,
                   bSocketed: bool, bIsStacked: bool, bIsSet: bool, bRuneWord: bool,
                   use_stat_cost: bool = False, d2r_order: bool = False):
        if bHasDef:
            if use_stat_cost:
                ac_stat = get_stat_cost(31)
                def_bits = ac_stat.save_bits if ac_stat else 11
            else:
                def_bits = 11
            bs.write_bits(def_bits, self.defence if self.defence is not None else 0)
        
        if bHasDur:
            if use_stat_cost:
                max_dur_stat = get_stat_cost(73)
                max_dur_bits = max_dur_stat.save_bits if max_dur_stat else 8
                dur_stat = get_stat_cost(72)
                dur_bits = dur_stat.save_bits if dur_stat else 9
            else:
                max_dur_bits = 8
                dur_bits = 9
            bs.write_bits(max_dur_bits, self.max_durability if self.max_durability is not None else 0)
            if self.max_durability is not None and self.max_durability > 0:
                bs.write_bits(dur_bits, self.current_durability if self.current_durability is not None else 0)
        
        if d2r_order:
            if version >= 0x69:
                has_quantity = self.quantity is not None
                bs.write_bits(1, 1 if has_quantity else 0)
                if has_quantity:
                    bs.write_bits(9, self.quantity)
            elif bIsStacked:
                bs.write_bits(9, self.quantity if self.quantity is not None else 0)
            if bSocketed:
                if use_stat_cost:
                    sock_stat = get_stat_cost(194)
                    sock_bits = sock_stat.save_bits if sock_stat else 3
                else:
                    sock_bits = 4
                bs.write_bits(sock_bits, self.sockets_count if self.sockets_count is not None else 1)
        else:
            if bSocketed:
                if use_stat_cost:
                    sock_stat = get_stat_cost(194)
                    sock_bits = sock_stat.save_bits if sock_stat else 3
                else:
                    sock_bits = 4
                bs.write_bits(sock_bits, self.sockets_count if self.sockets_count is not None else 1)
            if version >= 0x69:
                has_quantity = self.quantity is not None
                bs.write_bits(1, 1 if has_quantity else 0)
                if has_quantity:
                    bs.write_bits(9, self.quantity)
            elif bIsStacked:
                bs.write_bits(9, self.quantity if self.quantity is not None else 0)
        
        if bIsSet:
            for has_prop in self.has_set_prop_list:
                bs.write_bits(1, 1 if has_prop else 0)
        
        self.property_list.serialize(bs, version)
        
        if bIsSet:
            for i, prop_list in enumerate(self.set_properties):
                if i < len(self.has_set_prop_list) and self.has_set_prop_list[i] and prop_list:
                    prop_list.serialize(bs, version)
        
        if bRuneWord and self.runeword_property_list:
            self.runeword_property_list.serialize(bs, version)


class ItemInfo:
    STACKABLE_FOR_STASH = {
        b'rvs ', b'rvl ', b'gcv ', b'gfv ', b'gsv ', b'gzv ', b'gpv ',
        b'gcy ', b'gfy ', b'gsy ', b'gly ', b'gpy ',
        b'gcb ', b'gfb ', b'gsb ', b'glb ', b'gpb ',
        b'gcg ', b'gfg ', b'gsg ', b'glg ', b'gpg ',
        b'gcr ', b'gfr ', b'gsr ', b'glr ', b'gpr ',
        b'gcw ', b'gfw ', b'gsw ', b'glw ', b'gpw ',
        b'skc ', b'skf ', b'sku ', b'skl ', b'skz ',
        b'r01 ', b'r02 ', b'r03 ', b'r04 ', b'r05 ',
        b'r06 ', b'r07 ', b'r08 ', b'r09 ', b'r10 ',
        b'r11 ', b'r12 ', b'r13 ', b'r14 ', b'r15 ',
        b'r16 ', b'r17 ', b'r18 ', b'r19 ', b'r20 ',
        b'r21 ', b'r22 ', b'r23 ', b'r24 ', b'r25 ',
        b'r26 ', b'r27 ', b'r28 ', b'r29 ', b'r30 ',
        b'r31 ', b'r32 ', b'r33 ',
        b'pk1 ', b'pk2 ', b'pk3 ',
        b'dhn ', b'bey ', b'mbr ', b'toa ', b'tes ',
        b'ceh ', b'bet ', b'fed ',
    }

    def __init__(self, meta: ItemMetaData = None):
        self.type_name: bytes = b'    '
        self.ext_info: Optional[ExtItemInfo] = None
        self.gold: Optional[GoldQuantity] = None
        self.has_rand: bool = False
        self.timestamp_flag: List[int] = []
        self.realm_data: List[int] = []
        self.stash_stack_size: int = 0
        self.has_stash_stack_size: bool = False
        self.quest_difficulty: int = 0
        self.type_specific_info: Optional[TypeSpecificInfo] = None
        self.pad: int = 0
        self._meta = meta

    # Transitional property aliases
    @property
    def sTypeName(self) -> bytes: return self.type_name
    @sTypeName.setter
    def sTypeName(self, v: bytes): self.type_name = v

    @property
    def pExtItemInfo(self) -> Optional[ExtItemInfo]: return self.ext_info
    @pExtItemInfo.setter
    def pExtItemInfo(self, v: Optional[ExtItemInfo]): self.ext_info = v

    @property
    def pGold(self) -> Optional[GoldQuantity]: return self.gold
    @pGold.setter
    def pGold(self, v: Optional[GoldQuantity]): self.gold = v

    @property
    def bHasRand(self) -> bool: return self.has_rand
    @bHasRand.setter
    def bHasRand(self, v: bool): self.has_rand = v

    @property
    def pTimeStampFlag(self) -> List[int]: return self.timestamp_flag
    @pTimeStampFlag.setter
    def pTimeStampFlag(self, v: List[int]): self.timestamp_flag = v

    @property
    def pRealmData(self) -> List[int]: return self.realm_data
    @pRealmData.setter
    def pRealmData(self, v: List[int]): self.realm_data = v

    @property
    def iAdvancedStashStackSize(self) -> int: return self.stash_stack_size
    @iAdvancedStashStackSize.setter
    def iAdvancedStashStackSize(self, v: int): self.stash_stack_size = v

    @property
    def _bHasAdvancedStashSize(self) -> bool: return self.has_stash_stack_size
    @_bHasAdvancedStashSize.setter
    def _bHasAdvancedStashSize(self, v: bool): self.has_stash_stack_size = v

    @property
    def iQuestDifficulty(self) -> int: return self.quest_difficulty
    @iQuestDifficulty.setter
    def iQuestDifficulty(self, v: int): self.quest_difficulty = v

    @property
    def pTpSpInfo(self) -> Optional[TypeSpecificInfo]: return self.type_specific_info
    @pTpSpInfo.setter
    def pTpSpInfo(self, v: Optional[TypeSpecificInfo]): self.type_specific_info = v

    @property
    def iPad(self) -> int: return self.pad
    @iPad.setter
    def iPad(self, v: int): self.pad = v

    def is_gold(self) -> bool:
        return self.type_name == b'gld '

    def is_box(self) -> bool:
        return self.type_name == b'box '

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

    def deserialize(self, bs, version: int, bSimple: bool, bRuneWord: bool,
                  bPersonalized: bool, bSocketed: bool) -> Optional[ItemMetaData]:
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

        if not bSimple and meta:
            self.ext_info = ExtItemInfo(meta)
            self.ext_info.deserialize(bs, version,
                                      meta.is_charm if meta else False,
                                      bRuneWord, bPersonalized,
                                      meta.has_monster_id if meta else False,
                                      (meta.spell_id > 0) if meta else False)

        if self.is_gold():
            self.gold = GoldQuantity()
            self.gold.deserialize(bs)

        self.has_rand = bs.read_bits(1) != 0
        if self.has_rand:
            if is_d2r_ and version > 86:
                realm_count = 4 if version > 96 else (3 if version > 93 else 2)
                self.realm_data = [bs.read_bits(32) for _ in range(realm_count)]
            elif not bSimple:
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

        if not bSimple and meta:
            self.type_specific_info = TypeSpecificInfo(meta)
            self.type_specific_info.deserialize(bs, version,
                                               meta.has_def if meta else False,
                                               meta.has_dur if meta else False,
                                               bSocketed,
                                               meta.is_stacked if meta else False,
                                               self.is_set(),
                                               bRuneWord)
        elif is_d2r_ and version >= 0x69 and meta and meta.ipad_bits > 0:
            self.pad = bs.read_bits(meta.ipad_bits)

        return meta


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


class D2Item:
    def __init__(self, meta: ItemMetaData = None):
        self.version = 0
        self.magic = ITEM_LIST_MAGIC
        self.bQuest = False
        self.iTargetDelFlags = 0
        self.is_identified = True
        self.iSwitchInOutFlags = 0
        self.bDisabled = False
        self.iRepairFlags = 0
        self.is_socketed = False
        self.bNoSell = False
        self.bNew = False
        self.bBadEquipped = False
        self.bNamed = False
        self.is_ear = False
        self.bNewbie = False
        self.iInitFlags = 0
        self.is_simple = True
        self.is_ethereal = False
        self.bJustSaved = True
        self.is_personalized = False
        self.bLowQuality = False
        self.is_runeword = False
        self.iDuplicateChronicle = 0
        self.wVersion = 101
        self.iVersionHigh = 0xA0
        self.iLocation = 0
        self.iPosition = 0
        self.iColumn = 0
        self.iRow = 0
        self.iStoredIn = 1
        
        self._flags = 0
        self._bHasQuantity = False
        self._bChronicle = False
        self._bChronicleCompact = False

        self.ear: Optional[Ear] = None
        self.item_info: Optional[ItemInfo] = None
        self.gem_items: List[D2Item] = []

        self._meta = meta

    # Transitional property aliases
    @property
    def dwVersion(self) -> int: return self.version
    @dwVersion.setter
    def dwVersion(self, v: int): self.version = v

    @property
    def wMajic(self) -> int: return self.magic
    @wMajic.setter
    def wMajic(self, v: int): self.magic = v

    @property
    def bIdentified(self) -> bool: return self.is_identified
    @bIdentified.setter
    def bIdentified(self, v: bool): self.is_identified = v

    @property
    def bSocketed(self) -> bool: return self.is_socketed
    @bSocketed.setter
    def bSocketed(self, v: bool): self.is_socketed = v

    @property
    def bEar(self) -> bool: return self.is_ear
    @bEar.setter
    def bEar(self, v: bool): self.is_ear = v

    @property
    def bSimple(self) -> bool: return self.is_simple
    @bSimple.setter
    def bSimple(self, v: bool): self.is_simple = v

    @property
    def bEthereal(self) -> bool: return self.is_ethereal
    @bEthereal.setter
    def bEthereal(self, v: bool): self.is_ethereal = v

    @property
    def bPersonalized(self) -> bool: return self.is_personalized
    @bPersonalized.setter
    def bPersonalized(self, v: bool): self.is_personalized = v

    @property
    def bRuneWord(self) -> bool: return self.is_runeword
    @bRuneWord.setter
    def bRuneWord(self, v: bool): self.is_runeword = v

    @property
    def pEar(self) -> Optional[Ear]: return self.ear
    @pEar.setter
    def pEar(self, v: Optional[Ear]): self.ear = v

    @property
    def pItemInfo(self) -> Optional[ItemInfo]: return self.item_info
    @pItemInfo.setter
    def pItemInfo(self, v: Optional[ItemInfo]): self.item_info = v

    @property
    def aGemItems(self) -> List[D2Item]: return self.gem_items
    @aGemItems.setter
    def aGemItems(self, v: List[D2Item]): self.gem_items = v

    @property
    def type_name(self) -> bytes:
        if self.item_info and self.item_info.type_name.strip():
            return self.item_info.type_name
        if self.is_ear:
            return b'ear '
        if self._meta:
            return self._meta.type_id
        if self.item_info:
            return self.item_info.type_name
        return b'    '

    @type_name.setter
    def type_name(self, value: bytes):
        if self.item_info:
            self.item_info.type_name = value
        if self._meta:
            self._meta.type_id = value
        else:
            self._meta = ItemMetaData(type_id=value)

    @property
    def sTypeName(self) -> bytes: return self.type_name
    @sTypeName.setter
    def sTypeName(self, value: bytes): self.type_name = value

    def quality(self) -> int:
        if self.is_ear or self.is_simple:
            if self._meta and self._meta.is_unique:
                return 7
            return 2
        if self.item_info and self.item_info.ext_info:
            return self.item_info.ext_info.quality
        return 2

    def get_flag_names(self) -> List[str]:
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

    def deserialize(self, bs, version: int, read_magic: bool = True):
        if is_d2r(version):
            self._read_data_d2r(bs, version, read_magic)
        else:
            self._read_data_classic(bs, version, read_magic)

    def _read_data_d2r(self, bs, version: int, read_magic: bool = True):
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

        hf = bs.read_bits(1)
        vv = bs.read_bits(2)
        self.wVersion = (vv + 99) if hf else vv

        mode = bs.read_bits(3)
        self.iLocation = mode
        if mode == 3 or mode == 5:
            self.iPosition = 0
            self.iColumn = bs.read_bits(16)
            self.iRow = bs.read_bits(16)
            self.iStoredIn = 0
        else:
            self.iPosition = bs.read_bits(4)
            self.iColumn = bs.read_bits(4)
            self.iRow = bs.read_bits(4)
            self.iStoredIn = bs.read_bits(3) - 1

        huffman = get_huffman()
        if self.is_ear:
            self.ear = Ear()
            self.ear.deserialize(bs, self.version)
            self._meta = get_item_meta(b'ear ', self.version)
            type_name = b'ear '
        else:
            type_name = bytes([huffman.read_char(bs) for _ in range(4)])
            self._meta = get_item_meta(type_name, self.version)
            self.item_info = ItemInfo(self._meta)
            self.item_info.type_name = type_name

        if self.is_simple:
            self._read_compact_d2r(bs, version, type_name, self._bChronicle, self._bChronicleCompact)
        else:
            self._read_complete_d2r(bs, version, type_name, self._bChronicle, self._bChronicleCompact)

        bs.align_byte()

        gem_count = self.gems()
        self.gem_items = []
        for _ in range(gem_count):
            item = D2Item()
            item.deserialize(bs, self.version, self.version <= 96)
            self.gem_items.append(item)

    def _read_compact_d2r(self, bs, version: int, type_name: bytes,
                          bChronicle: bool, bChronicleCompact: bool):
        if self.is_ear:
            return

        if version > 92:
            from core.d2data import get_d2data
            d2data = get_d2data()
            code = type_name.decode('ascii', errors='replace').strip()
            type_info = d2data.get_item(code) if d2data else None
            if type_info and type_info.quest > 0 and type_info.questdiffcheck:
                quest_diff_stat = get_stat_cost(356)
                if quest_diff_stat and quest_diff_stat.save_bits > 0:
                    raw = bs.read_bits(quest_diff_stat.save_bits)
                    if self.item_info:
                        self.item_info.quest_difficulty = (raw - quest_diff_stat.save_add) << quest_diff_stat.val_shift

        realm_flag = bs.read_bits(1)
        if realm_flag:
            realm_count = 4 if version > 96 else (3 if version > 93 else 2)
            if self.item_info:
                self.item_info.realm_data = [bs.read_bits(32) for _ in range(realm_count)]

        self._read_advanced_stash_size(bs, version, type_name)

    def _read_complete_d2r(self, bs, version: int, type_name: bytes,
                           bChronicle: bool, bChronicleCompact: bool):
        if self.is_ear:
            return

        meta = self._meta

        ext = ExtItemInfo(meta)
        ext.deserialize(bs, version,
                      meta.is_charm if meta else False,
                      self.is_runeword,
                      self.is_personalized,
                      False, False,
                      (meta.is_body_part and not meta.is_player_body_part) if meta else False,
                      meta.is_scroll_or_book if meta else False)
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
        tp.deserialize(bs, version,
                     meta.has_def if meta else False,
                     meta.has_dur if meta else False,
                     self.is_socketed,
                     meta.is_stacked if meta else False,
                     self.is_set(),
                     self.is_runeword,
                     use_stat_cost=True, d2r_order=True)
        if self.item_info:
            self.item_info.type_specific_info = tp

        if bChronicle:
            chronicle_id = bs.read_bits(16)
            if bChronicleCompact:
                bs.read_bits(64)
            else:
                bs.read_bits(32)
                count = bs.read_bits(4)
                for _ in range(count):
                    bs.read_bits(64)

        self._read_advanced_stash_size(bs, version, type_name)

    def _read_advanced_stash_size(self, bs, version: int, type_name: bytes):
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

    def _read_data_classic(self, bs, version: int, read_magic: bool = True):
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

        self.bQuest = bs.read_bits(1) != 0
        self.iTargetDelFlags = bs.read_bits(3)
        self.is_identified = bs.read_bits(1) != 0
        self.iSwitchInOutFlags = bs.read_bits(3)
        self.bDisabled = bs.read_bits(1) != 0
        self.iRepairFlags = bs.read_bits(2)
        self.is_socketed = bs.read_bits(1) != 0
        self.bNoSell = bs.read_bits(1) != 0
        self.bNew = bs.read_bits(1) != 0
        self.bBadEquipped = bs.read_bits(1) != 0
        self.bNamed = bs.read_bits(1) != 0
        self.is_ear = bs.read_bits(1) != 0
        self.bNewbie = bs.read_bits(1) != 0
        self.iInitFlags = bs.read_bits(3)
        self.is_simple = bs.read_bits(1) != 0
        self.is_ethereal = bs.read_bits(1) != 0
        self.bJustSaved = bs.read_bits(1) != 0
        self.is_personalized = bs.read_bits(1) != 0
        self.bLowQuality = bs.read_bits(1) != 0
        self.is_runeword = bs.read_bits(1) != 0

        self.iDuplicateChronicle = bs.read_bits(5)
        self.wVersion = bs.read_bits(10)

        self.iLocation = bs.read_bits(3)
        self.iPosition = bs.read_bits(4)
        self.iColumn = bs.read_bits(4)
        self.iRow = bs.read_bits(4)
        self.iStoredIn = bs.read_bits(3)

        if self.is_ear:
            self.ear = Ear()
            self.ear.deserialize(bs, self.version)
            self._meta = get_item_meta(b'ear ', self.version)
        else:
            self.item_info = ItemInfo(self._meta)
            self._meta = self.item_info.deserialize(bs, self.version,
                                                   self.is_simple,
                                                   self.is_runeword,
                                                   self.is_personalized,
                                                   self.is_socketed)

        bs.align_byte()

        gem_count = self.gems()
        self.gem_items = []
        for _ in range(gem_count):
            item = D2Item()
            item.deserialize(bs, self.version, True)
            self.gem_items.append(item)

    def serialize(self, bs, version: int, write_magic: bool = True):
        if is_d2r(version):
            self._serialize_d2r(bs, version, write_magic and version <= 96)
        else:
            self._serialize_classic(bs, version, write_magic)
    
    def _serialize_d2r(self, bs, version: int, write_magic: bool = True):
        if write_magic:
            bs.align_byte()
            bs.write_word(self.magic)
            bs.write_dword(self.version)
        
        bs.write_bits(32, self._flags)
        
        if self.wVersion >= 99:
            bs.write_bits(1, 1)
            bs.write_bits(2, self.wVersion - 99)
        else:
            bs.write_bits(1, 0)
            bs.write_bits(2, self.wVersion)
        
        bs.write_bits(3, self.iLocation)
        if self.iLocation == 3 or self.iLocation == 5:
            bs.write_bits(16, self.iColumn)
            bs.write_bits(16, self.iRow)
        else:
            bs.write_bits(4, self.iPosition)
            bs.write_bits(4, self.iColumn)
            bs.write_bits(4, self.iRow)
            bs.write_bits(3, self.iStoredIn + 1)
        
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
    
    def _write_compact_d2r(self, bs, version: int):
        if not self.item_info:
            return
        
        if version > 92:
            if self.item_info.quest_difficulty > 0:
                quest_diff_stat = get_stat_cost(356)
                if quest_diff_stat and quest_diff_stat.save_bits > 0:
                    raw = (self.item_info.quest_difficulty >> quest_diff_stat.val_shift) + quest_diff_stat.save_add
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
    
    def _write_complete_d2r(self, bs, version: int):
        if not self.item_info or not self.item_info.ext_info:
            return
        
        ext = self.item_info.ext_info
        meta = self._meta
        
        ext.serialize(bs, version,
                       meta.is_charm if meta else False,
                       self.is_runeword,
                       self.is_personalized,
                       False, False,
                       (meta.is_body_part and not meta.is_player_body_part) if meta else False,
                       meta.is_scroll_or_book if meta else False)
        
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
            tp.serialize(bs, version,
                          meta.has_def if meta else False,
                          meta.has_dur if meta else False,
                          self.is_socketed,
                          meta.is_stacked if meta else False,
                          self.is_set(),
                          self.is_runeword,
                          use_stat_cost=True, d2r_order=True)
        
        self._write_advanced_stash_size(bs, version)
    
    def _write_advanced_stash_size(self, bs, version: int):
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
    
    def _serialize_classic(self, bs, version: int, write_magic: bool = True):
        if write_magic:
            bs.align_byte()
            bs.write_word(self.magic)
            bs.write_dword(self.version)
        
        bs.write_bits(1, 1 if self.bQuest else 0)
        bs.write_bits(3, self.iTargetDelFlags)
        bs.write_bits(1, 1 if self.is_identified else 0)
        bs.write_bits(3, self.iSwitchInOutFlags)
        bs.write_bits(1, 1 if self.bDisabled else 0)
        bs.write_bits(2, self.iRepairFlags)
        bs.write_bits(1, 1 if self.is_socketed else 0)
        bs.write_bits(1, 1 if self.bNoSell else 0)
        bs.write_bits(1, 1 if self.bNew else 0)
        bs.write_bits(1, 1 if self.bBadEquipped else 0)
        bs.write_bits(1, 1 if self.bNamed else 0)
        bs.write_bits(1, 1 if self.is_ear else 0)
        bs.write_bits(1, 1 if self.bNewbie else 0)
        bs.write_bits(3, self.iInitFlags)
        bs.write_bits(1, 1 if self.is_simple else 0)
        bs.write_bits(1, 1 if self.is_ethereal else 0)
        bs.write_bits(1, 1 if self.bJustSaved else 0)
        bs.write_bits(1, 1 if self.is_personalized else 0)
        bs.write_bits(1, 1 if self.bLowQuality else 0)
        bs.write_bits(1, 1 if self.is_runeword else 0)
        
        bs.write_bits(5, self.iDuplicateChronicle)
        bs.write_bits(10, self.wVersion)
        
        bs.write_bits(3, self.iLocation)
        bs.write_bits(4, self.iPosition)
        bs.write_bits(4, self.iColumn)
        bs.write_bits(4, self.iRow)
        bs.write_bits(3, self.iStoredIn)
        
        if self.is_ear:
            if self.ear:
                self.ear.serialize(bs, self.version)
        else:
            if self.item_info and self.item_info.ext_info:
                ext = self.item_info.ext_info
                meta = self._meta
                ext.serialize(bs, version,
                               meta.is_charm if meta else False,
                               self.is_runeword,
                               self.is_personalized,
                               False, False,
                               (meta.is_body_part and not meta.is_player_body_part) if meta else False,
                               meta.is_scroll_or_book if meta else False)
            
            if self.item_info and self.item_info.type_specific_info:
                tp = self.item_info.type_specific_info
                tp.serialize(bs, version,
                              meta.has_def if meta else False,
                              meta.has_dur if meta else False,
                              self.is_socketed,
                              meta.is_stacked if meta else False,
                              self.is_set(),
                              self.is_runeword)
        
        bs.align_byte()
        
        for gem_item in self.gem_items:
            gem_item.serialize(bs, self.version, True)


class ItemList:
    def __init__(self):
        self.magic = ITEM_LIST_MAGIC
        self.count = 0
        self.items: List[D2Item] = []


    def __len__(self) -> int:
        return len(self.items)

    def __iter__(self):
        return iter(self.items)

    def __getitem__(self, index):
        return self.items[index]
    
    def deserialize(self, bs, version: int):
        self.magic = bs.read_word()
        self.count = bs.read_word()
        if self.magic != ITEM_LIST_MAGIC:
            return
        
        self.items = []
        for i in range(self.count):
            if bs.isEnd():
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
            start_offset = bs.getOffset()
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
    
    def serialize(self, bs, version: int):
        bs.align_byte()
        bs.write_word(self.magic)
        bs.write_word(len(self.items))
        
        for item in self.items:
            item.serialize(bs, version, False)
    
    def get_items(self) -> List[D2Item]:
        return self.items
