# 0x69 版本 D2S 存档格式

## 1. 总体结构

0x69 版本对应 D2R 资料片术士君临 (Reign of the Warlock)，新增了术士职业。与 0x63 (D2R 基础版) 相比头部结构有显著变化。

| 偏移量 (字节) | 大小 (字节) | 字段 | 描述 |
|-------------|-----------|------|------|
| 0x0000      | 4         | dwMajic | 魔法数 (0xAA55AA55) |
| 0x0004      | 4         | dwVersion | 版本标识 (0x69) |
| 0x0008      | 4         | dwSize | 存档大小 |
| 0x000C      | 4         | dwCRC | CRC 校验 |
| 0x0010      | 4         | dwWeaponSet | 武器切换设置 |
| 0x0014      | 4         | charFlags | 角色标志 |
| 0x0018      | 1         | charClass | 角色职业 |
| 0x0019      | 1         | numStats | 属性数量 (16) |
| 0x001A      | 1         | numSkills | 技能数量 (30) |
| 0x001B      | 1         | charLevel | 角色等级 |
| 0x001C      | 4         | createTime | 创建时间 |
| 0x0020      | 4         | lastSaveTime | 最后保存时间 |
| 0x0024      | 4         | playTime | 游戏时间 |
| 0x0028      | 64        | dwSkillKey[16] | 技能快捷键 |
| 0x0068      | 4         | dwLeftSkill1 | 左手技能1 |
| 0x006C      | 4         | dwRightSkill1 | 右手技能1 |
| 0x0070      | 4         | dwLeftSkill2 | 左手技能2 |
| 0x0074      | 4         | dwRightSkill2 | 右手技能2 |
| 0x0078      | 16        | outfit[16] | 外观 |
| 0x0088      | 16        | colors[16] | 颜色 |
| 0x0098      | 3         | Town[3] | 城镇 |
| 0x009B      | 4         | dwMapSeed | 地图种子 |
| 0x009F      | 4         | mercFlags | 雇佣兵标志 |
| 0x00A3      | 4         | mercSeed | 雇佣兵种子 |
| 0x00A7      | 2         | mercNameIndex | 雇佣兵名称索引 |
| 0x00A9      | 2         | mercHirelingId | 雇佣兵雇佣ID |
| 0x00AB      | 4         | mercExperience | 雇佣兵经验 |
| 0x00AF      | 228       | previewData | 预览数据 |
| 可变        | 可变      | QuestInfo | 任务数据 |
| 可变        | 可变      | Waypoints | 小站数据 |
| 可变        | 可变      | NPC | NPC 信息 (0x34 字节) |
| 可变        | 可变      | PlayerStats | 玩家属性 |
| 可变        | 可变      | Skills | 技能数据 |
| 可变        | 可变      | ItemList | 物品列表 |
| 可变        | 可变      | Corpse | 尸体数据 |
| 可变        | 可变      | Mercenary | 雇佣兵数据 (资料片) |
| 可变        | 可变      | Golem | 石魔数据 (资料片) |
| 可变        | 可变      | Demon | 恶魔数据 (gameVersion >= 3) |

## 2. 与 0x63 版本的主要差异

### 2.1 头部结构变化

0x69 版本的头部与 0x63 版本完全不同：

| 差异点 | 0x63 | 0x69 |
|--------|------|------|
| 角色名称位置 | 0x0014 (16字节直接存储) | previewData 内偏移 0x7C (96字节, UTF-8) |
| charFlags | charType (1字节) | charFlags (4字节) |
| charClass | 0x0028 (1字节) | 0x0018 (1字节) |
| charLevel | 0x002C (1字节) | 0x001B (1字节) |
| 雇佣兵数据 | dwMercControl/wMercName/wMercType/dwMercExp | mercFlags/mercSeed/mercNameIndex/mercHirelingId/mercExperience |
| 新增字段 | 无 | createTime, lastSaveTime, playTime, previewData |

### 2.2 previewData 结构

previewData 是 0x69 版本新增的 228 字节数据区域，包含：

| 偏移 (相对 previewData) | 大小 (字节) | 描述 |
|------------------------|-----------|------|
| 0x49 (73) | 1 | gameVersion (游戏版本，3=术士君临资料片) |
| 0x7C | 96 | Name (角色名称, UTF-8, null终止) |

### 2.3 角色名称读取

0x69 版本的角色名称从 previewData 中提取：

```python
name_offset = 0x7C
name_bytes = previewData[name_offset:name_offset+96]
Name = name_bytes.split(b'\x00')[0]
```

## 3. 角色标志 (charFlags)

| 位 | 标志 | 描述 |
|----|------|------|
| 0x04 | Hardcore | 硬核角色 |
| 0x08 | Died | 曾经死亡 |
| 0x20 | Expansion | 资料片角色 (术士君临) |
| 0x40 | Ladder | 天梯角色 |

## 4. 角色职业 (charClass)

| 值 | 职业 |
|-----|------|
| 0 | Amazon (亚马逊) |
| 1 | Sorceress (法师) |
| 2 | Necromancer (死灵法师) |
| 3 | Paladin (圣骑士) |
| 4 | Barbarian (野蛮人) |
| 5 | Druid (德鲁伊) |
| 6 | Assassin (刺客) |
| 7 | Warlock (术士) |

## 5. 雇佣兵判断逻辑

```python
def has_mercenary(self):
    # 0x69 版本: mercSeed/mercNameIndex/mercExperience 任一非零
    return self.mercSeed != 0 or self.mercNameIndex != 0 or self.mercExperience != 0
```

## 6. 资料片判断逻辑

```python
def is_expansion(self):
    # 0x69 版本: gameVersion > 1 表示术士君临资料片
    return self.gameVersion > 1
```

## 7. 恶魔数据 (Demon)

仅在 gameVersion >= 3 时出现。

| 字段 | 大小 (字节) | 描述 |
|------|-----------|------|
| sectionVersion | 2 | 节版本 |
| wMagic | 2 | 魔法数 (0x666C) |
| hasDemon | 1 | 是否有恶魔 |
| padding | 1 | 填充 |

### 7.1 恶魔详细数据 (hasDemon = true)

| 字段 | 大小 (字节) | 描述 |
|------|-----------|------|
| stat_data_size | 2 | 属性数据大小 |
| demon_type | 2 | 恶魔类型 |
| class_id | 2 | 职业ID (实际值 - 1) |
| name_seed | 2 | 名称种子 |
| mon_flags | 2 | 怪物标志 |
| num_stats | 2 | 属性数量 |
| unknown | 2 | 未知 |
| unknown | 28 | 未知 |
| unknown | 20 | 未知 (5×dword) |
| unknown | 16 | 未知 |
| unknown | 10 | 未知 |
| unknown | 2 | 未知 |
| stat_data | stat_data_size | 属性数据 |

## 8. 其他数据段

任务数据、小站数据、玩家属性、技能数据、物品列表等与 0x63 版本格式相同，详见对应文档。
