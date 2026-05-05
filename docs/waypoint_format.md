# D2R 小站格式

## 1. 概述

小站 (Waypoint) 数据存储了角色在三个难度（Normal/Nightmare/Hell）中已激活的小站信息。0x63 和 0x69 版本使用相同的小站格式。

## 2. Waypoints 结构 (80 字节)

| 字段 | 大小 | 描述 |
|------|------|------|
| wMajic | 2 | 魔法数 (0x5357 = "WS") |
| unknown | 4 | 版本号 (通常为 1) |
| wSize | 2 | 段大小 (0x0050 = 80) |
| wp[0] | 24 | Normal 难度小站数据 |
| wp[1] | 24 | Nightmare 难度小站数据 |
| wp[2] | 24 | Hell 难度小站数据 |

## 3. WaypointData 结构 (24 字节)

每个难度的小站数据：

| 字段 | 大小 | 描述 |
|------|------|------|
| unknown | 2 | 头部 (通常为 0x0102) |
| Waypoints[5] | 5 | 小站位图 (39位有效 + 9位填充) |
| unknown2[17] | 17 | 保留 (全0) |

### 3.1 Waypoints 位图详解

5 字节 (40位) 中前 39 位为小站激活标志，最后 1 位为填充：

| 位范围 | 幕 | 小站数 | 描述 |
|--------|-----|--------|------|
| 0-8 | Act I | 9 | 罗格营地 → 修道院 |
| 9-17 | Act II | 9 | 鲁高因 → 神秘避难所 |
| 18-26 | Act III | 9 | 库拉斯特 → 混沌避难所 |
| 27-29 | Act IV | 3 | 群魔堡垒 → 混沌避难所 |
| 30-38 | Act V | 9 | 哈洛加斯 → 世界之石大殿 |
| 39 | — | — | 填充位 |

### 3.2 各幕小站详细列表

#### Act I (9 个小站, 位 0-8)

| 位 | 全局索引 | 小站名称 |
|----|----------|----------|
| 0 | 0 | Rogue Encampment (罗格营地) |
| 1 | 1 | Cold Plains (冰冷之原) |
| 2 | 2 | Stony Field (石块旷野) |
| 3 | 3 | Dark Wood (黑暗森林) |
| 4 | 4 | Black Marsh (黑色荒地) |
| 5 | 5 | Outer Cloister (外侧回廊) |
| 6 | 6 | Inner Cloister (内侧回廊) |
| 7 | 7 | Catacombs (地下墓穴) |
| 8 | 8 | Monastery Gate (修道院) |

#### Act II (9 个小站, 位 9-17)

| 位 | 全局索引 | 小站名称 |
|----|----------|----------|
| 0 | 9 | Lut Gholein (鲁高因) |
| 1 | 10 | Sewers (下水道) |
| 2 | 11 | Dry Hills (干燥高地) |
| 3 | 12 | Halls of the Dead (死灵大厅) |
| 4 | 13 | Far Oasis (遥远绿洲) |
| 5 | 14 | Lost City (失落城市) |
| 6 | 15 | Palace Cellar (皇宫地窖) |
| 7 | 16 | Arcane Sanctuary (神秘避难所) |
| 8 | 17 | Canyon of the Magi (术士峡谷) |

#### Act III (9 个小站, 位 18-26)

| 位 | 全局索引 | 小站名称 |
|----|----------|----------|
| 0 | 18 | Kurast Docks (库拉斯特海港) |
| 1 | 19 | Spider Forest (蜘蛛森林) |
| 2 | 20 | Great Marsh (大沼地) |
| 3 | 21 | Flayer Jungle (剥皮丛林) |
| 4 | 22 | Lower Kurast (库拉斯特下层) |
| 5 | 23 | Upper Kurast (库拉斯特上层) |
| 6 | 24 | Travincal (崔凡克) |
| 7 | 25 | Durance of Hate (憎恨之牢) |
| 8 | 26 | Pandemonium Fortress (混沌避难所) |

#### Act IV (3 个小站, 位 27-29)

| 位 | 全局索引 | 小站名称 |
|----|----------|----------|
| 0 | 27 | Pandemonium Fortress (群魔堡垒) |
| 1 | 28 | River of Flame (火焰之河) |
| 2 | 29 | Chaos Sanctuary (混沌避难所) |

#### Act V (9 个小站, 位 30-38)

| 位 | 全局索引 | 小站名称 |
|----|----------|----------|
| 0 | 30 | Harrogath (哈洛加斯) |
| 1 | 31 | Frigid Highlands (冰冻高原) |
| 2 | 32 | Arreat Plateau (亚瑞特高原) |
| 3 | 33 | Crystalline Passage (水晶通道) |
| 4 | 34 | Halls of Pain (痛苦之厅) |
| 5 | 35 | Glacial Trail (冰河路径) |
| 6 | 36 | Frozen Tundra (冰冻苔原) |
| 7 | 37 | The Ancients' Way (远古之路) |
| 8 | 38 | Worldstone Keep (世界之石大殿) |

## 4. 解析逻辑

### 4.1 d2savior 当前实现 (字节级)

```python
class WaypointData:
    def deserialize(self, bs):
        self.unknown = bs.read_word()       # 0x0102
        for i in range(5):
            self.Waypoints[i] = bs.read_byte()  # 5字节小站位图
        for i in range(17):
            self.unknown2[i] = bs.read_byte()   # 17字节保留

class Waypoints:
    def deserialize(self, bs):
        self.wMajic = bs.read_word()        # 0x5357
        self.unknown = bs.read_dword()      # 版本号
        self.wSize = bs.read_word()         # 0x0050
        for i in range(3):
            self.wp[i].deserialize(bs)
```

### 4.2 D2SSharp 实现 (位级)

D2SSharp 使用位级读取，按幕分别读取不同位数：

```csharp
// 每个难度
header = reader.ReadUInt16();        // 2字节
actI = reader.ReadBits(9);           // 9位
actII = reader.ReadBits(9);          // 9位
actIII = reader.ReadBits(9);         // 9位
actIV = reader.ReadBits(3);          // 3位
actV = reader.ReadBits(9);           // 9位
padding = reader.ReadBits(9);        // 9位填充
reserved = reader.ReadBytes(16);     // 16字节保留
```

> 注意：两种实现读取的总字节数相同 (24字节/难度)，但 D2SSharp 的位级实现更精确地按幕分割了小站位图。d2savior 的字节级实现将 5 字节作为原始数据处理，需要额外的位操作来提取各幕小站。

## 5. 小站位图提取方法

从 Waypoints[5] 字节数组中提取各幕小站：

```python
def get_waypoint(waypoints_bytes, global_index):
    """获取指定全局索引的小站是否激活"""
    if global_index < 0 or global_index > 38:
        return False
    byte_index = global_index // 8
    bit_index = global_index % 8
    return (waypoints_bytes[byte_index] & (1 << bit_index)) != 0

def set_waypoint(waypoints_bytes, global_index, active):
    """设置指定全局索引的小站激活状态"""
    byte_index = global_index // 8
    bit_index = global_index % 8
    if active:
        waypoints_bytes[byte_index] |= (1 << bit_index)
    else:
        waypoints_bytes[byte_index] &= ~(1 << bit_index)
```

## 6. 与任务数据的关联

小站数据与 QuestInfoData 中的 wTraval 字段有关联：

| wTraval 字段 | 描述 | 对应小站 |
|-------------|------|----------|
| wTraval1 | 从 Act I 旅行到 Act II | Act I 最后一个小站 (位8) |
| wTraval2 | 从 Act II 旅行到 Act III | Act II 最后一个小站 (位17) |
| wTraval3 | 从 Act III 旅行到 Act IV | Act III 最后一个小站 (位26) |
| wTraval4 | 从 Act IV 旅行到 Act V | Act IV 最后一个小站 (位29) |

> diablo_edit 的 DlgWayPoints.cpp 中将 wTraval 与小站数据关联：
> ```cpp
> character.QuestInfo.QIData[i].wTraval1 = m_bWayData[i][10] ? 1 : 0;
> character.QuestInfo.QIData[i].wTraval2 = m_bWayData[i][19] ? 1 : 0;
> character.QuestInfo.QIData[i].wTraval3 = m_bWayData[i][28] ? 1 : 0;
> character.QuestInfo.QIData[i].wTraval4 = m_bWayData[i][31] ? 1 : 0;
> ```
> 注意：这里的索引 10/19/28/31 是小站 UI 列表中的位置（包含起始城镇），不是位图中的位索引。
