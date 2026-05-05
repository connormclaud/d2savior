# 0x69 版本存档格式分析

## 1. 概述

0x69 版本对应 D2R 资料片术士君临 (Reign of the Warlock)，新增了术士职业。与 0x63 (D2R 基础版) 相比，头部结构有重大变化，增加了 previewData、恶魔数据等新结构。

## 2. 与 0x63 版本的主要差异

### 2.1 头部结构

0x69 版本的头部与 0x63 完全不同：

| 差异点 | 0x63 | 0x69 |
|--------|------|------|
| 角色名称 | 0x0014 (16字节直接存储) | previewData 内偏移 0x7C (96字节, UTF-8) |
| charType/charFlags | 1字节 (charType) | 4字节 (charFlags, 含Progression位) |
| 时间字段 | createTime(0) + dwTime(有效) + playTime(0xFFFFFFFF) | createTime(0) + lastSaveTime(有效) + playTime(0xFFFFFFFF) |
| 雇佣兵数据 | dwMercControl/wMercName/wMercType/dwMercExp | mercFlags/mercSeed/mercNameIndex/mercHirelingId/mercExperience |
| 预览数据 | previewPrefix(76字节) + NamePTR(64字节) + previewSuffix(4字节) | previewData(228字节, 含gameVersion/SaveTimes/Name) |

### 2.2 物品解析

| 差异点 | 0x63 | 0x69 |
|--------|------|------|
| 物品类型名称 | 4字节 ASCII (32位) | Huffman 编码 (9位长度 + 变长数据) |
| 版本特定数据 | 5位未知 + 10位版本 | 5位未知 + 10位版本 + 1位未知 |
| 符文之语 | wRune (16位) | wRune (16位) + bRuneWordComplete (1位) |
| 个性化名称编码 | 7位 ASCII | 8位 ASCII |

### 2.3 新增数据段

0x69 版本新增了恶魔数据段 (Demon)，仅在 gameVersion >= 3 时出现，以魔法数 `0x666C` 标识。

## 3. 关键发现

### 3.1 previewData

0x69 版本新增 228 字节的 previewData，包含：
- 偏移 0x49: gameVersion (游戏版本，3=术士君临资料片)
- 偏移 0x7C: Name (角色名称, UTF-8, null终止)

### 3.2 角色名称

0x69 版本的角色名称存储在 previewData 中，使用 UTF-8 编码，最长 96 字节。

### 3.3 雇佣兵判断

0x69 版本通过 mercSeed/mercNameIndex/mercExperience 任一非零来判断是否有雇佣兵。

### 3.4 资料片判断

0x69 版本 (v104+) 通过 `previewData[0x49]` (gameVersion) 判断游戏模式：
- gameVersion >= 3: 术士君临 (ReignOfTheWarlock)
- gameVersion >= 2: 资料片 (Expansion)
- gameVersion == 1: 经典版 (Classic)

v103 及以下版本使用 `charFlags & 0x20` 判断资料片。

### 3.5 时间字段

v104+ 版本中 createTime 和 playTime 均为无效默认值（0 和 0xFFFFFFFF），实际可用的时间数据是 lastSaveTime（Unix 时间戳）。v103 及以下版本对应字段为 dwTime。

### 3.6 Huffman 编码

0x69 版本使用 Huffman 编码压缩物品类型名称，编码表存储在 `huffman_tree.json` 中。

## 4. 详细格式

详见以下文档：
- [0x69_d2s_format.md](0x69_d2s_format.md) - 0x69 版本总体格式
- [0x69_item_format.md](0x69_item_format.md) - 0x69 版本物品格式
- [0x63_player_stat.md](0x63_player_stat.md) - 玩家属性格式 (两版本相同)
