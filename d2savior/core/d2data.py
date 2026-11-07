import copy
import os
from collections.abc import Buffer
from dataclasses import dataclass, field
from itertools import batched
from typing import Any, ClassVar

type ItemTypeId = Buffer | str


@dataclass(slots=True)
class StatInfo:
    stat_id: int = 0
    stat_name: str = ""
    send_bits: int = 0
    send_param_bits: int = 0
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
    descpriority: int = 0
    descfunc: int = 0
    descval: int = 0
    descstrpos: str = ""
    descstrneg: str = ""
    descstr2: str = ""


# StatCostItem is merged into StatInfo
StatCostItem = StatInfo


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
    is_body_part: bool = False
    is_player_body_part: bool = False
    is_scroll_or_book: bool = False

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
        if isinstance(type_id, str):
            raw_id = type_id.encode("ascii", errors="replace")
        else:
            raw_id = bytes(type_id)
        tid = raw_id.ljust(4)[:4]

        items = self._items.get(tid)
        if not items:
            return None

        best_match = None
        best_ver_min = -1
        for item in items:
            if item.ver_min <= version and item.ver_min > best_ver_min:
                best_match = item
                best_ver_min = item.ver_min

        if best_match is not None:
            return copy.copy(best_match)
        return copy.copy(items[-1])

    def get_item_by_name(self, name: str, version: int = 0) -> ItemMetaData | None:
        padded_name = name.ljust(4)[:4].encode("ascii")
        return self.get_item(padded_name, version)


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


@dataclass(slots=True)
class PropertyInfo:
    prop_id: int = 0
    code: str = ""
    func1: int = 0
    stat1: str = ""
    set1: int = 0
    val1: int = 0
    func2: int = 0
    stat2: str = ""
    set2: int = 0
    val2: int = 0
    func3: int = 0
    stat3: str = ""
    set3: int = 0
    val3: int = 0
    func4: int = 0
    stat4: str = ""
    set4: int = 0
    val4: int = 0
    func5: int = 0
    stat5: str = ""
    set5: int = 0
    val5: int = 0
    func6: int = 0
    stat6: str = ""
    set6: int = 0
    val6: int = 0
    func7: int = 0
    stat7: str = ""
    set7: int = 0
    val7: int = 0


@dataclass(slots=True)
class MagicAffixInfo:
    name: str = ""
    affix_id: int = 0
    level: int = 0
    levelreq: int = 0


@dataclass(slots=True)
class UniqueItemInfo:
    index: str = ""
    unique_id: int = 0
    code: str = ""


@dataclass(slots=True)
class SetItemInfo:
    name: str = ""
    set_id: int = 0


@dataclass(slots=True)
class RuneWordInfo:
    name: str = ""
    runeword_id: int = 0
    rune_codes: list = field(default_factory=list)
    key: str = ""


@dataclass(slots=True)
class ItemTypeInfo:
    code: str = ""
    name: str = ""
    item_type: str = ""
    item_type2: str = ""
    invwidth: int = 1
    invheight: int = 1
    hasinv: bool = False
    gemsockets: int = 0
    stackable: bool = False
    useable: bool = False
    throw: bool = False
    compactsave: bool = False
    version: int = 0
    rarity: int = 0
    spawnable: bool = False
    nodurability: bool = False
    durability: int = 0
    mindam: int = 0
    maxdam: int = 0
    minmisdam: int = 0
    maxmisdam: int = 0
    speed: int = 0
    reqstr: int = 0
    reqdex: int = 0
    level: int = 0
    levelreq: int = 0
    cost: int = 0
    component: int = 0
    type: str = ""
    type2: str = ""
    minstack: int = 0
    maxstack: int = 0
    spawnstack: int = 0
    quest: int = 0
    questdiffcheck: bool = False
    spellicon: int = 0
    spell_id: int = 0
    belt_rows: int = 0


@dataclass(slots=True)
class VersionData:
    """Stores all game data for a specific version."""

    version: int = 0x63
    stats: dict[int, StatInfo] = field(default_factory=dict)
    stats_by_name: dict[str, StatInfo] = field(default_factory=dict)
    properties: dict[int, PropertyInfo] = field(default_factory=dict)
    properties_by_code: dict[str, PropertyInfo] = field(default_factory=dict)
    items: dict[str, ItemTypeInfo] = field(default_factory=dict)
    magic_prefixes: dict[int, MagicAffixInfo] = field(default_factory=dict)
    magic_suffixes: dict[int, MagicAffixInfo] = field(default_factory=dict)
    unique_items: dict[int, UniqueItemInfo] = field(default_factory=dict)
    set_items: dict[int, SetItemInfo] = field(default_factory=dict)
    runewords: dict[int, RuneWordInfo] = field(default_factory=dict)
    skills: dict[int, str] = field(default_factory=dict)
    aura_skill_ids: set[int] = field(default_factory=set)
    type_ancestors: dict[str, set[str]] = field(default_factory=dict)
    type_descendants: dict[str, set[str]] = field(default_factory=dict)
    type_bodyloc: dict[str, tuple[int, int]] = field(default_factory=dict)
    type_beltable: set[str] = field(default_factory=set)
    item_manager: ItemMetaDataManager | None = None
    prop_meta: dict[int, PropertyMetaData] = field(default_factory=dict)

    @property
    def stat_cost(self) -> dict[int, StatInfo]:
        return self.stats

    @stat_cost.setter
    def stat_cost(self, val: dict[int, StatInfo]) -> None:
        self.stats = val

    def get_item(self, code: str) -> ItemTypeInfo | None:
        if not code:
            return None
        return self.items.get(code.lower().strip())

    def get_stat(self, stat_id: int) -> StatInfo | None:
        return self.stats.get(stat_id)

    def get_stat_by_name(self, stat_name: str) -> StatInfo | None:
        return self.stats_by_name.get(stat_name)

    def get_stat_cost(self, stat_id: int) -> StatInfo | None:
        return self.stats.get(stat_id)

    def get_property(self, prop_id: int) -> PropertyInfo | None:
        return self.properties.get(prop_id)

    def get_property_by_code(self, code: str) -> PropertyInfo | None:
        return self.properties_by_code.get(code)

    def get_magic_prefix(self, prefix_id: int) -> MagicAffixInfo | None:
        return self.magic_prefixes.get(prefix_id)

    def get_magic_suffix(self, suffix_id: int) -> MagicAffixInfo | None:
        return self.magic_suffixes.get(suffix_id)

    def get_unique_item(self, unique_id: int) -> UniqueItemInfo | None:
        return self.unique_items.get(unique_id)

    def get_set_item(self, set_id: int) -> SetItemInfo | None:
        return self.set_items.get(set_id)

    def get_runeword(self, runeword_id: int) -> RuneWordInfo | None:
        return self.runewords.get(runeword_id)

    def get_skill_name(self, skill_id: int) -> str:
        return self.skills.get(skill_id, "")

    def get_property_meta(
        self, prop_id: int, version: int | None = None
    ) -> PropertyMetaDataItem | None:
        if prop_id in self.prop_meta:
            return self.prop_meta[prop_id].find_data(self.version if version is None else version)
        return None

    def get_item_meta(self, type_id: ItemTypeId) -> ItemMetaData | None:
        if self.item_manager is not None:
            meta = self.item_manager.get_item(type_id, self.version)
            if meta is not None:
                self._supplement_meta(meta)
                return meta
        code = (
            type_id.strip()
            if isinstance(type_id, str)
            else bytes(type_id).decode("ascii", errors="replace").strip()
        )
        type_info = self.get_item(code)
        return _convert_item_type_to_meta(type_info, self)

    def _supplement_meta(self, meta: ItemMetaData) -> None:
        code = meta.type_id.decode("ascii", errors="replace").strip()
        type_info = self.get_item(code)
        if type_info is None or not type_info.item_type2:
            return
        if not meta.is_scroll_or_book:
            meta.is_scroll_or_book = self.is_descendant(
                type_info.item_type2, "scro"
            ) or self.is_descendant(type_info.item_type2, "book")
        if not meta.is_body_part:
            meta.is_body_part = self.is_descendant(type_info.item_type2, "body")
        if not meta.is_player_body_part:
            meta.is_player_body_part = self.is_descendant(type_info.item_type2, "play")
        if not meta.has_def and self.is_descendant(type_info.item_type2, "armo"):
            meta.has_def = True

    def is_descendant(self, item_type_code: str, ancestor_code: str) -> bool:
        if not item_type_code or not ancestor_code:
            return False
        # 检查祖先集合中是否包含指定的祖先
        ancestors = self.type_ancestors.get(item_type_code.lower(), set())
        if ancestor_code.lower() in ancestors:
            return True
        # 检查后代集合中是否包含指定的类型
        descendants = self.type_descendants.get(ancestor_code.lower(), set())
        return item_type_code.lower() in descendants

    def is_beltable(self, item_code: str) -> bool:
        if not item_code:
            return False
        code = item_code.lower().strip()
        if code in self.type_beltable:
            return True
        for ancestor in self.type_ancestors.get(code, set()):
            if ancestor in self.type_beltable:
                return True
        item_info = self.items.get(code)
        if item_info:
            item_type = getattr(item_info, "type", "") or getattr(item_info, "item_type", "")
            if item_type:
                it = item_type.lower().strip()
                if it in self.type_beltable:
                    return True
                for ancestor in self.type_ancestors.get(it, set()):
                    if ancestor in self.type_beltable:
                        return True
        return False

    def get_belt_rows(self, item_code: str) -> int:
        if not item_code:
            return 0
        code = item_code.lower().strip()
        item_info = self.items.get(code)
        if item_info and item_info.belt_rows > 0:
            return item_info.belt_rows
        return 0


class D2DataLoader:
    """加载单个版本的数据"""

    def __init__(self) -> None:
        pass

    def load_itemstatcost(self, filepath: str) -> tuple[dict[int, StatInfo], dict[str, StatInfo]]:
        stats = {}
        stats_by_name = {}

        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Required data file not found: {filepath}")

        with open(filepath, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        if len(lines) < 1:
            return stats, stats_by_name

        header = lines[0].strip().split("\t")
        col_map = {col.strip().lower(): i for i, col in enumerate(header)}

        for line in lines[1:]:
            line = line.strip()
            if not line or line.startswith("*"):
                continue

            parts = line.split("\t")

            def get_col(col_name: str, default: str = "", _parts: list[str] = parts) -> str:
                idx = col_map.get(col_name.strip().lower(), -1)
                if 0 <= idx < len(_parts):
                    return _parts[idx].strip()
                return default

            def get_int(col_name: str, default: int = 0) -> int:
                val = get_col(col_name)
                if val:
                    try:
                        return int(val)
                    except ValueError:
                        return default
                return default

            stat_name = get_col("Stat")
            stat_id = get_int("*ID")

            if stat_id < 0:
                continue

            stat = StatInfo(
                stat_id=stat_id,
                stat_name=stat_name,
                send_bits=get_int("Send Bits"),
                send_param_bits=get_int("Send Param Bits"),
                save_bits=get_int("Save Bits"),
                save_add=get_int("Save Add"),
                save_param_bits=get_int("Save Param Bits"),
                val_shift=get_int("ValShift"),
                op=get_int("op"),
                op_param=get_int("op param"),
                op_base=get_int("op base"),
                op_stat1=get_int("op stat1"),
                op_stat2=get_int("op stat2"),
                op_stat3=get_int("op stat3"),
                descpriority=get_int("descpriority"),
                descfunc=get_int("descfunc"),
                descval=get_int("descval"),
                descstrpos=get_col("descstrpos"),
                descstrneg=get_col("descstrneg"),
                descstr2=get_col("descstr2"),
            )

            stats[stat_id] = stat
            if stat_name:
                stats_by_name[stat_name] = stat

        return stats, stats_by_name

    def load_properties(
        self, filepath: str
    ) -> tuple[dict[int, PropertyInfo], dict[str, PropertyInfo]]:
        properties = {}
        properties_by_code = {}

        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Required data file not found: {filepath}")

        with open(filepath, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        if len(lines) < 1:
            return properties, properties_by_code

        header = lines[0].strip().split("\t")
        col_map = {}
        for i, col in enumerate(header):
            col_map[col] = i

        for line in lines[1:]:
            line = line.strip()
            if not line or line.startswith("*"):
                continue

            parts = line.split("\t")

            def get_col(col_name: str, default: str = "", _parts: list[str] = parts) -> str:
                if col_name in col_map and col_map[col_name] < len(_parts):
                    return _parts[col_map[col_name]]
                return default

            def get_int(col_name: str, default: int = 0) -> int:
                val = get_col(col_name)
                if val:
                    try:
                        return int(val)
                    except ValueError:
                        return default
                return default

            code = get_col("code")
            prop_id_str = get_col("*Id")

            if not prop_id_str or not code:
                continue

            try:
                prop_id = int(prop_id_str)
            except ValueError:
                continue

            if prop_id < 0:
                continue

            prop = PropertyInfo(
                prop_id=prop_id,
                code=code,
                func1=get_int("func1"),
                stat1=get_col("stat1"),
                set1=get_int("set1"),
                val1=get_int("val1"),
                func2=get_int("func2"),
                stat2=get_col("stat2"),
                set2=get_int("set2"),
                val2=get_int("val2"),
                func3=get_int("func3"),
                stat3=get_col("stat3"),
                set3=get_int("set3"),
                val3=get_int("val3"),
                func4=get_int("func4"),
                stat4=get_col("stat4"),
                set4=get_int("set4"),
                val4=get_int("val4"),
                func5=get_int("func5"),
                stat5=get_col("stat5"),
                set5=get_int("set5"),
                val5=get_int("val5"),
                func6=get_int("func6"),
                stat6=get_col("stat6"),
                set6=get_int("set6"),
                val6=get_int("val6"),
                func7=get_int("func7"),
                stat7=get_col("stat7"),
                set7=get_int("set7"),
                val7=get_int("val7"),
            )

            properties[prop_id] = prop
            properties_by_code[code] = prop

        return properties, properties_by_code

    def load_items_txt(self, filepath: str, item_category: str) -> dict[str, ItemTypeInfo]:
        items = {}

        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Required data file not found: {filepath}")

        with open(filepath, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        if len(lines) < 1:
            return items

        header = lines[0].strip().split("\t")
        col_map = {}
        for i, col in enumerate(header):
            col_map[col] = i

        for line in lines[1:]:
            line = line.strip()
            if not line or line.startswith("*"):
                continue

            parts = line.split("\t")

            def get_col(col_name: str, default: str = "", _parts: list[str] = parts) -> str:
                if col_name in col_map and col_map[col_name] < len(_parts):
                    return _parts[col_map[col_name]]
                return default

            def get_int(col_name: str, default: int = 0) -> int:
                val = get_col(col_name)
                if val:
                    try:
                        return int(val)
                    except ValueError:
                        return default
                return default

            def get_bool(col_name: str) -> bool:
                val = get_col(col_name)
                return val == "1"

            code = get_col("code")
            if not code or code == "xxx":
                continue

            belt_col_to_rows = {0: 3, 1: 2, 3: 4, 4: 2, 5: 3, 6: 4}
            item_type_col = get_col("type").lower().strip()
            belt_rows = 0
            if item_type_col == "belt":
                belt_col_val = get_int("belt", -1)
                belt_rows = belt_col_to_rows.get(belt_col_val, 0)

            item = ItemTypeInfo(
                code=code,
                name=get_col("name"),
                item_type=item_category,
                item_type2=get_col("type"),
                invwidth=get_int("invwidth", 1),
                invheight=get_int("invheight", 1),
                hasinv=get_bool("hasinv"),
                gemsockets=get_int("gemsockets"),
                stackable=get_bool("stackable"),
                useable=get_bool("useable"),
                compactsave=get_bool("compactsave"),
                version=get_int("version"),
                rarity=get_int("rarity"),
                spawnable=get_bool("spawnable"),
                nodurability=get_bool("nodurability"),
                durability=get_int("durability"),
                mindam=get_int("mindam"),
                maxdam=get_int("maxdam"),
                minmisdam=get_int("minmisdam"),
                maxmisdam=get_int("maxmisdam"),
                speed=get_int("speed"),
                reqstr=get_int("reqstr"),
                reqdex=get_int("reqdex"),
                level=get_int("level"),
                levelreq=get_int("levelreq"),
                cost=get_int("cost"),
                component=get_int("component"),
                type=get_col("type"),
                type2=get_col("type2"),
                minstack=get_int("minstack"),
                maxstack=get_int("maxstack"),
                spawnstack=get_int("spawnstack"),
                quest=get_int("quest"),
                questdiffcheck=get_bool("questdiffcheck"),
                spell_id=get_int("pSpell"),
                spellicon=get_int("spellicon"),
                belt_rows=belt_rows,
            )

            items[code] = item

            normcode = get_col("normcode")
            if normcode and normcode != "xxx" and normcode not in items:
                items[normcode] = item

            ubercode = get_col("ubercode")
            if ubercode and ubercode != "xxx" and ubercode not in items:
                items[ubercode] = item

            ultracode = get_col("ultracode")
            if ultracode and ultracode != "xxx" and ultracode not in items:
                items[ultracode] = item

        return items

    def load_magic_affix(self, filepath: str, is_prefix: bool) -> dict[int, MagicAffixInfo]:
        affix_dict = {}

        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Required data file not found: {filepath}")

        with open(filepath, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        if len(lines) < 1:
            return affix_dict

        header = lines[0].strip().split("\t")
        col_map = {}
        for i, col in enumerate(header):
            col_map[col] = i

        for idx, line in enumerate(lines[1:]):
            line = line.strip()
            if not line or line.startswith("*"):
                continue

            parts = line.split("\t")

            def get_col(col_name: str, default: str = "", _parts: list[str] = parts) -> str:
                if col_name in col_map and col_map[col_name] < len(_parts):
                    return _parts[col_map[col_name]]
                return default

            def get_int(col_name: str, default: int = 0) -> int:
                val = get_col(col_name)
                if val:
                    try:
                        return int(val)
                    except ValueError:
                        return default
                return default

            name = get_col("Name")
            if not name:
                continue

            affix = MagicAffixInfo(
                name=name,
                affix_id=idx + 1,
                level=get_int("level"),
                levelreq=get_int("levelreq"),
            )
            affix_dict[idx + 1] = affix

        return affix_dict

    def load_unique_items(self, filepath: str) -> dict[int, UniqueItemInfo]:
        unique_items = {}

        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Required data file not found: {filepath}")

        with open(filepath, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        if len(lines) < 1:
            return unique_items

        header = lines[0].strip().split("\t")
        col_map = {}
        for i, col in enumerate(header):
            col_map[col] = i

        for line in lines[1:]:
            line = line.strip()
            if not line or line.startswith("*"):
                continue

            parts = line.split("\t")

            def get_col(col_name: str, default: str = "", _parts: list[str] = parts) -> str:
                if col_name in col_map and col_map[col_name] < len(_parts):
                    return _parts[col_map[col_name]]
                return default

            def get_int(col_name: str, default: int = 0) -> int:
                val = get_col(col_name)
                if val:
                    try:
                        return int(val)
                    except ValueError:
                        return default
                return default

            unique_id = get_int("*ID")
            if unique_id <= 0:
                continue

            item = UniqueItemInfo(
                index=get_col("index"),
                unique_id=unique_id,
                code=get_col("code"),
            )
            unique_items[unique_id] = item

        return unique_items

    def load_runewords(self, filepath: str) -> dict[int, RuneWordInfo]:
        runewords = {}

        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Required data file not found: {filepath}")

        import json

        with open(filepath, encoding="utf-8-sig") as f:
            data = json.load(f)

        for item in data:
            key = item.get("Key", "")
            if key.startswith("Runeword"):
                runeword_id = item.get("id", 0)
                name = item.get("enUS", "")
                if runeword_id > 0 and name:
                    runewords[runeword_id] = RuneWordInfo(
                        name=name, runeword_id=runeword_id, key=key
                    )

        return runewords

    def load_runes_txt(self, filepath: str, runewords: dict[int, RuneWordInfo]) -> None:
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Required data file not found: {filepath}")

        key_to_id = {}
        for rw_id, rw_info in runewords.items():
            if rw_info.key:
                key_to_id[rw_info.key] = rw_id

        with open(filepath, encoding="utf-8-sig") as f:
            lines = f.readlines()

            if not lines:
                return

            header = lines[0].strip().split("\t")
            name_idx = header.index("Name") if "Name" in header else 0
            rune_fields = []
            for i in range(1, 7):
                field = f"Rune{i}"
                if field in header:
                    rune_fields.append(header.index(field))

            for line in lines[1:]:
                parts = line.strip().split("\t")
                if len(parts) <= name_idx:
                    continue
                name_val = parts[name_idx]
                if name_val not in key_to_id:
                    continue

                rw_id = key_to_id[name_val]
                rune_codes = []
                for idx in rune_fields:
                    if idx < len(parts) and parts[idx]:
                        rune_codes.append(parts[idx])

                if rune_codes and rw_id in runewords:
                    runewords[rw_id].rune_codes = rune_codes

    def load_set_items(self, filepath: str) -> dict[int, SetItemInfo]:
        set_items = {}

        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Required data file not found: {filepath}")

        import json

        with open(filepath, encoding="utf-8-sig") as f:
            data = json.load(f)

        name_to_id = {}
        for item in data:
            if isinstance(item, dict):
                key = item.get("Key", "")
                item_id = item.get("id", 0)
                if key and item_id:
                    name_to_id[key] = item_id

            set_item_names = [
                "Civerb's Ward",
                "Civerb's Icon",
                "Civerb's Cudgel",
                "Hsarus' Iron Heel",
                "Hsarus' Iron Fist",
                "Hsarus' Iron Stay",
                "Cleglaw's Tooth",
                "Cleglaw's Claw",
                "Cleglaw's Pincers",
                "Iratha's Collar",
                "Iratha's Cuff",
                "Iratha's Coil",
                "Iratha's Cord",
                "Isenhart's Lightbrand",
                "Isenhart's Parry",
                "Isenhart's Case",
                "Isenhart's Horns",
                "Vidala's Barb",
                "Vidala's Fetlock",
                "Vidala's Ambush",
                "Vidala's Snare",
                "Milabrega's Orb",
                "Milabrega's Rod",
                "Milabrega's Diadem",
                "Milabrega's Robe",
                "Cathan's Rule",
                "Cathan's Mesh",
                "Cathan's Visage",
                "Cathan's Sigil",
                "Cathan's Seal",
                "Tancred's Crowbill",
                "Tancred's Spine",
                "Tancred's Hobnails",
                "Tancred's Weird",
                "Tancred's Skull",
                "Sigon's Gage",
                "Sigon's Visor",
                "Sigon's Shelter",
                "Sigon's Sabot",
                "Sigon's Wrap",
                "Sigon's Guard",
                "Infernal Cranium",
                "Infernal Torch",
                "Infernal Sign",
                "Berserker's Headgear",
                "Berserker's Hauberk",
                "Berserker's Hatchet",
                "Death's Hand",
                "Death's Guard",
                "Death's Touch",
                "Angelic Sickle",
                "Angelic Mantle",
                "Angelic Halo",
                "Angelic Wings",
                "Arctic Horn",
                "Arctic Furs",
                "Arctic Binding",
                "Arctic Mitts",
                "Arcanna's Sign",
                "Arcanna's Deathwand",
                "Arcanna's Head",
                "Arcanna's Flesh",
                "Natalya's Totem",
                "Natalya's Mark",
                "Natalya's Shadow",
                "Natalya's Soul",
                "Aldur's Stony Gaze",
                "Aldur's Deception",
                "Aldur's Gauntlet",
                "Aldur's Advance",
                "Immortal King's Will",
                "Immortal King's Soul Cage",
                "Immortal King's Detail",
                "Immortal King's Forge",
                "Immortal King's Pillar",
                "Immortal King's Stone Crusher",
                "Tal Rasha's Fine-Spun Cloth",
                "Tal Rasha's Adjudication",
                "Tal Rasha's Lidless Eye",
                "Tal Rasha's Guardianship",
                "Tal Rasha's Horadric Crest",
                "Griswold's Valor",
                "Griswold's Heart",
                "Griswold's Redemption",
                "Griswold's Honor",
                "Trang-Oul's Guise",
                "Trang-Oul's Scales",
                "Trang-Oul's Wing",
                "Trang-Oul's Claws",
                "Trang-Oul's Girth",
                "M'avina's True Sight",
                "M'avina's Embrace",
                "M'avina's Icy Clutch",
                "M'avina's Tenet",
                "M'avina's Caster",
                "Telling of Beads",
                "Laying of Hands",
                "Rite of Passage",
                "Spiritual Custodian",
                "Credendum",
                "Dangoon's Teaching",
                "Heaven's Taebaek",
                "Haemosu's Adament",
                "Ondal's Almighty",
                "Guillaume's Face",
                "Wilhelm's Pride",
                "Magnus' Skin",
                "Wihtstan's Guard",
                "Hwanin's Splendor",
                "Hwanin's Refuge",
                "Hwanin's Seal",
                "Hwanin's Justice",
                "Sazabi's Cobalt Redeemer",
                "Sazabi's Ghost Liberator",
                "Sazabi's Mental Sheath",
                "Bul-Kathos' Sacred Charge",
                "Bul-Kathos' Tribal Guardian",
                "Cow King's Horns",
                "Cow King's Hide",
                "Cow King's Hoofs",
                "Naj's Puzzler",
                "Naj's Light Plate",
                "Naj's Circlet",
                "McAuley's Paragon",
                "McAuley's Riprap",
                "McAuley's Taboo",
                "McAuley's Superstition",
                "Warlord's Lust",
                "Warlord's Conquest",
                "Warlord's Mantle",
                "Warlord's Crushers",
                "Warlord's Authority",
                "Bane's Oathmaker",
                "Bane's Wraithskin",
                "Bane's Authority",
                "Horazon's Countenance",
                "Horazon's Dominion",
                "Horazon's Hold",
                "Horazon's Legacy",
                "Horazon's Secrets",
            ]

            for idx, name in enumerate(set_item_names):
                item_id = name_to_id.get(name, 0)
                set_items[idx] = SetItemInfo(name=name, set_id=item_id)

        return set_items

    def load_skills(self, filepath: str) -> tuple[dict[int, str], set[int]]:
        skills = {}
        aura_skill_ids = set()

        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Required data file not found: {filepath}")

        with open(filepath, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        if len(lines) < 1:
            return skills, aura_skill_ids

        header = lines[0].strip().split("\t")
        col_map = {}
        for i, col in enumerate(header):
            col_map[col] = i

        for line in lines[1:]:
            line = line.strip()
            if not line or line.startswith("*"):
                continue

            parts = line.split("\t")

            def get_col(col_name: str, default: str = "", _parts: list[str] = parts) -> str:
                if col_name in col_map and col_map[col_name] < len(_parts):
                    return _parts[col_map[col_name]]
                return default

            def get_int(col_name: str, default: int = 0) -> int:
                val = get_col(col_name)
                if val:
                    try:
                        return int(val)
                    except ValueError:
                        return default
                return default

            skill_name = get_col("skill")
            skill_id = get_int("*Id")

            if skill_id >= 0 and skill_name:
                skills[skill_id] = skill_name

            aura_val = get_int("aura")
            if aura_val == 1:
                aura_skill_ids.add(skill_id)

        return skills, aura_skill_ids

    BODYLOC_MAP: ClassVar[dict[str, int]] = {
        "head": 1,
        "neck": 2,
        "tors": 3,
        "rarm": 4,
        "larm": 5,
        "rrin": 6,
        "lrin": 7,
        "belt": 8,
        "feet": 9,
        "glov": 10,
    }

    def load_itemtypes(
        self, filepath: str
    ) -> tuple[dict[str, set[str]], dict[str, set[str]], dict[str, tuple[int, int]], set[str]]:
        type_ancestors = {}
        type_descendants = {}
        type_bodyloc = {}
        beltable_codes = set()

        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Required data file not found: {filepath}")

        with open(filepath, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        if len(lines) < 1:
            return type_ancestors, type_descendants, type_bodyloc, beltable_codes

        header = lines[0].strip().split("\t")
        col_map = {}
        for i, col in enumerate(header):
            col_map[col.strip().lower()] = i

        type_equivs: dict[str, tuple[str, str]] = {}
        all_codes: set[str] = set()
        for line in lines[1:]:
            line = line.strip()
            if not line or line.startswith(("*", "Expansion")):
                continue
            parts = line.split("\t")

            def get_col(name: str, default: str = "", _parts: list[str] = parts) -> str:
                idx = col_map.get(name.strip().lower(), -1)
                return _parts[idx].strip() if 0 <= idx < len(_parts) else default

            type_name = get_col("itemtype")
            code = get_col("code")
            equiv1 = get_col("equiv1")
            equiv2 = get_col("equiv2")
            bodyloc1 = get_col("bodyloc1", "0")
            bodyloc2 = get_col("bodyloc2", "0")

            if not type_name:
                continue

            key = type_name.lower()
            type_equivs[key] = (equiv1.lower(), equiv2.lower())
            all_codes.add(key)
            bl1 = self.BODYLOC_MAP.get(bodyloc1.lower(), 0) if bodyloc1 else 0
            bl2 = self.BODYLOC_MAP.get(bodyloc2.lower(), 0) if bodyloc2 else 0
            type_bodyloc[key] = (bl1, bl2)
            if code:
                code_lower = code.lower()
                type_equivs[code_lower] = (equiv1.lower(), equiv2.lower())
                all_codes.add(code_lower)
                type_bodyloc[code_lower] = (bl1, bl2)

            beltable = get_col("beltable", "0")
            if beltable == "1":
                beltable_codes.add(key)
                if code:
                    beltable_codes.add(code.lower())

        # 构建祖先关系
        for key in all_codes:
            type_ancestors[key] = self._build_ancestors(key, type_equivs)

        # 构建后代关系
        for key in all_codes:
            type_descendants[key] = {key}
        for code, ancestors in type_ancestors.items():
            for ancestor in ancestors:
                if ancestor not in type_descendants:
                    type_descendants[ancestor] = set()
                type_descendants[ancestor].add(code)

        return type_ancestors, type_descendants, type_bodyloc, beltable_codes

    def _build_ancestors(
        self, code: str, type_equivs: dict[str, tuple[str, str]], visited: set[str] | None = None
    ) -> set[str]:
        if visited is None:
            visited = set()
        if code in visited:
            return set()
        visited.add(code)

        ancestors = set()
        equivs = type_equivs.get(code)
        if equivs:
            for equiv in equivs:
                if equiv:
                    ancestors.add(equiv)
                    ancestors.update(self._build_ancestors(equiv, type_equivs, visited))
        return ancestors

    def _resolve_path(self, filename: str, data_dir: str, fallback_dir: str | None = None) -> str:
        """解析文件路径，优先从版本目录加载，缺失时回退到根目录"""
        path = os.path.join(data_dir, filename)
        if os.path.exists(path):
            return path
        if fallback_dir:
            fallback_path = os.path.join(fallback_dir, filename)
            if os.path.exists(fallback_path):
                return fallback_path
        return path

    def load_version_data(self, data_dir: str, fallback_dir: str | None = None) -> VersionData:
        """加载单个版本的所有数据

        Args:
            data_dir: 版本数据目录（如 data/0x63/）
            fallback_dir: 回退目录，当版本目录中缺失文件时从此目录加载（如 data/）
        """
        version_data = VersionData()

        # 加载itemtypes.txt（需要先加载，因为其他数据可能依赖它）
        itemtypes_path = self._resolve_path("itemtypes.txt", data_dir, fallback_dir)
        (
            version_data.type_ancestors,
            version_data.type_descendants,
            version_data.type_bodyloc,
            version_data.type_beltable,
        ) = self.load_itemtypes(itemtypes_path)

        # 加载ItemStatCost.txt
        itemstatcost_path = self._resolve_path("ItemStatCost.txt", data_dir, fallback_dir)
        version_data.stats, version_data.stats_by_name = self.load_itemstatcost(itemstatcost_path)

        # 加载Properties.txt
        properties_path = self._resolve_path("Properties.txt", data_dir, fallback_dir)
        version_data.properties, version_data.properties_by_code = self.load_properties(
            properties_path
        )

        # 加载Armor.txt
        armor_path = self._resolve_path("Armor.txt", data_dir, fallback_dir)
        armor_items = self.load_items_txt(armor_path, "armor")
        version_data.items.update(armor_items)

        # 加载Weapons.txt
        weapons_path = self._resolve_path("Weapons.txt", data_dir, fallback_dir)
        weapons_items = self.load_items_txt(weapons_path, "weapon")
        version_data.items.update(weapons_items)

        # 加载Misc.txt
        misc_path = self._resolve_path("Misc.txt", data_dir, fallback_dir)
        misc_items = self.load_items_txt(misc_path, "misc")
        version_data.items.update(misc_items)

        # 加载magicprefix.txt
        magicprefix_path = self._resolve_path("magicprefix.txt", data_dir, fallback_dir)
        version_data.magic_prefixes = self.load_magic_affix(magicprefix_path, is_prefix=True)

        # 加载magicsuffix.txt
        magicsuffix_path = self._resolve_path("magicsuffix.txt", data_dir, fallback_dir)
        version_data.magic_suffixes = self.load_magic_affix(magicsuffix_path, is_prefix=False)

        # 加载uniqueitems.txt
        uniqueitems_path = self._resolve_path("uniqueitems.txt", data_dir, fallback_dir)
        version_data.unique_items = self.load_unique_items(uniqueitems_path)

        # 加载set items
        setitems_path = self._resolve_path(
            os.path.join("local", "item-names.json"), data_dir, fallback_dir
        )
        version_data.set_items = self.load_set_items(setitems_path)

        # 加载runewords
        runewords_path = self._resolve_path(
            os.path.join("local", "item-runes.json"), data_dir, fallback_dir
        )
        version_data.runewords = self.load_runewords(runewords_path)

        # 加载runes.txt补充符文列表
        runes_txt_path = self._resolve_path("runes.txt", data_dir, fallback_dir)
        self.load_runes_txt(runes_txt_path, version_data.runewords)

        # 加载skills.txt
        skills_path = self._resolve_path("skills.txt", data_dir, fallback_dir)
        version_data.skills, version_data.aura_skill_ids = self.load_skills(skills_path)

        # Load itemdata.txt
        itemdata_path = self._resolve_path("itemdata.txt", data_dir, fallback_dir)
        version_data.item_manager = self.load_itemdata(itemdata_path)

        # Load property.txt
        property_path = self._resolve_path("property.txt", data_dir, fallback_dir)
        version_data.prop_meta = self.load_property_meta(property_path)

        return version_data

    def load_property_meta(self, filepath: str) -> dict[int, PropertyMetaData]:
        properties: dict[int, PropertyMetaData] = {}
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Required data file not found: {filepath}")

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

    def load_itemdata(self, filepath: str) -> ItemMetaDataManager:
        manager = ItemMetaDataManager()
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Required data file not found: {filepath}")

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
                has_dur=parse_bool(parts[10 + idx_offset])
                if len(parts) > 10 + idx_offset
                else False,
                is_stacked=parse_bool(parts[11 + idx_offset])
                if len(parts) > 11 + idx_offset
                else False,
                has_monster_id=parse_bool(parts[12 + idx_offset])
                if len(parts) > 12 + idx_offset
                else False,
                is_charm=parse_bool(parts[13 + idx_offset])
                if len(parts) > 13 + idx_offset
                else False,
                spell_id=parse_int(parts[14 + idx_offset]) if len(parts) > 14 + idx_offset else 0,
                is_unique=parse_bool(parts[15 + idx_offset])
                if len(parts) > 15 + idx_offset
                else False,
                is_craft=parse_bool(parts[16 + idx_offset])
                if len(parts) > 16 + idx_offset
                else False,
                is_gem=parse_bool(parts[17 + idx_offset])
                if len(parts) > 17 + idx_offset
                else False,
                dmg1_min=parse_int(parts[18 + idx_offset]) if len(parts) > 18 + idx_offset else 0,
                dmg1_max=parse_int(parts[19 + idx_offset]) if len(parts) > 19 + idx_offset else 0,
                dmg2_min=parse_int(parts[20 + idx_offset]) if len(parts) > 20 + idx_offset else 0,
                dmg2_max=parse_int(parts[21 + idx_offset]) if len(parts) > 21 + idx_offset else 0,
                ipad_bits=parse_int(parts[22 + idx_offset]) if len(parts) > 22 + idx_offset else 0,
                ipad=parse_int(parts[23 + idx_offset]) if len(parts) > 23 + idx_offset else 0,
            )
            manager.add_item(item)

        return manager


class GameData:
    """Manages versioned data stores."""

    def __init__(self) -> None:
        self.version_data: dict[int, VersionData] = {}
        self.default_version: int = 0x63

    @classmethod
    def load(cls, base_data_dir: str) -> GameData:
        mgr = cls()
        mgr.load_all_versions(base_data_dir)
        return mgr

    def for_version(self, version: int) -> VersionData:
        """Return VersionData for a given game version."""
        if version in self.version_data:
            return self.version_data[version]
        if version >= 0x69 and 0x69 in self.version_data:
            return self.version_data[0x69]
        if self.default_version in self.version_data:
            return self.version_data[self.default_version]
        if self.version_data:
            return next(iter(self.version_data.values()))
        raise KeyError(f"No game data loaded for version {version:#x}")

    def load_version(self, version: int, data_dir: str, fallback_dir: str | None = None) -> bool:
        if not os.path.exists(data_dir):
            raise FileNotFoundError(f"Version data directory not found: {data_dir}")

        loader = D2DataLoader()
        version_data = loader.load_version_data(data_dir, fallback_dir)
        version_data.version = version
        self.version_data[version] = version_data
        return True

    def load_all_versions(self, base_data_dir: str) -> bool:
        if not os.path.exists(base_data_dir):
            raise FileNotFoundError(f"Base data directory not found: {base_data_dir}")

        success = True

        v63_dir = os.path.join(base_data_dir, "0x63")
        if os.path.exists(v63_dir):
            if not self.load_version(0x63, v63_dir, base_data_dir):
                success = False
        else:
            if not self.load_version(0x63, base_data_dir):
                success = False

        v69_dir = os.path.join(base_data_dir, "0x69")
        if os.path.exists(v69_dir) and not self.load_version(0x69, v69_dir, base_data_dir):
            success = False

        return success


_g_game_data: GameData | None = None


def init_d2data(data_dir: str) -> bool:
    """Initialize versioned game data from data_dir."""
    global _g_game_data
    _g_game_data = GameData.load(data_dir)
    return True


def get_game_data() -> GameData | None:
    return _g_game_data


class GameDataResolver:
    """Facade unifying versioned GameData lookups and localization."""

    def __init__(
        self,
        version: int | VersionData = 0x63,
        game_data: GameData | None = None,
    ) -> None:
        if isinstance(version, VersionData):
            self.data = version
            self.version = version.version
        else:
            self.version = version
            gd = game_data or get_game_data()
            if gd is None:
                raise RuntimeError("GameData is not initialized")
            self.data = gd.for_version(self.version)

    def get_item(self, code: str) -> ItemTypeInfo | None:
        return self.data.get_item(code)

    def get_skill_name(self, skill_id: int) -> str:
        from d2savior.core.property import get_skill_name as prop_get_skill_name

        loc_name, _ = prop_get_skill_name(skill_id)
        if loc_name and loc_name != "Unknown Skill":
            return loc_name
        return self.data.get_skill_name(skill_id)

    def get_runeword(self, runeword_id: int) -> RuneWordInfo | None:
        return self.data.get_runeword(runeword_id)

    def get_unique_item(self, unique_id: int) -> UniqueItemInfo | None:
        return self.data.get_unique_item(unique_id)

    def get_set_item(self, set_id: int) -> SetItemInfo | None:
        return self.data.get_set_item(set_id)

    def get_magic_prefix(self, prefix_id: int) -> MagicAffixInfo | None:
        return self.data.get_magic_prefix(prefix_id)

    def get_magic_suffix(self, suffix_id: int) -> MagicAffixInfo | None:
        return self.data.get_magic_suffix(suffix_id)

    def get_stat(self, stat_id: int) -> StatInfo | None:
        return self.data.get_stat(stat_id)

    def get_property(self, prop_id: int) -> PropertyInfo | None:
        return self.data.get_property(prop_id)

    def get_item_meta(self, type_id: Any) -> ItemMetaData | None:
        return self.data.get_item_meta(type_id)

    def get_property_meta(
        self, prop_id: int, version: int | None = None
    ) -> PropertyMetaDataItem | None:
        return self.data.get_property_meta(prop_id, version)

    def is_beltable(self, item_code: str) -> bool:
        return self.data.is_beltable(item_code)

    def get_belt_rows(self, item_code: str) -> int:
        return self.data.get_belt_rows(item_code)

    def is_descendant(self, item_type_code: str, ancestor_code: str) -> bool:
        return self.data.is_descendant(item_type_code, ancestor_code)

    def get_localized_item_name(self, code_or_name: str, fallback: str = "") -> str:
        from d2savior.core.localized_data import get_localized_data

        loc = get_localized_data()
        if not loc:
            return fallback or code_or_name

        name = loc.get_item_name(code_or_name)
        if name and name != code_or_name:
            return name

        name = loc.get_item_nameaffix(code_or_name)
        if name and name != code_or_name:
            return name

        name = loc.get_rune_name(code_or_name)
        if name and name != code_or_name:
            return name

        if fallback and fallback != code_or_name:
            name = loc.get_item_name(fallback)
            if name and name != fallback:
                return name
            name = loc.get_item_nameaffix(fallback)
            if name and name != fallback:
                return name

        return fallback or code_or_name

    def get_localized_unique_name(self, unique_id: int) -> str:
        u_info = self.get_unique_item(unique_id)
        if not u_info:
            return ""
        from d2savior.core.localized_data import get_localized_data

        loc = get_localized_data()
        if loc:
            name = loc.get_item_name(u_info.index)
            if name and name != u_info.index:
                return name
        return u_info.index

    def get_localized_set_name(self, set_id: int) -> str:
        s_info = self.get_set_item(set_id)
        if not s_info:
            return ""
        from d2savior.core.localized_data import get_localized_data

        loc = get_localized_data()
        if loc:
            name = loc.get_item_name(s_info.name)
            if name and name != s_info.name:
                return name
        return s_info.name

    def get_localized_runeword_name(self, runeword_id: int) -> str:
        rw_info = self.get_runeword(runeword_id)
        if not rw_info:
            return ""
        from d2savior.core.localized_data import get_localized_data

        loc = get_localized_data()
        if loc:
            name = loc.get_rune_name(rw_info.name)
            if name and name != rw_info.name:
                return name
            name = loc.get_rune_name(f"Runeword{runeword_id}")
            if name and name != f"Runeword{runeword_id}":
                return name
        return rw_info.name

    def get_localized_magic_prefix(self, prefix_id: int) -> str:
        p_info = self.get_magic_prefix(prefix_id)
        if not p_info:
            return ""
        from d2savior.core.localized_data import get_localized_data

        loc = get_localized_data()
        if loc:
            name = loc.get_item_nameaffix(p_info.name)
            if name and name != p_info.name:
                return name
        return p_info.name

    def get_localized_magic_suffix(self, suffix_id: int) -> str:
        s_info = self.get_magic_suffix(suffix_id)
        if not s_info:
            return ""
        from d2savior.core.localized_data import get_localized_data

        loc = get_localized_data()
        if loc:
            name = loc.get_item_nameaffix(s_info.name)
            if name and name != s_info.name:
                return name
        return s_info.name

    def get_localized_quality_name(self, quality_name: str) -> str:
        from d2savior.core.localized_data import get_localized_data

        loc = get_localized_data()
        if not loc or loc.current_lang == "enUS":
            return quality_name
        name = loc.get_item_nameaffix(quality_name)
        if name and name != quality_name:
            return name
        ui_key = f"LootFilter{quality_name}Rarity"
        name = loc.get_clean_string("ui.json", ui_key, default="")
        if name:
            return name
        quality_fallbacks = {
            "ruRU": {"Crafted": "созданный", "Rare": "редкий"},
            "zhCN": {"Crafted": "手工艺", "Rare": "稀有"},
            "zhTW": {"Crafted": "手工艺", "Rare": "稀有"},
        }
        fb = quality_fallbacks.get(loc.current_lang, {}).get(quality_name)
        if fb:
            return fb
        return quality_name

    def get_localized_gem_type_name(self, gem_type: str) -> str:
        from d2savior.core.localized_data import get_localized_data

        loc = get_localized_data()
        if not loc:
            return gem_type
        name = loc.get_item_name(gem_type)
        if name and name != gem_type:
            return name
        name = loc.get_item_nameaffix(gem_type)
        if name and name != gem_type:
            return name
        return gem_type

    def get_localized_rune_short_name(self, code_str: str) -> str:
        from d2savior.core.localized_data import get_localized_data

        loc = get_localized_data()
        type_info = self.get_item(code_str)
        eng_name = type_info.name if type_info else code_str
        if not loc or loc.current_lang == "enUS":
            return eng_name[:-5] if eng_name.endswith(" Rune") else eng_name

        loc_name = loc.get_rune_name(code_str)
        if loc_name and loc_name != code_str:
            if loc_name.startswith("Руна "):
                return loc_name[len("Руна ") :]
            if loc_name.endswith("符文"):
                return loc_name[: -len("符文")]
            if loc_name.endswith(" Rune"):
                return loc_name[: -len(" Rune")]
            return loc_name
        return eng_name[:-5] if eng_name.endswith(" Rune") else eng_name

    def get_localized_class_name(self, class_id: int) -> str:
        class_keys = [
            "Amazon",
            "Sorceress",
            "Necromancer",
            "Paladin",
            "Barbarian",
            "Druid",
            "Assassin",
            "Warlock",
        ]
        default_name = class_keys[class_id] if 0 <= class_id < len(class_keys) else "Unknown"
        from d2savior.core.localized_data import get_localized_data

        loc = get_localized_data()
        if loc:
            name = loc.get_class_name(class_id)
            if name:
                return name
        return default_name
