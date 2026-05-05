# 0x63 版本 D2S 存档格式

## 1. 总体结构

0x63 版本的 Diablo II Resurrected 存档文件 (.d2s) 采用二进制格式，所有多字节数值使用小端序。

| 偏移量 (字节) | 大小 (字节) | 字段 | 描述 |
|-------------|-----------|------|------|
| 0x0000      | 4         | dwMajic | 魔法数 (0xAA55AA55) |
| 0x0004      | 4         | dwVersion | 版本标识 (0x63) |
| 0x0008      | 4         | dwSize | 存档大小 |
| 0x000C      | 4         | dwCRC | CRC 校验 |
| 0x0010      | 4         | dwWeaponSet | 武器切换设置 |
| 0x0014      | 16        | Name | 角色名称 (null 终止) |
| 0x0024      | 1         | charType | 角色类型标志 |
| 0x0025      | 1         | charTitle | 角色称号 |
| 0x0026      | 2         | numStatsNumSkills | 属性数量(高8位) + 技能数量(低8位) |
| 0x0028      | 1         | charClass | 角色职业 |
| 0x0029      | 2         | padding1 | 填充 (固定 0x101E) |
| 0x002C      | 1         | charLevel | 角色等级 |
| 0x002D      | 4         | createTime | 创建时间 (0x63版本中通常为0) |
| 0x0031      | 4         | dwTime | 最后保存时间 (Unix时间戳) |
| 0x0035      | 4         | playTime | 游戏时间 (0x63版本中通常为0xFFFFFFFF, 未使用) |
| 0x0039      | 64        | dwSkillKey[16] | 技能快捷键 |
| 0x0079      | 4         | dwLeftSkill1 | 左手技能1 |
| 0x007D      | 4         | dwRightSkill1 | 右手技能1 |
| 0x0081      | 4         | dwLeftSkill2 | 左手技能2 |
| 0x0085      | 4         | dwRightSkill2 | 右手技能2 |
| 0x0089      | 16        | outfit[16] | 外观 |
| 0x0099      | 16        | colors[16] | 颜色 |
| 0x00A9      | 3         | Town[3] | 城镇 |
| 0x00AC      | 4         | dwMapSeed | 地图种子 |
| 0x00B0      | 2         | mercFlagsLow | 雇佣兵标志低16位 |
| 0x00B2      | 1         | bMercDead | 雇佣兵死亡标志 |
| 0x00B3      | 1         | mercFlagsHigh | 雇佣兵标志高8位 |
| 0x00B4      | 4         | dwMercControl | 雇佣兵控制 |
| 0x00B8      | 2         | wMercName | 雇佣兵名称 |
| 0x00BA      | 2         | wMercType | 雇佣兵类型 |
| 0x00BC      | 4         | dwMercExp | 雇佣兵经验 |
| 0x00C0      | 76        | previewPrefix | 预览数据前缀 (含装备预览+公会徽章+经验值) |
| 0x010C      | 64        | NamePTR | 名称指针 (含Name) |
| 0x014C      | 4         | previewSuffix | 预览数据后缀 |
| 可变        | 可变      | QuestInfo | 任务数据 |
| 可变        | 可变      | Waypoints | 小站数据 |
| 可变        | 可变      | NPC | NPC 信息 (0x34 字节) |
| 可变        | 可变      | PlayerStats | 玩家属性 |
| 可变        | 可变      | Skills | 技能数据 |
| 可变        | 可变      | ItemList | 物品列表 |
| 可变        | 可变      | Corpse | 尸体数据 |
| 可变        | 可变      | Mercenary | 雇佣兵数据 (扩展版) |
| 可变        | 可变      | Golem | 石魔数据 (扩展版) |

## 2. 角色类型标志 (charType)

charType 字段包含多个布尔标志的位组合：

| 位 | 标志 | 描述 |
|----|------|------|
| 0x01 | Init | 初始化标志 |
| 0x02 | RealmChar | 战网角色 |
| 0x04 | Hardcore | 硬核角色 |
| 0x08 | Died | 曾经死亡 |
| 0x10 | SaveProcess | 保存处理中 |
| 0x20 | Expansion | 资料片角色 |
| 0x40 | Ladder | 天梯角色 |
| 0x80 | NeedsRenaming | 需要重命名 |

> 0x63 版本 (v97~v103) 使用 charType (1字节) 存储角色标志。0x69 版本 (v104+) 扩展为 charFlags (4字节)，其中 bit8~bit12 存储角色进度 (Progression)。

## 3. 角色职业 (charClass)

| 值 | 职业 |
|-----|------|
| 0 | Amazon (亚马逊) |
| 1 | Sorceress (法师) |
| 2 | Necromancer (死灵法师) |
| 3 | Paladin (圣骑士) |
| 4 | Barbarian (野蛮人) |
| 5 | Druid (德鲁伊) |
| 6 | Assassin (刺客) |

## 4. 任务数据 (QuestInfo)

| 字段 | 大小 (字节) | 描述 |
|------|-----------|------|
| dwMajic | 4 | 魔法数 |
| dwActs | 4 | 已解锁章节数 |
| wSize | 2 | 数据大小 |
| QIData[3] | 可变 | 3个难度的任务数据 |

### 4.1 单个难度任务数据 (QuestInfoData)

| 字段 | 大小 (字节) | 描述 |
|------|-----------|------|
| wIntroduced1 | 2 | Act I 引入 |
| wActI[6] | 12 | Act I 任务 (6个word) |
| wTraval1 | 2 | Act I 旅行 |
| wIntroduced2 | 2 | Act II 引入 |
| wActII[6] | 12 | Act II 任务 |
| wTraval2 | 2 | Act II 旅行 |
| wIntroduced3 | 2 | Act III 引入 |
| wActIII[6] | 12 | Act III 任务 |
| wTraval3 | 2 | Act III 旅行 |
| wIntroduced4 | 2 | Act IV 引入 |
| wActIV[3] | 6 | Act IV 任务 (3个word) |
| wTraval4 | 2 | Act IV 旅行 |
| unknown1[3] | 6 | 未知 |
| wIntroduced5 | 2 | Act V 引入 |
| unknown2[2] | 4 | 未知 |
| wActV[6] | 12 | Act V 任务 |
| bResetStats | 1 | 重置属性标志 |
| unknown3 | 1 | 未知 |
| unknown4[6] | 12 | 未知 |

## 5. 小站数据 (Waypoints)

详细格式见 [waypoint_format.md](waypoint_format.md)。

| 字段 | 大小 (字节) | 描述 |
|------|-----------|------|
| wMajic | 2 | 魔法数 (0x5357 = "WS") |
| unknown | 4 | 版本号 (通常为 1) |
| wSize | 2 | 数据大小 (0x0050 = 80) |
| wp[3] | 72 | 3个难度的小站数据 (每个24字节) |

### 5.1 单个难度小站数据 (WaypointData)

| 字段 | 大小 (字节) | 描述 |
|------|-----------|------|
| unknown | 2 | 头部 (通常为 0x0102) |
| Waypoints[5] | 5 | 小站标志位图 (39位有效 + 1位填充) |
| unknown2[17] | 17 | 保留 (全0) |

## 6. 玩家属性 (PlayerStats)

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| wMajic | 16 | 魔法数 (0x6667) |
| 属性数据 | 可变 | 9位ID + 变长值 的序列 |
| 结束标志 | 9 | >= 0x10 时结束 |

### 6.1 属性ID与位长

| ID | 属性 | 位长 |
|----|------|------|
| 0 | Strength (力量) | 10 |
| 1 | Energy (精力) | 10 |
| 2 | Dexterity (敏捷) | 10 |
| 3 | Vitality (体力) | 10 |
| 4 | Unused Stats (剩余属性点) | 10 |
| 5 | Unused Skills (剩余技能点) | 8 |
| 6 | Current HP (当前生命) | 21 |
| 7 | Max HP (最大生命) | 21 |
| 8 | Current Mana (当前法力) | 21 |
| 9 | Max Mana (最大法力) | 21 |
| 10 | Current Stamina (当前耐力) | 21 |
| 11 | Max Stamina (最大耐力) | 21 |
| 12 | Level (等级) | 7 |
| 13 | Experience (经验) | 32 |
| 14 | Gold (金币) | 25 |
| 15 | Stash Gold (存储金币) | 25 |

## 7. 技能数据 (Skills)

| 字段 | 大小 (字节) | 描述 |
|------|-----------|------|
| wMagic | 2 | 魔法数 |
| bSkillLevel[30] | 30 | 每个技能的点数 (每技能1字节) |

## 8. 物品列表

详见 [0x63_itemlist_format.md](0x63_itemlist_format.md)。

## 9. 尸体数据 (Corpse)

| 字段 | 大小 (字节) | 描述 |
|------|-----------|------|
| wMagic | 2 | 魔法数 (0x4D4A) |
| wCount | 2 | 尸体数量 (0 或 1) |
| CorpseData | 可变 | 尸体详细数据 (如果 wCount > 0) |

### 9.1 尸体详细数据 (CorpseData)

| 字段 | 大小 (字节) | 描述 |
|------|-----------|------|
| unknown | 12 | 未知 |
| stItems | 可变 | 尸体上的物品列表 |

## 10. 雇佣兵数据 (Mercenary)

仅在扩展版角色中出现。

| 字段 | 大小 (字节) | 描述 |
|------|-----------|------|
| wMagic | 2 | 魔法数 (0x666A) |
| stItems | 可变 | 雇佣兵装备物品列表 |

## 11. 石魔数据 (Golem)

仅在扩展版角色中出现。

| 字段 | 大小 (字节) | 描述 |
|------|-----------|------|
| wMagic | 2 | 魔法数 (0x666B 或 0x6669) |
| bHasGolem | 1 | 是否有石魔 |
| pItem | 可变 | 石魔物品数据 (如果 bHasGolem) |

## 12. 雇佣兵判断逻辑

```python
def has_mercenary(self):
    # 0x61+ 版本: dwMercControl != 0
    return self.dwMercControl != 0
```

## 13. 扩展版判断逻辑

```python
def is_expansion(self):
    # v97~v103: 使用 charType 的 Expansion 位
    if (self.charFlags & 0x20) != 0:
        return True
    # 兜底: 任务数据中 Act 数 >= 5
    if self.QuestInfo and self.QuestInfo.dwActs >= 5:
        return True
    return False
```

## 14. 时间字段说明

0x63 版本的时间字段：

| 字段 | 描述 | 实际值 |
|------|------|--------|
| createTime | 创建时间 | 通常为 0 (0x63版本中未使用) |
| dwTime | 最后保存时间 | Unix 时间戳，可正常转换为日期 |
| playTime | 游戏时间 | 通常为 0xFFFFFFFF (0x63版本中未使用) |

> 0x69 版本 (v104+) 中对应字段为 createTime、lastSaveTime、playTime，其中 createTime 和 playTime 同样为无效默认值，实际使用 lastSaveTime。
