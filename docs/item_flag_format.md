# D2R 物品标志位格式

## 1. 概述

D2R 物品使用 32 位标志位 (flags) 存储物品状态信息。标志位的读取方式取决于版本：

- **D2R 格式 (version > 96)**：整体读取 32 位 `flags`，通过位掩码提取各标志
- **Classic 格式 (version <= 96)**：逐位读取 (多个 `read_bits(1)`)

0x63 和 0x69 版本均使用 D2R 格式。

## 2. 标志位定义

### 2.1 32位 flags 整体布局

| 位 | 位掩码 | 标志 | 描述 |
|----|--------|------|------|
| 0 | 0x00000001 | NewItem | 新物品 |
| 1 | 0x00000002 | Target | 目标 |
| 2 | 0x00000004 | Targeting | 正在瞄准 |
| 3 | 0x00000008 | Deleted | 已删除 |
| 4 | 0x00000010 | Identified | 已鉴定 |
| 5 | 0x00000020 | HasQuantity | 有数量 |
| 6 | 0x00000040 | SwitchIn | 武器切换进入 |
| 7 | 0x00000080 | SwitchOut | 武器切换离开 |
| 8 | 0x00000100 | Broken | 已损坏 |
| 9 | 0x00000200 | Repaired | 已修复 |
| 10 | 0x00000400 | (undefined) | 未定义 |
| 11 | 0x00000800 | Socketed | 有孔 |
| 12 | 0x00001000 | NoSell | 不可出售 |
| 13 | 0x00002000 | InStore | 在商店 |
| 14 | 0x00004000 | NoEquip | 不可装备 |
| 15 | 0x00008000 | Named | 已命名 |
| 16 | 0x00010000 | IsEar | 耳朵物品 |
| 17 | 0x00020000 | StarterItem | 新手物品 |
| 18 | 0x00040000 | (undefined) | 未定义 |
| 19 | 0x00080000 | Init | 初始化标志 (读取时清除) |
| 20 | 0x00100000 | (undefined) | 未定义 |
| 21 | 0x00200000 | CompactSave | 简单物品 (紧凑存储) |
| 22 | 0x00400000 | Ethereal | 无形物品 |
| 23 | 0x00800000 | JustSaved | 刚保存标志 |
| 24 | 0x01000000 | Personalized | 个性化物品 |
| 25 | 0x02000000 | LowQuality/Gamble | 低品质/赌博标志 |
| 26 | 0x04000000 | Runeword | 符文之语 |
| 27 | 0x08000000 | Duplicated | 已复制 |
| 28 | 0x10000000 | Chronicle | 编年史标志 (v100+) |
| 29 | 0x20000000 | ChronicleCompact | 编年史紧凑标志 (v100+) |
| 30 | 0x40000000 | (undefined) | 未定义 |
| 31 | 0x80000000 | (undefined) | 未定义 |

### 2.2 D2R 逐位读取顺序

D2R 格式虽然整体读取 32 位 flags，但内部按位顺序读取，某些位是组合标志：

| 读取顺序 | 位数 | 字段名 | 对应 flags 位 | 描述 |
|----------|------|--------|--------------|------|
| 1 | 1 | bQuest | bit 0 (NewItem) | 任务物品标志 |
| 2 | 3 | iTargetDelFlags | bit 1~3 (Target+Targeting+Deleted) | 目标/删除组合标志 |
| 3 | 1 | bIdentified | bit 4 | 已鉴定 |
| 4 | 3 | iSwitchInOutFlags | bit 5~7 (HasQuantity+SwitchIn+SwitchOut) | 切换/数量组合标志 |
| 5 | 1 | bDisabled | bit 8 (Broken) | 禁用/损坏 |
| 6 | 2 | iRepairFlags | bit 9~10 (Repaired+undefined) | 修复组合标志 |
| 7 | 1 | bSocketed | bit 11 | 有孔 |
| 8 | 1 | bNoSell | bit 12 | 不可出售 |
| 9 | 1 | bNew | bit 13 (InStore) | 新物品 |
| 10 | 1 | bBadEquipped | bit 14 (NoEquip) | 装备不当 |
| 11 | 1 | bNamed | bit 15 | 已命名 |
| 12 | 1 | bEar | bit 16 | 耳朵物品 |
| 13 | 1 | bNewbie | bit 17 (StarterItem) | 新手物品 |
| 14 | 3 | iInitFlags | bit 18~20 (undefined+Init+undefined) | 初始化组合标志 |
| 15 | 1 | bSimple | bit 21 (CompactSave) | 紧凑存储 |
| 16 | 1 | bEthereal | bit 22 | 无形 |
| 17 | 1 | bJustSaved | bit 23 | 刚保存 |
| 18 | 1 | bPersonalized | bit 24 | 个性化 |
| 19 | 1 | bLowQuality | bit 25 | 低品质/赌博 |
| 20 | 1 | bRuneWord | bit 26 | 符文之语 |
| 21 | 5 | iDuplicateChronicle | bit 27~31 (Duplicated+Chronicle+ChronicleCompact+2×undefined) | 复制/编年史组合标志 |

> 注意：D2R 逐位读取时，某些标志的语义与 32 位 flags 掩码不完全对应。例如 bit 0 在 32 位 flags 中是 NewItem，但在逐位读取时第一个 bit 被称为 bQuest。这是因为 D2R 格式在读取时对标志位做了重新映射。

## 3. 重要标志处理逻辑

### 3.1 LowQuality / 赌博物品

如果 `LowQuality` (0x02000000) 标志被设置，表示该物品是赌博物品：
1. 记录该标志
2. 清除 flags 中的 LowQuality 位
3. 如果是完整物品，将品质设为 Inferior (1)，跳过后续品质数据读取

### 3.2 Init 标志

`Init` (0x00080000) 标志在读取时清除，写入时也不设置。

### 3.3 JustSaved 标志

`JustSaved` (0x00800000) 标志在写入时始终设置。

### 3.4 CompactSave 标志

`CompactSave` (0x00200000) 决定物品使用紧凑格式还是完整格式。紧凑物品只包含最少数据，没有扩展信息和属性列表。

### 3.5 Chronicle 标志

`Chronicle` (0x10000000) 和 `ChronicleCompact` (0x20000000) 是 v100+ 新增标志，用于编年史数据。

## 4. Classic 格式对比 (version <= 96)

Classic 格式逐位读取，每个标志独立读取 1 位：

| 读取顺序 | 标志 | 描述 |
|----------|------|------|
| 1 | bIdentified | 已鉴定 |
| 2 | bShiftSwitch | 切换 |
| 3 | bLeftAttack | 左手攻击 |
| 4 | bHasQuantity | 有数量 |
| 5 | bSimple | 紧凑存储 |
| 6 | bEthereal | 无形 |
| 7 | bPersonalized | 个性化 |
| 8 | bRuneWord | 符文之语 |
| 9 | bVarGfx | 可变图形 |
| 10 | bShort | 短格式 |
| 11 | bMaxDur | 有最大耐久 |
| 12 | bSocketed | 有孔 |
| 13 | bUnknown | 未知 |
| 14 | bEar | 耳朵物品 |
| 15 | bStarterItem | 新手物品 |
| 16 | bSimple2 | 紧凑存储2 |
| 17 | bRunewordComplete | 符文之语完成 |

Classic 格式的标志位数量和含义与 D2R 格式有显著差异。
