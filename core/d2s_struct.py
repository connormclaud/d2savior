from core.item import D2Item, ItemList, init_item_data
from core.enums import (
    PLAYER_STATS_MAGIC, ITEM_LIST_MAGIC, MERCENARY_MAGIC,
    GOLEM_MAGIC_1, GOLEM_MAGIC_2, DEMON_MAGIC, PLAYER_STATS_BITS_COUNT
)

class QuestInfoData:
    def __init__(self):
        self.wIntroduced1 = 0
        self.wActI = [0] * 6
        self.travel_1 = 0
        self.wIntroduced2 = 0
        self.wActII = [0] * 6
        self.travel_2 = 0
        self.wIntroduced3 = 0
        self.wActIII = [0] * 6
        self.travel_3 = 0
        self.wIntroduced4 = 0
        self.wActIV = [0] * 3
        self.travel_4 = 0
        self.unknown1 = [0] * 3
        self.wIntroduced5 = 0
        self.unknown2 = [0] * 2
        self.wActV = [0] * 6
        self.bResetStats = 0
        self.unknown3 = 0
        self.unknown4 = [0] * 6
    
    def deserialize(self, bs):
        self.wIntroduced1 = bs.read_word()
        for i in range(6):
            self.wActI[i] = bs.read_word()
        self.travel_1 = bs.read_word()
        self.wIntroduced2 = bs.read_word()
        for i in range(6):
            self.wActII[i] = bs.read_word()
        self.travel_2 = bs.read_word()
        self.wIntroduced3 = bs.read_word()
        for i in range(6):
            self.wActIII[i] = bs.read_word()
        self.travel_3 = bs.read_word()
        self.wIntroduced4 = bs.read_word()
        for i in range(3):
            self.wActIV[i] = bs.read_word()
        self.travel_4 = bs.read_word()
        for i in range(3):
            self.unknown1[i] = bs.read_word()
        self.wIntroduced5 = bs.read_word()
        for i in range(2):
            self.unknown2[i] = bs.read_word()
        for i in range(6):
            self.wActV[i] = bs.read_word()
        self.bResetStats = bs.read_byte()
        self.unknown3 = bs.read_byte()
        for i in range(6):
            self.unknown4[i] = bs.read_word()
    
    def serialize(self, bs):
        bs.write_word(self.wIntroduced1)
        for i in range(6):
            bs.write_word(self.wActI[i])
        bs.write_word(self.travel_1)
        bs.write_word(self.wIntroduced2)
        for i in range(6):
            bs.write_word(self.wActII[i])
        bs.write_word(self.travel_2)
        bs.write_word(self.wIntroduced3)
        for i in range(6):
            bs.write_word(self.wActIII[i])
        bs.write_word(self.travel_3)
        bs.write_word(self.wIntroduced4)
        for i in range(3):
            bs.write_word(self.wActIV[i])
        bs.write_word(self.travel_4)
        for i in range(3):
            bs.write_word(self.unknown1[i])
        bs.write_word(self.wIntroduced5)
        for i in range(2):
            bs.write_word(self.unknown2[i])
        for i in range(6):
            bs.write_word(self.wActV[i])
        bs.write_byte(self.bResetStats)
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
        self.Waypoints = [0] * 5
        self.unknown2 = [0] * 17
    
    def deserialize(self, bs):
        self.unknown = bs.read_word()
        for i in range(5):
            self.Waypoints[i] = bs.read_byte()
        for i in range(17):
            self.unknown2[i] = bs.read_byte()
    
    def serialize(self, bs):
        bs.write_word(self.unknown)
        for i in range(5):
            bs.write_byte(self.Waypoints[i])
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
        self.iEnd = 0
    
    def deserialize(self, bs):
        self.magic = bs.read_word()
        if self.magic != PLAYER_STATS_MAGIC:
            return
        self.stat_values = [0] * 0x10
        while True:
            try:
                self.iEnd = bs.read_bits(9)
                if self.iEnd >= 0x10:
                    break
                self.stat_values[self.iEnd] = bs.read_bits(PLAYER_STATS_BITS_COUNT[self.iEnd])
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
        self.wMagic = 0
        self.bSkillLevel = [0] * 30
    
    def deserialize(self, bs):
        self.wMagic = bs.read_word()
        for i in range(30):
            self.bSkillLevel[i] = bs.read_byte()
    
    def serialize(self, bs):
        bs.write_word(self.wMagic)
        for i in range(30):
            bs.write_byte(self.bSkillLevel[i])

class CorpseData:
    def __init__(self):
        self.unknown = b''
        self.stItems = None
    
    def deserialize(self, bs, version):
        self.unknown = bs.data[bs.bytes_pos:bs.bytes_pos+12]
        bs.bytes_pos += 12
        self.stItems = ItemList()
        self.stItems.deserialize(bs, version)
    
    def serialize(self, bs, version):
        bs.write_bytes(self.unknown)
        if self.stItems:
            self.stItems.serialize(bs, version)

class Corpse:
    def __init__(self):
        self.wMagic = 0
        self.wCount = 0
        self.pCorpseData = None
    
    def deserialize(self, bs, version):
        self.wMagic = bs.read_word()
        self.wCount = bs.read_word()
        if self.wMagic != ITEM_LIST_MAGIC:
            # 不是CCorpse，回退并返回
            bs.seek_back_bytes(4)
            return
        if self.wCount > 0:
            self.pCorpseData = CorpseData()
            self.pCorpseData.deserialize(bs, version)
    
    def has_corpse(self):
        return self.wCount > 0 and self.pCorpseData is not None
    
    def serialize(self, bs, version):
        bs.write_word(self.wMagic)
        bs.write_word(self.wCount)
        if self.pCorpseData:
            self.pCorpseData.serialize(bs, version)

class Mercenary:
    def __init__(self):
        self.wMagic = 0
        self.stItems = None
    
    def deserialize(self, bs, has_mercenary, version):
        self.wMagic = bs.read_word()
        if self.wMagic != MERCENARY_MAGIC:
            # 不是CMercenary，回退并返回
            bs.seek_back_bytes(2)
            return
        if has_mercenary:
            self.stItems = ItemList()
            self.stItems.deserialize(bs, version)
    
    def serialize(self, bs, has_mercenary, version):
        bs.write_word(self.wMagic)
        if has_mercenary and self.stItems:
            self.stItems.serialize(bs, version)

class Golem:
    def __init__(self):
        self.wMagic = 0
        self.bHasGolem = 0
        self.pItem = None
    
    def deserialize(self, bs, version):
        self.wMagic = bs.read_word()
        self.bHasGolem = bs.read_byte()
        if self.wMagic not in [GOLEM_MAGIC_1, GOLEM_MAGIC_2]:
            bs.seek_back_bytes(3)
            return
        if self.bHasGolem:
            self.pItem = D2Item()
            self.pItem.deserialize(bs, version)
    
    def serialize(self, bs, version):
        bs.write_word(self.wMagic)
        bs.write_byte(self.bHasGolem)
        if self.bHasGolem and self.pItem:
            self.pItem.serialize(bs, version, False)

class Demon:
    def __init__(self):
        self.sectionVersion = 0
        self.wMagic = 0
        self.hasDemon = False
        self.padding = 0
        self.demonData = None
        self._raw_data = b''
    
    def deserialize(self, bs):
        start_pos = bs.bytes_pos
        self.sectionVersion = bs.read_word()
        self.wMagic = bs.read_word()
        if self.wMagic != DEMON_MAGIC:
            bs.seek_back_bytes(4)
            return
        has_demon_byte = bs.read_byte()
        self.hasDemon = has_demon_byte != 0
        self.padding = bs.read_byte()
        if self.hasDemon:
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
        bs.data[bs.bytes_pos:bs.bytes_pos+28]
        bs.bytes_pos += 28
        bs.read_dword()
        bs.read_dword()
        bs.read_dword()
        bs.read_dword()
        bs.read_dword()
        bs.data[bs.bytes_pos:bs.bytes_pos+16]
        bs.bytes_pos += 16
        bs.data[bs.bytes_pos:bs.bytes_pos+10]
        bs.bytes_pos += 10
        bs.data[bs.bytes_pos:bs.bytes_pos+2]
        bs.bytes_pos += 2
        if stat_data_size > 0:
            bs.data[bs.bytes_pos:bs.bytes_pos+stat_data_size]
            bs.bytes_pos += stat_data_size
    
    def serialize(self, bs):
        if self._raw_data:
            bs.write_bytes(self._raw_data)

class D2SStruct:
    def __init__(self):
        self.magic = 0
        self.version = 0
        self.dwSize = 0
        self.dwCRC = 0
        self.dwWeaponSet = 0
        self.Name = b''
        self.charFlags = 0
        self.charClass = 0
        self.numStats = 16
        self.numSkills = 30
        self.charLevel = 0
        self.createTime = 0
        self.lastSaveTime = 0
        self.playTime = 0
        self.dwSkillKey = [0] * 16
        self.dwLeftSkill1 = 0
        self.dwRightSkill1 = 0
        self.dwLeftSkill2 = 0
        self.dwRightSkill2 = 0
        self.outfit = b''
        self.colors = b''
        self.Town = b''
        self.dwMapSeed = 0
        self.mercFlags = 0
        self.mercSeed = 0
        self.mercNameIndex = 0
        self.mercHirelingId = 0
        self.mercExperience = 0
        self.previewData = b''
        self.charType = 0
        self.charTitle = 0
        self.dwMercControl = 0
        self.wMercName = 0
        self.wMercType = 0
        self.dwMercExp = 0
        
        self.quests = QuestInfo()
        self.waypoints = Waypoints()
        self.NPC = b''
        self.player_stats = PlayerStats()
        self.skills = CharSkills()
        self.item_list = ItemList()
        self.corpse = Corpse()
        self.mercenary = Mercenary()
        self.golem = Golem()
        self.demon = Demon()
        self.gameVersion = 0

    # Transitional property aliases
    @property
    def dwMajic(self) -> int: return self.magic
    @dwMajic.setter
    def dwMajic(self, v: int): self.magic = v

    @property
    def dwVersion(self) -> int: return self.version
    @dwVersion.setter
    def dwVersion(self, v: int): self.version = v

    @property
    def QuestInfo(self) -> QuestInfo: return self.quests
    @QuestInfo.setter
    def QuestInfo(self, v: QuestInfo): self.quests = v

    @property
    def Waypoints(self) -> Waypoints: return self.waypoints
    @Waypoints.setter
    def Waypoints(self, v: Waypoints): self.waypoints = v

    @property
    def PlayerStats(self) -> PlayerStats: return self.player_stats
    @PlayerStats.setter
    def PlayerStats(self, v: PlayerStats): self.player_stats = v

    @property
    def Skills(self) -> CharSkills: return self.skills
    @Skills.setter
    def Skills(self, v: CharSkills): self.skills = v

    @property
    def ItemList(self) -> ItemList: return self.item_list
    @ItemList.setter
    def ItemList(self, v: ItemList): self.item_list = v

    @property
    def stCorpse(self) -> Corpse: return self.corpse
    @stCorpse.setter
    def stCorpse(self, v: Corpse): self.corpse = v

    @property
    def stMercenary(self) -> Mercenary: return self.mercenary
    @stMercenary.setter
    def stMercenary(self, v: Mercenary): self.mercenary = v

    @property
    def stGolem(self) -> Golem: return self.golem
    @stGolem.setter
    def stGolem(self, v: Golem): self.golem = v

    @property
    def stDemon(self) -> Demon: return self.demon
    @stDemon.setter
    def stDemon(self, v: Demon): self.demon = v
    
    def deserialize(self, bs):
        self.magic = bs.read_dword()
        self.version = bs.read_dword()
        self.dwSize = bs.read_dword()
        self.dwCRC = bs.read_dword()
        self.dwWeaponSet = bs.read_dword()
        
        if self.version >= 0x69:
            self._read_data_v69(bs)
        else:
            self._read_data_common(bs)
    
    def _read_data_v69(self, bs):
        self.charFlags = bs.read_dword()
        self.charType = self.charFlags
        self.charTitle = (self.charFlags >> 8) & 0x1F
        self.charClass = bs.read_byte()
        self.numStats = bs.read_byte()
        self.numSkills = bs.read_byte()
        self.charLevel = bs.read_byte()
        self.createTime = bs.read_dword()
        self.lastSaveTime = bs.read_dword()
        self.playTime = bs.read_dword()
        
        for i in range(16):
            self.dwSkillKey[i] = bs.read_dword()
        
        self.dwLeftSkill1 = bs.read_dword()
        self.dwRightSkill1 = bs.read_dword()
        self.dwLeftSkill2 = bs.read_dword()
        self.dwRightSkill2 = bs.read_dword()
        
        self.outfit = bs.data[bs.bytes_pos:bs.bytes_pos+16]
        bs.bytes_pos += 16
        self.colors = bs.data[bs.bytes_pos:bs.bytes_pos+16]
        bs.bytes_pos += 16
        
        self.Town = bs.data[bs.bytes_pos:bs.bytes_pos+3]
        bs.bytes_pos += 3
        
        self.dwMapSeed = bs.read_dword()
        
        self.mercFlags = bs.read_dword()
        self.mercSeed = bs.read_dword()
        self.mercNameIndex = bs.read_word()
        self.mercHirelingId = bs.read_word()
        self.mercExperience = bs.read_dword()
        
        preview_size = 228
        self.previewData = bs.data[bs.bytes_pos:bs.bytes_pos+preview_size]
        bs.bytes_pos += preview_size
        
        self.gameVersion = self.previewData[73]
        
        name_offset = 0x7C
        name_bytes = self.previewData[name_offset:name_offset+96]
        self.Name = name_bytes.split(b'\x00')[0]
        
        self.QuestInfo.deserialize(bs)
        
        self.Waypoints.deserialize(bs)
        
        self.NPC = bs.data[bs.bytes_pos:bs.bytes_pos+0x34]
        bs.bytes_pos += 0x34
        
        self.PlayerStats.deserialize(bs)
        
        self.Skills.deserialize(bs)
        
        self.ItemList.deserialize(bs, self.dwVersion)
        
        self.stCorpse.deserialize(bs, self.dwVersion)
        
        if self.is_expansion():
            self.stMercenary.deserialize(bs, self.has_mercenary(), self.dwVersion)
            self.stGolem.deserialize(bs, self.dwVersion)
        
        if self.dwVersion >= 0x69 and self.gameVersion >= 3:
            self.stDemon.deserialize(bs)
        
        bs.align_byte()
    
    def _read_data_common(self, bs):
        self.Name = bs.data[bs.bytes_pos:bs.bytes_pos+16]
        bs.bytes_pos += 16
        
        charType = bs.read_byte()
        self.charFlags = charType
        self.charType = charType
        self.charTitle = bs.read_byte()
        self.numStatsNumSkills = bs.read_word()
        self.charClass = bs.read_byte()
        self.padding1 = bs.read_word()
        self.charLevel = bs.read_byte()
        self.createTime = bs.read_dword()
        self.dwTime = bs.read_dword()
        self.playTime = bs.read_dword()
        
        for i in range(16):
            self.dwSkillKey[i] = bs.read_dword()
        
        self.dwLeftSkill1 = bs.read_dword()
        self.dwRightSkill1 = bs.read_dword()
        self.dwLeftSkill2 = bs.read_dword()
        self.dwRightSkill2 = bs.read_dword()
        
        # 读取outfit和colors
        self.outfit = bs.data[bs.bytes_pos:bs.bytes_pos+16]
        bs.bytes_pos += 16
        self.colors = bs.data[bs.bytes_pos:bs.bytes_pos+16]
        bs.bytes_pos += 16
        
        # 读取Town
        self.Town = bs.data[bs.bytes_pos:bs.bytes_pos+3]
        bs.bytes_pos += 3
        
        self.dwMapSeed = bs.read_dword()
        self.mercFlagsLow = bs.read_word()
        self.bMercDead = bs.read_byte()
        self.mercFlagsHigh = bs.read_byte()
        self.dwMercControl = bs.read_dword()
        self.wMercName = bs.read_word()
        self.wMercType = bs.read_word()
        self.dwMercExp = bs.read_dword()
        
        self.previewPrefix = bs.data[bs.bytes_pos:bs.bytes_pos+0x4C]
        bs.bytes_pos += 0x4C
        
        self.NamePTR = bs.data[bs.bytes_pos:bs.bytes_pos+0x40]
        bs.bytes_pos += 0x40
        
        self.previewSuffix = bs.read_dword()
        
        self.QuestInfo.deserialize(bs)
        
        # 读取传送点信息
        self.Waypoints.deserialize(bs)
        
        # 读取NPC信息
        self.NPC = bs.data[bs.bytes_pos:bs.bytes_pos+0x34]
        bs.bytes_pos += 0x34
        
        # 读取人物属性
        self.PlayerStats.deserialize(bs)
        
        # 读取技能信息
        self.Skills.deserialize(bs)
        
        # 读取物品列表
        self.ItemList.deserialize(bs, self.dwVersion)
        
        # 读取尸体
        self.stCorpse.deserialize(bs, self.dwVersion)
        
        # 如果是扩展版，读取雇佣兵和石魔
        if self.is_expansion():
            self.stMercenary.deserialize(bs, self.has_mercenary(), self.dwVersion)
            self.stGolem.deserialize(bs, self.dwVersion)
        
        bs.align_byte()
    
    def has_mercenary(self):
        if self.dwVersion >= 0x69:
            return self.mercSeed != 0 or self.mercNameIndex != 0 or self.mercExperience != 0
        elif self.dwVersion >= 0x61:
            return self.dwMercControl != 0
        else:
            return self.wMercName > 0

    @property
    def merc_name_id(self) -> int:
        return self.mercNameIndex if self.dwVersion >= 0x69 else getattr(self, 'wMercName', 0)

    @property
    def merc_type_id(self) -> int:
        return self.mercHirelingId if self.dwVersion >= 0x69 else getattr(self, 'wMercType', 0)

    @property
    def merc_experience(self) -> int:
        return self.mercExperience if self.dwVersion >= 0x69 else getattr(self, 'dwMercExp', 0)

    @property
    def merc_is_dead(self) -> bool:
        return bool(getattr(self, 'bMercDead', 0))
    
    def is_ladder(self):
        return (self.charFlags & 0x40) != 0
    
    def is_expansion(self):
        if self.dwVersion >= 0x69:
            return self.gameVersion > 1
        if (self.charFlags & 0x20) != 0:
            return True
        if self.quests and self.quests.acts >= 5:
            return True
        return False
    
    def is_warlock_expansion(self):
        return (self.charFlags & 0x20) != 0
    
    def is_died_before(self):
        return (self.charFlags & 0x08) != 0
    
    def is_hardcore(self):
        return (self.charFlags & 0x04) != 0
    
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
        if 0 <= self.charClass < len(class_names):
            return class_names[self.charClass]
        return "Unknown"
    
    def get_char_name(self):
        if self.dwVersion >= 0x69:
            name_data = self.Name
        elif self.dwVersion >= 0x62:
            name_data = self.NamePTR
        else:
            name_data = self.Name
        null_pos = name_data.find(b'\x00')
        if null_pos != -1:
            name_bytes = name_data[:null_pos]
        else:
            name_bytes = name_data
        if self.dwVersion >= 0x62:
            name = name_bytes.decode('utf-8', errors='replace')
        else:
            name = name_bytes.decode('ascii', errors='replace')
        return name
    
    def get_char_title(self):

        return self.charTitle
    
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
        bs.write_dword(self.dwSize)
        bs.write_dword(self.dwCRC)
        bs.write_dword(self.dwWeaponSet)
        
        if self.version >= 0x69:
            self._serialize_v69(bs)
        else:
            self._serialize_common(bs)
    
    def _serialize_v69(self, bs):
        bs.write_dword(self.charFlags)
        bs.write_byte(self.charClass)
        bs.write_byte(self.numStats)
        bs.write_byte(self.numSkills)
        bs.write_byte(self.charLevel)
        bs.write_dword(self.createTime)
        bs.write_dword(self.lastSaveTime)
        bs.write_dword(self.playTime)
        
        for i in range(16):
            bs.write_dword(self.dwSkillKey[i])
        
        bs.write_dword(self.dwLeftSkill1)
        bs.write_dword(self.dwRightSkill1)
        bs.write_dword(self.dwLeftSkill2)
        bs.write_dword(self.dwRightSkill2)
        
        bs.write_bytes(self.outfit)
        bs.write_bytes(self.colors)
        bs.write_bytes(self.Town)
        
        bs.write_dword(self.dwMapSeed)
        
        bs.write_dword(self.mercFlags)
        bs.write_dword(self.mercSeed)
        bs.write_word(self.mercNameIndex)
        bs.write_word(self.mercHirelingId)
        bs.write_dword(self.mercExperience)
        
        bs.write_bytes(self.previewData)
        
        self.QuestInfo.serialize(bs)
        self.Waypoints.serialize(bs)
        bs.write_bytes(self.NPC)
        self.PlayerStats.serialize(bs)
        self.Skills.serialize(bs)
        self.ItemList.serialize(bs, self.dwVersion)
        self.stCorpse.serialize(bs, self.dwVersion)
        
        if self.is_expansion():
            self.stMercenary.serialize(bs, self.has_mercenary(), self.dwVersion)
            self.stGolem.serialize(bs, self.dwVersion)
        
        if self.dwVersion >= 0x69 and self.gameVersion >= 3:
            self.stDemon.serialize(bs)
        
        bs.align_byte()
    
    def _serialize_common(self, bs):
        bs.write_bytes(self.Name)
        bs.write_byte(self.charType)
        bs.write_byte(self.charTitle)
        bs.write_word(self.numStatsNumSkills)
        bs.write_byte(self.charClass)
        bs.write_word(self.padding1)
        bs.write_byte(self.charLevel)
        bs.write_dword(self.createTime)
        bs.write_dword(self.dwTime)
        bs.write_dword(self.playTime)
        
        for i in range(16):
            bs.write_dword(self.dwSkillKey[i])
        
        bs.write_dword(self.dwLeftSkill1)
        bs.write_dword(self.dwRightSkill1)
        bs.write_dword(self.dwLeftSkill2)
        bs.write_dword(self.dwRightSkill2)
        
        bs.write_bytes(self.outfit)
        bs.write_bytes(self.colors)
        bs.write_bytes(self.Town)
        
        bs.write_dword(self.dwMapSeed)
        bs.write_word(self.mercFlagsLow)
        bs.write_byte(self.bMercDead)
        bs.write_byte(self.mercFlagsHigh)
        bs.write_dword(self.dwMercControl)
        bs.write_word(self.wMercName)
        bs.write_word(self.wMercType)
        bs.write_dword(self.dwMercExp)
        
        bs.write_bytes(self.previewPrefix)
        bs.write_bytes(self.NamePTR)
        bs.write_dword(self.previewSuffix)
        
        self.QuestInfo.serialize(bs)
        self.Waypoints.serialize(bs)
        bs.write_bytes(self.NPC)
        self.PlayerStats.serialize(bs)
        self.Skills.serialize(bs)
        self.ItemList.serialize(bs, self.dwVersion)
        self.stCorpse.serialize(bs, self.dwVersion)
        
        if self.is_expansion():
            self.stMercenary.serialize(bs, self.has_mercenary(), self.dwVersion)
            self.stGolem.serialize(bs, self.dwVersion)
        
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
        data[0x0C:0x10] = checksum.to_bytes(4, 'little')
        return bytes(data)
    
