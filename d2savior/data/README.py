#!/usr/bin/env python3
"""
数据文件说明

【核心数据文件】（生成 itemdata.txt 和 property.txt 必需）
- ItemStatCost.txt - 属性统计定义，包含 save_bits 等关键信息
- Properties.txt - 属性映射，定义属性ID和统计名称的关系
- Weapons.txt - 武器数据
- Armor.txt - 护甲数据
- Misc.txt - 杂项物品数据

【生成的加载文件】（解析存档必需）
- itemdata.txt - 物品元数据，包含物品类型、bSimple、bCharm 等标志
- property.txt - 属性定义，包含属性ID、位数、基值等

【可选数据文件】（用于扩展功能）
- itemtypes.txt - 物品类型分类
- gems.txt - 宝石数据
- runes.txt - 符文数据
- uniqueitems.txt - 暗金物品
- sets.txt - 套装定义
- magicprefix.txt - 魔法前缀
- magicsuffix.txt - 魔法后缀
- rareprefix.txt - 稀有前缀
- raresuffix.txt - 稀有后缀
- automagic.txt - 自动魔法属性
- charstats.txt - 角色属性
- skills.txt - 技能数据
- skilldesc.txt - 技能描述
- monstats.txt - 怪物数据
- levels.txt - 地牢层数
- experience.txt - 经验值表
- treasureclassex.txt - 掉落表
- itemratio.txt - 物品比率
- difficultylevels.txt - 难度等级

【本地化数据】（data/local/）
- item-names.json - 物品名称
- skills.json - 技能名称
- 等等

【数据文件生成】
运行 scripts/regenerate_data_files.py 可以从原始游戏数据生成 itemdata.txt 和 property.txt

使用方法：
  python scripts/regenerate_data_files.py              # 输出到 data/
  python scripts/regenerate_data_files.py -o "Generate Data"  # 输出到 Generate Data/
"""

print(__doc__)
