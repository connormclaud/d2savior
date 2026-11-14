from collections.abc import Iterator
from typing import ClassVar

from d2savior.core.bit_io import BitIO, BitReader, BitWriter
from d2savior.core.ear import Ear, is_ptr24_and_above
from d2savior.core.enums import ITEM_LIST_MAGIC
from d2savior.core.ibitstream import IBitStream
from d2savior.core.item_name import GoldQuantity, LongName
from d2savior.core.loader import GameData
from d2savior.core.models import ItemMetaData, VersionData
from d2savior.core.obitstream import OBitStream
from d2savior.core.property_list import PropertyList, is_d2r
from d2savior.core.resolver import GameDataResolver
from d2savior.core.stash import GEM_CODES, MATERIAL_CODES, RUNE_CODES

VALID_VERSIONS = [0x69, 0x63, 0x62, 0x61, 0x60, 0x5C, 0x59, 0x57, 0x47]


def is_valid_version(version: int) -> bool:
    return version in VALID_VERSIONS


class ExtItemInfo:
    def __init__(self, meta: ItemMetaData | None = None) -> None:
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
        self._meta = meta

    def is_set(self) -> bool:
        return self.quality == 5

    def rune_word_id(self) -> int:
        return self.rune_id if self.rune_id is not None else 0

    def codec(
        self,
        io: BitIO,
        version: int,
        is_runeword: bool = False,
        is_personalized: bool = False,
    ) -> None:
        meta = self._meta
        charm_flag = meta.is_charm if meta else False
        monster_flag = meta.has_monster_id if meta else False
        spell_flag = (meta.spell_id > 0) if meta else False
        body_part_flag = (meta.is_body_part and not meta.is_player_body_part) if meta else False
        scroll_flag = meta.is_scroll_or_book if meta else False

        self.gems = io.bits(3, self.gems)
        self.guid = io.bits(32, self.guid)
        self.drop_level = io.bits(7, self.drop_level)
        self.quality = io.bits(4, self.quality)

        self.var_gfx = io.opt_bits(3, self.var_gfx if self.has_var_gfx else None)
        self.has_var_gfx = self.var_gfx is not None

        self.item_class = io.opt_bits(11, self.item_class if self.has_class else None)
        self.has_class = self.item_class is not None

        match self.quality:
            case 1:
                self.low_quality_id = io.bits(3, self.low_quality_id or 0)
            case 2:
                if charm_flag:
                    self.charm_id = io.bits(12, self.charm_id or 0)
                elif body_part_flag:
                    self.body_part_file_index = io.bits(10, self.body_part_file_index or 0)
                elif scroll_flag:
                    self.spell_type = io.bits(5, self.spell_type or 0)
            case 3:
                self.high_quality_id = io.bits(3, self.high_quality_id or 0)
            case 4:
                self.magic_prefix = io.bits(11, self.magic_prefix or 0)
                self.magic_suffix = io.bits(11, self.magic_suffix or 0)
            case 5:
                self.set_id = io.bits(12, self.set_id or 0)
            case 6:
                if io.is_reading:
                    self.rare_name = LongName()
                if self.rare_name:
                    self.rare_name.codec(io)
            case 7:
                self.unique_id = io.bits(12, self.unique_id or 0)
            case 8:
                if io.is_reading:
                    self.craft_name = LongName()
                if self.craft_name:
                    self.craft_name.codec(io)

        if is_runeword:
            self.rune_id = io.bits(16, self.rune_id or 0)

        if is_personalized:
            bits_per_char = 8 if is_ptr24_and_above(version) else 7
            if io.is_writing:
                for c in self.person_name:
                    io.bits(bits_per_char, c)
                io.bits(bits_per_char, 0)
            else:
                self.person_name = []
                for _ in range(16):
                    c = io.bits(bits_per_char)
                    if c == 0:
                        break
                    self.person_name.append(c)

        if monster_flag:
            self.monster_id = io.bits(10, self.monster_id or 0)
        elif spell_flag:
            self.spell_id = io.bits(5, self.spell_id or 0)

    def deserialize(
        self,
        bs: IBitStream,
        version: int,
        is_runeword: bool = False,
        is_personalized: bool = False,
    ) -> None:
        self.codec(
            BitReader(bs),
            version,
            is_runeword=is_runeword,
            is_personalized=is_personalized,
        )

    def serialize(
        self,
        bs: OBitStream,
        version: int,
        is_runeword: bool = False,
        is_personalized: bool = False,
    ) -> None:
        self.codec(
            BitWriter(bs),
            version,
            is_runeword=is_runeword,
            is_personalized=is_personalized,
        )


class TypeSpecificInfo:
    def __init__(self, meta: ItemMetaData | None = None) -> None:
        self.defence: int | None = None
        self.max_durability: int | None = None
        self.current_durability: int | None = None
        self.sockets_count: int | None = None
        self.quantity: int | None = None
        self.has_set_prop_list: list[bool] = []
        self.property_list: PropertyList = PropertyList()
        self.set_properties: list[PropertyList | None] = []
        self.runeword_property_list: PropertyList | None = None
        self._meta = meta
        self._data: VersionData | None = None

    def sockets(self) -> tuple[int, int]:
        base = self.sockets_count if self.sockets_count is not None else 0
        ext = self.property_list.ext_sockets()
        return (base, ext)

    def total_sockets(self) -> int:
        b, e = self.sockets()
        return min(7, b + e)

    def get_defence(self, data: VersionData | None = None) -> int:
        if self.defence is None:
            return 0
        d = data or self._data
        ac_stat = d.get_stat(31) if d else None
        save_add = ac_stat.save_add if ac_stat else 10
        return self.defence - save_add

    def is_indestructible(self) -> bool:
        return self.max_durability == 0 or self.property_list.is_indestructible()

    def codec(
        self,
        io: BitIO,
        version: int,
        is_socketed: bool = False,
        is_set: bool = False,
        is_runeword: bool = False,
        data: VersionData | GameData | GameDataResolver | None = None,
    ) -> None:
        if isinstance(data, GameDataResolver):
            d = data.game_data.for_version(version)
        elif isinstance(data, GameData):
            d = data.for_version(version)
        elif data is not None:
            d = data
        else:
            d = None

        if d is None:
            raise ValueError(
                f"VersionData or GameData is required to parse item properties for version {version:#x}"
            )
        self._data = d

        meta = self._meta
        has_def = meta.has_def if meta else False
        has_dur = meta.has_dur if meta else False
        is_stacked = meta.is_stacked if meta else False
        use_stat_cost = is_d2r(version)
        d2r_order = is_d2r(version)

        if has_def:
            if use_stat_cost:
                ac_stat = d.get_stat(31)
                def_bits = ac_stat.save_bits if ac_stat else 11
            else:
                def_bits = 11
            self.defence = io.bits(def_bits, self.defence or 0)

        if has_dur:
            if use_stat_cost:
                max_dur_stat = d.get_stat(73)
                max_dur_bits = max_dur_stat.save_bits if max_dur_stat else 8
                dur_stat = d.get_stat(72)
                dur_bits = dur_stat.save_bits if dur_stat else 9
            else:
                max_dur_bits = 8
                dur_bits = 9
            self.max_durability = io.bits(max_dur_bits, self.max_durability or 0)
            if self.max_durability and self.max_durability > 0:
                self.current_durability = io.bits(dur_bits, self.current_durability or 0)

        def _rw_quantity() -> None:
            if version >= 0x69:
                self.quantity = io.opt_bits(9, self.quantity)
            elif is_stacked:
                self.quantity = io.bits(9, self.quantity or 0)

        def _rw_sockets() -> None:
            if is_socketed:
                if use_stat_cost:
                    sock_stat = d.get_stat(194)
                    sock_bits = sock_stat.save_bits if sock_stat else 3
                else:
                    sock_bits = 4
                self.sockets_count = io.bits(
                    sock_bits,
                    self.sockets_count if self.sockets_count is not None else 1,
                )
                if io.is_reading and self.sockets_count < 1:
                    self.sockets_count = 1

        if d2r_order:
            _rw_quantity()
            _rw_sockets()
        else:
            _rw_sockets()
            _rw_quantity()

        if is_set:
            if io.is_reading:
                self.has_set_prop_list = [io.bit() for _ in range(5)]
            else:
                for has_prop in self.has_set_prop_list:
                    io.bit(has_prop)
        else:
            self.has_set_prop_list = [False] * 5

        self.property_list.codec(io, version, d)

        if is_set:
            if io.is_reading:
                self.set_properties = []
                for i in range(5):
                    if self.has_set_prop_list[i]:
                        prop_list = PropertyList()
                        prop_list.codec(io, version, d)
                        self.set_properties.append(prop_list)
                    else:
                        self.set_properties.append(None)
            else:
                for i, prop_list in enumerate(self.set_properties):
                    if i < len(self.has_set_prop_list) and self.has_set_prop_list[i] and prop_list:
                        prop_list.codec(io, version, d)

        if is_runeword:
            if io.is_reading:
                self.runeword_property_list = PropertyList()
            if self.runeword_property_list:
                self.runeword_property_list.codec(io, version, d)

    def deserialize(
        self,
        bs: IBitStream,
        version: int,
        is_socketed: bool = False,
        is_set: bool = False,
        is_runeword: bool = False,
        data: VersionData | GameData | None = None,
    ) -> None:
        self.codec(
            BitReader(bs),
            version,
            is_socketed=is_socketed,
            is_set=is_set,
            is_runeword=is_runeword,
            data=data,
        )

    def serialize(
        self,
        bs: OBitStream,
        version: int,
        is_socketed: bool = False,
        is_set: bool = False,
        is_runeword: bool = False,
        data: VersionData | GameData | None = None,
    ) -> None:
        self.codec(
            BitWriter(bs),
            version,
            is_socketed=is_socketed,
            is_set=is_set,
            is_runeword=is_runeword,
            data=data,
        )


class ItemInfo:
    STACKABLE_FOR_STASH: ClassVar[set[bytes]] = RUNE_CODES | GEM_CODES | MATERIAL_CODES

    def __init__(self, meta: ItemMetaData | None = None) -> None:
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
        self._data: VersionData | None = None

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
        type_name = (
            self.type_name if self.type_name.strip() or not self._meta else self._meta.type_id
        )
        return type_name in self.STACKABLE_FOR_STASH

    def _codec_realm_data(self, io: BitIO, version: int) -> None:
        realm_count = 4 if version > 96 else (3 if version > 93 else 2)
        if io.is_reading:
            self.realm_data = [io.bits(32) for _ in range(realm_count)]
        else:
            for i in range(realm_count):
                val = self.realm_data[i] if i < len(self.realm_data) else 0
                io.bits(32, val)

    def _codec_optional_realm_data(self, io: BitIO, version: int) -> None:
        if io.bit(bool(self.realm_data)):
            self._codec_realm_data(io, version)
        elif io.is_reading:
            self.realm_data = []

    def _codec_stash_stack_size(self, io: BitIO, version: int) -> None:
        if not is_d2r(version) or version <= 99:
            return
        if version <= 101:
            if self._is_stackable_for_stash():
                self.stash_stack_size = io.bits(8, self.stash_stack_size)
                self.has_stash_stack_size = True
        else:
            has_stash = io.bit(self.has_stash_stack_size)
            self.has_stash_stack_size = has_stash
            if has_stash:
                self.stash_stack_size = io.bits(8, self.stash_stack_size)

    def codec(
        self,
        io: BitIO,
        version: int,
        is_simple: bool,
        is_runeword: bool,
        is_personalized: bool,
        is_socketed: bool,
        data: VersionData | None = None,
    ) -> ItemMetaData | None:
        self._data = data
        is_d2r_ = is_d2r(version)

        if is_d2r_:
            if io.is_reading:
                self.type_name = bytes(io.huffman_char() for _ in range(4))
            else:
                for c in self.type_name:
                    io.huffman_char(c)
        else:
            if io.is_reading:
                self.type_name = bytes([io.byte() for _ in range(4)])
            else:
                for b in self.type_name:
                    io.byte(b)

        meta = data.get_item_meta(self.type_name) if data else None
        if meta is None:
            meta = self._meta
        self._meta = meta

        if not is_simple and meta:
            if io.is_reading:
                self.ext_info = ExtItemInfo(meta)
            if self.ext_info:
                self.ext_info.codec(
                    io,
                    version,
                    is_runeword=is_runeword,
                    is_personalized=is_personalized,
                )

        if self.is_gold():
            if io.is_reading or self.gold is None:
                self.gold = GoldQuantity()
            self.gold.codec(io)

        has_rand = io.bit(self.has_rand or bool(self.realm_data) or bool(self.timestamp_flag))
        self.has_rand = has_rand
        if has_rand:
            if is_d2r_ and version > 86:
                self._codec_realm_data(io, version)
            elif not is_simple:
                if io.is_reading:
                    self.timestamp_flag = [io.bits(32) for _ in range(4)]
                else:
                    for ts in self.timestamp_flag:
                        io.bits(32, ts)

        self._codec_stash_stack_size(io, version)

        if not is_simple and meta:
            if io.is_reading:
                self.type_specific_info = TypeSpecificInfo(meta)
            if self.type_specific_info:
                self.type_specific_info.codec(
                    io,
                    version,
                    is_socketed=is_socketed,
                    is_set=self.is_set(),
                    is_runeword=is_runeword,
                    data=data,
                )
        elif is_d2r_ and version >= 0x69 and meta and meta.ipad_bits > 0:
            self.pad = io.bits(meta.ipad_bits, self.pad)

        return meta

    def deserialize(
        self,
        bs: IBitStream,
        version: int,
        is_simple: bool,
        is_runeword: bool,
        is_personalized: bool,
        is_socketed: bool,
        data: VersionData | None = None,
    ) -> ItemMetaData | None:
        return self.codec(
            BitReader(bs),
            version,
            is_simple,
            is_runeword,
            is_personalized,
            is_socketed,
            data=data,
        )

    def serialize(
        self,
        bs: OBitStream,
        version: int,
        is_simple: bool,
        is_runeword: bool,
        is_personalized: bool,
        is_socketed: bool,
        data: VersionData | None = None,
    ) -> None:
        self.codec(
            BitWriter(bs),
            version,
            is_simple,
            is_runeword,
            is_personalized,
            is_socketed,
            data=data,
        )


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
    def __init__(self, meta: ItemMetaData | None = None) -> None:
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

        self.chronicle_id: int | None = None
        self.chronicle_compact_data: int | None = None
        self.chronicle_data_header: int | None = None
        self.chronicle_entries: list[int] = []

        self.ear: Ear | None = None
        self.item_info: ItemInfo | None = None
        self.gem_items: list[D2Item] = []

        self._meta = meta
        self._data: VersionData | None = None

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

    @property
    def code_str(self) -> str:
        """Return the stripped ASCII item type code (e.g., 'amu', 'rin')."""
        return self.type_name.decode("ascii", errors="replace").strip()

    @property
    def ext_info(self) -> ExtItemInfo | None:
        return self.item_info.ext_info if self.item_info else None

    @property
    def type_specific_info(self) -> TypeSpecificInfo | None:
        return self.item_info.type_specific_info if self.item_info else None

    @property
    def stash_stack_size(self) -> int:
        return self.item_info.stash_stack_size if self.item_info else 0

    def quality(self) -> int:
        if self.is_ear or self.is_simple:
            if self._meta and self._meta.is_unique:
                return 7
            return 2
        if ext := self.ext_info:
            return ext.quality
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
        return self.type_specific_info is not None

    def codec(
        self,
        io: BitIO,
        version: int = 0x63,
        magic_flag: bool = True,
        data: VersionData | GameData | GameDataResolver | None = None,
    ) -> None:
        if isinstance(data, GameDataResolver):
            data = data.game_data
        if io.is_writing and not is_valid_version(self.version):
            self.version = version
        vd = data.for_version(version) if isinstance(data, GameData) else (data or self._data)
        self._data = vd
        if is_d2r(version):
            self._codec_d2r(io, version, magic_flag, data=data)
        else:
            self._codec_classic(io, version, magic_flag, data=data)

    def deserialize(
        self,
        bs: IBitStream,
        version: int = 0x63,
        read_magic: bool = True,
        data: VersionData | GameData | GameDataResolver | None = None,
    ) -> None:
        self.codec(BitReader(bs), version, read_magic, data=data)

    def serialize(
        self,
        bs: OBitStream,
        version: int,
        write_magic: bool = True,
        data: VersionData | GameData | GameDataResolver | None = None,
    ) -> None:
        self.codec(BitWriter(bs), version, write_magic, data=data)

    def _codec_header(
        self,
        io: BitIO,
        version: int,
        magic_flag: bool,
        data: VersionData | GameData | None,
    ) -> VersionData | None:
        if io.is_reading:
            if magic_flag:
                io.align_byte()
                self.magic = io.word()
                if self.magic != ITEM_LIST_MAGIC:
                    io.seek_back_bytes(2)
                    self.magic = ITEM_LIST_MAGIC
                self.version = io.dword()
                if not is_valid_version(self.version):
                    io.seek_back_bytes(4)
                    self.version = version
            else:
                self.magic = ITEM_LIST_MAGIC
                self.version = version

            d = (
                data.for_version(self.version)
                if isinstance(data, GameData)
                else (data or self._data)
            )
            self._data = d
            return d

        d = data.for_version(version) if isinstance(data, GameData) else (data or self._data)
        if magic_flag:
            io.align_byte()
            io.word(self.magic)
            io.dword(self.version)
        return d

    def _codec_gem_items(
        self,
        io: BitIO,
        *,
        magic_flag: bool,
        data: VersionData | None,
    ) -> None:
        io.align_byte()
        if io.is_reading:
            self.gem_items = []
            for _ in range(self.gems()):
                item = D2Item()
                item.codec(io, self.version, magic_flag=magic_flag, data=data)
                self.gem_items.append(item)
        else:
            for gem_item in self.gem_items:
                gem_item.codec(io, self.version, magic_flag=magic_flag, data=data)

    def _codec_d2r(
        self,
        io: BitIO,
        version: int,
        magic_flag: bool = True,
        data: VersionData | GameData | None = None,
    ) -> None:
        d = self._codec_header(io, version, magic_flag, data)

        if io.is_writing:

            def _sync_bit(f: int, mask: int, val: bool) -> int:
                return (f | mask) if val else (f & ~mask)

            flags = self._flags
            flags = _sync_bit(flags, 0x00000010, self.is_identified)
            flags = _sync_bit(flags, 0x00000020, self._has_quantity)
            flags = _sync_bit(flags, 0x00000800, self.is_socketed)
            flags = _sync_bit(flags, 0x00010000, self.is_ear)
            flags = _sync_bit(flags, 0x00020000, self.is_newbie)
            flags = _sync_bit(flags, 0x00200000, self.is_simple)
            flags = _sync_bit(flags, 0x00400000, self.is_ethereal)
            flags = _sync_bit(flags, 0x01000000, self.is_personalized)
            flags = _sync_bit(flags, 0x04000000, self.is_runeword)
            flags = _sync_bit(flags, 0x10000000, self._is_chronicle)
            flags = _sync_bit(flags, 0x20000000, self._is_chronicle_compact)
            self._flags = flags
            io.bits(32, flags)

            if self.item_version >= 99:
                io.bit(True)
                io.bits(2, self.item_version - 99)
            else:
                io.bit(False)
                io.bits(2, self.item_version)
        else:
            flags = io.bits(32)
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

            hf = io.bit()
            vv = io.bits(2)
            self.item_version = (vv + 99) if hf else vv

        self.location = io.bits(3, self.location)
        if self.location == 3 or self.location == 5:
            if io.is_reading:
                self.position = 0
                self.stored_in = 0
            self.column = io.bits(16, self.column)
            self.row = io.bits(16, self.row)
        else:
            self.position = io.bits(4, self.position)
            self.column = io.bits(4, self.column)
            self.row = io.bits(4, self.row)
            if io.is_writing:
                io.bits(3, self.stored_in + 1)
            else:
                self.stored_in = io.bits(3) - 1

        if self.is_ear:
            if io.is_reading:
                self.ear = Ear()
                self._meta = d.get_item_meta(b"ear ") if d else None
            if self.ear:
                self.ear.codec(io, self.version)
        else:
            if io.is_reading:
                type_name = bytes(io.huffman_char() for _ in range(4))
                self._meta = d.get_item_meta(type_name) if d else None
                self.item_info = ItemInfo(self._meta)
                self.item_info.type_name = type_name
            else:
                for c in self.type_name:
                    io.huffman_char(c)

        item_ver = self.version if io.is_reading else version
        if self.is_simple:
            self._codec_compact_d2r(io, item_ver, data=d)
        else:
            self._codec_complete_d2r(io, item_ver, data=d)

        self._codec_gem_items(io, magic_flag=self.version <= 96, data=d)

    def _codec_compact_d2r(
        self,
        io: BitIO,
        version: int,
        data: VersionData | None = None,
    ) -> None:
        if self.is_ear or not self.item_info:
            return

        d = data or self._data
        if version > 92 and d:
            type_info = d.get_item(self.code_str)
            if type_info and type_info.quest > 0 and type_info.questdiffcheck:
                quest_diff_stat = d.get_stat(356)
                if quest_diff_stat and quest_diff_stat.save_bits > 0:
                    if io.is_writing:
                        raw = (
                            self.item_info.quest_difficulty >> quest_diff_stat.val_shift
                        ) + quest_diff_stat.save_add
                        io.bits(quest_diff_stat.save_bits, raw)
                    else:
                        raw = io.bits(quest_diff_stat.save_bits)
                        self.item_info.quest_difficulty = (
                            raw - quest_diff_stat.save_add
                        ) << quest_diff_stat.val_shift

        self.item_info._codec_optional_realm_data(io, version)
        self.item_info._codec_stash_stack_size(io, version)

    def _codec_complete_d2r(
        self,
        io: BitIO,
        version: int,
        data: VersionData | None = None,
    ) -> None:
        if self.is_ear or not self.item_info:
            return

        d = data or self._data
        meta = self._meta

        if io.is_reading:
            self.item_info.ext_info = ExtItemInfo(meta)
        if self.item_info.ext_info:
            self.item_info.ext_info.codec(
                io,
                version,
                is_runeword=self.is_runeword,
                is_personalized=self.is_personalized,
            )

        self.item_info._codec_optional_realm_data(io, version)

        if self.item_info.is_gold():
            if io.is_reading or self.item_info.gold is None:
                self.item_info.gold = GoldQuantity()
            self.item_info.gold.codec(io)

        if io.is_reading:
            self.item_info.type_specific_info = TypeSpecificInfo(meta)
        if self.item_info.type_specific_info:
            self.item_info.type_specific_info.codec(
                io,
                version,
                is_socketed=self.is_socketed,
                is_set=self.is_set(),
                is_runeword=self.is_runeword,
                data=d,
            )

        if self._is_chronicle:
            self.chronicle_id = io.bits(16, self.chronicle_id or 0)
            if self._is_chronicle_compact:
                self.chronicle_compact_data = io.qword(self.chronicle_compact_data or 0)
            else:
                self.chronicle_data_header = io.dword(self.chronicle_data_header or 0)
                count = io.bits(4, len(self.chronicle_entries))
                if io.is_reading:
                    self.chronicle_entries = [io.qword() for _ in range(count)]
                else:
                    for entry in self.chronicle_entries:
                        io.qword(entry)

        self.item_info._codec_stash_stack_size(io, version)

    def _codec_classic(
        self,
        io: BitIO,
        version: int,
        magic_flag: bool = True,
        data: VersionData | GameData | None = None,
    ) -> None:
        d = self._codec_header(io, version, magic_flag, data)

        self.is_quest = io.bit(self.is_quest)
        self.target_del_flags = io.bits(3, self.target_del_flags)
        self.is_identified = io.bit(self.is_identified)
        self.switch_in_out_flags = io.bits(3, self.switch_in_out_flags)
        self.is_disabled = io.bit(self.is_disabled)
        self.repair_flags = io.bits(2, self.repair_flags)
        self.is_socketed = io.bit(self.is_socketed)
        self.is_no_sell = io.bit(self.is_no_sell)
        self.is_new = io.bit(self.is_new)
        self.is_bad_equipped = io.bit(self.is_bad_equipped)
        self.is_named = io.bit(self.is_named)
        self.is_ear = io.bit(self.is_ear)
        self.is_newbie = io.bit(self.is_newbie)
        self.init_flags = io.bits(3, self.init_flags)
        self.is_simple = io.bit(self.is_simple)
        self.is_ethereal = io.bit(self.is_ethereal)
        self.is_just_saved = io.bit(self.is_just_saved)
        self.is_personalized = io.bit(self.is_personalized)
        self.is_low_quality = io.bit(self.is_low_quality)
        self.is_runeword = io.bit(self.is_runeword)

        self.duplicate_chronicle = io.bits(5, self.duplicate_chronicle)
        self.item_version = io.bits(10, self.item_version)

        self.location = io.bits(3, self.location)
        self.position = io.bits(4, self.position)
        self.column = io.bits(4, self.column)
        self.row = io.bits(4, self.row)
        self.stored_in = io.bits(3, self.stored_in)

        if self.is_ear:
            if io.is_reading:
                self.ear = Ear()
                self._meta = d.get_item_meta(b"ear ") if d else None
            if self.ear:
                self.ear.codec(io, self.version)
        else:
            if io.is_reading:
                self.item_info = ItemInfo(self._meta)
            if self.item_info:
                meta = self.item_info.codec(
                    io,
                    self.version,
                    self.is_simple,
                    self.is_runeword,
                    self.is_personalized,
                    self.is_socketed,
                    data=d,
                )
                if io.is_reading and meta is not None:
                    self._meta = meta

        self._codec_gem_items(io, magic_flag=True, data=d)


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

    def codec(
        self,
        io: BitIO,
        version: int,
        data: VersionData | GameData | GameDataResolver | None = None,
    ) -> None:
        if io.is_writing:
            io.align_byte()
            self.magic = io.word(self.magic)
            self.count = io.word(len(self.items))
            for item in self.items:
                item.codec(io, version, not is_d2r(version), data=data)
        else:
            self.magic = io.word(self.magic)
            self.count = io.word(self.count)
            if self.magic != ITEM_LIST_MAGIC:
                return

            self.items = []
            for _ in range(self.count):
                assert isinstance(io, BitReader)
                if io.bs.is_end():
                    break
                if io.bs.remaining() < 16 * 8:
                    break
                item = D2Item()
                start_offset = io.get_offset()
                try:
                    item.codec(io, version, not is_d2r(version), data=data)
                except ValueError:
                    io.seek_bits(start_offset)
                    continue
                self.items.append(item)

    def deserialize(
        self,
        bs: IBitStream,
        version: int,
        data: VersionData | GameData | GameDataResolver | None = None,
    ) -> None:
        self.codec(BitReader(bs), version, data=data)

    def serialize(
        self,
        bs: OBitStream,
        version: int,
        data: VersionData | GameData | GameDataResolver | None = None,
    ) -> None:
        self.codec(BitWriter(bs), version, data=data)

    def get_items(self) -> list[D2Item]:
        return self.items
