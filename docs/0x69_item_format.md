# 0x69 版本物品格式

## 1. 物品列表结构

与 0x63 版本相同，以魔法数 `0x4D4A` 开始。

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| wMajic | 16 | 魔法数 (0x4D4A) |
| nItems | 16 | 物品总数 |
| vItems | 可变 | 每个物品的详细数据 |

## 2. 单个物品结构 (0x69 版本 - D2R 格式)

0x69 版本属于 D2R (`version >= 0x61`)，使用 `_read_data_d2r` 方法解析物品。0x69 是 D2R v3.x 版本，与 0x63 相比有多个重要差异。

### 2.1 物品头部

**version > 96 (0x69 属于此范围)**：

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| flags | 32 | 物品标志位 (见 2.2) |

注意：当 version > 96 时，不读取 wMajic 和 dwVersion。物品版本继承存档版本。

**version <= 96**：

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| wMajic | 16 | 物品魔法数 (0x4D4A) |
| dwVersion | 32 | 物品版本号 |
| flags | 32 | 物品标志位 |

### 2.2 物品标志位 (flags)

与 0x63 版本完全相同，32 位整数，通过位掩码提取。详细的标志位定义和逐位读取顺序见 [item_flag_format.md](item_flag_format.md)。

| 标志 | 位掩码 | 描述 |
|------|--------|------|
| NewItem | 0x00000001 | 新物品 |
| Identified | 0x00000010 | 已鉴定 |
| HasQuantity | 0x00000020 | 有数量 |
| Socketed | 0x00000800 | 有孔 |
| IsEar | 0x00010000 | 耳朵物品 |
| StarterItem | 0x00020000 | 新手物品 |
| CompactSave | 0x00200000 | 简单物品 (紧凑存储) |
| Ethereal | 0x00400000 | 无形物品 |
| Personalized | 0x01000000 | 个性化物品 |
| Runeword | 0x04000000 | 符文之语 |
| Chronicle | 0x10000000 | 编年史标志 |
| ChronicleCompact | 0x20000000 | 编年史紧凑标志 |

### 2.3 物品格式版本 (wVersion)

**D2R 格式 (version > 96)**：

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| hf | 1 | 高版本标志 |
| vv | 2 | 版本值 |

解码规则：
- 如果 `hf = 1`：`wVersion = vv + 99`（编码 99-102）
- 如果 `hf = 0`：`wVersion = vv`（编码 0-3）

0x69 版本的物品 wVersion 通常为 101。

### 2.4 位置信息

与 0x63 版本完全相同，根据 mode (3位) 的值有不同的读取方式：

| mode 值 | 模式 | 位置数据 |
|---------|------|----------|
| 0 | Stored | BodyLocation(4) + InvX(4) + InvY(4) + StorePage(3) |
| 1 | Equipped | BodyLocation(4) + InvX(4) + InvY(4) + StorePage(3) |
| 2 | InBelt | BodyLocation(4) + InvX(4) + InvY(4) + StorePage(3) |
| 3 | OnGround | GroundX(16) + GroundY(16) |
| 4 | OnCursor | BodyLocation(4) + InvX(4) + InvY(4) + StorePage(3) |
| 5 | Dropping | GroundX(16) + GroundY(16) |
| 6 | Socketed | BodyLocation(4) + InvX(4) + InvY(4) + StorePage(3) |

StorePage 存储值 = 内部值 + 1。

## 3. 物品类型名称 (Huffman 编码) ★ 0x69 差异

**0x69 与 0x63 的关键差异**：物品类型名称的编码方式不同。

| 版本 | 编码方式 | 描述 |
|------|----------|------|
| version > 96 | Huffman 编码 | 使用 Huffman 树解码，4个字符逐个解码 |
| version <= 96 | 4字节 ASCII | 32位原始数据，逐字节读取 |

0x69 版本使用 Huffman 编码压缩物品类型名称。解码使用 `huffman_tree.json` 中的编码表，逐字符解码 4 个字符。

Huffman 编码的优势：物品类型代码通常只有少量不同值（如 "hdm ", "ci3 " 等），Huffman 编码可以将 32 位压缩到约 10-15 位。

## 4. 紧凑物品 (CompactSave = true)

### 4.1 耳朵物品 (IsEar = true)

与 0x63 版本相同：

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| EarFileIndex | 3 | 被杀者职业文件索引 |
| EarLevel | 7 | 被杀者等级 |
| EarName | 变长 | 被杀者名称 (8位字符, null终止) |

### 4.2 普通紧凑物品

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| sTypeName | Huffman编码 | 物品类型代码 (Huffman编码, 4字符) |

#### 4.2.1 金币紧凑物品

如果物品类型为 `gld `：

| 字段 | 大小 (位) | 条件 | 描述 |
|------|-----------|------|------|
| bigGold | 1 | 始终 | 大额金币标志 |
| GoldAmount | 32 | bigGold=true | 金币数量 |
| GoldAmount | 12 | bigGold=false | 金币数量 |
| PlayerGold | 1 | version > 96 | 玩家金币标志 |

#### 4.2.2 任务难度 (version > 92)

如果物品是任务物品且需要难度检查：

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| QuestDifficulty | stat 356 的 save_bits | 任务难度值 |

值计算：`value = (raw - save_add) << val_shift`

#### 4.2.3 Realm 数据 (version > 86)

| 字段 | 大小 (位) | 条件 | 描述 |
|------|-----------|------|------|
| realm_flag | 1 | 始终 | Realm 数据标志 |
| RealmData | 4×32 | realm_flag=true, version > 96 | Realm 数据 |

0x69 版本 (version > 96) 始终使用 4 个 32 位整数。

#### 4.2.4 高级储物箱堆叠大小 (version > 99)

见第 8 节。

## 5. 完整物品 (CompactSave = false)

### 5.1 物品类型名称

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| sTypeName | Huffman编码 | 物品类型代码 (Huffman编码, 4字符) |

### 5.2 扩展物品信息

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

### 5.3 品质特定数据 ★ 0x69 差异

品质 (iQuality) 决定了后续读取的数据：

| iQuality | 品质 | 额外数据 |
|----------|------|----------|
| 1 | Inferior (劣质) | InferiorFileIndex (3位) |
| 2 | Normal (普通) | 特殊子类型数据 (见 5.3.1) |
| 3 | Superior (超强) | SuperiorFileIndex (3位) |
| 4 | Magic (魔法) | PrefixId (11位) + SuffixId (11位) |
| 5 | Set (套装) | SetUniqueFileIndex (12位) |
| 6 | Rare (稀有) | LongName (8+8位名称ID + 6个可选前缀/后缀) |
| 7 | Unique (独特) | SetUniqueFileIndex (12位) |
| 8 | Craft (合成) | LongName (同 Rare 格式) |
| **9** | **Tempered (锻造) ★** | **RarePrefixId (8位) + RareSuffixId (8位)** |

#### 5.3.1 Normal 品质特殊子类型

与 0x63 版本相同：

**护身符 (is_charm = true)**：

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| HasPrefix | 1 | 有前缀标志 |
| PrefixId | 11 | HasPrefix=true | 魔法前缀ID |
| SuffixId | 11 | HasPrefix=false | 魔法后缀ID |

**怪物身体部位 (is_body_part=true, is_player_body_part=false)**：

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| BodyPartFileIndex | 10 | 身体部位文件索引 |

**卷轴/书 (is_scroll_or_book=true)**：

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| SpellType | 5 | 法术类型 |

#### 5.3.2 Tempered 品质 ★ 0x69 新增

0x69 版本新增了 Tempered (锻造) 品质 (iQuality = 9)。

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| RarePrefixId | 8 | 稀有名称前缀ID |
| RareSuffixId | 8 | 稀有名称后缀ID |

Tempered 品质的数据结构比 Rare/Craft 简单得多——只有两个 8 位的名称 ID，没有词缀列表。词缀数据存储在属性列表中。

#### 5.3.3 LongName 结构 (Rare/Crafted 名称)

与 0x63 版本相同：

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| iName1 | 8 | 名称词缀1 ID |
| iName2 | 8 | 名称词缀2 ID |
| bPref1 | 1 | 有前缀1 |
| wPref1 | 11 | bPref1=true | 前缀1 ID |
| bSuff1 | 1 | 有后缀1 |
| wSuff1 | 11 | bSuff1=true | 后缀1 ID |
| bPref2 | 1 | 有前缀2 |
| wPref2 | 11 | bPref2=true | 前缀2 ID |
| bSuff2 | 1 | 有后缀2 |
| wSuff2 | 11 | bSuff2=true | 后缀2 ID |
| bPref3 | 1 | 有前缀3 |
| wPref3 | 11 | bPref3=true | 前缀3 ID |
| bSuff3 | 1 | 有后缀3 |
| wSuff3 | 11 | bSuff3=true | 后缀3 ID |

### 5.4 符文之语数据 (Runeword = true)

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| wRune | 16 | 符文之语ID |

注意：0x69 版本的符文之语数据与 0x63 版本相同，只有 wRune (16位)。旧文档中提到的 `bRuneWordComplete` 字段在实际实现中不存在。

### 5.5 个性化名称 (Personalized = true)

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| sPersonName | 8×变长 | 个性化名称 (8位字符, null终止, 最长16字符) |

0x69 版本 (is_ptr24_and_above) 使用 8 位字符编码。

### 5.6 Realm 数据

同紧凑物品的 Realm 数据格式 (见 4.2.3)。

### 5.7 类型特定信息

#### 5.7.1 防御值 (护甲物品, has_def=true)

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| iDefence | stat 31 (ArmorClass) 的 save_bits | 防御原始值 |

实际防御值 = 原始值 - save_add (stat 31)

#### 5.7.2 耐久度 (has_dur=true)

| 字段 | 大小 (位) | 条件 | 描述 |
|------|-----------|------|------|
| iMaxDurability | stat 73 (MaxDurability) 的 save_bits | 始终 | 最大耐久度原始值 |
| iCurDur | stat 72 (Durability) 的 save_bits | iMaxDurability > 0 | 当前耐久度原始值 |

#### 5.7.3 金币物品

与 0x63 版本相同。

#### 5.7.4 堆叠数量 ★ 0x69 差异

**version >= 0x69 (0x69 版本)**：

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| qty_flag | 1 | 有数量标志 |
| iQuantity | 9 | qty_flag=true | 堆叠数量 |

**version > 104**：

与 0x69 相同格式。

**version <= 104**：

| 字段 | 大小 (位) | 条件 | 描述 |
|------|-----------|------|------|
| iQuantity | 9 | is_stacked=true | 堆叠数量 |

0x69 版本的关键差异：所有物品都有 qty_flag 字段，不仅仅是堆叠物品。qty_flag 为 true 时才读取 9 位数量值。

#### 5.7.5 孔数 (Socketed = true)

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| iSocket | stat 194 (NumSockets) 的 save_bits | 孔数 |

如果读取到的孔数 < 1，强制设为 1。

### 5.8 套装属性标志 (iQuality == 5)

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| aHasSetPropList | 5×1 | 5个套装属性列表标志 |

### 5.9 属性列表

与 0x63 版本使用相同的 ItemStatCost.txt 驱动的解析方式。详见 [0x63_item_property_format.md](0x63_item_property_format.md)。

### 5.10 套装属性列表

如果 aHasSetPropList[i] 为 true，则读取对应的属性列表。最多 5 个附加属性列表。

### 5.11 符文之语属性列表

如果 Runeword 为 true，在基础属性列表和套装属性列表之后读取符文之语属性列表。

### 5.12 编年史数据 (version > 99, Chronicle 标志)

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

### 5.13 高级储物箱堆叠大小 (version > 99)

见第 8 节。

## 6. 紧凑物品的 iPad 字段 ★ 0x69 差异

0x69 版本中，紧凑物品 (CompactSave=true) 在读取完 Realm 数据和高级储物箱堆叠大小后，如果物品元数据中 `ipad_bits > 0`，还会读取一个填充字段：

| 字段 | 大小 (位) | 条件 | 描述 |
|------|-----------|------|------|
| iPad | meta.ipad_bits | version >= 0x69 且 ipad_bits > 0 | 填充数据 |

此字段来自 `itemdata.txt` 中的定义，用于对齐物品数据。完整物品不需要此字段，因为其数据已经通过对齐机制处理。

## 7. Socket 物品

与 0x63 版本相同。每个物品数据读取完毕后，位流对齐到字节边界。然后读取镶嵌的物品。

## 8. 高级储物箱堆叠大小 (version > 99)

0x69 版本 (version 通常为 0x69 = 105) 的处理方式：

**version > 101**：

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| has_stash_size | 1 | 有高级储物箱堆叠大小标志 |
| AdvancedStashStackSize | 8 | has_stash_size=true | 堆叠大小 |

**version 100-101**：

仅对硬编码的可堆叠物品类型（药水、宝石、符文、钥匙等）读取：

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| AdvancedStashStackSize | 8 | 堆叠大小 (无条件读取) |

可堆叠物品类型列表（硬编码）：
- 药水: rvs, rvl, gcv-gpv (各品质), gcy-gpy, gcb-gpb, gcg-gpg, gcr-gpr, gcw-gpw
- 符文: r01-r33
- 宝石头: skc, skf, sku, skl, skz
- 钥匙: pk1, pk2, pk3
- 其他: dhn, bey, mbr, toa, tes, ceh, bet, fed

## 9. 与 0x63 版本的差异总结

| 差异点 | 0x63 | 0x69 |
|--------|------|------|
| 物品类型名称编码 | 4字节 ASCII (32位, version<=96) / Huffman (version>96) | Huffman 编码 (version>96) |
| 品质等级 | 1-8 (无 Tempered) | 1-9 (新增 Tempered = 9) |
| Tempered 品质数据 | 不存在 | RarePrefixId(8) + RareSuffixId(8) |
| 堆叠数量读取 | version>104: qty_flag+9位; version<=104: 仅堆叠物品9位 | version>=0x69: 所有物品qty_flag+9位 |
| 紧凑物品 iPad | 不存在 | version>=0x69: ipad_bits>0时读取 |
| 属性解析 | ItemStatCost.txt | ItemStatCost.txt (相同逻辑) |
| Realm 数据 | version>96: 4×32位 | version>96: 4×32位 (相同) |
| 编年史数据 | version>99: 有 | version>99: 有 (相同) |
| 高级储物箱堆叠 | version>99: 有 | version>99: 有 (相同) |
| 符文之语数据 | wRune(16位) | wRune(16位) (相同) |
| 个性化名称 | 8位字符 (is_ptr24_and_above) | 8位字符 (相同) |
| ItemStatCost 数据 | 0x63 版本的 ItemStatCost.txt | 0x69 版本的 ItemStatCost.txt (某些 stat 的 save_bits 不同) |

### 9.1 ItemStatCost 版本差异

0x63 和 0x69 版本使用不同的 ItemStatCost.txt 数据文件，某些 stat 的 save_bits 不同：

| stat_id | stat 名称 | 0x63 save_bits | 0x69 save_bits | 说明 |
|---------|-----------|----------------|----------------|------|
| 31 | ArmorClass | 11 | 11 | 防御值 (可能相同) |
| 72 | Durability | 9 | 9 | 当前耐久度 (可能相同) |
| 73 | MaxDurability | 8 | 8 | 最大耐久度 (可能相同) |
| 194 | NumSockets | 3 | 3 | 孔数 (可能相同) |
| 356 | QuestItemDifficulty | - | 存在 | 0x69 新增 stat |

关键：两个版本的属性解析逻辑完全相同，差异仅在 ItemStatCost.txt 的数据定义上。必须使用对应版本的 ItemStatCost.txt 来解析对应版本的存档。

### 9.2 数量位宽差异

| 版本范围 | 堆叠数量位宽 | 条件 |
|----------|-------------|------|
| version > 104 | qty_flag(1) + 9位 | 所有物品 |
| version >= 0x69 且 <= 104 | qty_flag(1) + 9位 | 所有物品 |
| version > 80 且 < 0x69 | 9位 | 仅堆叠物品 |
| version <= 80 | 8位 | 仅堆叠物品 |

注意：0x69 = 105 > 104，所以 0x69 版本实际上使用 qty_flag + 9位格式。但代码中 `version >= 0x69` 的判断先于 `version > 104` 的判断，确保了正确性。
