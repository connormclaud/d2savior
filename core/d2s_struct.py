from enum import FlagBoundary, IntFlag

from core.enums import (
    DEMON_MAGIC,
    GOLEM_MAGIC_1,
    GOLEM_MAGIC_2,
    ITEM_LIST_MAGIC,
    MERCENARY_MAGIC,
    PLAYER_STATS_BITS_COUNT,
    PLAYER_STATS_MAGIC,
)
from core.item import D2Item, ItemList, init_item_data


class CharStatus(IntFlag, boundary=FlagBoundary.KEEP):
    LADDER = 0x40
    EXPANSION = 0x20
    DIED = 0x08
    HARDCORE = 0x04


class QuestInfoData:
    def __init__(self):
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

    def deserialize(self, bs):
        self.introduced_1 = bs.read_word()
        for i in range(6):
            self.act_1[i] = bs.read_word()
        self.travel_1 = bs.read_word()
        self.introduced_2 = bs.read_word()
        for i in range(6):
            self.act_2[i] = bs.read_word()
        self.travel_2 = bs.read_word()
        self.introduced_3 = bs.read_word()
        for i in range(6):
            self.act_3[i] = bs.read_word()
        self.travel_3 = bs.read_word()
        self.introduced_4 = bs.read_word()
        for i in range(3):
            self.act_4[i] = bs.read_word()
        self.travel_4 = bs.read_word()
        for i in range(3):
            self.unknown1[i] = bs.read_word()
        self.introduced_5 = bs.read_word()
        for i in range(2):
            self.unknown2[i] = bs.read_word()
        for i in range(6):
            self.act_5[i] = bs.read_word()
        self.reset_stats = bs.read_byte()
        self.unknown3 = bs.read_byte()
        for i in range(6):
            self.unknown4[i] = bs.read_word()

    def serialize(self, bs):
        bs.write_word(self.introduced_1)
        for i in range(6):
            bs.write_word(self.act_1[i])
        bs.write_word(self.travel_1)
        bs.write_word(self.introduced_2)
        for i in range(6):
            bs.write_word(self.act_2[i])
        bs.write_word(self.travel_2)
        bs.write_word(self.introduced_3)
        for i in range(6):
            bs.write_word(self.act_3[i])
        bs.write_word(self.travel_3)
        bs.write_word(self.introduced_4)
        for i in range(3):
            bs.write_word(self.act_4[i])
        bs.write_word(self.travel_4)
        for i in range(3):
            bs.write_word(self.unknown1[i])
        bs.write_word(self.introduced_5)
        for i in range(2):
            bs.write_word(self.unknown2[i])
        for i in range(6):
            bs.write_word(self.act_5[i])
        bs.write_byte(self.reset_stats)
        bs.write_byte(self.unknown3)
        for i in range(6):
            bs.write_word(self.unknown4[i])


class QuestInfo:
    def __init__(self):
        self.magic = 0
        self.acts = 0
        self.size = 0
        self.qi_data = [QuestInfoData() for _ in range(3)]

    def deserialize(self, bs):
        self.magic = bs.read_dword()
        self.acts = bs.read_dword()
        self.size = bs.read_word()
        for i in range(3):
            self.qi_data[i].deserialize(bs)

    def serialize(self, bs):
        bs.write_dword(self.magic)
        bs.write_dword(self.acts)
        bs.write_word(self.size)
        for i in range(3):
            self.qi_data[i].serialize(bs)


class WaypointData:
    def __init__(self):
        self.unknown = 0
        self.waypoints = [0] * 5
        self.unknown2 = [0] * 17

    def deserialize(self, bs):
        self.unknown = bs.read_word()
        for i in range(5):
            self.waypoints[i] = bs.read_byte()
        for i in range(17):
            self.unknown2[i] = bs.read_byte()

    def serialize(self, bs):
        bs.write_word(self.unknown)
        for i in range(5):
            bs.write_byte(self.waypoints[i])
        for i in range(17):
            bs.write_byte(self.unknown2[i])


class Waypoints:
    def __init__(self):
        self.magic = 0
        self.unknown = 0
        self.size = 0
        self.wp = [WaypointData() for _ in range(3)]

    def deserialize(self, bs):
        self.magic = bs.read_word()
        self.unknown = bs.read_dword()
        self.size = bs.read_word()
        for i in range(3):
            self.wp[i].deserialize(bs)

    def serialize(self, bs):
        bs.write_word(self.magic)
        bs.write_dword(self.unknown)
        bs.write_word(self.size)
        for i in range(3):
            self.wp[i].serialize(bs)


class PlayerStats:
    def __init__(self):
        self.magic = 0
        self.stat_values = [0] * 0x10
        self.end_flag = 0

    def deserialize(self, bs):
        self.magic = bs.read_word()
        if self.magic != PLAYER_STATS_MAGIC:
            return
        self.stat_values = [0] * 0x10
        while True:
            try:
                self.end_flag = bs.read_bits(9)
                if self.end_flag >= 0x10:
                    break
                self.stat_values[self.end_flag] = bs.read_bits(
                    PLAYER_STATS_BITS_COUNT[self.end_flag]
                )
            except ValueError:
                break
        bs.align_byte()

    def serialize(self, bs):
        bs.write_word(self.magic)

        for i in range(0x10):
            if self.stat_values[i] != 0:
                bs.write_bits(9, i)
                bs.write_bits(PLAYER_STATS_BITS_COUNT[i], self.stat_values[i])

        bs.write_bits(9, 0x1FF)
        bs.align_byte()

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
    def __init__(self):
        self.magic = 0
        self.skill_levels = [0] * 30

    def deserialize(self, bs):
        self.magic = bs.read_word()
        for i in range(30):
            self.skill_levels[i] = bs.read_byte()

    def serialize(self, bs):
        bs.write_word(self.magic)
        for i in range(30):
            bs.write_byte(self.skill_levels[i])


class CorpseData:
    def __init__(self):
        self.unknown = b""
        self.items = None

    def deserialize(self, bs, version):
        self.unknown = bs.data[bs.bytes_pos : bs.bytes_pos + 12]
        bs.bytes_pos += 12
        self.items = ItemList()
        self.items.deserialize(bs, version)

    def serialize(self, bs, version):
        bs.write_bytes(self.unknown)
        if self.items:
            self.items.serialize(bs, version)


class Corpse:
    def __init__(self):
        self.magic = 0
        self.count = 0
        self.corpse_data = None

    def deserialize(self, bs, version):
        self.magic = bs.read_word()
        self.count = bs.read_word()
        if self.magic != ITEM_LIST_MAGIC:
            # 不是CCorpse，回退并返回
            bs.seek_back_bytes(4)
            return
        if self.count > 0:
            self.corpse_data = CorpseData()
            self.corpse_data.deserialize(bs, version)

    def has_corpse(self):
        return self.count > 0 and self.corpse_data is not None

    def serialize(self, bs, version):
        bs.write_word(self.magic)
        bs.write_word(self.count)
        if self.corpse_data:
            self.corpse_data.serialize(bs, version)


class Mercenary:
    def __init__(self):
        self.magic = 0
        self.items = None

    def deserialize(self, bs, has_mercenary, version):
        self.magic = bs.read_word()
        if self.magic != MERCENARY_MAGIC:
            # 不是CMercenary，回退并返回
            bs.seek_back_bytes(2)
            return
        if has_mercenary:
            self.items = ItemList()
            self.items.deserialize(bs, version)

    def serialize(self, bs, has_mercenary, version):
        bs.write_word(self.magic)
        if has_mercenary and self.items:
            self.items.serialize(bs, version)


class Golem:
    def __init__(self):
        self.magic = 0
        self.has_golem = 0
        self.item = None

    def deserialize(self, bs, version):
        self.magic = bs.read_word()
        self.has_golem = bs.read_byte()
        if self.magic not in [GOLEM_MAGIC_1, GOLEM_MAGIC_2]:
            bs.seek_back_bytes(3)
            return
        if self.has_golem:
            self.item = D2Item()
            self.item.deserialize(bs, version)

    def serialize(self, bs, version):
        bs.write_word(self.magic)
        bs.write_byte(self.has_golem)
        if self.has_golem and self.item:
            self.item.serialize(bs, version, False)


class Demon:
    def __init__(self):
        self.section_version = 0
        self.magic = 0
        self.has_demon = False
        self.padding = 0
        self.demon_data = None
        self._raw_data = b""

    def deserialize(self, bs):
        start_pos = bs.bytes_pos
        self.section_version = bs.read_word()
        self.magic = bs.read_word()
        if self.magic != DEMON_MAGIC:
            bs.seek_back_bytes(4)
            return
        has_demon_byte = bs.read_byte()
        self.has_demon = has_demon_byte != 0
        self.padding = bs.read_byte()
        if self.has_demon:
            self._read_demon_data(bs)

        end_pos = bs.bytes_pos
        bs.bytes_pos = start_pos
        self._raw_data = bs.data[start_pos:end_pos]
        bs.bytes_pos = end_pos

    def _read_demon_data(self, bs):
        stat_data_size = bs.read_word()
        demon_type = bs.read_word()
        class_id = bs.read_word() - 1
        name_seed = bs.read_word()
        mon_flags = bs.read_word()
        num_stats = bs.read_word()
        bs.read_byte()
        bs.read_byte()
        bs.read_word()
        bs.data[bs.bytes_pos : bs.bytes_pos + 28]
        bs.bytes_pos += 28
        bs.read_dword()
        bs.read_dword()
        bs.read_dword()
        bs.read_dword()
        bs.read_dword()
        bs.data[bs.bytes_pos : bs.bytes_pos + 16]
        bs.bytes_pos += 16
        bs.data[bs.bytes_pos : bs.bytes_pos + 10]
        bs.bytes_pos += 10
        bs.data[bs.bytes_pos : bs.bytes_pos + 2]
        bs.bytes_pos += 2
        if stat_data_size > 0:
            bs.data[bs.bytes_pos : bs.bytes_pos + stat_data_size]
            bs.bytes_pos += stat_data_size

    def serialize(self, bs):
        if self._raw_data:
            bs.write_bytes(self._raw_data)


class D2SStruct:
    def __init__(self):
        self.magic = 0
        self.version = 0
        self.size = 0
        self.crc = 0
        self.weapon_set = 0
        self.name = b""
        self.char_flags: CharStatus = CharStatus(0)
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

        self.quests = QuestInfo()
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

    @property
    def merc_experience(self) -> int:
        return self._merc_experience if self.version >= 0x69 else getattr(self, "merc_exp", 0)

    @merc_experience.setter
    def merc_experience(self, val: int):
        self._merc_experience = val

    def deserialize(self, bs):
        self.magic = bs.read_dword()
        self.version = bs.read_dword()
        self.size = bs.read_dword()
        self.crc = bs.read_dword()
        self.weapon_set = bs.read_dword()

        if self.version >= 0x69:
            self._read_data_v69(bs)
        else:
            self._read_data_common(bs)

    def _read_data_v69(self, bs):
        self.char_flags = CharStatus(bs.read_dword())
        self.char_type = self.char_flags
        self.char_title = (self.char_flags >> 8) & 0x1F
        self.char_class = bs.read_byte()
        self.num_stats = bs.read_byte()
        self.num_skills = bs.read_byte()
        self.char_level = bs.read_byte()
        self.create_time = bs.read_dword()
        self.last_save_time = bs.read_dword()
        self.play_time = bs.read_dword()

        for i in range(16):
            self.skill_keys[i] = bs.read_dword()

        self.left_skill_1 = bs.read_dword()
        self.right_skill_1 = bs.read_dword()
        self.left_skill_2 = bs.read_dword()
        self.right_skill_2 = bs.read_dword()

        self.outfit = bs.data[bs.bytes_pos : bs.bytes_pos + 16]
        bs.bytes_pos += 16
        self.colors = bs.data[bs.bytes_pos : bs.bytes_pos + 16]
        bs.bytes_pos += 16

        self.town = bs.data[bs.bytes_pos : bs.bytes_pos + 3]
        bs.bytes_pos += 3

        self.map_seed = bs.read_dword()

        self.merc_flags = bs.read_dword()
        self.merc_seed = bs.read_dword()
        self.merc_name_index = bs.read_word()
        self.merc_hireling_id = bs.read_word()
        self._merc_experience = bs.read_dword()

        preview_size = 228
        self.preview_data = bs.data[bs.bytes_pos : bs.bytes_pos + preview_size]
        bs.bytes_pos += preview_size

        self.game_version = self.preview_data[73]

        name_offset = 0x7C
        name_bytes = self.preview_data[name_offset : name_offset + 96]
        self.name = name_bytes.split(b"\x00")[0]

        self.quests.deserialize(bs)

        self.waypoints.deserialize(bs)

        self.npc = bs.data[bs.bytes_pos : bs.bytes_pos + 0x34]
        bs.bytes_pos += 0x34

        self.player_stats.deserialize(bs)

        self.skills.deserialize(bs)

        self.item_list.deserialize(bs, self.version)

        self.corpse.deserialize(bs, self.version)

        if self.is_expansion():
            self.mercenary.deserialize(bs, self.has_mercenary(), self.version)
            self.golem.deserialize(bs, self.version)

        if self.version >= 0x69 and self.game_version >= 3:
            self.demon.deserialize(bs)

        bs.align_byte()

    def _read_data_common(self, bs):
        self.name = bs.data[bs.bytes_pos : bs.bytes_pos + 16]
        bs.bytes_pos += 16

        char_type = bs.read_byte()
        self.char_flags = CharStatus(char_type)
        self.char_type = char_type
        self.char_title = bs.read_byte()
        self.num_stats_num_skills = bs.read_word()
        self.char_class = bs.read_byte()
        self.padding1 = bs.read_word()
        self.char_level = bs.read_byte()
        self.create_time = bs.read_dword()
        self.dw_time = bs.read_dword()
        self.play_time = bs.read_dword()

        for i in range(16):
            self.skill_keys[i] = bs.read_dword()

        self.left_skill_1 = bs.read_dword()
        self.right_skill_1 = bs.read_dword()
        self.left_skill_2 = bs.read_dword()
        self.right_skill_2 = bs.read_dword()

        # 读取outfit和colors
        self.outfit = bs.data[bs.bytes_pos : bs.bytes_pos + 16]
        bs.bytes_pos += 16
        self.colors = bs.data[bs.bytes_pos : bs.bytes_pos + 16]
        bs.bytes_pos += 16

        # 读取Town
        self.town = bs.data[bs.bytes_pos : bs.bytes_pos + 3]
        bs.bytes_pos += 3

        self.map_seed = bs.read_dword()
        self.merc_flags_low = bs.read_word()
        self.merc_dead = bs.read_byte()
        self.merc_flags_high = bs.read_byte()
        self.merc_control = bs.read_dword()
        self.merc_name = bs.read_word()
        self.merc_type = bs.read_word()
        self.merc_exp = bs.read_dword()

        self.preview_prefix = bs.data[bs.bytes_pos : bs.bytes_pos + 0x4C]
        bs.bytes_pos += 0x4C

        self.name_ptr = bs.data[bs.bytes_pos : bs.bytes_pos + 0x40]
        bs.bytes_pos += 0x40

        self.preview_suffix = bs.read_dword()

        self.quests.deserialize(bs)

        # 读取传送点信息
        self.waypoints.deserialize(bs)

        # 读取NPC信息
        self.npc = bs.data[bs.bytes_pos : bs.bytes_pos + 0x34]
        bs.bytes_pos += 0x34

        # 读取人物属性
        self.player_stats.deserialize(bs)

        # 读取技能信息
        self.skills.deserialize(bs)

        # 读取物品列表
        self.item_list.deserialize(bs, self.version)

        # 读取尸体
        self.corpse.deserialize(bs, self.version)

        # 如果是扩展版，读取雇佣兵和石魔
        if self.is_expansion():
            self.mercenary.deserialize(bs, self.has_mercenary(), self.version)
            self.golem.deserialize(bs, self.version)

        bs.align_byte()

    def has_mercenary(self):
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

    def is_ladder(self):
        return bool(self.char_flags & CharStatus.LADDER)

    def is_expansion(self):
        if self.version >= 0x69:
            return self.game_version > 1
        if self.char_flags & CharStatus.EXPANSION:
            return True
        return bool(self.quests and self.quests.acts >= 5)

    def is_warlock_expansion(self):
        return bool(self.char_flags & CharStatus.EXPANSION)

    def is_died_before(self):
        return bool(self.char_flags & CharStatus.DIED)

    def is_hardcore(self):
        return bool(self.char_flags & CharStatus.HARDCORE)

    def get_char_class_name(self):
        class_names = [
            "Amazon",
            "Sorceress",
            "Necromancer",
            "Paladin",
            "Barbarian",
            "Druid",
            "Assassin",
            "Warlock",
        ]
        if 0 <= self.char_class < len(class_names):
            return class_names[self.char_class]
        return "Unknown"

    def get_char_name(self):
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

    def get_char_title(self):
        return self.char_title

    def get_char_title_name(self):
        title = self.get_char_title()
        title_names = {
            0: "None",
            5: "Slayer",
            10: "Champion",
            15: "Matriarch/Patriarch",
        }
        return title_names.get(title, f"Unknown({title})")

    def serialize(self, bs):
        bs.write_dword(self.magic)
        bs.write_dword(self.version)
        bs.write_dword(self.size)
        bs.write_dword(self.crc)
        bs.write_dword(self.weapon_set)

        if self.version >= 0x69:
            self._serialize_v69(bs)
        else:
            self._serialize_common(bs)

    def _serialize_v69(self, bs):
        bs.write_dword(self.char_flags)
        bs.write_byte(self.char_class)
        bs.write_byte(self.num_stats)
        bs.write_byte(self.num_skills)
        bs.write_byte(self.char_level)
        bs.write_dword(self.create_time)
        bs.write_dword(self.last_save_time)
        bs.write_dword(self.play_time)

        for i in range(16):
            bs.write_dword(self.skill_keys[i])

        bs.write_dword(self.left_skill_1)
        bs.write_dword(self.right_skill_1)
        bs.write_dword(self.left_skill_2)
        bs.write_dword(self.right_skill_2)

        bs.write_bytes(self.outfit)
        bs.write_bytes(self.colors)
        bs.write_bytes(self.town)

        bs.write_dword(self.map_seed)

        bs.write_dword(self.merc_flags)
        bs.write_dword(self.merc_seed)
        bs.write_word(self.merc_name_index)
        bs.write_word(self.merc_hireling_id)
        bs.write_dword(self._merc_experience)

        bs.write_bytes(self.preview_data)

        self.quests.serialize(bs)
        self.waypoints.serialize(bs)
        bs.write_bytes(self.npc)
        self.player_stats.serialize(bs)
        self.skills.serialize(bs)
        self.item_list.serialize(bs, self.version)
        self.corpse.serialize(bs, self.version)

        if self.is_expansion():
            self.mercenary.serialize(bs, self.has_mercenary(), self.version)
            self.golem.serialize(bs, self.version)

        if self.version >= 0x69 and self.game_version >= 3:
            self.demon.serialize(bs)

        bs.align_byte()

    def _serialize_common(self, bs):
        bs.write_bytes(self.name)
        bs.write_byte(self.char_type)
        bs.write_byte(self.char_title)
        bs.write_word(self.num_stats_num_skills)
        bs.write_byte(self.char_class)
        bs.write_word(self.padding1)
        bs.write_byte(self.char_level)
        bs.write_dword(self.create_time)
        bs.write_dword(self.dw_time)
        bs.write_dword(self.play_time)

        for i in range(16):
            bs.write_dword(self.skill_keys[i])

        bs.write_dword(self.left_skill_1)
        bs.write_dword(self.right_skill_1)
        bs.write_dword(self.left_skill_2)
        bs.write_dword(self.right_skill_2)

        bs.write_bytes(self.outfit)
        bs.write_bytes(self.colors)
        bs.write_bytes(self.town)

        bs.write_dword(self.map_seed)
        bs.write_word(self.merc_flags_low)
        bs.write_byte(self.merc_dead)
        bs.write_byte(self.merc_flags_high)
        bs.write_dword(self.merc_control)
        bs.write_word(self.merc_name)
        bs.write_word(self.merc_type)
        bs.write_dword(self.merc_exp)

        bs.write_bytes(self.preview_prefix)
        bs.write_bytes(self.name_ptr)
        bs.write_dword(self.preview_suffix)

        self.quests.serialize(bs)
        self.waypoints.serialize(bs)
        bs.write_bytes(self.npc)
        self.player_stats.serialize(bs)
        self.skills.serialize(bs)
        self.item_list.serialize(bs, self.version)
        self.corpse.serialize(bs, self.version)

        if self.is_expansion():
            self.mercenary.serialize(bs, self.has_mercenary(), self.version)
            self.golem.serialize(bs, self.version)

        bs.align_byte()

    def calculate_checksum(self, data: bytes) -> int:
        checksum = 0
        for i, b in enumerate(data):
            if 0x0C <= i < 0x10:
                b = 0
            checksum = ((checksum << 1) | (checksum >> 31)) + b
            checksum &= 0xFFFFFFFF
        return checksum

    def update_checksum(self, data: bytes) -> bytes:
        data = bytearray(data)
        checksum = self.calculate_checksum(data)
        data[0x0C:0x10] = checksum.to_bytes(4, "little")
        return bytes(data)
