# 0x63 版本物品属性格式

## 1. 属性列表结构

物品的属性列表是一个连续的属性ID和属性值序列，以结束标志结束。

### 1.1 基本结构 (Classic 格式)

0x63 版本使用 `property_merged.txt` 中的属性元数据解析。

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| 属性ID | 9 | 属性的唯一标识符 |
| 属性值 | 可变 | 根据 property_merged.txt 中的 bits_sum 确定 |
| 结束标志 | 9 | 0x1FF，表示属性列表结束 |

### 1.2 D2R 格式 (is_d2r = true)

0x63 版本虽然是 D2R，但在属性解析时使用 `ItemStatCost.txt` 中的定义：

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| 属性ID | 9 | 属性的唯一标识符 (stat_id) |
| layer | save_param_bits | 参数层 (如果 save_param_bits > 0) |
| raw_value | save_bits | 原始值 |
| 结束标志 | 9 | >= 0x1FF，表示属性列表结束 |

实际值计算: `value = (raw_value - save_add) << val_shift`

## 2. 属性元数据来源

### 2.1 ItemStatCost.txt

D2R 版本使用 `ItemStatCost.txt` 定义属性的存储参数：

| 字段 | 描述 |
|------|------|
| *ID | 属性唯一标识符 |
| Stat | 属性名称 |
| Save Bits | 值的存储位长 |
| Save Add | 值的偏移基数 |
| Save Param Bits | 参数的存储位长 |
| ValShift | 值的位移量 |
| Op | 运算类型 |
| Op Param | 运算参数 |
| Op Base | 运算基础属性 |
| Op Stat1/2/3 | 运算关联属性 |

### 2.2 property_merged.txt

Classic 格式使用 `property_merged.txt` 定义属性的存储参数：

| 字段 | 描述 |
|------|------|
| ID | 属性唯一标识符 |
| VersionMin | 适用的最低版本 (0x63 标记为0x63版本特有) |
| DefaultValue | 默认值 |
| Fields | 字段列表 (bits, base, min, max) |

## 3. 配对属性 (Paired Stats)

某些属性会自动附带配对属性，不需要在数据中单独存储：

| 主属性ID | 配对属性ID | 描述 |
|----------|-----------|------|
| 17 | 18 | Enhanced Damage → % Enhanced Damage |
| 48 | 49 | Fire Min Damage → Fire Max Damage |
| 50 | 51 | Light Min Damage → Light Max Damage |
| 52 | 53 | Magic Min Damage → Magic Max Damage |
| 54 | 55, 56 | Cold Min Damage → Cold Max Damage, Cold Length |
| 57 | 58, 59 | Poison Min Damage → Poison Max Damage, Poison Length |

注意: 当读取 stat 57 (Poison Min Damage) 时，会自动添加 stat 88 (item_doubleherbduration) 值为1。

## 4. 常见属性ID

### 4.1 基础属性

| 属性ID | 名称 | 描述 |
|--------|------|------|
| 0 | strength | 力量 |
| 1 | energy | 精力 |
| 2 | dexterity | 敏捷 |
| 3 | vitality | 体力 |

### 4.2 生命/法力/耐力

| 属性ID | 名称 | 描述 |
|--------|------|------|
| 7 | maxhp | 最大生命 |
| 9 | maxmana | 最大法力 |
| 11 | maxstamina | 最大耐力 |

### 4.3 伤害相关

| 属性ID | 名称 | 描述 |
|--------|------|------|
| 16 | enhanceddefense | 增强防御 |
| 17 | enhanceddamage | 增强伤害 |
| 21 | mindamage | 最小伤害 |
| 22 | maxdamage | 最大伤害 |
| 23 | secondarymindamage | 次要最小伤害 |
| 24 | secondarymaxdamage | 次要最大伤害 |

### 4.4 元素伤害

| 属性ID | 名称 | 描述 |
|--------|------|------|
| 48 | firemindam | 火焰最小伤害 |
| 49 | firemaxdam | 火焰最大伤害 |
| 50 | lightmindam | 闪电最小伤害 |
| 51 | lightmaxdam | 闪电最大伤害 |
| 52 | magicmindam | 魔法最小伤害 |
| 53 | magicmaxdam | 魔法最大伤害 |
| 54 | coldmindam | 冰冷最小伤害 |
| 55 | coldmaxdam | 冰冷最大伤害 |
| 56 | coldlength | 冰冷持续时间 |
| 57 | poisonmindam | 毒素最小伤害 |
| 58 | poisonmaxdam | 毒素最大伤害 |
| 59 | poisonlength | 毒素持续时间 |

### 4.5 抗性

| 属性ID | 名称 | 描述 |
|--------|------|------|
| 39 | fireresist | 火焰抗性 |
| 41 | lightresist | 闪电抗性 |
| 43 | coldresist | 冰冷抗性 |
| 45 | poisonresist | 毒素抗性 |

### 4.6 攻击相关

| 属性ID | 名称 | 描述 |
|--------|------|------|
| 19 | tohit | 攻击命中率 |
| 20 | tohitpercent | 攻击命中率百分比 |
| 31 | armorclass | 防御等级 |
| 60 | damagepercent | 伤害偷取生命% |
| 62 | manadamagepercent | 伤害偷取法力% |

### 4.7 速度相关

| 属性ID | 名称 | 描述 |
|--------|------|------|
| 93 | velocitypercent | 跑步/行走速度 |
| 96 | move_velocity | 更快跑步/行走 |
| 99 | attackrate | 更快攻击速度 |
| 105 | castrate | 更快施法速度 |
| 102 | fasterblock | 更快格挡速度 |

### 4.8 技能相关

| 属性ID | 名称 | 描述 |
|--------|------|------|
| 83 | item_addskill_tab | +X 到技能树 |
| 97 | item_nonclassskill | +X 到非职业技能 |
| 107 | item_singleskill | +X 到特定技能 |
| 126 | item_addclassskills | +X 到职业全技能 |
| 127 | item_addskills | +X 到所有技能 |

### 4.9 特殊属性

| 属性ID | 名称 | 描述 |
|--------|------|------|
| 73 | maxdurability | 最大耐久度 |
| 79 | item_goldbonus | 额外金币获取 |
| 80 | item_magicbonus | 魔法装备发现率 |
| 92 | item_levelreq | 需求等级 |
| 136 | item_crushingblow | 压碎性打击 |
| 137 | item_openwounds | 撕裂伤口 |
| 141 | item_deadlystrike | 致命打击 |
| 152 | item_indesctructible | 不可破坏 |
| 153 | item_cannotbefrozen | 无法冰冻 |
| 194 | item_numsockets | 孔数 |

## 5. 属性值解析 (D2R 格式)

### 5.1 从原始数据到参数

D2R 格式的属性值需要从 `layer` 和 `value` 转换为 `params` 数组：

1. 计算 `display_value = value >> val_shift` (如果 val_shift > 0)
2. 如果 `property_merged.txt` 中有对应属性定义且字段数 > 1，从 `layer` 中按位拆分参数
3. 否则使用 `[layer, display_value, 0, 0]` 格式

### 5.2 参数拆分示例

对于 stat 97 (item_nonclassskill)，property_merged.txt 定义了两个字段：
- Field 1: skill_id (bits=9)
- Field 2: skill_level (bits=7)

`layer` 的低9位是 skill_id，`display_value` 是 skill_level。

## 6. 属性格式化

属性格式化使用 `item-modifiers.json` 中的描述字符串模板，结合 `descfunc` 和 `descval` 控制显示格式。

### 6.1 descfunc 值

| descfunc | 格式 | 示例 |
|----------|------|------|
| 1 | +[value] [desc] | +10 to Strength |
| 2 | [value]% [desc] | 30% Fire Resist |
| 3 | [value] [desc] | 50 to Life |
| 4 | +[value]% [desc] | +100% Enhanced Defense |
| 5 | [value]% [desc] (class only) | +3 to Fire Skills (Sorceress Only) |
| 6 | [value] [desc] | 25% Crushing Blow |
| 7 | [value]% [desc] | 50% Deadly Strike |
| 8 | +[value] [skill] | +1 to Teleport |
| 9 | +[value] to [skilltab] [class] | +1 to Fire Skills (Sorceress Only) |
| 11 | Repairs [value] per [time] | Repairs 1 Durability per 3 Seconds |

### 6.2 descval 值

| descval | 描述 |
|---------|------|
| 0 | 不显示数值 |
| 1 | 正值显示 + |
| 2 | 正值不显示 + |

## 7. 版本差异

0x63 与 0x69 版本在属性格式上的主要差异：

- 0x63 使用 `property_merged.txt` (Classic) 或 `ItemStatCost.txt` (D2R) 定义
- 0x69 使用 `ItemStatCost.txt` 定义
- 某些属性的 save_bits 和 save_param_bits 在两个版本间不同
- 0x69 版本有更多属性 (如 stat 356 quest_difficulty)
