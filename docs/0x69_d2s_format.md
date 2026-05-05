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
| 0x001C      | 4         | createTime | 创建时间 (v104+中通常为0, 未使用) |
| 0x0020      | 4         | lastSaveTime | 最后保存时间 (Unix时间戳) ★ |
| 0x0024      | 4         | playTime | 游戏时间 (v104+中通常为0xFFFFFFFF, 未使用) |
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
| 0x00 | 48 | SaveTimes[6] (6个存档时间, Windows FILETIME) |
| 0x30 | 24 | Experiences[6] (6个模式经验值) |
| 0x48 | 1 | GuildEmblemColor (公会徽章颜色) |
| 0x49 | 1 | GameVersion (游戏版本, 见下表) ★ |
| 0x4A | 2 | PreviewPadding (填充) |
| 0x4C | 48 | PreviewItems[4] (预览装备: 左手/右手/躯干/头部) |
| 0x7C | 96 | Name (角色名称, UTF-8, null终止) |
| 0xDC | 8 | Unk1 (保留) |

#### GameVersion 枚举 (previewData[0x49])

| 值 | 名称 | 描述 |
|----|------|------|
| 0 | None | 未指定 |
| 1 | Classic | 经典版 (非资料片) |
| 2 | Expansion | 资料片 (毁灭之王) |
| 3 | ReignOfTheWarlock | 术士君临资料片 ★ |

> ★ GameVersion 是 v104+ 新增字段，替代了旧版 charFlags 的 Expansion 位 (0x20)。判断角色是否为资料片时，v104+ 使用 `gameVersion > 1`，v103 及以下使用 `charFlags & 0x20`。

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
| 0x01 | Init | 初始化标志 |
| 0x02 | RealmChar | 战网角色 |
| 0x04 | Hardcore | 硬核角色 |
| 0x08 | Died | 曾经死亡 |
| 0x10 | SaveProcess | 保存处理中 |
| 0x20 | Expansion | 资料片角色 ★ v104+ 不再使用此位，改用 gameVersion |
| 0x40 | Ladder | 天梯角色 |
| 0x80 | NeedsRenaming | 需要重命名 |
| 0x0100-0x1F00 | Progression | 角色进度 (每完成一幕+1) |
| 0x2000 | WeaponSwitch | 武器切换状态 |

> ★ **v104+ 版本注意**：Expansion 位 (0x20) 在 v104+ 中不再用于判断资料片。游戏在从 v103 升级到 v104 时，会清除 charFlags 的 Expansion 位，将信息迁移到 previewData.gameVersion 字段。反向转换时从 gameVersion 恢复此位。

### 3.1 Progression 字段详解

charFlags 的 bit8~bit12 (掩码 0x1F00) 存储角色进度值，每完成一个 Act 加 1：

| Progression 值 | 资料片 (5幕/难度) | 经典版 (4幕/难度) |
|----------------|-------------------|-------------------|
| 0 | Normal 进行中 | Normal 进行中 |
| 1-4 | Normal Act I~IV 完成 | Normal Act I~IV 完成 |
| 5 | Normal 完成 → Nightmare 解锁 | — |
| 6-9 | Nightmare Act I~IV 完成 | Nightmare Act I~IV 完成 |
| 10 | Nightmare 完成 → Hell 解锁 | — |
| 11-14 | Hell Act I~IV 完成 | Hell Act I~IV 完成 |
| 15 | Hell 完成 | — |

最大难度计算：`difficulty = progression / acts_per_difficulty` (0=Normal, 1=NM, 2=Hell)

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
    if self.dwVersion >= 0x69:
        # v104+: 使用 previewData 中的 gameVersion 字段
        return self.gameVersion > 1
    # v97~v103: 使用 charFlags 的 Expansion 位
    if (self.charFlags & 0x20) != 0:
        return True
    # 兜底: 任务数据中 Act 数 >= 5
    if self.QuestInfo and self.QuestInfo.dwActs >= 5:
        return True
    return False
```

> ★ v104+ 版本中，charFlags 的 Expansion 位 (0x20) 不再使用。资料片信息已迁移到 previewData.gameVersion 字段。

## 7.1 时间字段说明

v104+ 版本的时间字段：

| 字段 | 偏移 | 描述 | 实际值 |
|------|------|------|--------|
| createTime | 0x001C | 创建时间 | 通常为 0 (v104+中未使用) |
| lastSaveTime | 0x0020 | 最后保存时间 | Unix 时间戳，可正常转换为日期 ★ |
| playTime | 0x0024 | 游戏时间 | 通常为 0xFFFFFFFF (v104+中未使用) |

> ★ lastSaveTime 是 v104+ 中唯一有效的时间字段，存储为 Unix 时间戳（秒）。createTime 和 playTime 在 D2SSharp 源码中注释分别为 "Creation timestamp" 和 "Total play time (set to -1)"，实际存档中 createTime 始终为 0，playTime 始终为 0xFFFFFFFF。
>
> 0x63 版本 (v97~v103) 中对应字段为 createTime (0)、dwTime (有效Unix时间戳)、playTime (0xFFFFFFFF)。

## 7.2 游戏版本类型判断

```python
def get_game_mode(self):
    game_version = self.gameVersion  # previewData[0x49]
    if game_version >= 3:
        return "ReignOfTheWarlock"  # 术士君临
    elif game_version >= 2:
        return "Expansion"          # 资料片
    elif game_version >= 1:
        return "Classic"            # 经典版
    else:
        return "Unknown"
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

## 8. 共享储物箱格式

游戏存档目录下存在两个版本的共享储物箱文件，分别对应 Classic 和 Expansion 角色：

| 文件名 | 类型 | StashFormat | ItemFormat | 描述 |
|--------|------|-------------|------------|------|
| `SharedStashSoftCoreV2.d2i` | Classic | 1 | 较低 (如 99) | 经典版软核共享箱子 |
| `SharedStashHardCoreV2.d2i` | Classic | 1 | 较低 (如 99) | 经典版硬核共享箱子 |
| `ModernSharedStashSoftCoreV2.d2i` | Modern | 2 | 较高 (如 105) | 资料片软核共享箱子 ★ |
| `ModernSharedStashHardCoreV2.d2i` | Modern | 2 | 较高 (如 105) | 资料片硬核共享箱子 ★ |

> ★ Modern 箱子对应 gameVersion > 1 (Expansion/ReignOfTheWarlock) 的角色，Classic 箱子对应 gameVersion = 1 (Classic) 的角色。角色选择使用哪个箱子由 gameVersion (v104+) 或 charFlags.Expansion (v103-) 决定。

### 8.1 文件总体结构

共享储物箱文件由多个储物箱标签页 (Tab) 顺序排列组成，每个标签页有独立的头部和体部。

```
[Tab1][Tab2][Tab3]...[TabN]
```

每个标签页的大小由其头部的 `TabSize` 字段指定，读取完一个标签页后跳转到下一个标签页的起始位置。

### 8.2 单个标签页头部 (64 字节固定)

| 偏移量 (字节) | 大小 (字节) | 字段 | 描述 |
|-------------|-----------|------|------|
| 0 | 4 | Magic | 魔法数 (0xAA55AA55) |
| 4 | 4 | StashFormat | 储物箱格式版本 |
| 8 | 4 | ItemFormat | 物品格式版本 (存档版本号) |
| 12 | 4 | Gold | 金币数量 |
| 16 | 2 | TabSize | 本标签页总大小 (含头部, 字节) |
| 18 | 2 | Season | 赛季编号 (0=非赛季) |
| 20 | 1 | TabType | 标签页类型 (见 8.3) |
| 21 | 43 | Reserved | 保留/填充数据 |

### 8.3 标签页类型 (TabType)

仅在 StashFormat >= 2 时有效，StashFormat < 2 时强制设为 Normal (0)。

| 值 | 类型 | 描述 | 体部内容 |
|----|------|------|----------|
| 0 | Normal | 普通储物箱 | 物品列表 (JM 段) |
| 1 | AdvancedStash | 高级储物箱 | 物品列表 (JM 段) |
| 2 | Chronicle | 编年史标签页 | 编年史数据 (0xC0EAEDC0) |

### 8.4 标签页体部

**Normal / AdvancedStash 类型**：

体部是标准的物品列表，以魔法数 `0x4D4A` 开始：

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| wMajic | 16 | 魔法数 (0x4D4A) |
| nItems | 16 | 物品总数 |
| vItems | 可变 | 每个物品的详细数据 |

物品解析使用标签页头部的 ItemFormat 作为版本号。

**Chronicle 类型**：

体部是编年史数据，以魔法数 `0xC0EAEDC0` 开始：

| 字段 | 大小 (字节) | 描述 |
|------|-----------|------|
| Magic | 4 | 魔法数 (0xC0EAEDC0) |
| Version | 2 | 编年史版本 |
| SetCount | 2 | 套装条目数 |
| UniqueCount | 2 | 独特物品条目数 |
| RunewordCount | 2 | 符文之语条目数 |
| Reserved | 8 | 保留数据 |
| SetEntries | SetCount × 10 | 套装条目 |
| UniqueEntries | UniqueCount × 10 | 独特物品条目 |
| RunewordEntries | RunewordCount × 10 | 符文之语条目 |
| TrailingData | 可变 | 尾部数据 |

每个条目 (10 字节)：

| 字段 | 大小 (字节) | 描述 |
|------|-----------|------|
| ItemId | 4 | 物品ID (items.txt 行索引) |
| Source | 2 | 来源标识 (套装/独特非零, 符文之语为0) |
| Timestamp | 4 | 创建时间戳 |

### 8.5 AdvancedStash 子类型

高级储物箱根据内容物分为三种子类型：

| 子类型 | 布局 (列×行) | 内容 |
|--------|-------------|------|
| Gem (宝石) | 7×5 | 宝石 + 宝石头 |
| Rune (符文) | 9×4 | 符文 #01-#33 |
| Material (材料) | 10×3 | 药水 + 钥匙 + 材料 |

子类型根据物品类型自动判断：如果标签页中只有符文则为 Rune 子类型，只有宝石则为 Gem 子类型，只有材料则为 Material 子类型。混合内容时按数量最多的类型判断。

### 8.6 StashFormat 版本差异

| StashFormat | 描述 |
|-------------|------|
| 1 | 0x63 版本格式，无 TabType 字段，所有标签页为 Normal |
| 2 | 0x69 版本格式，支持 TabType，新增 AdvancedStash 和 Chronicle 标签页 |

StashFormat >= 2 时，ItemFormat >= 100 的标签页可能包含 Chronicle 和 AdvancedStash 类型。

### 8.7 序列化注意事项

写入标签页时，TabSize 字段需要先写 0 占位，序列化完体部后再回填实际大小。每个标签页的读取位置由 `startPos + TabSize` 决定，与实际解析消耗的字节数无关。

## 9. 其他数据段

任务数据、小站数据、玩家属性、技能数据、物品列表等格式与 0x63 版本基本相同，但注意以下差异：

- 物品列表使用 0x69 版本的物品格式，详见 [0x69_item_format.md](0x69_item_format.md)
- 属性解析使用 0x69 版本的 ItemStatCost.txt
- 小站格式与 0x63 相同，详见 [waypoint_format.md](waypoint_format.md)
- 玩家属性格式与 0x63 相同，详见 [0x63_player_stat.md](0x63_player_stat.md)
- 新增恶魔数据段 (gameVersion >= 3)
- 新增术士职业 (charClass = 7)
