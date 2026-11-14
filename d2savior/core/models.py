"""Data model definitions for parsed Diablo II game tables and version stores."""

import copy
from collections.abc import Buffer
from dataclasses import dataclass, field
from typing import NotRequired, TypedDict

type ItemTypeId = Buffer | str


class LocalizedEntry(TypedDict, extra_items=str):
    """Raw localized JSON entry with optional metadata fields and language strings."""

    id: NotRequired[int]
    Key: NotRequired[str]


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


def _convert_item_type_to_meta(
    type_info: ItemTypeInfo | None,
    version_data: VersionData | None = None,
) -> ItemMetaData | None:
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

    if version_data is not None and type_info.item_type2:
        meta.is_scroll_or_book = version_data.is_descendant(
            type_info.item_type2, "scro"
        ) or version_data.is_descendant(type_info.item_type2, "book")
        meta.is_body_part = version_data.is_descendant(type_info.item_type2, "body")
        meta.is_player_body_part = version_data.is_descendant(type_info.item_type2, "play")
        if version_data.is_descendant(type_info.item_type2, "armo"):
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
class GemMod:
    code: str = ""
    param: int = 0
    min_val: int = 0
    max_val: int = 0


@dataclass(slots=True)
class GemInfo:
    code: str = ""
    name: str = ""
    weapon_mods: list[GemMod] = field(default_factory=list)
    helm_mods: list[GemMod] = field(default_factory=list)
    shield_mods: list[GemMod] = field(default_factory=list)


@dataclass(slots=True)
class HirelingLevelInfo:
    """Level-breakpoint stat progression for a mercenary hireling from hireling.txt."""

    level: int = 0
    exp_per_lvl: int = 0
    str_base: int = 0
    str_per_lvl: int = 0
    dex_base: int = 0
    dex_per_lvl: int = 0
    resist_fire: int = 0
    resist_fire_per_lvl: int = 0
    resist_cold: int = 0
    resist_cold_per_lvl: int = 0
    resist_lightning: int = 0
    resist_lightning_per_lvl: int = 0
    resist_poison: int = 0
    resist_poison_per_lvl: int = 0


@dataclass(slots=True)
class HirelingInfo:
    """Metadata and level progression for a mercenary hireling type from hireling.txt."""

    hireling_id: int = 0
    hireling: str = ""
    act: int = 0
    difficulty: int = 0
    name_first: str = ""
    name_last: str = ""
    hire_desc: str = ""
    skill_1: str = ""
    levels: list[HirelingLevelInfo] = field(default_factory=list)

    def level_stats_for(self, level: int) -> HirelingLevelInfo | None:
        """Return the highest level breakpoint <= level (or the lowest available breakpoint)."""
        if not self.levels:
            return None
        best = self.levels[0]
        for entry in self.levels:
            if entry.level > level:
                break
            best = entry
        return best


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
    rare_prefixes: dict[int, str] = field(default_factory=dict)
    rare_suffixes: dict[int, str] = field(default_factory=dict)
    unique_items: dict[int, UniqueItemInfo] = field(default_factory=dict)
    set_items: dict[int, SetItemInfo] = field(default_factory=dict)
    runewords: dict[int, RuneWordInfo] = field(default_factory=dict)
    gems: dict[str, GemInfo] = field(default_factory=dict)
    hirelings: dict[int, HirelingInfo] = field(default_factory=dict)
    monsters: dict[int, str] = field(default_factory=dict)
    skills: dict[int, str] = field(default_factory=dict)
    aura_skill_ids: set[int] = field(default_factory=set)
    fire_skill_ids: set[int] = field(default_factory=set)
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

    def get_rare_prefix(self, prefix_id: int) -> str | None:
        if prefix_id in self.rare_prefixes:
            return self.rare_prefixes[prefix_id]
        if (prefix_id + 155) in self.rare_prefixes:
            return self.rare_prefixes[prefix_id + 155]
        return None

    def get_rare_suffix(self, suffix_id: int) -> str | None:
        return self.rare_suffixes.get(suffix_id)

    def get_unique_item(self, unique_id: int) -> UniqueItemInfo | None:
        return self.unique_items.get(unique_id)

    def get_set_item(self, set_id: int) -> SetItemInfo | None:
        return self.set_items.get(set_id)

    def get_runeword(self, runeword_id: int) -> RuneWordInfo | None:
        return self.runewords.get(runeword_id)

    def get_gem_info(self, code: str) -> GemInfo | None:
        if not code:
            return None
        return self.gems.get(code.lower().strip())

    def get_hireling(self, hireling_id: int) -> HirelingInfo | None:
        return self.hirelings.get(hireling_id)

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
        # Check if ancestor set contains specified ancestor
        ancestors = self.type_ancestors.get(item_type_code.lower(), set())
        if ancestor_code.lower() in ancestors:
            return True
        # Check if descendant set contains specified type
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
            item_type = item_info.type or item_info.item_type
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
