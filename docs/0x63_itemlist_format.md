# 0x63 版本物品列表格式

## 1. 物品列表结构

物品列表以魔法数 `0x4D4A` 开始，后跟物品数量，然后是每个物品的数据。

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| wMajic | 16 | 魔法数 (0x4D4A) |
| nItems | 16 | 物品总数 |
| vItems | 可变 | 每个物品的详细数据 |

## 2. 单个物品结构 (0x63 版本 - D2R 格式)

0x63 版本属于 D2R (`version >= 0x61`)，使用 `_read_data_d2r` 方法解析物品。与 Classic (<0x61) 的 `_read_data_classic` 方法有根本性差异。

### 2.1 物品头部

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| wMajic | 16 | 物品魔法数 (0x4D4A)，仅 version <= 96 时读取 |
| dwVersion | 32 | 物品版本号，仅 version <= 96 时读取 |
| flags | 32 | 物品标志位 (见 2.2) |

注意：当 version > 96 时，不读取 wMajic 和 dwVersion，物品版本继承存档版本。

### 2.2 物品标志位 (flags)

D2R 格式将所有标志打包为 32 位整数，通过位掩码提取。详细的标志位定义和逐位读取顺序见 [item_flag_format.md](item_flag_format.md)。

| 标志 | 位掩码 | 描述 |
|------|--------|------|
| NewItem | 0x00000001 | 新物品 |
| Target | 0x00000002 | 目标 |
| Targeting | 0x00000004 | 正在瞄准 |
| Deleted | 0x00000008 | 已删除 |
| Identified | 0x00000010 | 已鉴定 |
| HasQuantity | 0x00000020 | 有数量 |
| SwitchIn | 0x00000040 | 武器切换进入 |
| SwitchOut | 0x00000080 | 武器切换离开 |
| Broken | 0x00000100 | 已损坏 |
| Repaired | 0x00000200 | 已修复 |
| Socketed | 0x00000800 | 有孔 |
| NoSell | 0x00001000 | 不可出售 |
| InStore | 0x00002000 | 在商店 |
| NoEquip | 0x00004000 | 不可装备 |
| Named | 0x00008000 | 已命名 |
| IsEar | 0x00010000 | 耳朵物品 |
| StarterItem | 0x00020000 | 新手物品 |
| Init | 0x00080000 | 初始化标志 (读取时清除) |
| CompactSave | 0x00200000 | 简单物品 (紧凑存储) |
| Ethereal | 0x00400000 | 无形物品 |
| JustSaved | 0x00800000 | 刚保存标志 |
| Personalized | 0x01000000 | 个性化物品 |
| LowQuality/Gamble | 0x02000000 | 低品质/赌博标志 |
| Runeword | 0x04000000 | 符文之语 |
| Duplicated | 0x08000000 | 已复制 |
| Chronicle | 0x10000000 | 编年史标志 (v100+) |
| ChronicleCompact | 0x20000000 | 编年史紧凑标志 (v100+) |

重要处理逻辑：
- 如果 `LowQuality` (0x02000000) 标志被设置，表示该物品是赌博物品，读取后清除该标志
- `Init` (0x00080000) 标志在读取时清除
- `CompactSave` 标志决定物品使用紧凑格式还是完整格式

### 2.3 物品格式版本 (wVersion)

D2R 格式的物品版本编码与 Classic 不同：

**D2R 格式 (version > 96)**：

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| hf | 1 | 高版本标志 |
| vv | 2 | 版本值 |

解码规则：
- 如果 `hf = 1`：`wVersion = vv + 99`（编码 99-102）
- 如果 `hf = 0`：`wVersion = vv`（编码 0-3）

**Classic 格式 (version <= 96)**：

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| wVersion | 10 | 物品版本号 (0-1023) |

### 2.4 位置信息

位置数据根据 mode (3位) 的值有不同的读取方式：

| 字段 | 大小 (位) | 条件 | 描述 |
|------|-----------|------|------|
| mode | 3 | 始终 | 物品模式/位置类型 |

**mode = 3 或 5 (地面/掉落中)**：

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| GroundX | 16 | 地面 X 坐标 |
| GroundY | 16 | 地面 Y 坐标 |

**其他 mode (装备/存储/腰带等)**：

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| BodyLocation | 4 | 装备位置 |
| InvX | 4 | 背包 X 坐标 (0-15) |
| InvY | 4 | 背包 Y 坐标 (0-15) |
| StorePage | 3 | 存储页 (存储时 +1，读取时 -1) |

mode 值含义：

| 值 | 模式 | 描述 |
|----|------|------|
| 0 | Stored | 存储中 (背包/箱子/方块) |
| 1 | Equipped | 已装备 |
| 2 | InBelt | 在腰带 |
| 3 | OnGround | 在地面 |
| 4 | OnCursor | 在光标上 |
| 5 | Dropping | 掉落中 |
| 6 | Socketed | 镶嵌在其他物品中 |

StorePage 值含义 (存储值 = 内部值 + 1)：

| 内部值 | 存储值 | 描述 |
|--------|--------|------|
| 0 | 1 | 主背包 (Inventory) |
| 1 | 2 | 装备页 (Equip) |
| 2 | 3 | 交易页 (Trade) |
| 3 | 4 | 赫拉迪克方块 (Cube) |
| 4 | 5 | 储物箱 (Stash) |
| 5 | 6 | 腰带 (Belt) |

## 3. 紧凑物品 (CompactSave = true)

紧凑物品只包含最少的数据，没有扩展信息和属性列表。

### 3.1 耳朵物品 (IsEar = true)

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| EarFileIndex | 3 | 被杀者职业文件索引 |
| EarLevel | 7 | 被杀者等级 |
| EarName | 变长 | 被杀者名称 (8位字符, null终止) |

### 3.2 普通紧凑物品

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| sTypeName | 32 | 物品类型代码 (4字节, 逐字节读取) |

#### 3.2.1 金币紧凑物品

如果物品类型为 `gld `：

| 字段 | 大小 (位) | 条件 | 描述 |
|------|-----------|------|------|
| bigGold | 1 | 始终 | 大额金币标志 |
| GoldAmount | 32 | bigGold=true | 金币数量 |
| GoldAmount | 12 | bigGold=false | 金币数量 |
| PlayerGold | 1 | version > 96 | 玩家金币标志 |

#### 3.2.2 任务难度 (version > 92)

如果物品是任务物品且需要难度检查 (`quest > 0 && questdiffcheck`)：

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| QuestDifficulty | stat 356 的 save_bits | 任务难度值 |

值计算：`value = (raw - save_add) << val_shift`

#### 3.2.3 Realm 数据 (version > 86)

| 字段 | 大小 (位) | 条件 | 描述 |
|------|-----------|------|------|
| realm_flag | 1 | 始终 | Realm 数据标志 |
| RealmData | 2×32 | realm_flag=true, version <= 93 | Realm 数据 |
| RealmData | 3×32 | realm_flag=true, 93 < version <= 96 | Realm 数据 |
| RealmData | 4×32 | realm_flag=true, version > 96 | Realm 数据 |

#### 3.2.4 高级储物箱堆叠大小 (version > 99)

见第 7 节。

## 4. 完整物品 (CompactSave = false)

### 4.1 物品类型名称

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| sTypeName | 32 | 物品类型代码 (4字节, 逐字节读取) |

### 4.2 扩展物品信息

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| nGems | 3 | 孔中物品数量 (0-7) |
| dwGUID | 32 | 物品全局唯一ID (随机种子) |
| iDropLevel | 7 | 掉落等级 (物品等级, 最小值1) |
| iQuality | 4 | 品质等级 |
| bVarGfx | 1 | 可变图形标志 |
| iVarGfx | 3 | bVarGfx=true | 可变图形索引 |
| bAutoAffix | 1 | 自动词缀标志 |
| wAutoAffix | 11 | bAutoAffix=true | 自动词缀ID |

注意：`bAutoAffix` 在旧文档中称为 `bClass`/`wClass`，实际含义是自动魔法词缀。读取后的值需要加上 `nAutoMagicOffset`。

### 4.3 品质特定数据

品质 (iQuality) 决定了后续读取的数据：

| iQuality | 品质 | 额外数据 |
|----------|------|----------|
| 1 | Inferior (劣质) | InferiorFileIndex (3位) |
| 2 | Normal (普通) | 特殊子类型数据 (见 4.3.1) |
| 3 | Superior (超强) | SuperiorFileIndex (3位) |
| 4 | Magic (魔法) | PrefixId (11位) + SuffixId (11位) |
| 5 | Set (套装) | SetUniqueFileIndex (12位) |
| 6 | Rare (稀有) | LongName (见 4.3.2) |
| 7 | Unique (独特) | SetUniqueFileIndex (12位) |
| 8 | Craft (合成) | LongName (同 Rare 格式) |

#### 4.3.1 Normal 品质特殊子类型

Normal 品质的物品根据类型有不同额外数据：

**护身符 (is_charm = true)**：

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| HasPrefix | 1 | 有前缀标志 |
| PrefixId | 11 | HasPrefix=true | 魔法前缀ID (需加 nAutoMagicOffset) |
| SuffixId | 11 | HasPrefix=false | 魔法后缀ID |

**怪物身体部位 (is_body_part=true, is_player_body_part=false)**：

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| BodyPartFileIndex | 10 | 身体部位文件索引 |

**卷轴/书 (is_scroll_or_book=true)**：

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| SpellType | 5 | 法术类型 |

**其他 Normal 物品**：无额外数据。

#### 4.3.2 LongName 结构 (Rare/Crafted 名称)

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| iName1 | 8 | 名称词缀1 ID |
| iName2 | 8 | 名称词缀2 ID |
| bPref1 | 1 | 有前缀1 |
| wPref1 | 11 | bPref1=true | 前缀1 ID (需加 nAutoMagicOffset) |
| bSuff1 | 1 | 有后缀1 |
| wSuff1 | 11 | bSuff1=true | 后缀1 ID |
| bPref2 | 1 | 有前缀2 |
| wPref2 | 11 | bPref2=true | 前缀2 ID (需加 nAutoMagicOffset) |
| bSuff2 | 1 | 有后缀2 |
| wSuff2 | 11 | bSuff2=true | 后缀2 ID |
| bPref3 | 1 | 有前缀3 |
| wPref3 | 11 | bPref3=true | 前缀3 ID (需加 nAutoMagicOffset) |
| bSuff3 | 1 | 有后缀3 |
| wSuff3 | 11 | bSuff3=true | 后缀3 ID |

注意：Rare/Crafted 的词缀对在存档文件中始终读取，不受鉴定状态影响 (C++: bServer=TRUE for save files)。

### 4.4 符文之语数据 (Runeword = true)

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| wRune | 16 | 符文之语ID |

### 4.5 个性化名称 (Personalized = true, 非 Ear)

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| sPersonName | 8×变长 | 个性化名称 (8位字符, null终止, 最长16字符) |

注意：0x62+ 版本使用 8 位字符编码，更早版本使用 7 位。

### 4.6 Realm 数据

同紧凑物品的 Realm 数据格式 (见 3.2.3)。

### 4.7 类型特定信息

#### 4.7.1 防御值 (护甲物品, has_def=true)

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| iDefence | stat 31 (ArmorClass) 的 save_bits | 防御原始值 |

实际防御值 = 原始值 - save_add (stat 31)

防御值的位宽不是固定的 11 位，而是由 `ItemStatCost.txt` 中 stat 31 (ArmorClass) 的 `save_bits` 决定。

#### 4.7.2 耐久度 (has_dur=true)

| 字段 | 大小 (位) | 条件 | 描述 |
|------|-----------|------|------|
| iMaxDurability | stat 73 (MaxDurability) 的 save_bits | 始终 | 最大耐久度原始值 |
| iCurDur | stat 72 (Durability) 的 save_bits | iMaxDurability > 0 | 当前耐久度原始值 |

实际值 = 原始值 - save_add

耐久度的位宽由 `ItemStatCost.txt` 中对应 stat 的 `save_bits` 决定。

#### 4.7.3 金币物品 (is_gold=true)

| 字段 | 大小 (位) | 条件 | 描述 |
|------|-----------|------|------|
| bigGold | 1 | 始终 | 大额金币标志 |
| GoldAmount | 32 | bigGold=true | 金币数量 |
| GoldAmount | 12 | bigGold=false | 金币数量 |
| PlayerGold | 1 | version > 96 | 玩家金币标志 |

#### 4.7.4 堆叠数量

数量读取方式取决于版本：

**version > 104**：

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| qty_flag | 1 | 有数量标志 |
| iQuantity | 9 | qty_flag=true | 堆叠数量 |

所有物品都有此字段，不仅仅是堆叠物品。

**version <= 104**：

| 字段 | 大小 (位) | 条件 | 描述 |
|------|-----------|------|------|
| iQuantity | 9 | is_stacked=true | 堆叠数量 |

仅堆叠物品有此字段。

#### 4.7.5 孔数 (Socketed = true)

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| iSocket | stat 194 (NumSockets) 的 save_bits | 孔数 |

孔数的位宽由 `ItemStatCost.txt` 中 stat 194 的 `save_bits` 决定，不是固定的 4 位。

如果读取到的孔数 < 1，强制设为 1。

### 4.8 套装属性标志 (iQuality == 5)

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| aHasSetPropList | 5×1 | 5个套装属性列表标志 (掩码) |

### 4.9 属性列表

详见 [0x63_item_property_format.md](0x63_item_property_format.md)。

### 4.10 套装属性列表

如果 aHasSetPropList[i] 为 true，则读取对应的属性列表。最多 5 个附加属性列表。

### 4.11 符文之语属性列表

如果 Runeword 为 true，在基础属性列表和套装属性列表之后读取符文之语属性列表。

### 4.12 编年史数据 (version > 99, Chronicle 标志)

如果 `flags & 0x10000000` (Chronicle) 为 true：

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| ChronicleId | 16 | 编年史ID |

如果 `flags & 0x20000000` (ChronicleCompact) 为 true：

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| CompactData | 64 | 紧凑编年史数据 |

如果 ChronicleCompact 为 false：

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| Timestamp | 32 | 时间戳 |
| RecipientCount | 4 | 接收者数量 |
| RecipientData | RecipientCount × 64 | 接收者数据 |

### 4.13 高级储物箱堆叠大小 (version > 99)

见第 7 节。

## 5. 耳朵物品 (IsEar = true, 完整格式)

在完整物品格式中，耳朵物品的处理：

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| EarFileIndex | 3 | 被杀者职业文件索引 |
| EarLevel | 7 | 被杀者等级 |
| EarName | 变长 | 被杀者名称 (8位字符, null终止) |

注意：Ear 和 Personalized 是互斥的。如果是 Ear 物品，不会读取个性化名称。

## 6. Socket 物品

如果物品有孔 (Socketed = true) 且 nGems > 0，在主物品数据之后会读取 nGems 个嵌套物品。

每个嵌套物品使用相同的 D2Item 结构解析：
- version <= 96：读取 wMajic 和 dwVersion (read_magic=True)
- version > 96：不读取 wMajic 和 dwVersion (read_magic=False)

## 7. 高级储物箱堆叠大小 (version > 99)

**version 100-101**：

仅对特定堆叠物品（宝石、符文、药水等，见 `STACKABLE_FOR_STASH` 列表）：

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| iAdvancedStashStackSize | 8 | 高级储物箱堆叠大小 |

**version > 101**：

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| has_stash_size | 1 | 有储物箱堆叠大小标志 |
| iAdvancedStashStackSize | 8 | has_stash_size=true | 高级储物箱堆叠大小 |

## 8. 物品数据对齐

每个物品数据读取完毕后，位流会对齐到字节边界 (`bs.align_byte()`)。

## 9. 赌博物品

如果 flags 中的 `LowQuality` (0x02000000) 位被设置，表示这是一个赌博物品。读取时：
1. 记录该标志
2. 清除 flags 中的 LowQuality 位
3. 如果是完整物品，将品质设为 Inferior (1)，跳过后续品质数据读取

## 10. Classic 格式对比 (version < 0x61)

Classic 格式与 D2R 格式的主要差异：

| 差异点 | Classic | D2R |
|--------|---------|-----|
| 标志位 | 逐位读取 (多个 read_bits(1)) | 32位 flags 整体读取 |
| 物品版本 | 10位直接读取 | 3位编码 (1位标志+2位值) |
| 位置数据 | 固定格式 (3+4+4+4+3位) | mode决定格式 |
| 物品类型名称 | 4字节逐字节读取 | 0x69+: Huffman编码 |
| wMajic/dwVersion | 始终读取 | version>96时不读取 |
| 个性化名称编码 | 7位 ASCII | 8位 ASCII (0x62+) |
| Realm数据 | 无 | version > 86 |
| 编年史数据 | 无 | version > 99 |
| 高级储物箱 | 无 | version > 99 |
