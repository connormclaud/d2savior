from core.item import CD2Item, CItemList, init_item_data

class CQuestInfoData:
    def __init__(self):
        self.wIntroduced1 = 0
        self.wActI = [0] * 6
        self.wTraval1 = 0
        self.wIntroduced2 = 0
        self.wActII = [0] * 6
        self.wTraval2 = 0
        self.wIntroduced3 = 0
        self.wActIII = [0] * 6
        self.wTraval3 = 0
        self.wIntroduced4 = 0
        self.wActIV = [0] * 3
        self.wTraval4 = 0
        self.unknown1 = [0] * 3
        self.wIntroduced5 = 0
        self.unknown2 = [0] * 2
        self.wActV = [0] * 6
        self.bResetStats = 0
        self.unknown3 = 0
        self.unknown4 = [0] * 6
    
    def read_data(self, bs):
        self.wIntroduced1 = bs.read_word()
        for i in range(6):
            self.wActI[i] = bs.read_word()
        self.wTraval1 = bs.read_word()
        self.wIntroduced2 = bs.read_word()
        for i in range(6):
            self.wActII[i] = bs.read_word()
        self.wTraval2 = bs.read_word()
        self.wIntroduced3 = bs.read_word()
        for i in range(6):
            self.wActIII[i] = bs.read_word()
        self.wTraval3 = bs.read_word()
        self.wIntroduced4 = bs.read_word()
        for i in range(3):
            self.wActIV[i] = bs.read_word()
        self.wTraval4 = bs.read_word()
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

class CQuestInfo:
    def __init__(self):
        self.dwMajic = 0
        self.dwActs = 0
        self.wSize = 0
        self.QIData = [CQuestInfoData() for _ in range(3)]
    
    def read_data(self, bs):
        self.dwMajic = bs.read_dword()
        self.dwActs = bs.read_dword()
        self.wSize = bs.read_word()
        for i in range(3):
            self.QIData[i].read_data(bs)

class CWaypointData:
    def __init__(self):
        self.unkown = 0
        self.Waypoints = [0] * 5
        self.unkown2 = [0] * 17
    
    def read_data(self, bs):
        self.unkown = bs.read_word()
        for i in range(5):
            self.Waypoints[i] = bs.read_byte()
        for i in range(17):
            self.unkown2[i] = bs.read_byte()

class CWaypoints:
    def __init__(self):
        self.wMajic = 0
        self.unkown = 0
        self.wSize = 0
        self.wp = [CWaypointData() for _ in range(3)]
    
    def read_data(self, bs):
        self.wMajic = bs.read_word()
        self.unkown = bs.read_dword()
        self.wSize = bs.read_word()
        for i in range(3):
            self.wp[i].read_data(bs)

class CPlayerStats:
    def __init__(self):
        self.wMajic = 0
        self.m_adwValue = [0] * 0x10
        self.iEnd = 0
    
    def read_data(self, bs):
        PLAYER_STATS_BITS_COUNT = [10, 10, 10, 10, 10, 8, 21, 21, 21, 21, 21, 21, 7, 32, 25, 25]
        self.wMajic = bs.read_word()
        if self.wMajic != 0x6667:
            return
        self.m_adwValue = [0] * 0x10
        while True:
            try:
                self.iEnd = bs.read_bits(9)
                if self.iEnd >= 0x10:
                    break
                self.m_adwValue[self.iEnd] = bs.read_bits(PLAYER_STATS_BITS_COUNT[self.iEnd])
            except ValueError:
                break
        bs.align_byte()

class CCharSkills:
    def __init__(self):
        self.wMagic = 0
        self.bSkillLevel = [0] * 30
    
    def read_data(self, bs):
        self.wMagic = bs.read_word()
        for i in range(30):
            self.bSkillLevel[i] = bs.read_byte()

class CCorpseData:
    def __init__(self):
        self.unknown = b''
        self.stItems = None
    
    def read_data(self, bs, version):
        self.unknown = bs.data[bs.bytes_pos:bs.bytes_pos+12]
        bs.bytes_pos += 12
        self.stItems = CItemList()
        self.stItems.read_data(bs, version)

class CCorpse:
    def __init__(self):
        self.wMagic = 0
        self.wCount = 0
        self.pCorpseData = None
    
    def read_data(self, bs, version):
        self.wMagic = bs.read_word()
        self.wCount = bs.read_word()
        if self.wMagic != 0x4D4A:
            # 不是CCorpse，回退并返回
            bs.seek_back_bytes(4)
            return
        if self.wCount > 0:
            self.pCorpseData = CCorpseData()
            self.pCorpseData.read_data(bs, version)
    
    def has_corpse(self):
        return self.wCount > 0 and self.pCorpseData is not None

class CMercenary:
    def __init__(self):
        self.wMagic = 0
        self.stItems = None
    
    def read_data(self, bs, has_mercenary, version):
        self.wMagic = bs.read_word()
        if self.wMagic != 0x666A:
            # 不是CMercenary，回退并返回
            bs.seek_back_bytes(2)
            return
        if has_mercenary:
            self.stItems = CItemList()
            self.stItems.read_data(bs, version)

class CGolem:
    def __init__(self):
        self.wMagic = 0
        self.bHasGolem = 0
        self.pItem = None
    
    def read_data(self, bs, version):
        self.wMagic = bs.read_word()
        self.bHasGolem = bs.read_byte()
        if self.wMagic not in [0x666B, 0x6669]:
            bs.seek_back_bytes(3)
            return
        if self.bHasGolem:
            self.pItem = CD2Item()
            self.pItem.read_data(bs, version)

class CDemon:
    def __init__(self):
        self.sectionVersion = 0
        self.wMagic = 0
        self.hasDemon = False
        self.padding = 0
        self.demonData = None
    
    def read_data(self, bs):
        self.sectionVersion = bs.read_word()
        self.wMagic = bs.read_word()
        if self.wMagic != 0x666C:
            bs.seek_back_bytes(4)
            return
        has_demon_byte = bs.read_byte()
        self.hasDemon = has_demon_byte != 0
        self.padding = bs.read_byte()
        if self.hasDemon:
            self._read_demon_data(bs)
    
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

class CD2S_Struct:
    def __init__(self):
        self.dwMajic = 0
        self.dwVersion = 0
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
        
        self.QuestInfo = CQuestInfo()
        self.Waypoints = CWaypoints()
        self.NPC = b''
        self.PlayerStats = CPlayerStats()
        self.Skills = CCharSkills()
        self.ItemList = CItemList()
        self.stCorpse = CCorpse()
        self.stMercenary = CMercenary()
        self.stGolem = CGolem()
        self.stDemon = CDemon()
        self.gameVersion = 0
    
    def read_data(self, bs):
        self.dwMajic = bs.read_dword()
        self.dwVersion = bs.read_dword()
        self.dwSize = bs.read_dword()
        self.dwCRC = bs.read_dword()
        self.dwWeaponSet = bs.read_dword()
        
        if self.dwVersion >= 0x69:
            self._read_data_v69(bs)
        else:
            self._read_data_common(bs)
    
    def _read_data_v69(self, bs):
        self.charFlags = bs.read_dword()
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
        
        self.QuestInfo.read_data(bs)
        
        self.Waypoints.read_data(bs)
        
        self.NPC = bs.data[bs.bytes_pos:bs.bytes_pos+0x34]
        bs.bytes_pos += 0x34
        
        self.PlayerStats.read_data(bs)
        
        self.Skills.read_data(bs)
        
        self.ItemList.read_data(bs, self.dwVersion)
        
        self.stCorpse.read_data(bs, self.dwVersion)
        
        if self.is_expansion():
            self.stMercenary.read_data(bs, self.has_mercenary(), self.dwVersion)
            self.stGolem.read_data(bs, self.dwVersion)
        
        if self.dwVersion >= 0x69 and self.gameVersion >= 3:
            self.stDemon.read_data(bs)
        
        bs.align_byte()
    
    def _read_data_common(self, bs):
        self.Name = bs.data[bs.bytes_pos:bs.bytes_pos+16]
        bs.bytes_pos += 16
        
        charType = bs.read_byte()
        self.charFlags = charType
        self.charType = charType
        self.charTitle = bs.read_byte()
        self.unkown1 = bs.read_word()
        self.charClass = bs.read_byte()
        self.unkown2 = bs.read_word()
        self.charLevel = bs.read_byte()
        self.unkown3 = bs.read_dword()
        self.dwTime = bs.read_dword()
        self.unkown4 = bs.read_dword()
        
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
        self.unkown5 = bs.read_word()
        self.bMercDead = bs.read_byte()
        self.unkown6 = bs.read_byte()
        self.dwMercControl = bs.read_dword()
        self.wMercName = bs.read_word()
        self.wMercType = bs.read_word()
        self.dwMercExp = bs.read_dword()
        
        # 读取unkown7
        self.unkown7 = bs.data[bs.bytes_pos:bs.bytes_pos+0x4C]
        bs.bytes_pos += 0x4C
        
        self.NamePTR = bs.data[bs.bytes_pos:bs.bytes_pos+0x40]
        bs.bytes_pos += 0x40
        
        self.unkown8 = bs.read_dword()
        
        self.QuestInfo.read_data(bs)
        
        # 读取传送点信息
        self.Waypoints.read_data(bs)
        
        # 读取NPC信息
        self.NPC = bs.data[bs.bytes_pos:bs.bytes_pos+0x34]
        bs.bytes_pos += 0x34
        
        # 读取人物属性
        self.PlayerStats.read_data(bs)
        
        # 读取技能信息
        self.Skills.read_data(bs)
        
        # 读取物品列表
        self.ItemList.read_data(bs, self.dwVersion)
        
        # 读取尸体
        self.stCorpse.read_data(bs, self.dwVersion)
        
        # 如果是扩展版，读取雇佣兵和石魔
        if self.is_expansion():
            self.stMercenary.read_data(bs, self.has_mercenary(), self.dwVersion)
            self.stGolem.read_data(bs, self.dwVersion)
        
        bs.align_byte()
    
    def has_mercenary(self):
        if self.dwVersion >= 0x69:
            return self.mercSeed != 0 or self.mercNameIndex != 0 or self.mercExperience != 0
        elif self.dwVersion >= 0x61:
            return self.dwMercControl != 0
        else:
            return self.wMercName > 0
    
    def is_ladder(self):
        return (self.charFlags & 0x40) != 0
    
    def is_expansion(self):
        if self.dwVersion >= 0x69:
            return self.gameVersion > 1
        if (self.charFlags & 0x20) != 0:
            return True
        if self.QuestInfo and self.QuestInfo.dwActs >= 5:
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
    
