# 0x63 版本物品属性格式

## 1. 属性列表结构

物品的属性列表是一个连续的属性ID和属性值序列，以结束标志结束。

### 1.1 D2R 格式 (ItemStatCost 驱动)

0x63 版本属于 D2R，属性解析使用 `ItemStatCost.txt` 中的定义。这是唯一使用的格式。

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| stat_id | 9 | 属性唯一标识符 |
| layer | save_param_bits | 参数层 (如果 save_param_bits > 0) |
| raw_value | save_bits | 原始值 |
| 结束标志 | 9 | 0x1FF，表示属性列表结束 |

实际值计算：`value = (raw_value - save_add) << val_shift`

### 1.2 Classic 格式 (property_merged.txt 驱动)

仅 Classic 版本 (version < 0x61) 使用此格式，0x63 版本不使用。

| 字段 | 大小 (位) | 描述 |
|------|-----------|------|
| 属性ID | 9 | 属性的唯一标识符 |
| 属性值 | bits_sum | 根据 property_merged.txt 中的 bits_sum 确定 |
| 结束标志 | 9 | 0x1FF，表示属性列表结束 |

## 2. 属性元数据来源

### 2.1 ItemStatCost.txt (D2R 格式)

D2R 版本使用 `ItemStatCost.txt` 定义属性的存储参数：

| 字段 | 描述 |
|------|------|
| *ID | 属性唯一标识符 (stat_id) |
| Stat | 属性名称 |
| Save Bits | 值的存储位长 (save_bits) |
| Save Add | 值的偏移基数 (save_add) |
| Save Param Bits | 参数的存储位长 (save_param_bits) |
| ValShift | 值的位移量 (val_shift) |
| Op | 运算类型 |
| Op Param | 运算参数 |
| Op Base | 运算基础属性 |
| Op Stat1/2/3 | 运算关联属性 |

### 2.2 property_merged.txt (Classic 格式)

Classic 格式使用 `property_merged.txt` 定义属性的存储参数：

| 字段 | 描述 |
|------|------|
| ID | 属性唯一标识符 |
| VersionMin | 适用的最低版本 |
| DefaultValue | 默认值 |
| Fields | 字段列表 (bits, base, min, max) |

## 3. D2R 属性解析流程

### 3.1 读取流程

```
while True:
    stat_id = read_bits(9)
    if stat_id >= 0x1FF:
        break
    
    stat_cost = get_stat_cost(stat_id)
    if stat_cost is None or stat_cost.save_bits == 0:
        continue
    
    layer = 0
    if stat_cost.save_param_bits > 0:
        layer = read_bits(stat_cost.save_param_bits)
    
    raw_value = read_bits(stat_cost.save_bits)
    value = (raw_value - stat_cost.save_add) << stat_cost.val_shift
    
    # 处理配对属性
    for paired_id in PAIRED_STATS.get(stat_id, []):
        paired_cost = get_stat_cost(paired_id)
        paired_raw = read_bits(paired_cost.save_bits)
        paired_value = (paired_raw - paired_cost.save_add) << paired_cost.val_shift
    
    # 特殊: stat 57 (PoisonMinDamage) 自动添加 stat 88 (PoisonCount) = 1
    if stat_id == 57:
        add_implicit_stat(88, 0, 1)
```

### 3.2 写入流程

```
all_paired_ids = 所有配对属性ID的集合
implicit_stats = {88}  # PoisonCount 不写入

for stat_id, layer, value in properties:
    if stat_id in all_paired_ids:
        continue  # 配对属性随主属性写入
    if stat_id in implicit_stats:
        continue  # 隐式属性不写入
    
    write_bits(9, stat_id)
    
    stat_cost = get_stat_cost(stat_id)
    if stat_cost.save_param_bits > 0:
        write_bits(stat_cost.save_param_bits, layer)
    
    raw_value = (value >> stat_cost.val_shift) + stat_cost.save_add
    write_bits(stat_cost.save_bits, raw_value)
    
    # 写入配对属性
    for paired_id in PAIRED_STATS.get(stat_id, []):
        paired_cost = get_stat_cost(paired_id)
        paired_value = find_property(paired_id) or 0
        paired_raw = (paired_value >> paired_cost.val_shift) + paired_cost.save_add
        write_bits(paired_cost.save_bits, paired_raw)

write_bits(9, 0x1FF)  # 结束标志
```

注意：写入时跳过 `shifted_value == 0` 的属性 (C++ 行为)。

## 4. 配对属性 (Paired Stats)

某些属性会自动附带配对属性，不需要在数据中单独存储属性ID。配对属性紧跟在主属性值之后读取，没有自己的 9 位 ID。

| 主属性ID | 配对属性ID | 描述 |
|----------|-----------|------|
| 17 | 18 | Enhanced Damage → % Enhanced Damage |
| 48 | 49 | Fire Min Damage → Fire Max Damage |
| 50 | 51 | Light Min Damage → Light Max Damage |
| 52 | 53 | Magic Min Damage → Magic Max Damage |
| 54 | 55, 56 | Cold Min Damage → Cold Max Damage, Cold Length |
| 57 | 58, 59 | Poison Min Damage → Poison Max Damage, Poison Length |

特殊规则：
- 当读取 stat 57 (Poison Min Damage) 时，自动添加 stat 88 (PoisonCount) 值为 1
- stat 88 在写入时被跳过 (隐式属性)

## 5. 属性值解析 (D2R 格式)

### 5.1 从 layer 和 value 到参数数组

D2R 格式的属性值需要从 `layer` 和 `value` 转换为 `params` 数组，用于属性描述显示。

转换逻辑：

1. 计算 `display_value = value >> val_shift` (如果 val_shift > 0)
2. 获取 `property_merged.txt` 中对应属性的 fields 定义
3. 如果有多个活跃字段 (bits > 0)，从 `layer` 中按位拆分参数
4. 否则使用 `[display_value, 0, 0, 0]` 格式

### 5.2 参数拆分规则

```
active_fields = [f for f in prop_meta.fields if f.bits > 0]

if len(active_fields) <= 1:
    if save_param_bits > 0:
        # 尝试从 property_merged.txt 0x63 版本获取字段定义
        return _isc_layer_to_params(prop_id, layer, display_value)
    return [display_value, 0, 0, 0]

isc_bits = save_bits + save_param_bits
if len(active_fields) <= 1 and save_param_bits > 0 and isc_bits > prop_meta.bits_sum:
    return _isc_layer_to_params(prop_id, layer, display_value)

param_fields = active_fields[:-1]  # 最后一个字段是主值

params = [0, 0, 0, 0]
remaining_layer = layer
for i, f in enumerate(param_fields):
    mask = (1 << f.bits) - 1
    params[i] = remaining_layer & mask
    remaining_layer >>= f.bits

params[len(param_fields)] = display_value
```

### 5.3 参数拆分示例

**stat 97 (item_nonclassskill)**：

property_merged.txt 定义了两个字段：
- Field 1: skill_id (bits=9)
- Field 2: skill_level (bits=7)

`layer` 的低 9 位是 skill_id，`display_value` 是 skill_level。

结果：`params = [skill_id, skill_level, 0, 0]`

**stat 83 (item_addskill_tab)**：

property_merged.txt 定义了两个字段：
- Field 1: tab_id (bits=3)
- Field 2: class_id (bits=3)

`layer` 的低 3 位是 tab_id，接下来 3 位是 class_id，`display_value` 是技能点数。

结果：`params = [tab_id, class_id, skill_points, 0]`

## 6. 类型特定字段的位宽

以下字段的位宽不是固定的，由 `ItemStatCost.txt` 中对应 stat 的 `save_bits` 决定：

| 字段 | 对应 stat_id | stat 名称 | 说明 |
|------|-------------|-----------|------|
| 防御值 | 31 | ArmorClass (armorclass) | 护甲物品的防御 |
| 最大耐久度 | 73 | MaxDurability (maxdurability) | 有耐久物品 |
| 当前耐久度 | 72 | Durability (durability) | 最大耐久度 > 0 时 |
| 孔数 | 194 | NumSockets (item_numsockets) | 有孔物品 |
| 任务难度 | 356 | QuestItemDifficulty (quest_difficulty) | 紧凑任务物品 |

这些字段的读取方式与属性列表不同——它们是固定位置的字段，不是 9 位 ID + 值的格式。但位宽和 save_add 同样来自 ItemStatCost.txt。

示例 (0x63 版本的典型值)：

| stat_id | save_bits | save_add | 说明 |
|---------|-----------|----------|------|
| 31 (ArmorClass) | 11 | 10 | 防御值需减去 10 |
| 72 (Durability) | 9 | 0 | 当前耐久度 |
| 73 (MaxDurability) | 8 | 0 | 最大耐久度 |
| 194 (NumSockets) | 3 | 0 | 孔数 (0-7) |

注意：不同版本的 save_bits 可能不同，必须根据版本从对应的 ItemStatCost.txt 读取。

## 7. 常见属性ID

### 7.1 基础属性

| 属性ID | 名称 | 描述 |
|--------|------|------|
| 0 | strength | 力量 |
| 1 | energy | 精力 |
| 2 | dexterity | 敏捷 |
| 3 | vitality | 体力 |

### 7.2 生命/法力/耐力

| 属性ID | 名称 | 描述 |
|--------|------|------|
| 7 | maxhp | 最大生命 |
| 9 | maxmana | 最大法力 |
| 11 | maxstamina | 最大耐力 |

### 7.3 伤害相关

| 属性ID | 名称 | 描述 |
|--------|------|------|
| 16 | enhanceddefense | 增强防御 |
| 17 | enhanceddamage | 增强伤害 |
| 21 | mindamage | 最小伤害 |
| 22 | maxdamage | 最大伤害 |
| 23 | secondarymindamage | 次要最小伤害 |
| 24 | secondarymaxdamage | 次要最大伤害 |

### 7.4 元素伤害

| 属性ID | 名称 | 描述 | 配对 |
|--------|------|------|------|
| 48 | firemindam | 火焰最小伤害 | → 49 (firemaxdam) |
| 49 | firemaxdam | 火焰最大伤害 | |
| 50 | lightmindam | 闪电最小伤害 | → 51 (lightmaxdam) |
| 51 | lightmaxdam | 闪电最大伤害 | |
| 52 | magicmindam | 魔法最小伤害 | → 53 (magicmaxdam) |
| 53 | magicmaxdam | 魔法最大伤害 | |
| 54 | coldmindam | 冰冷最小伤害 | → 55 (coldmaxdam), 56 (coldlength) |
| 55 | coldmaxdam | 冰冷最大伤害 | |
| 56 | coldlength | 冰冷持续时间 | |
| 57 | poisonmindam | 毒素最小伤害 | → 58 (poisonmaxdam), 59 (poisonlength) |
| 58 | poisonmaxdam | 毒素最大伤害 | |
| 59 | poisonlength | 毒素持续时间 | |

### 7.5 抗性

| 属性ID | 名称 | 描述 |
|--------|------|------|
| 39 | fireresist | 火焰抗性 |
| 41 | lightresist | 闪电抗性 |
| 43 | coldresist | 冰冷抗性 |
| 45 | poisonresist | 毒素抗性 |

### 7.6 攻击相关

| 属性ID | 名称 | 描述 |
|--------|------|------|
| 19 | tohit | 攻击命中率 |
| 20 | tohitpercent | 攻击命中率百分比 |
| 31 | armorclass | 防御等级 |
| 60 | damagepercent | 伤害偷取生命% |
| 62 | manadamagepercent | 伤害偷取法力% |

### 7.7 速度相关

| 属性ID | 名称 | 描述 |
|--------|------|------|
| 93 | velocitypercent | 跑步/行走速度 |
| 96 | move_velocity | 更快跑步/行走 |
| 99 | attackrate | 更快攻击速度 |
| 105 | castrate | 更快施法速度 |
| 102 | fasterblock | 更快格挡速度 |

### 7.8 技能相关

| 属性ID | 名称 | save_param_bits | 描述 |
|--------|------|----------------|------|
| 83 | item_addskill_tab | 6 | +X 到技能树 (layer含tab+class) |
| 97 | item_nonclassskill | 9 | +X 到非职业技能 (layer含skill_id) |
| 107 | item_singleskill | 变长 | +X 到特定技能 |
| 126 | item_addclassskills | 变长 | +X 到职业全技能 |
| 127 | item_addskills | 0 | +X 到所有技能 |

### 7.9 特殊属性

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
| 356 | quest_difficulty | 任务难度 (0x69+ 紧凑物品) |

## 8. 属性格式化

属性格式化使用 `item-modifiers.json` 中的描述字符串模板，结合 `descfunc` 和 `descval` 控制显示格式。

### 8.1 descfunc 值

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

### 8.2 descval 值

| descval | 描述 |
|---------|------|
| 0 | 不显示数值 |
| 1 | 正值显示 + |
| 2 | 正值不显示 + |

## 9. 版本差异

0x63 与 0x69 版本在属性格式上的主要差异：

| 差异点 | 0x63 | 0x69 |
|--------|------|------|
| 属性解析方式 | ItemStatCost.txt | ItemStatCost.txt (相同) |
| stat 356 (quest_difficulty) | 不存在 | 存在，用于紧凑任务物品 |
| stat 151 (item_aura) bits_sum | 14 | 5 |
| 某些 stat 的 save_bits | 不同 | 不同 |
| 属性总数 | 较少 | 更多 (新增术士相关属性) |

关键：两个版本的属性解析逻辑相同，差异仅在 ItemStatCost.txt 的数据定义上。
