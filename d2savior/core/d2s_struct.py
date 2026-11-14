from enum import FlagBoundary, IntFlag
from typing import Any

from d2savior.core.bit_io import BitIO, BitReader, BitWriter
from d2savior.core.d2data import GameData, GameDataResolver
from d2savior.core.enums import (
    CLASS_NAMES,
    DEMON_MAGIC,
    GOLEM_MAGIC_1,
    GOLEM_MAGIC_2,
    ITEM_LIST_MAGIC,
    MERCENARY_MAGIC,
    PLAYER_STATS_BITS_COUNT,
    PLAYER_STATS_MAGIC,
)
from d2savior.core.ibitstream import IBitStream
from d2savior.core.item import D2Item, ItemList
from d2savior.core.obitstream import OBitStream


class CharStatus(IntFlag, boundary=FlagBoundary.KEEP):
    LADDER = 0x40
    EXPANSION = 0x20
    DIED = 0x08
    HARDCORE = 0x04


class QuestInfoData:
    def __init__(self) -> None:
        self.introduced_1 = 0
        self.act_1 = [0] * 6
        self.travel_1 = 0
        self.introduced_2 = 0
        self.act_2 = [0] * 6
        self.travel_2 = 0
        self.introduced_3 = 0
        self.act_3 = [0] * 6
        self.travel_3 = 0
        self.introduced_4 = 0
        self.act_4 = [0] * 3
        self.travel_4 = 0
        self.unknown1 = [0] * 3
        self.introduced_5 = 0
        self.unknown2 = [0] * 2
        self.act_5 = [0] * 6
        self.reset_stats = 0
        self.unknown3 = 0
        self.unknown4 = [0] * 6

    def codec(self, io: BitIO) -> None:
        self.introduced_1 = io.word(self.introduced_1)
        for i in range(6):
            self.act_1[i] = io.word(self.act_1[i])
        self.travel_1 = io.word(self.travel_1)
        self.introduced_2 = io.word(self.introduced_2)
        for i in range(6):
            self.act_2[i] = io.word(self.act_2[i])
        self.travel_2 = io.word(self.travel_2)
        self.introduced_3 = io.word(self.introduced_3)
        for i in range(6):
            self.act_3[i] = io.word(self.act_3[i])
        self.travel_3 = io.word(self.travel_3)
        self.introduced_4 = io.word(self.introduced_4)
        for i in range(3):
            self.act_4[i] = io.word(self.act_4[i])
        self.travel_4 = io.word(self.travel_4)
        for i in range(3):
            self.unknown1[i] = io.word(self.unknown1[i])
        self.introduced_5 = io.word(self.introduced_5)
        for i in range(2):
            self.unknown2[i] = io.word(self.unknown2[i])
        for i in range(6):
            self.act_5[i] = io.word(self.act_5[i])
        self.reset_stats = io.byte(self.reset_stats)
        self.unknown3 = io.byte(self.unknown3)
        for i in range(6):
            self.unknown4[i] = io.word(self.unknown4[i])

    def deserialize(self, bs: IBitStream) -> None:
        self.codec(BitReader(bs))

    def serialize(self, bs: OBitStream) -> None:
        self.codec(BitWriter(bs))


class QuestInfo:
    def __init__(self) -> None:
        self.magic = 0
        self.acts = 0
        self.size = 0
        self.qi_data = [QuestInfoData() for _ in range(3)]

    def codec(self, io: BitIO) -> None:
        self.magic = io.dword(self.magic)
        self.acts = io.dword(self.acts)
        self.size = io.word(self.size)
        for i in range(3):
            self.qi_data[i].codec(io)

    def deserialize(self, bs: IBitStream) -> None:
        self.codec(BitReader(bs))

    def serialize(self, bs: OBitStream) -> None:
        self.codec(BitWriter(bs))


class WaypointData:
    def __init__(self) -> None:
        self.unknown = 0
        self.waypoints = [0] * 5
        self.unknown2 = [0] * 17

    def codec(self, io: BitIO) -> None:
        self.unknown = io.word(self.unknown)
        for i in range(5):
            self.waypoints[i] = io.byte(self.waypoints[i])
        for i in range(17):
            self.unknown2[i] = io.byte(self.unknown2[i])

    def deserialize(self, bs: IBitStream) -> None:
        self.codec(BitReader(bs))

    def serialize(self, bs: OBitStream) -> None:
        self.codec(BitWriter(bs))


class Waypoints:
    def __init__(self) -> None:
        self.magic = 0
        self.unknown = 0
        self.size = 0
        self.wp = [WaypointData() for _ in range(3)]

    def codec(self, io: BitIO) -> None:
        self.magic = io.word(self.magic)
        self.unknown = io.dword(self.unknown)
        self.size = io.word(self.size)
        for i in range(3):
            self.wp[i].codec(io)

    def deserialize(self, bs: IBitStream) -> None:
        self.codec(BitReader(bs))

    def serialize(self, bs: OBitStream) -> None:
        self.codec(BitWriter(bs))


class PlayerStats:
    def __init__(self) -> None:
        self.magic = 0
        self.stat_values = [0] * 0x10
        self.end_flag = 0

    def codec(self, io: BitIO) -> None:
        self.magic = io.word(self.magic)
        if io.is_writing:
            for i in range(0x10):
                if self.stat_values[i] != 0:
                    io.bits(9, i)
                    io.bits(PLAYER_STATS_BITS_COUNT[i], self.stat_values[i])
            io.bits(9, 0x1FF)
            io.align_byte()
        else:
            if self.magic != PLAYER_STATS_MAGIC:
                return
            self.stat_values = [0] * 0x10
            while True:
                try:
                    self.end_flag = io.bits(9)
                    if self.end_flag >= 0x10:
                        break
                    self.stat_values[self.end_flag] = io.bits(
                        PLAYER_STATS_BITS_COUNT[self.end_flag]
                    )
                except ValueError:
                    break
            io.align_byte()

    def deserialize(self, bs: IBitStream) -> None:
        self.codec(BitReader(bs))

    def serialize(self, bs: OBitStream) -> None:
        self.codec(BitWriter(bs))

    @property
    def is_valid(self) -> bool:
        return self.magic == PLAYER_STATS_MAGIC

    @property
    def strength(self) -> int:
        return self.stat_values[0]

    @property
    def energy(self) -> int:
        return self.stat_values[1]

    @property
    def dexterity(self) -> int:
        return self.stat_values[2]

    @property
    def vitality(self) -> int:
        return self.stat_values[3]

    @property
    def stat_points_remaining(self) -> int:
        return self.stat_values[4]

    @property
    def skill_points_remaining(self) -> int:
        return self.stat_values[5]

    @property
    def current_life(self) -> int:
        return self.stat_values[6] >> 8

    @property
    def max_life(self) -> int:
        return self.stat_values[7] >> 8

    @property
    def current_mana(self) -> int:
        return self.stat_values[8] >> 8

    @property
    def max_mana(self) -> int:
        return self.stat_values[9] >> 8

    @property
    def current_stamina(self) -> int:
        return self.stat_values[0xA] >> 8

    @property
    def max_stamina(self) -> int:
        return self.stat_values[0xB] >> 8

    @property
    def level(self) -> int:
        return self.stat_values[0xC]

    @property
    def experience(self) -> int:
        return self.stat_values[0xD]

    @property
    def gold(self) -> int:
        return self.stat_values[0xE]

    @property
    def gold_stash(self) -> int:
        return self.stat_values[0xF]


class CharSkills:
    def __init__(self) -> None:
        self.magic = 0
        self.skill_levels = [0] * 30

    def codec(self, io: BitIO) -> None:
        self.magic = io.word(self.magic)
        for i in range(30):
            self.skill_levels[i] = io.byte(self.skill_levels[i])

    def deserialize(self, bs: IBitStream) -> None:
        self.codec(BitReader(bs))

    def serialize(self, bs: OBitStream) -> None:
        self.codec(BitWriter(bs))


class CorpseData:
    def __init__(self) -> None:
        self.unknown = b""
        self.items = None

    def codec(self, io: BitIO, version: int, data: Any = None) -> None:
        self.unknown = io.bytes(12, self.unknown)
        if io.is_reading:
            self.items = ItemList()
        if self.items:
            self.items.codec(io, version, data=data)

    def deserialize(self, bs: IBitStream, version: int, data: Any = None) -> None:
        self.codec(BitReader(bs), version, data=data)

    def serialize(self, bs: OBitStream, version: int, data: Any = None) -> None:
        self.codec(BitWriter(bs), version, data=data)


class Corpse:
    def __init__(self) -> None:
        self.magic = 0
        self.count = 0
        self.corpse_data = None

    def codec(self, io: BitIO, version: int, data: Any = None) -> None:
        self.magic = io.word(self.magic)
        self.count = io.word(self.count)
        if io.is_reading:
            if self.magic != ITEM_LIST_MAGIC:
                # Not CCorpse, seek back and return
                io.seek_back_bytes(4)
                return
            if self.count > 0:
                self.corpse_data = CorpseData()
                self.corpse_data.codec(io, version, data=data)
        else:
            if self.corpse_data:
                self.corpse_data.codec(io, version, data=data)

    def has_corpse(self) -> bool:
        return self.count > 0 and self.corpse_data is not None

    def deserialize(self, bs: IBitStream, version: int, data: Any = None) -> None:
        self.codec(BitReader(bs), version, data=data)

    def serialize(self, bs: OBitStream, version: int, data: Any = None) -> None:
        self.codec(BitWriter(bs), version, data=data)


class Mercenary:
    def __init__(self) -> None:
        self.magic = 0
        self.items = None

    def codec(self, io: BitIO, has_mercenary: bool, version: int, data: Any = None) -> None:
        self.magic = io.word(self.magic)
        if io.is_reading:
            if self.magic != MERCENARY_MAGIC:
                # Not CMercenary, seek back and return
                io.seek_back_bytes(2)
                return
            if has_mercenary:
                self.items = ItemList()
                self.items.codec(io, version, data=data)
        else:
            if has_mercenary and self.items:
                self.items.codec(io, version, data=data)

    def deserialize(
        self, bs: IBitStream, has_mercenary: bool, version: int, data: Any = None
    ) -> None:
        self.codec(BitReader(bs), has_mercenary, version, data=data)

    def serialize(
        self, bs: OBitStream, has_mercenary: bool, version: int, data: Any = None
    ) -> None:
        self.codec(BitWriter(bs), has_mercenary, version, data=data)


class Golem:
    def __init__(self) -> None:
        self.magic = 0
        self.has_golem = 0
        self.item = None

    def codec(self, io: BitIO, version: int, data: Any = None) -> None:
        self.magic = io.word(self.magic)
        self.has_golem = io.byte(self.has_golem)
        if io.is_reading:
            if self.magic not in [GOLEM_MAGIC_1, GOLEM_MAGIC_2]:
                io.seek_back_bytes(3)
                return
            if self.has_golem:
                self.item = D2Item()
                self.item.codec(io, version, False, data=data)
        else:
            if self.has_golem and self.item:
                self.item.codec(io, version, False, data=data)

    def deserialize(self, bs: IBitStream, version: int, data: Any = None) -> None:
        self.codec(BitReader(bs), version, data=data)

    def serialize(self, bs: OBitStream, version: int, data: Any = None) -> None:
        self.codec(BitWriter(bs), version, data=data)


class Demon:
    def __init__(self) -> None:
        self.section_version = 0
        self.magic = 0
        self.has_demon = False
        self.padding = 0
        self.demon_data = None
        self._raw_data = b""

    def codec(self, io: BitIO) -> None:
        if io.is_writing:
            if self._raw_data:
                io.bytes(len(self._raw_data), self._raw_data)
        else:
            if isinstance(io, BitReader):
                start_pos = io.bs.bytes_pos
                self.section_version = io.word(self.section_version)
                self.magic = io.word(self.magic)
                if self.magic != DEMON_MAGIC:
                    io.seek_back_bytes(4)
                    return
                has_demon_byte = io.byte()
                self.has_demon = has_demon_byte != 0
                self.padding = io.byte(self.padding)
                if self.has_demon:
                    self._read_demon_data(io)

                end_pos = io.bs.bytes_pos
                io.bs.bytes_pos = start_pos
                self._raw_data = io.bs.read_bytes(end_pos - start_pos)

    def _read_demon_data(self, io: BitIO) -> None:
        stat_data_size = io.word()
        _demon_type = io.word()
        _class_id = io.word() - 1
        _name_seed = io.word()
        _mon_flags = io.word()
        _num_stats = io.word()
        io.byte()
        io.byte()
        io.word()
        io.bytes(28)
        io.dword()
        io.dword()
        io.dword()
        io.dword()
        io.dword()
        io.bytes(16)
        io.bytes(10)
        io.bytes(2)
        if stat_data_size > 0:
            io.bytes(stat_data_size)

    def deserialize(self, bs: IBitStream) -> None:
        self.codec(BitReader(bs))

    def serialize(self, bs: OBitStream) -> None:
        self.codec(BitWriter(bs))


class D2SStruct:
    def __init__(self) -> None:
        self.magic = 0
        self.version = 0
        self.size = 0
        self.crc = 0
        self.weapon_set = 0
        self.name = b""
        self.char_flags: CharStatus | int = CharStatus(0)
        self.char_class = 0
        self.num_stats = 16
        self.num_skills = 30
        self.char_level = 0
        self.create_time = 0
        self.last_save_time = 0
        self.play_time = 0
        self.dw_time = 0
        self.skill_keys = [0] * 16
        self.left_skill_1 = 0
        self.right_skill_1 = 0
        self.left_skill_2 = 0
        self.right_skill_2 = 0
        self.outfit = b""
        self.colors = b""
        self.town = b""
        self.map_seed = 0
        self.merc_flags = 0
        self.merc_seed = 0
        self.merc_name_index = 0
        self.merc_hireling_id = 0
        self._merc_experience = 0
        self.preview_data = b""
        self.char_type = 0
        self.char_title = 0
        self.merc_control = 0
        self.merc_name = 0
        self.merc_type = 0
        self.merc_exp = 0
        self.merc_dead = 0
        self.merc_flags_low = 0
        self.merc_flags_high = 0
        self.preview_prefix = b""
        self.name_ptr = b""
        self.preview_suffix = 0
        self.num_stats_num_skills = 0
        self.padding1 = 0

        self.quests: QuestInfo | None = QuestInfo()
        self.waypoints = Waypoints()
        self.npc = b""
        self.player_stats = PlayerStats()
        self.skills = CharSkills()
        self.item_list = ItemList()
        self.corpse = Corpse()
        self.mercenary = Mercenary()
        self.golem = Golem()
        self.demon = Demon()
        self.game_version = 0
        self._data: Any = None

    @property
    def merc_experience(self) -> int:
        return self._merc_experience if self.version >= 0x69 else getattr(self, "merc_exp", 0)

    @merc_experience.setter
    def merc_experience(self, val: int) -> None:
        self._merc_experience = val

    def codec(self, io: BitIO, data: Any = None) -> None:
        self.magic = io.dword(self.magic)
        self.version = io.dword(self.version)
        self.size = io.dword(self.size)
        self.crc = io.dword(self.crc)
        self.weapon_set = io.dword(self.weapon_set)

        if isinstance(data, GameDataResolver):
            vd = data.game_data.for_version(self.version)
        elif isinstance(data, GameData):
            vd = data.for_version(self.version)
        else:
            vd = data or self._data
        self._data = vd

        if self.version >= 0x69:
            self._codec_v69(io, data=vd)
        else:
            self._codec_common(io, data=vd)

    def deserialize(self, bs: IBitStream, data: Any = None) -> None:
        self.codec(BitReader(bs), data=data)

    def _codec_hotkeys_and_appearance(self, io: BitIO) -> None:
        for i in range(16):
            self.skill_keys[i] = io.dword(self.skill_keys[i])

        self.left_skill_1 = io.dword(self.left_skill_1)
        self.right_skill_1 = io.dword(self.right_skill_1)
        self.left_skill_2 = io.dword(self.left_skill_2)
        self.right_skill_2 = io.dword(self.right_skill_2)

        self.outfit = io.bytes(16, self.outfit)
        self.colors = io.bytes(16, self.colors)
        self.town = io.bytes(3, self.town)

        self.map_seed = io.dword(self.map_seed)

    def _codec_sections(self, io: BitIO, data: Any = None) -> None:
        if self.quests is not None:
            self.quests.codec(io)

        self.waypoints.codec(io)

        self.npc = io.bytes(0x34, self.npc)

        self.player_stats.codec(io)

        self.skills.codec(io)

        self.item_list.codec(io, self.version, data=data)

        self.corpse.codec(io, self.version, data=data)

        if self.is_expansion():
            self.mercenary.codec(io, self.has_mercenary(), self.version, data=data)
            self.golem.codec(io, self.version, data=data)

        if self.version >= 0x69 and self.game_version >= 3:
            self.demon.codec(io)

        io.align_byte()

    def _codec_v69(self, io: BitIO, data: Any = None) -> None:
        self.char_flags = CharStatus(io.dword(int(self.char_flags)))
        if io.is_reading:
            self.char_type = self.char_flags
            self.char_title = (self.char_flags >> 8) & 0x1F

        self.char_class = io.byte(self.char_class)
        self.num_stats = io.byte(self.num_stats)
        self.num_skills = io.byte(self.num_skills)
        self.char_level = io.byte(self.char_level)
        self.create_time = io.dword(self.create_time)
        self.last_save_time = io.dword(self.last_save_time)
        self.play_time = io.dword(self.play_time)

        self._codec_hotkeys_and_appearance(io)

        self.merc_flags = io.dword(self.merc_flags)
        self.merc_seed = io.dword(self.merc_seed)
        self.merc_name_index = io.word(self.merc_name_index)
        self.merc_hireling_id = io.word(self.merc_hireling_id)
        self._merc_experience = io.dword(self._merc_experience)

        self.preview_data = io.bytes(228, self.preview_data)

        if io.is_reading:
            self.game_version = self.preview_data[73]
            name_offset = 0x7C
            name_bytes = self.preview_data[name_offset : name_offset + 96]
            self.name = name_bytes.split(b"\x00")[0]

        self._codec_sections(io, data=data)

    def _read_data_v69(self, bs: IBitStream, data: Any = None) -> None:
        self._codec_v69(BitReader(bs), data=data)

    def _codec_common(self, io: BitIO, data: Any = None) -> None:
        self.name = io.bytes(16, self.name)

        if io.is_reading:
            char_type = io.byte()
            self.char_flags = CharStatus(char_type)
            self.char_type = char_type
        else:
            io.byte(self.char_type)

        self.char_title = io.byte(self.char_title)
        self.num_stats_num_skills = io.word(self.num_stats_num_skills)
        self.char_class = io.byte(self.char_class)
        self.padding1 = io.word(self.padding1)
        self.char_level = io.byte(self.char_level)
        self.create_time = io.dword(self.create_time)
        self.dw_time = io.dword(self.dw_time)
        self.play_time = io.dword(self.play_time)

        self._codec_hotkeys_and_appearance(io)

        self.merc_flags_low = io.word(self.merc_flags_low)
        self.merc_dead = io.byte(self.merc_dead)
        self.merc_flags_high = io.byte(self.merc_flags_high)
        self.merc_control = io.dword(self.merc_control)
        self.merc_name = io.word(self.merc_name)
        self.merc_type = io.word(self.merc_type)
        self.merc_exp = io.dword(self.merc_exp)

        self.preview_prefix = io.bytes(0x4C, self.preview_prefix)
        self.name_ptr = io.bytes(0x40, self.name_ptr)
        self.preview_suffix = io.dword(self.preview_suffix)

        self._codec_sections(io, data=data)

    def _read_data_common(self, bs: IBitStream, data: Any = None) -> None:
        self._codec_common(BitReader(bs), data=data)

    def has_mercenary(self) -> bool:
        if self.version >= 0x69:
            return self.merc_seed != 0 or self.merc_name_index != 0 or self.merc_experience != 0
        elif self.version >= 0x61:
            return self.merc_control != 0
        else:
            return self.merc_name > 0

    @property
    def merc_name_id(self) -> int:
        return self.merc_name_index if self.version >= 0x69 else getattr(self, "merc_name", 0)

    @property
    def merc_type_id(self) -> int:
        return self.merc_hireling_id if self.version >= 0x69 else getattr(self, "merc_type", 0)

    @property
    def merc_is_dead(self) -> bool:
        return bool(getattr(self, "merc_dead", 0))

    def is_ladder(self) -> bool:
        return bool(self.char_flags & CharStatus.LADDER)

    def is_expansion(self) -> bool:
        if self.version >= 0x69:
            return self.game_version > 1
        if self.char_flags & CharStatus.EXPANSION:
            return True
        return bool(self.quests and self.quests.acts >= 5)

    def is_warlock_expansion(self) -> bool:
        return bool(self.char_flags & CharStatus.EXPANSION)

    def is_died_before(self) -> bool:
        return bool(self.char_flags & CharStatus.DIED)

    def is_hardcore(self) -> bool:
        return bool(self.char_flags & CharStatus.HARDCORE)

    def get_char_class_name(self) -> str:
        if 0 <= self.char_class < len(CLASS_NAMES):
            return CLASS_NAMES[self.char_class]
        return "Unknown"

    def get_char_name(self) -> str:
        if self.version >= 0x69:
            name_data = self.name
        elif self.version >= 0x62:
            name_data = self.name_ptr
        else:
            name_data = self.name
        null_pos = name_data.find(b"\x00")
        name_bytes = name_data[:null_pos] if null_pos != -1 else name_data
        if self.version >= 0x62:
            name = name_bytes.decode("utf-8", errors="replace")
        else:
            name = name_bytes.decode("ascii", errors="replace")
        return name

    def get_char_title(self) -> int:
        return self.char_title

    def get_char_title_name(self) -> str:
        title = self.get_char_title()
        title_names = {
            0: "None",
            5: "Slayer",
            10: "Champion",
            15: "Matriarch/Patriarch",
        }
        return title_names.get(title, f"Unknown({title})")

    def serialize(self, bs: OBitStream, data: Any = None) -> None:
        self.codec(BitWriter(bs), data=data)

    def _serialize_v69(self, bs: OBitStream, data: Any = None) -> None:
        self._codec_v69(BitWriter(bs), data=data)

    def _serialize_common(self, bs: OBitStream, data: Any = None) -> None:
        self._codec_common(BitWriter(bs), data=data)

    def calculate_checksum(self, data: bytes | bytearray) -> int:
        checksum = 0
        for i, b in enumerate(data):
            if 0x0C <= i < 0x10:
                b = 0
            checksum = ((checksum << 1) | (checksum >> 31)) + b
            checksum &= 0xFFFFFFFF
        return checksum

    def update_checksum(self, data: bytes) -> bytes:
        buf = bytearray(data)
        checksum = self.calculate_checksum(buf)
        buf[0x0C:0x10] = checksum.to_bytes(4, "little")
        return bytes(buf)
