# 0x63 版本物品列表格式

## 1. 物品列表结构

物品列表以魔法数 `0x4D4A` 开始，后跟物品数量，然后是每个物品的数据。

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| wMajic | 16 | 魔法数 (0x4D4A) |
| nItems | 16 | 物品总数 |
| vItems | 可变 | 每个物品的详细数据 |

## 2. 单个物品结构 (0x63 版本)

0x63 版本属于 D2R (`is_d2r() == True`)，使用 `_read_data_d2r` 方法解析物品。与 Classic (<0x61) 的 `_read_data_classic` 不同，0x63 的物品类型名称使用 Huffman 编码，属性解析使用 `ItemStatCost.txt`。

### 2.1 物品头部

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| wMajic | 16 | 物品魔法数 (0x4D4A) |
| dwVersion | 32 | 物品版本 |
| bQuest | 1 | 任务物品标志 |
| iUNKNOWN_01 | 3 | 未知 |
| bIdentified | 1 | 已鉴定标志 |
| iUNKNOWN_02 | 3 | 未知 |
| bDisabled | 1 | 禁用标志 |
| iUNKNOWN_10 | 2 | 未知 |
| bSocketed | 1 | 有孔标志 |
| bUNKNOWN_03 | 1 | 未知 |
| bNew | 1 | 新物品标志 |
| bBadEquipped | 1 | 装备错误标志 |
| bUNKNOWN_04 | 1 | 未知 |
| bEar | 1 | 耳朵物品标志 |
| bNewbie | 1 | 新手物品标志 |
| iUNKNOWN_05 | 3 | 未知 |
| bSimple | 1 | 简单物品标志 (compactsave) |
| bEthereal | 1 | 无形物品标志 |
| bUNKNOWN_06 | 1 | 未知 |
| bPersonalized | 1 | 个性化物品标志 |
| bUNKNOWN_07 | 1 | 未知 |
| bRuneWord | 1 | 符文之语标志 |

### 2.2 版本特定数据

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| iUNKNOWN_08 | 5 | 未知 |
| wVersion | 10 | 物品内部版本号 |

### 2.3 位置信息

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| iLocation | 3 | 物品位置 (0=装备, 1=腰带, 2=地面, 3=存储, 4=武器切换, 5=存储扩展) |
| iPosition | 4 | 物品位置索引 |
| iColumn | 4 | 物品列 |
| iRow | 4 | 物品行 |
| iStoredIn | 3 | 存储位置 |

## 3. 耳朵物品 (bEar = true)

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| iEarClass | 3 | 被杀者职业 |
| iEarLevel | 7 | 被杀者等级 |
| sEarName | 7×15 | 被杀者名称 (7位ASCII, null终止) |

## 4. 普通物品 (bEar = false)

### 4.1 物品类型名称

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| sTypeName | 32 | 物品类型代码 (4字节ASCII, 逐字节读取) |

### 4.2 扩展物品信息 (bSimple = false)

| 字段 | 大小 (位) | 条件 | 描述 |
|------|-----------|------|------|
| nGems | 3 | 始终 | 宝石/孔中物品数量 |
| dwGUID | 32 | 始终 | 物品全局唯一ID |
| iDropLevel | 7 | 始终 | 掉落等级 |
| iQuality | 4 | 始终 | 品质等级 |
| bVarGfx | 1 | 始终 | 可变图形标志 |
| iVarGfx | 3 | bVarGfx=true | 可变图形索引 |
| bClass | 1 | 始终 | 职业限制标志 |
| wClass | 11 | bClass=true | 职业限制掩码 |

### 4.3 品质特定数据

品质 (iQuality) 决定了后续读取的数据：

| iQuality | 品质 | 额外数据 |
|----------|------|----------|
| 1 | Low (劣质) | loQual (3位) |
| 2 | Normal (普通) | wCharm (12位, 仅护身符) / iBodyPartFileIndex (10位, 仅身体部位) / iSpellType (5位, 仅卷轴/书) |
| 3 | Superior (超强) | hiQual (3位) |
| 4 | Magic (魔法) | wPrefix (11位) + wSuffix (11位) |
| 5 | Set (套装) | wSetID (12位) |
| 6 | Rare (稀有) | CLongName (2×8位名称ID + 6个可选前缀/后缀) |
| 7 | Unique (独特) | wUniID (12位) |
| 8 | Crafted (合成) | CCraftName (同CLongName格式) |

### 4.4 CLongName 结构 (Rare/Crafted 名称)

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| iName1 | 8 | 名称词缀1 ID |
| iName2 | 8 | 名称词缀2 ID |
| bPref1 | 1 | 有前缀1 |
| wPref1 | 11 | 前缀1 ID (如果 bPref1) |
| bSuff1 | 1 | 有后缀1 |
| wSuff1 | 11 | 后缀1 ID (如果 bSuff1) |
| bPref2 | 1 | 有前缀2 |
| wPref2 | 11 | 前缀2 ID (如果 bPref2) |
| bSuff2 | 1 | 有后缀2 |
| wSuff2 | 11 | 后缀2 ID (如果 bSuff2) |
| bPref3 | 1 | 有前缀3 |
| wPref3 | 11 | 前缀3 ID (如果 bPref3) |
| bSuff3 | 1 | 有后缀3 |
| wSuff3 | 11 | 后缀3 ID (如果 bSuff3) |

### 4.5 符文之语数据 (bRuneWord = true)

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| wRune | 16 | 符文之语ID |

### 4.6 个性化名称 (bPersonalized = true)

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| sPersonName | 7×16 | 个性化名称 (7位ASCII, null终止) |

注意: 0x62+ 版本使用 8位字符编码。

### 4.7 随机属性标志

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| bHasRand | 1 | 有随机属性标志 |
| pTimeStampFlag | 128 | 时间戳标志 (4×32位, 如果 bHasRand 且非Simple) |

### 4.8 类型特定信息 (bSimple = false)

| 字段 | 大小 (位) | 条件 | 描述 |
|------|-----------|------|------|
| iDefence | 11 | has_def=true | 防御值 (需减去 save_add) |
| iMaxDurability | 8 | has_dur=true | 最大耐久度 |
| iCurDur | 9 | iMaxDurability > 0 | 当前耐久度 |
| iSocket | 4 | bSocketed=true | 孔数 |
| iQuantity | 9 | is_stacked=true | 堆叠数量 |

### 4.9 套装属性标志 (iQuality == 5)

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| aHasSetPropList | 5×1 | 5个套装属性列表标志 |

### 4.10 属性列表

详见 [0x63_item_property_format.md](0x63_item_property_format.md)。

### 4.11 套装属性列表

如果 aHasSetPropList[i] 为 true，则读取对应的属性列表。

### 4.12 符文之语属性列表

如果 bRuneWord 为 true，在基础属性列表和套装属性列表之后读取符文之语属性列表。

## 5. 简单物品 (bSimple = true)

简单物品只包含物品类型名称，不包含扩展信息和属性列表。

## 6. Socket 物品

如果物品有孔 (bSocketed = true) 且 nGems > 0，在主物品数据之后会读取 nGems 个嵌套物品。

每个嵌套物品使用相同的 CD2Item 结构解析，但不读取 wMajic 和 dwVersion (read_magic=True)。

## 7. 金币物品

类型名称为 `gld ` 的物品是金币，有特殊结构：

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| bNotGold | 1 | 非金币标志 |
| wQuantity | 12 | 金币数量 |

## 8. 物品数据对齐

每个物品数据读取完毕后，位流会对齐到字节边界 (`bs.align_byte()`)。
