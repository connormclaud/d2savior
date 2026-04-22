import os
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from core.huffman import HuffmanDecoder, get_huffman


def is_d2r(version: int) -> bool:
    return version >= 0x61


def _convert_item_type_to_meta(type_info, d2data=None) -> Optional['CItemMetaData']:
    if type_info is None:
        return None
    
    meta = CItemMetaData()
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
class CPropertyField:
    bits: int = 0
    base: int = 0
    min_val: int = 0
    max_val: int = 0


@dataclass
class CPropertyMetaDataItem:
    ver_min: int = 0
    fields: List[CPropertyField] = field(default_factory=list)
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


class CPropertyMetaData:
    def __init__(self):
        self._data: List[CPropertyMetaDataItem] = []

    def add_item(self, item: CPropertyMetaDataItem):
        self._data.append(item)

    def find_data(self, version: int) -> Optional[CPropertyMetaDataItem]:
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
class CItemMetaData:
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


class CItemMetaDataManager:
    def __init__(self):
        self._items: Dict[bytes, List[CItemMetaData]] = {}

    def add_item(self, item: CItemMetaData):
        if item.type_id not in self._items:
            self._items[item.type_id] = []
        self._items[item.type_id].append(item)

    def get_item(self, type_id: bytes, version: int = 0) -> Optional[CItemMetaData]:
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

    def get_item_by_name(self, name: str, version: int = 0) -> Optional[CItemMetaData]:
        padded_name = name.ljust(4)[:4].encode('ascii')
        return self.get_item(padded_name, version)



def parse_property_txt(filepath: str) -> Dict[int, CPropertyMetaData]:
    properties: Dict[int, CPropertyMetaData] = {}
    
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
        
        fields: List[CPropertyField] = []
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
                
                fields.append(CPropertyField(bits, base, min_val, max_val))
                bits_sum += bits
            except ValueError:
                break
            
            field_col_idx += 4
        
        while len(fields) < 4:
            fields.append(CPropertyField())
        
        item = CPropertyMetaDataItem(ver_min, fields, default_value, bits_sum)
        
        if prop_id not in properties:
            properties[prop_id] = CPropertyMetaData()
        properties[prop_id].add_item(item)
    
    return properties


def parse_itemdata_txt(filepath: str) -> CItemMetaDataManager:
    manager = CItemMetaDataManager()
    
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
        
        item = CItemMetaData(
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


_g_item_manager: Optional[CItemMetaDataManager] = None
_g_properties: Optional[Dict[int, CPropertyMetaData]] = None
_g_stat_cost: Optional[Dict[int, 'CStatCostItem']] = None


PAIRED_STATS = {
    17: [18],
    48: [49],
    50: [51],
    52: [53],
    54: [55, 56],
    57: [58, 59],
}


@dataclass
class CStatCostItem:
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


def parse_itemstatcost_txt(filepath: str) -> Dict[int, CStatCostItem]:
    result: Dict[int, CStatCostItem] = {}
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

        item = CStatCostItem(
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


def get_item_meta(type_id: bytes, version: int = 0) -> Optional[CItemMetaData]:
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


def _supplement_meta_from_d2data(meta: CItemMetaData, d2data):
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


def get_property_meta(prop_id: int, version: int) -> Optional[CPropertyMetaDataItem]:
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


def get_stat_cost(stat_id: int) -> Optional[CStatCostItem]:
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
    def __init__(self, value_type=int, bits: int = 0):
        self._exists = False
        self._value = None
        self._value_type = value_type
        self._bits = bits

    def exist(self) -> bool:
        return self._exists

    def ensure(self, value=None):
        self._exists = True
        if value is not None:
            self._value = value
        elif self._value_type == int or self._value_type == bool:
            self._value = 0
        return self

    def __getitem__(self, key):
        if self._value is None:
            self._value = {}
        return self._value[key]

    def __setitem__(self, key, value):
        if self._value is None:
            self._value = {}
        self._value[key] = value

    def __int__(self):
        return int(self._value) if self._value is not None else 0

    def __bool__(self):
        return bool(self._value) if self._value is not None else False

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, v):
        self._value = v
        self._exists = True


class CEar:
    def __init__(self, name: str = ""):
        self.iEarClass = 0
        self.iEarLevel = 1
        self.sEarName = name

    def read_data(self, bs, version: int):
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


class CLongName:
    def __init__(self):
        self.iName1 = 0
        self.iName2 = 0
        self.bPref1 = False
        self.wPref1 = MayExist(int, 11)
        self.bSuff1 = False
        self.wSuff1 = MayExist(int, 11)
        self.bPref2 = False
        self.wPref2 = MayExist(int, 11)
        self.bSuff2 = False
        self.wSuff2 = MayExist(int, 11)
        self.bPref3 = False
        self.wPref3 = MayExist(int, 11)
        self.bSuff3 = False
        self.wSuff3 = MayExist(int, 11)

    def read_data(self, bs):
        self.iName1 = bs.read_bits(8)
        self.iName2 = bs.read_bits(8)
        self.bPref1 = bs.read_bits(1) != 0
        if self.bPref1:
            self.wPref1.ensure(bs.read_bits(11))
        self.bSuff1 = bs.read_bits(1) != 0
        if self.bSuff1:
            self.wSuff1.ensure(bs.read_bits(11))
        self.bPref2 = bs.read_bits(1) != 0
        if self.bPref2:
            self.wPref2.ensure(bs.read_bits(11))
        self.bSuff2 = bs.read_bits(1) != 0
        if self.bSuff2:
            self.wSuff2.ensure(bs.read_bits(11))
        self.bPref3 = bs.read_bits(1) != 0
        if self.bPref3:
            self.wPref3.ensure(bs.read_bits(11))
        self.bSuff3 = bs.read_bits(1) != 0
        if self.bSuff3:
            self.wSuff3.ensure(bs.read_bits(11))


class CGoldQuantity:
    def __init__(self):
        self.bNotGold = False
        self.wQuantity = 0

    def read_data(self, bs):
        self.bNotGold = bs.read_bits(1) != 0
        self.wQuantity = bs.read_bits(12)


_TRACE_PROPERTY = False
_TRACE_ITEM = False
_TRACE_ITEM_IDX = -1

class CPropertyList:
    def __init__(self):
        self.mProperty: List[Tuple[int, int, int]] = []
        self.iEndFlag = 0
        self._version: int = 0
        self._use_stat_cost: bool = False

    def read_data(self, bs, version: int):
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


class CExtItemInfo:
    def __init__(self, meta: CItemMetaData = None):
        self.nGems = 0
        self.dwGUID = 0
        self.iDropLevel = 99
        self.iQuality = 2
        self.bVarGfx = False
        self.iVarGfx = MayExist(int, 3)
        self.bClass = False
        self.wClass = MayExist(int, 11)
        self.loQual = MayExist(int, 3)
        self.hiQual = MayExist(int, 3)
        self.wPrefix = MayExist(int, 11)
        self.wSuffix = MayExist(int, 11)
        self.wSetID = MayExist(int, 12)
        self.pRareName: Optional[CLongName] = None
        self.wUniID = MayExist(int, 12)
        self.pCraftName: Optional[CLongName] = None
        self.wRune = MayExist(int, 16)
        self.sPersonName: List[int] = []
        self.wMonsterID = MayExist(int, 10)
        self.wCharm = MayExist(int, 12)
        self.iSpellID = MayExist(int, 5)
        self.iBodyPartFileIndex = MayExist(int, 10)
        self.iSpellType = MayExist(int, 5)

    def is_set(self) -> bool:
        return self.iQuality == 5

    def rune_word_id(self) -> int:
        return self.wRune.value if self.wRune.exist() else 0

    def read_data(self, bs, version: int, bIsCharm: bool, bRuneWord: bool,
                  bPersonalized: bool, bHasMonsterID: bool, bHasSpellId: bool):
        self.nGems = bs.read_bits(3)
        self.dwGUID = bs.read_bits(32)
        self.iDropLevel = bs.read_bits(7)
        self.iQuality = bs.read_bits(4)
        self.bVarGfx = bs.read_bits(1) != 0
        if self.bVarGfx:
            self.iVarGfx.ensure(bs.read_bits(3))
        self.bClass = bs.read_bits(1) != 0
        if self.bClass:
            self.wClass.ensure(bs.read_bits(11))

        if self.iQuality == 1:
            self.loQual.ensure(bs.read_bits(3))
        elif self.iQuality == 2:
            if bIsCharm:
                self.wCharm.ensure(bs.read_bits(12))
        elif self.iQuality == 3:
            self.hiQual.ensure(bs.read_bits(3))
        elif self.iQuality == 4:
            self.wPrefix.ensure(bs.read_bits(11))
            self.wSuffix.ensure(bs.read_bits(11))
        elif self.iQuality == 5:
            self.wSetID.ensure(bs.read_bits(12))
        elif self.iQuality == 6:
            self.pRareName = CLongName()
            self.pRareName.read_data(bs)
        elif self.iQuality == 7:
            self.wUniID.ensure(bs.read_bits(12))
        elif self.iQuality == 8:
            self.pCraftName = CLongName()
            self.pCraftName.read_data(bs)

        if bRuneWord:
            self.wRune.ensure(bs.read_bits(16))

        if bPersonalized:
            bits_per_char = 8 if is_ptr24_and_above(version) else 7
            for _ in range(16):
                c = bs.read_bits(bits_per_char)
                if c == 0:
                    break
                self.sPersonName.append(c)

        if bHasMonsterID:
            self.wMonsterID.ensure(bs.read_bits(10))
        elif bHasSpellId:
            self.iSpellID.ensure(bs.read_bits(5))


class CTypeSpecificInfo:
    def __init__(self, meta: CItemMetaData = None):
        self.iDefence = MayExist(int, 11)
        self.iMaxDurability = MayExist(int, 8)
        self.iCurDur = MayExist(int, 9)
        self.iSocket = MayExist(int, 4)
        self.iQuantity = MayExist(int, 9)
        self.aHasSetPropList: List[bool] = []
        self.stPropertyList = CPropertyList()
        self.apSetProperty: List[Optional[CPropertyList]] = []
        self.stRuneWordPropertyList: Optional[CPropertyList] = None

    def sockets(self) -> Tuple[int, int]:
        base = self.iSocket.value if self.iSocket.exist() else 0
        ext = self.stPropertyList.ext_sockets()
        return (base, ext)

    def total_sockets(self) -> int:
        b, e = self.sockets()
        return min(7, b + e)

    def get_defence(self) -> int:
        if not self.iDefence.exist():
            return 0
        ac_stat = get_stat_cost(31)
        save_add = ac_stat.save_add if ac_stat else 10
        return self.iDefence.value - save_add

    def is_indestructible(self) -> bool:
        if self.iMaxDurability.exist() and self.iMaxDurability.value == 0:
            return True
        if self.stPropertyList.is_indestructible():
            return True
        return False

    def read_data(self, bs, version: int, bHasDef: bool, bHasDur: bool,
                  bSocketed: bool, bIsStacked: bool, bIsSet: bool, bRuneWord: bool):
        if bHasDef:
            self.iDefence.ensure(bs.read_bits(11))
        if bHasDur:
            self.iMaxDurability.ensure(bs.read_bits(8))
            if self.iMaxDurability.value > 0:
                self.iCurDur.ensure(bs.read_bits(9))
        if bSocketed:
            self.iSocket.ensure(bs.read_bits(4))
            if self.iSocket.value < 1:
                self.iSocket.value = 1
        if version >= 0x69:
            if bs.read_bits(1):
                self.iQuantity.ensure(bs.read_bits(9))
        elif bIsStacked:
            self.iQuantity.ensure(bs.read_bits(9))
        if bIsSet:
            self.aHasSetPropList = [bs.read_bits(1) != 0 for _ in range(5)]
        else:
            self.aHasSetPropList = [False] * 5

        self.stPropertyList.read_data(bs, version)

        self.apSetProperty = []
        if bIsSet:
            for i in range(5):
                if self.aHasSetPropList[i]:
                    prop_list = CPropertyList()
                    prop_list.read_data(bs, version)
                    self.apSetProperty.append(prop_list)
                else:
                    self.apSetProperty.append(None)

        if bRuneWord:
            self.stRuneWordPropertyList = CPropertyList()
            self.stRuneWordPropertyList.read_data(bs, version)


class CItemInfo:
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

    def __init__(self, meta: CItemMetaData = None):
        self.sTypeName: bytes = b'    '
        self.pExtItemInfo: Optional[CExtItemInfo] = None
        self.pGold: Optional[CGoldQuantity] = None
        self.bHasRand = False
        self.pTimeStampFlag: List[int] = []
        self.pRealmData: List[int] = []
        self.iAdvancedStashStackSize: int = 0
        self.iQuestDifficulty: int = 0
        self.pTpSpInfo: Optional[CTypeSpecificInfo] = None
        self.iPad = 0
        self._meta = meta

    def is_gold(self) -> bool:
        return self.sTypeName == b'gld '

    def is_box(self) -> bool:
        return self.sTypeName == b'box '

    def is_set(self) -> bool:
        return self.pExtItemInfo is not None and self.pExtItemInfo.is_set()

    def rune_word_id(self) -> int:
        return self.pExtItemInfo.rune_word_id() if self.pExtItemInfo else 0

    def gems(self) -> int:
        return self.pExtItemInfo.nGems if self.pExtItemInfo else 0

    def sockets(self) -> int:
        if self.pTpSpInfo:
            return self.pTpSpInfo.total_sockets()
        return 0

    def _is_stackable_for_stash(self) -> bool:
        return self.sTypeName in self.STACKABLE_FOR_STASH

    def read_data(self, bs, version: int, bSimple: bool, bRuneWord: bool,
                  bPersonalized: bool, bSocketed: bool) -> Optional[CItemMetaData]:
        is_d2r_ = is_d2r(version)
        huffman = get_huffman()

        if is_d2r_:
            self.sTypeName = bytes([huffman.read_char(bs) for _ in range(4)])
        else:
            # 读取4个字节，注意小端序
            self.sTypeName = bytes([bs.read_byte() for _ in range(4)])

        meta = get_item_meta(self.sTypeName, version)
        if meta is None:
            meta = self._meta

        if not bSimple and meta:
            self.pExtItemInfo = CExtItemInfo(meta)
            self.pExtItemInfo.read_data(bs, version,
                                         meta.is_charm if meta else False,
                                         bRuneWord, bPersonalized,
                                         meta.has_monster_id if meta else False,
                                         (meta.spell_id > 0) if meta else False)

        if self.is_gold():
            self.pGold = CGoldQuantity()
            self.pGold.read_data(bs)

        self.bHasRand = bs.read_bits(1) != 0
        if self.bHasRand:
            if is_d2r_ and version > 86:
                realm_count = 4 if version > 96 else (3 if version > 93 else 2)
                self.pRealmData = [bs.read_bits(32) for _ in range(realm_count)]
            elif not bSimple:
                self.pTimeStampFlag = [bs.read_bits(32) for _ in range(4)]

        if is_d2r_ and version > 99:
            if version <= 101:
                if self._is_stackable_for_stash():
                    self.iAdvancedStashStackSize = bs.read_bits(8)
            else:
                if bs.read_bits(1):
                    self.iAdvancedStashStackSize = bs.read_bits(8)

        if not bSimple and meta:
            self.pTpSpInfo = CTypeSpecificInfo(meta)
            self.pTpSpInfo.read_data(bs, version,
                                      meta.has_def if meta else False,
                                      meta.has_dur if meta else False,
                                      bSocketed,
                                      meta.is_stacked if meta else False,
                                      self.is_set(),
                                      bRuneWord)
        elif is_d2r_ and version >= 0x69 and meta and meta.ipad_bits > 0:
            self.iPad = bs.read_bits(meta.ipad_bits)

        return meta


class CD2Item:
    def __init__(self, meta: CItemMetaData = None):
        self.dwVersion = 0
        self.wMajic = 0x4D4A
        self.bQuest = False
        self.iUNKNOWN_01 = 0
        self.bIdentified = True
        self.iUNKNOWN_02 = 0
        self.bDisabled = False
        self.iUNKNOWN_10 = 0
        self.bSocketed = False
        self.bUNKNOWN_03 = False
        self.bNew = False
        self.bBadEquipped = False
        self.bUNKNOWN_04 = False
        self.bEar = False
        self.bNewbie = False
        self.iUNKNOWN_05 = 0
        self.bSimple = True
        self.bEthereal = False
        self.bUNKNOWN_06 = True
        self.bPersonalized = False
        self.bUNKNOWN_07 = False
        self.bRuneWord = False
        self.iUNKNOWN_08 = 0
        self.wVersion = 101
        self.iUNKNOWN_09 = 0xA0
        self.iLocation = 0
        self.iPosition = 0
        self.iColumn = 0
        self.iRow = 0
        self.iStoredIn = 1

        self.pEar: Optional[CEar] = None
        self.pItemInfo: Optional[CItemInfo] = None
        self.aGemItems: List[CD2Item] = []

        self._meta = meta

    @property
    def sTypeName(self) -> bytes:
        if self.pItemInfo:
            return self.pItemInfo.sTypeName
        if self.bEar:
            return b'ear '
        if self._meta:
            return self._meta.type_id
        return b'    '

    def quality(self) -> int:
        if self.bEar or self.bSimple:
            if self._meta and self._meta.is_unique:
                return 7
            return 2
        if self.pItemInfo and self.pItemInfo.pExtItemInfo:
            return self.pItemInfo.pExtItemInfo.iQuality
        return 2

    def is_set(self) -> bool:
        return self.pItemInfo is not None and self.pItemInfo.is_set()

    def is_rune_word(self) -> bool:
        return self.bRuneWord

    def rune_word_id(self) -> int:
        if self.bRuneWord and self.pItemInfo:
            return self.pItemInfo.rune_word_id()
        return 0

    def gems(self) -> int:
        if self.pItemInfo:
            return self.pItemInfo.gems()
        return 0

    def sockets(self) -> int:
        if self.bSocketed and self.pItemInfo:
            return self.pItemInfo.sockets()
        return 0

    def is_box(self) -> bool:
        return self.pItemInfo is not None and self.pItemInfo.is_box()

    def has_property_list(self) -> bool:
        return self.pItemInfo is not None and self.pItemInfo.pTpSpInfo is not None

    def read_data(self, bs, version: int, read_magic: bool = True):
        if is_d2r(version):
            self._read_data_d2r(bs, version, read_magic)
        else:
            self._read_data_classic(bs, version, read_magic)

    def _read_data_d2r(self, bs, version: int, read_magic: bool = True):
        if read_magic:
            bs.align_byte()
            self.wMajic = bs.read_word()
            if self.wMajic != 0x4D4A:
                bs.seek_back_bytes(2)
                self.wMajic = 0x4D4A
            self.dwVersion = bs.read_dword()
            if not is_valid_version(self.dwVersion):
                bs.seek_back_bytes(4)
                self.dwVersion = version
        else:
            self.wMajic = 0x4D4A
            self.dwVersion = version

        flags = bs.read_bits(32)
        self.bIdentified = bool(flags & 0x00000010)
        bHasQuantity = bool(flags & 0x00000020)
        self.bSocketed = bool(flags & 0x00000800)
        self.bEar = bool(flags & 0x00010000)
        self.bNewbie = bool(flags & 0x00020000)
        self.bSimple = bool(flags & 0x00200000)
        self.bEthereal = bool(flags & 0x00400000)
        self.bPersonalized = bool(flags & 0x01000000)
        self.bRuneWord = bool(flags & 0x04000000)
        bChronicle = bool(flags & 0x10000000)
        bChronicleCompact = bool(flags & 0x20000000)

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
        if self.bEar:
            self.pEar = CEar()
            self.pEar.read_data(bs, self.dwVersion)
            self._meta = get_item_meta(b'ear ', self.dwVersion)
            type_name = b'ear '
        else:
            type_name = bytes([huffman.read_char(bs) for _ in range(4)])
            self._meta = get_item_meta(type_name, self.dwVersion)
            self.pItemInfo = CItemInfo(self._meta)
            self.pItemInfo.sTypeName = type_name

        if self.bSimple:
            self._read_compact_d2r(bs, version, type_name, bChronicle, bChronicleCompact)
        else:
            self._read_complete_d2r(bs, version, type_name, bChronicle, bChronicleCompact)

        bs.align_byte()

        gem_count = self.gems()
        self.aGemItems = []
        for _ in range(gem_count):
            item = CD2Item()
            item.read_data(bs, self.dwVersion, True)
            self.aGemItems.append(item)

    def _read_compact_d2r(self, bs, version: int, type_name: bytes,
                          bChronicle: bool, bChronicleCompact: bool):
        if self.bEar:
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
                    self.pItemInfo.iQuestDifficulty = (raw - quest_diff_stat.save_add) << quest_diff_stat.val_shift

        realm_flag = bs.read_bits(1)
        if realm_flag:
            realm_count = 4 if version > 96 else (3 if version > 93 else 2)
            self.pItemInfo.pRealmData = [bs.read_bits(32) for _ in range(realm_count)]

        self._read_advanced_stash_size(bs, version, type_name)

    def _read_complete_d2r(self, bs, version: int, type_name: bytes,
                           bChronicle: bool, bChronicleCompact: bool):
        if self.bEar:
            return

        _t = _TRACE_ITEM
        meta = self._meta
        ext = CExtItemInfo(meta)
        if _t: pos = bs.getOffset(); print(f'  [TRACE] before nGems: bit={pos}')
        ext.nGems = bs.read_bits(3)
        if _t: print(f'  [TRACE] nGems={ext.nGems} bit={bs.getOffset()}')
        ext.dwGUID = bs.read_bits(32)
        if _t: print(f'  [TRACE] dwGUID=0x{ext.dwGUID:08X} bit={bs.getOffset()}')
        ext.iDropLevel = bs.read_bits(7)
        if _t: print(f'  [TRACE] iDropLevel={ext.iDropLevel} bit={bs.getOffset()}')
        ext.iQuality = bs.read_bits(4)
        if _t: print(f'  [TRACE] iQuality={ext.iQuality} bit={bs.getOffset()}')

        ext.bVarGfx = bs.read_bits(1) != 0
        if ext.bVarGfx:
            ext.iVarGfx.ensure(bs.read_bits(3))
        if _t: print(f'  [TRACE] bVarGfx={ext.bVarGfx} bit={bs.getOffset()}')

        ext.bClass = bs.read_bits(1) != 0
        if ext.bClass:
            ext.wClass.ensure(bs.read_bits(11))
        if _t: print(f'  [TRACE] bClass={ext.bClass} bit={bs.getOffset()}')

        if ext.iQuality == 1:
            ext.loQual.ensure(bs.read_bits(3))
        elif ext.iQuality == 2:
            if meta and meta.is_charm:
                ext.wCharm.ensure(bs.read_bits(12))
            elif meta and meta.is_body_part and not meta.is_player_body_part:
                ext.iBodyPartFileIndex.ensure(bs.read_bits(10))
            elif meta and meta.is_scroll_or_book:
                ext.iSpellType.ensure(bs.read_bits(5))
        elif ext.iQuality == 3:
            ext.hiQual.ensure(bs.read_bits(3))
        elif ext.iQuality == 4:
            ext.wPrefix.ensure(bs.read_bits(11))
            ext.wSuffix.ensure(bs.read_bits(11))
        elif ext.iQuality == 5:
            ext.wSetID.ensure(bs.read_bits(12))
        elif ext.iQuality == 6:
            ext.pRareName = CLongName()
            ext.pRareName.read_data(bs)
        elif ext.iQuality == 7:
            ext.wUniID.ensure(bs.read_bits(12))
        elif ext.iQuality == 8:
            ext.pCraftName = CLongName()
            ext.pCraftName.read_data(bs)
        if _t: print(f'  [TRACE] after quality data bit={bs.getOffset()}')

        if self.bRuneWord:
            ext.wRune.ensure(bs.read_bits(16))
        if _t: print(f'  [TRACE] after runeWord bit={bs.getOffset()} wRune={ext.wRune.value if ext.wRune.exist() else "N/A"}')

        if self.bPersonalized:
            for _ in range(16):
                c = bs.read_bits(8)
                if c == 0:
                    break
                ext.sPersonName.append(c)
        if _t: print(f'  [TRACE] after personalized bit={bs.getOffset()}')

        self.pItemInfo.pExtItemInfo = ext

        realm_flag = bs.read_bits(1)
        if realm_flag:
            realm_count = 4 if version > 96 else (3 if version > 93 else 2)
            self.pItemInfo.pRealmData = [bs.read_bits(32) for _ in range(realm_count)]
        if _t: print(f'  [TRACE] after realm bit={bs.getOffset()} realm_flag={realm_flag}')

        tp = CTypeSpecificInfo(meta)
        if meta and meta.has_def:
            ac_stat = get_stat_cost(31)
            def_bits = ac_stat.save_bits if ac_stat else 11
            tp.iDefence.ensure(bs.read_bits(def_bits))
        if _t: print(f'  [TRACE] after defence bit={bs.getOffset()} has_def={meta.has_def if meta else "N/A"}')

        if meta and meta.has_dur:
            max_dur_stat = get_stat_cost(73)
            max_dur_bits = max_dur_stat.save_bits if max_dur_stat else 8
            dur_stat = get_stat_cost(72)
            dur_bits = dur_stat.save_bits if dur_stat else 9
            tp.iMaxDurability.ensure(bs.read_bits(max_dur_bits))
            if tp.iMaxDurability.value > 0:
                tp.iCurDur.ensure(bs.read_bits(dur_bits))
        if _t: print(f'  [TRACE] after durability bit={bs.getOffset()} has_dur={meta.has_dur if meta else "N/A"} maxdur={tp.iMaxDurability.value if tp.iMaxDurability.exist() else "N/A"}')

        if self.pItemInfo.is_gold():
            self.pItemInfo.pGold = CGoldQuantity()
            self.pItemInfo.pGold.read_data(bs)
        if _t: print(f'  [TRACE] after gold bit={bs.getOffset()} is_gold={self.pItemInfo.is_gold()}')

        if version > 104:
            qty_flag = bs.read_bits(1)
            if qty_flag:
                tp.iQuantity.ensure(bs.read_bits(9))
        elif meta and meta.is_stacked:
            tp.iQuantity.ensure(bs.read_bits(9))
        if _t: print(f'  [TRACE] after quantity bit={bs.getOffset()}')

        if self.bSocketed:
            sock_stat = get_stat_cost(194)
            sock_bits = sock_stat.save_bits if sock_stat else 3
            tp.iSocket.ensure(bs.read_bits(sock_bits))
            if tp.iSocket.value < 1:
                tp.iSocket.value = 1
        if _t: print(f'  [TRACE] after socket bit={bs.getOffset()} bSocketed={self.bSocketed} iSocket={tp.iSocket.value if tp.iSocket.exist() else "N/A"}')

        if ext.iQuality == 5:
            tp.aHasSetPropList = [bs.read_bits(1) != 0 for _ in range(5)]
        else:
            tp.aHasSetPropList = [False] * 5
        if _t: print(f'  [TRACE] before property list bit={bs.getOffset()}')

        tp.stPropertyList.read_data(bs, version)
        if _t: print(f'  [TRACE] after base property list bit={bs.getOffset()} count={len(tp.stPropertyList.mProperty)}')

        if ext.iQuality == 5:
            tp.apSetProperty = []
            for j in range(5):
                if tp.aHasSetPropList[j]:
                    pl = CPropertyList()
                    pl.read_data(bs, version)
                    tp.apSetProperty.append(pl)
                else:
                    tp.apSetProperty.append(None)

        if self.bRuneWord:
            tp.stRuneWordPropertyList = CPropertyList()
            tp.stRuneWordPropertyList.read_data(bs, version)
        if _t: print(f'  [TRACE] after runeword property list bit={bs.getOffset()}')

        self.pItemInfo.pTpSpInfo = tp

        if bChronicle:
            chronicle_id = bs.read_bits(16)
            if bChronicleCompact:
                bs.read_bits(64)
            else:
                bs.read_bits(32)
                count = bs.read_bits(4)
                for _ in range(count):
                    bs.read_bits(64)
        if _t: print(f'  [TRACE] after chronicle bit={bs.getOffset()} bChronicle={bChronicle}')

        self._read_advanced_stash_size(bs, version, type_name)
        if _t: print(f'  [TRACE] after advanced stash bit={bs.getOffset()}')

    def _read_advanced_stash_size(self, bs, version: int, type_name: bytes):
        if version <= 99:
            return
        if version <= 101:
            if type_name in CItemInfo.STACKABLE_FOR_STASH:
                self.pItemInfo.iAdvancedStashStackSize = bs.read_bits(8)
        else:
            if bs.read_bits(1):
                self.pItemInfo.iAdvancedStashStackSize = bs.read_bits(8)

    def _read_data_classic(self, bs, version: int, read_magic: bool = True):
        if read_magic:
            bs.align_byte()
            self.wMajic = bs.read_word()
            if self.wMajic != 0x4D4A:
                bs.seek_back_bytes(2)
                self.wMajic = 0x4D4A
            self.dwVersion = bs.read_dword()
            if not is_valid_version(self.dwVersion):
                bs.seek_back_bytes(4)
                self.dwVersion = version
        else:
            self.wMajic = 0x4D4A
            self.dwVersion = version

        self.bQuest = bs.read_bits(1) != 0
        self.iUNKNOWN_01 = bs.read_bits(3)
        self.bIdentified = bs.read_bits(1) != 0
        self.iUNKNOWN_02 = bs.read_bits(3)
        self.bDisabled = bs.read_bits(1) != 0
        self.iUNKNOWN_10 = bs.read_bits(2)
        self.bSocketed = bs.read_bits(1) != 0
        self.bUNKNOWN_03 = bs.read_bits(1) != 0
        self.bNew = bs.read_bits(1) != 0
        self.bBadEquipped = bs.read_bits(1) != 0
        self.bUNKNOWN_04 = bs.read_bits(1) != 0
        self.bEar = bs.read_bits(1) != 0
        self.bNewbie = bs.read_bits(1) != 0
        self.iUNKNOWN_05 = bs.read_bits(3)
        self.bSimple = bs.read_bits(1) != 0
        self.bEthereal = bs.read_bits(1) != 0
        self.bUNKNOWN_06 = bs.read_bits(1) != 0
        self.bPersonalized = bs.read_bits(1) != 0
        self.bUNKNOWN_07 = bs.read_bits(1) != 0
        self.bRuneWord = bs.read_bits(1) != 0

        self.iUNKNOWN_08 = bs.read_bits(5)
        self.wVersion = bs.read_bits(10)

        self.iLocation = bs.read_bits(3)
        self.iPosition = bs.read_bits(4)
        self.iColumn = bs.read_bits(4)
        self.iRow = bs.read_bits(4)
        self.iStoredIn = bs.read_bits(3)

        if self.bEar:
            self.pEar = CEar()
            self.pEar.read_data(bs, self.dwVersion)
            self._meta = get_item_meta(b'ear ', self.dwVersion)
        else:
            self.pItemInfo = CItemInfo(self._meta)
            self._meta = self.pItemInfo.read_data(bs, self.dwVersion,
                                                   self.bSimple,
                                                   self.bRuneWord,
                                                   self.bPersonalized,
                                                   self.bSocketed)

        bs.align_byte()

        gem_count = self.gems()
        self.aGemItems = []
        for _ in range(gem_count):
            item = CD2Item()
            item.read_data(bs, self.dwVersion, True)
            self.aGemItems.append(item)


class CItemList:
    def __init__(self):
        self.wMajic = 0x4D4A
        self.nItems = 0
        self.vItems: List[CD2Item] = []
    
    def read_data(self, bs, version: int):
        self.wMajic = bs.read_word()
        self.nItems = bs.read_word()
        if self.wMajic != 0x4D4A:
            return
        
        self.vItems = []
        for i in range(self.nItems):
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
            item = CD2Item()
            start_offset = bs.getOffset()
            try:
                if is_d2r(version):
                    item.read_data(bs, version, False)
                else:
                    item.read_data(bs, version, True)
            except ValueError:
                bs._offset = start_offset
                continue
            _self_mod._TRACE_ITEM = old_trace
            _self_mod._TRACE_PROPERTY = old_trace_prop
            self.vItems.append(item)
    
    def get_items(self) -> List[CD2Item]:
        return self.vItems
