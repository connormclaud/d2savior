# 0x63 版本玩家属性格式

## 1. PlayerStats 结构

玩家属性数据位于存档文件的后半部分，以魔法数 `0x6667` 开始。

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| wMajic | 16 | 魔法数 (0x6667) |
| 属性数据 | 可变 | 9位ID + 变长值 的序列 |
| 结束标志 | 9 | >= 0x10 时结束 |

## 2. 属性存储格式

每个属性由 9 位 ID 和对应位长的值组成。属性按 ID 顺序存储，但不保证连续。当读取到的 ID >= 0x10 时，表示属性列表结束。

### 2.1 属性ID与位长

| ID | 属性名称 | 位长 | 描述 |
|----|----------|------|------|
| 0 | Strength | 10 | 力量 |
| 1 | Energy | 10 | 精力 |
| 2 | Dexterity | 10 | 敏捷 |
| 3 | Vitality | 10 | 体力 |
| 4 | Unused Stats | 10 | 剩余属性点 |
| 5 | Unused Skills | 8 | 剩余技能点 |
| 6 | Current HP | 21 | 当前生命值 (内部值，显示值 = 内部值 >> 8) |
| 7 | Max HP | 21 | 最大生命值 (内部值) |
| 8 | Current Mana | 21 | 当前法力值 (内部值) |
| 9 | Max Mana | 21 | 最大法力值 (内部值) |
| 10 | Current Stamina | 21 | 当前耐力值 (内部值) |
| 11 | Max Stamina | 21 | 最大耐力值 (内部值) |
| 12 | Level | 7 | 等级 |
| 13 | Experience | 32 | 经验值 |
| 14 | Gold | 25 | 身上金币 |
| 15 | Stash Gold | 25 | 存储金币 |

### 2.2 生命/法力/耐力的内部值

HP、Mana、Stamina 使用 21 位存储内部值，实际显示值需要右移 8 位：

```
显示值 = 内部值 >> 8
```

例如：内部值 0x1400 = 5120，显示值 = 5120 >> 8 = 20

## 3. 解析逻辑

```python
PLAYER_STATS_BITS_COUNT = [10, 10, 10, 10, 10, 8, 21, 21, 21, 21, 21, 21, 7, 32, 25, 25]

def read_player_stats(bs):
    wMajic = bs.read_word()  # 0x6667
    values = [0] * 16
    while True:
        stat_id = bs.read_bits(9)
        if stat_id >= 0x10:  # 结束标志
            break
        values[stat_id] = bs.read_bits(PLAYER_STATS_BITS_COUNT[stat_id])
    bs.align_byte()
```

## 4. 与 0x69 版本的差异

0x69 版本的 PlayerStats 格式与 0x63 版本相同，使用相同的魔法数和属性ID定义。
