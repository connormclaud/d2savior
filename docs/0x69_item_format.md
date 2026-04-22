# 0x69 版本物品格式

## 1. 物品列表结构

与 0x63 版本相同，以魔法数 `0x4D4A` 开始。

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| wMajic | 16 | 魔法数 (0x4D4A) |
| nItems | 16 | 物品总数 |
| vItems | 可变 | 每个物品的详细数据 |

## 2. 单个物品结构 (0x69 版本)

0x69 版本属于 D2R (`is_d2r() == True`)，同样使用 `_read_data_d2r` 方法解析物品。与 0x63 相比，0x69 在物品头部标志位读取、版本特定数据、符文之语数据等方面有差异（详见第 9 节）。

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

### 2.2 版本特定数据 (D2R)

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| iUNKNOWN_08 | 5 | 未知 |
| wVersion | 10 | 物品内部版本号 |
| iUNKNOWN_09 | 1 | 未知 (D2R 新增) |

### 2.3 位置信息

与 0x63 版本相同：

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| iLocation | 3 | 物品位置 |
| iPosition | 4 | 物品位置索引 |
| iColumn | 4 | 物品列 |
| iRow | 4 | 物品行 |
| iStoredIn | 3 | 存储位置 |

## 3. 耳朵物品 (bEar = true)

与 0x63 版本相同。

## 4. 普通物品 (bEar = false)

### 4.1 物品类型名称 (Huffman 编码)

0x69 版本使用 Huffman 编码压缩物品类型名称，与 0x63 版本的 4 字节 ASCII 不同。

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| nTypeNameBits | 9 | 类型名称编码后的位长 |
| sTypeName | nTypeNameBits | Huffman 编码的类型名称 |

Huffman 解码使用 `huffman_tree.json` 中的编码表进行解码。

### 4.2 扩展物品信息 (bSimple = false)

与 0x63 版本相同：

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

与 0x63 版本相同，参见 [0x63_itemlist_format.md](0x63_itemlist_format.md) 第 4.3 节。

### 4.4 符文之语数据 (bRuneWord = true)

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| wRune | 16 | 符文之语ID |
| bRuneWordComplete | 1 | 符文之语是否完成 (D2R 新增) |

### 4.5 个性化名称 (bPersonalized = true)

0x69 版本使用 8 位字符编码：

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| sPersonName | 8×16 | 个性化名称 (8位ASCII, null终止) |

### 4.6 随机属性标志

与 0x63 版本相同。

### 4.7 类型特定信息 (bSimple = false)

与 0x63 版本相同，参见 [0x63_itemlist_format.md](0x63_itemlist_format.md) 第 4.8 节。

### 4.8 套装属性标志 (iQuality == 5)

与 0x63 版本相同。

### 4.9 属性列表

0x69 版本使用 `ItemStatCost.txt` 中的定义解析属性，详见 [0x63_item_property_format.md](0x63_item_property_format.md) 第 1.2 节。

### 4.10 套装属性列表和符文之语属性列表

与 0x63 版本相同。

## 5. 简单物品 (bSimple = true)

与 0x63 版本相同，简单物品只包含物品类型名称（Huffman 编码），不包含扩展信息和属性列表。

## 6. Socket 物品

与 0x63 版本相同。

## 7. 金币物品

与 0x63 版本相同。

## 8. 物品数据对齐

每个物品数据读取完毕后，位流会对齐到字节边界。

## 9. 与 0x63 版本的差异总结

| 差异点 | 0x63 | 0x69 |
|--------|------|------|
| 物品类型名称 | 4字节 ASCII (32位) | Huffman 编码 (9位长度 + 变长数据) |
| 版本特定数据 | 5位未知 + 10位版本 | 5位未知 + 10位版本 + 1位未知 |
| 符文之语 | wRune (16位) | wRune (16位) + bRuneWordComplete (1位) |
| 个性化名称编码 | 7位 ASCII | 8位 ASCII |
| 属性解析 | property_merged.txt / ItemStatCost.txt | ItemStatCost.txt |
