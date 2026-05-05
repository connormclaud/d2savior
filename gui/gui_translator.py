import locale
from typing import Dict, Optional


TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "enUS": {},
    "zhCN": {
        "D2Savior - Diablo II Character Editor": "D2Savior - 暗黑破坏神II角色编辑器",
        "Ready": "就绪",

        "File": "文件",
        "Open Character...": "打开角色...",
        "Open Item...": "打开物品...",
        "Save": "保存",
        "Save As...": "另存为...",
        "Save All": "全部保存",
        "Recent Files": "最近文件",
        "No recent files": "无最近文件",
        "Close": "关闭",
        "Exit": "退出",

        "View": "视图",
        "Language": "语言",
        "English": "English",
        "Simplified Chinese": "简体中文",
        "Character List": "角色列表",
        "Shared Stash": "共享储物箱",
        "Cascade Windows": "层叠窗口",
        "Tile Windows": "平铺窗口",
        "Toolbar": "工具栏",
        "Toggle Character List": "切换角色列表",
        "Toggle Shared Stash": "切换共享储物箱",

        "Window": "窗口",
        "Settings": "设置",
        "Set Save Folder...": "设置存档文件夹...",
        "Set Save Folder": "设置存档文件夹",

        "Open Diablo II Character Save File": "打开暗黑破坏神II角色存档文件",
        "D2S Files (*.d2s);;All Files (*)": "D2S 文件 (*.d2s);;所有文件 (*)",
        "Open Diablo II Item File": "打开暗黑破坏神II物品文件",
        "D2I Files (*.d2i);;All Files (*)": "D2I 文件 (*.d2i);;所有文件 (*)",
        "Save Diablo II Save File": "保存暗黑破坏神II存档文件",
        "Select Diablo II Save Folder": "选择暗黑破坏神II存档文件夹",

        "Unsaved Changes": "未保存的更改",
        "You have {} document(s) with unsaved changes.\nDo you want to save all changes?": "您有 {} 个文档包含未保存的更改。\n是否保存所有更改？",

        "Error": "错误",
        "Failed to load file:\n{}": "加载文件失败：\n{}",
        "Unknown document type: {}": "未知文档类型：{}",
        "Failed to save file:\n{}": "保存文件失败：\n{}",
        "No item data to save": "无物品数据可保存",
        "No character data to save": "无角色数据可保存",

        "Loaded: {}": "已加载：{}",
        "Saved: {}": "已保存：{}",

        "Unsaved Changes": "未保存的更改",
        "Character '{}' has unsaved changes.\nDo you want to save?": "角色 '{}' 有未保存的更改。\n是否保存？",

        "Success": "成功",
        "Item saved to:\n{}": "物品已保存至：\n{}",
        "Failed to save item:\n{}": "保存物品失败：\n{}",
        "Save Item": "保存物品",
        "Save Item As...": "物品另存为...",

        "Character Info": "角色信息",
        "Items": "物品",
        "Quests": "任务",
        "Waypoints": "传送点",
        "Mercenary": "雇佣兵",

        "Basic Information": "基本信息",
        "Name:": "名称：",
        "Class:": "职业：",
        "Level:": "等级：",
        "Version:": "版本：",
        "Type:": "类型：",
        "Title:": "头衔：",
        "Character Stats": "角色属性",
        "Strength": "力量",
        "Energy": "精力",
        "Dexterity": "敏捷",
        "Vitality": "体力",
        "Stat Points": "属性点",
        "Skills": "技能",
        "Life": "生命",
        "Max Life": "最大生命",
        "Mana": "法力",
        "Max Mana": "最大法力",
        "Stamina": "耐力",
        "Max Stamina": "最大耐力",
        "Experience": "经验",
        "Gold": "金币",
        "Gold: {}": "金币：{}",
        "Stash Gold": "储物箱金币",

        "Amazon": "亚马逊",
        "Sorceress": "女巫",
        "Necromancer": "死灵法师",
        "Paladin": "圣骑士",
        "Barbarian": "野蛮人",
        "Druid": "德鲁伊",
        "Assassin": "刺客",
        "Warlock": "术士",

        "Ladder": "天梯",
        "Expansion": "资料片",
        "Died": "已死亡",
        "Hardcore": "专家模式",
        "Normal": "普通",
        "Classic": "经典",
        "Reign of Warlock": "术士君临",
        "Game Mode:": "游戏模式：",
        "Last Save:": "最后保存：",

        "None": "无",
        "Matriarch": "女族长",
        "Patriarch": "族长",
        "Champion": "冠军",
        "Slayer": "杀手",

        "Characters": "角色",
        "Refresh": "刷新",
        "No save folder set": "未设置存档文件夹",
        "(No save folder)": "（无存档文件夹）",
        "(No characters found)": "（未找到角色）",

        "Shared Stash": "共享储物箱",
        "Reload Stash": "重新加载储物箱",
        "No shared stash\nSet save folder to auto-load": "无共享储物箱\n设置存档文件夹以自动加载",
        "Failed to load stash:\n{}": "加载储物箱失败：\n{}",
        "Normal": "普通",
        "Advanced Stash": "高级储物箱",
        "Chronicle": "编年史",
        "Gem": "宝石箱",
        "Rune": "符文箱",
        "Material": "材料箱",
        "Type {}": "类型 {}",
        "Chronicle Tab": "编年史标签",
        "Items: {}": "物品：{}",

        "Low": "低级",
        "High": "高级",
        "Magic": "魔法",
        "Set": "套装",
        "Rare": "稀有",
        "Unique": "暗金",
        "Crafted": "合成",

        "Helmet": "头盔",
        "Amulet": "护身符",
        "Armor": "盔甲",
        "Weapon I": "武器 I",
        "Shield I": "盾牌 I",
        "Ring (Right)": "戒指（右）",
        "Ring (Left)": "戒指（左）",
        "Belt": "腰带",
        "Boots": "靴子",
        "Gloves": "手套",
        "Weapon II": "武器 II",
        "Shield II": "盾牌 II",

        "Helm": "头盔",
        "Amu": "护符",
        "Weapon": "武器",
        "Shield": "盾牌",
        "Ring": "戒指",

        "Inventory": "背包",
        "Cube": "赫拉迪克方块",
        "Stash": "储物箱",

        "Level": "等级",
        "Quantity": "数量",
        "Defense": "防御",
        "Indestructible": "无法破坏",
        "Durability": "耐久度",
        "Ethereal": "无形",
        "Socketed": "镶孔",
        "Unidentified": "未鉴定",

        "Low Quality": "低品质",
        "Hiquality": "高品质",

        "Mercenary Information": "雇佣兵信息",
        "Status:": "状态：",
        "No Mercenary": "无雇佣兵",
        "Type:": "类型：",
        "Name ID:": "名称ID：",
        "Experience:": "经验：",
        "Hired": "已雇佣",
        "No data": "无数据",
        "Mercenary Items": "雇佣兵物品",
        "Item": "物品",
        "Location": "位置",
        "Quality": "品质",
        "Equipped": "已装备",
        "Golem": "石魔",
        "Has Golem:": "是否有石魔：",
        "Golem Item:": "石魔物品：",
        "Yes": "是",
        "No": "否",

        "Rogue Scout (Act I)": "罗格斥候（第一幕）",
        "Desert Mercenary (Act II)": "沙漠雇佣兵（第二幕）",
        "Iron Wolf (Act III)": "铁狼（第三幕）",
        "Barbarian (Act V)": "野蛮人（第五幕）",

        "Den of Evil": "邪恶洞窟",
        "Sisters' Burial Grounds": "修女埋骨之地",
        "Tools of the Trade": "交易工具",
        "The Search for Cain": "寻找凯恩",
        "The Forgotten Tower": "遗忘之塔",
        "Sisters to the Slaughter": "屠杀的修女",
        "Radament's Lair": "罗达门特的巢穴",
        "The Horadric Staff": "赫拉迪克法杖",
        "Tainted Sun": "被污染的太阳",
        "Arcane Sanctuary": "神秘避难所",
        "The Summoner": "召唤者",
        "The Seven Tombs": "七座古墓",
        "The Golden Bird": "金鸟",
        "Blade of the Old Religion": "古老宗教之刃",
        "Khalim's Will": "卡里姆的意志",
        "Lam Esen's Tome": "拉姆·艾森之书",
        "The Blackened Temple": "黑暗神殿",
        "The Guardian": "守护者",
        "The Fallen Angel": "堕落天使",
        "The Hellforge": "地狱熔炉",
        "Terror's End": "恐惧终结",
        "Siege on Harrogath": "围攻哈洛加斯",
        "Rescue on Mount Arreat": "亚瑞特山救援",
        "Prison of Ice": "冰之囚牢",
        "Betrayal of Harrogath": "哈洛加斯的背叛",
        "Rite of Passage": "通过仪式",
        "Eve of Destruction": "毁灭前夕",

        "Normal": "普通",
        "Nightmare": "噩梦",
        "Hell": "地狱",

        "Act I": "第一幕",
        "Act II": "第二幕",
        "Act III": "第三幕",
        "Act IV": "第四幕",
        "Act V": "第五幕",

        "Quests - {}": "任务 - {}",
        "Stat Reset Available: {}": "属性重置可用：{}",

        "No quest data available": "无任务数据",
        "No waypoint data available": "无传送点数据",
        "No skill data available": "无技能数据",

        "Rogue Encampment": "罗格营地",
        "Cold Plains": "冰冷高地",
        "Stony Field": "石块旷野",
        "Dark Wood": "黑暗森林",
        "Black Marsh": "黑色荒地",
        "Outer Cloister": "外侧回廊",
        "Jail Level 1": "监牢第一层",
        "Inner Cloister": "内侧回廊",
        "Catacombs Level 2": "地下墓穴第二层",
        "Lut Gholein": "鲁·高因",
        "Sewers Level 2": "下水道第二层",
        "Dry Hills": "干燥高地",
        "Halls of the Dead Level 2": "死亡之殿第二层",
        "Far Oasis": "遥远绿洲",
        "Lost City": "失落之城",
        "Palace Cellar Level 1": "皇宫地窖第一层",
        "Arcane Sanctuary": "神秘避难所",
        "Canyon of the Magi": "术士峡谷",
        "Kurast Docks": "库拉斯特海港",
        "Spider Forest": "蜘蛛森林",
        "Great Marsh": "庞大湿地",
        "Flayer Jungle": "剥皮森林",
        "Lower Kurast": "库拉斯特下层",
        "Kurast Bazaar": "库拉斯特商场",
        "Upper Kurast": "库拉斯特上层",
        "Travincal": "崔凡克",
        "Durance of Hate Level 2": "憎恨之牢第二层",
        "The Pandemonium Fortress": "混沌避难所",
        "City of the Damned": "诅咒之城",
        "River of Flame": "火焰之河",
        "Harrogath": "哈洛加斯",
        "Frigid Highlands": "冰冻高地",
        "Arreat Plateau": "亚瑞特高原",
        "Crystalline Passage": "水晶通道",
        "Halls of Pain": "痛苦之厅",
        "Glacial Trail": "冰河路径",
        "Frozen Tundra": "冰冻苔原",
        "The Ancients' Way": "远古之路",
        "Worldstone Keep Level 2": "世界之石大殿第二层",

        "Waypoints - {}": "传送点 - {}",

        "Skill Tree {}": "技能树 {}",
        "Equipped Skills": "装备技能",
        "Left Skill:": "左键技能：",
        "Right Skill:": "右键技能：",
        "Class: {}": "职业：{}",

        "Edit Item": "编辑物品",
        "Basic Information": "基本信息",
        "Type Specific": "类型属性",
        "Properties": "属性列表",
        "Identified": "已鉴定",
        "Newbie": "新手",
        "Simple": "简单",
        "Personalized": "个性化",
        "Rune Word": "符文之语",
        "GUID:": "GUID：",
        "Drop Level:": "掉落等级：",
        "Defense:": "防御：",
        "Max Durability:": "最大耐久：",
        "Current Durability:": "当前耐久：",
        "Sockets:": "孔数：",
        "Quantity:": "数量：",
        "ID": "ID",
        "Property": "属性",
        "Value": "值",
        "Layer": "层",
        "Add Property": "添加属性",
        "Remove Property": "删除属性",
        "Property ID:": "属性ID：",
        "OK": "确定",
        "Cancel": "取消",
        "Ear": "耳朵",
        "Select Property": "选择属性",
        "Filter": "筛选",
        "Category:": "分类：",
        "Category": "分类",
        "Search:": "搜索：",
        "Search": "搜索",
        "Type to filter by name or ID...": "输入名称或ID筛选...",
        "Select": "选择",
        "Description": "描述",
        "All": "全部",
        "Attributes": "基础属性",
        "Life / Mana / Stamina": "生命/法力/耐力",
        "Combat": "战斗",
        "Defense": "防御",
        "Damage %": "伤害百分比",
        "Fire Damage": "火焰伤害",
        "Lightning Damage": "闪电伤害",
        "Cold Damage": "冰霜伤害",
        "Poison Damage": "毒素伤害",
        "Magic Damage": "魔法伤害",
        "Life / Mana Drain": "生命/法力偷取",
        "Fire Resist": "火焰抗性",
        "Lightning Resist": "闪电抗性",
        "Cold Resist": "冰霜抗性",
        "Poison Resist": "毒素抗性",
        "Other Resist": "其他抗性",
        "Fire Absorb": "火焰吸收",
        "Lightning Absorb": "闪电吸收",
        "Cold Absorb": "冰霜吸收",
        "Magic Absorb": "魔法吸收",
        "Speed": "速度",
        "Skills": "技能",
        "Aura": "光环",
        "Chance to Cast": "触发施放",
        "Charges": "充能",
        "Special Effects": "特殊效果",
        "Gold / Magic Find": "寻宝/寻金",
        "Per Level": "按等级成长",
        "Sunder": "破免",
        "Replenish": "补充",
        "Other": "其他",

        "X seconds cold duration": "X秒冰冻持续时间",
        "X seconds poison duration": "X秒毒素持续时间",
        "+X% Faster Run/Walk": "+X% 高速跑步/行走",
        "+X% Faster Attack Rate": "+X% 提升攻击速度",
        "+X to Maximum Durability": "+X 最大耐久度",
        "Double Potion Duration": "双倍药水持续时间",
        "Required Level: X": "需要等级: X",
        "+X% Howl": "+X% 嚎叫",
        "+X to Skill (Class Only)": "+X 技能（限本职业）",
        "X% Reanimate as: Monster": "X% 复活为：怪物",
        "+X to Minimum Throw Damage": "+X 最小投掷伤害",
        "+X to Maximum Throw Damage": "+X 最大投掷伤害",
        "+X% to Attack Rating versus Monster": "+X% 对怪物的攻击准确率",
        "+X% to Damage versus Monster": "+X% 对怪物的伤害",
        "Replenish Durability": "恢复耐久度",
        "Replenish Quantity": "恢复数量",
    },
}


class GuiTranslator:
    def __init__(self):
        self._lang: str = "enUS"
        self._translations: Dict[str, Dict[str, str]] = TRANSLATIONS

    @property
    def current_lang(self) -> str:
        return self._lang

    def set_language(self, lang: str):
        if lang in self._translations:
            self._lang = lang

    def tr(self, text: str) -> str:
        lang_dict = self._translations.get(self._lang, {})
        return lang_dict.get(text, text)

    def tr_format(self, template: str, *args) -> str:
        translated_template = self.tr(template)
        if "{}" in translated_template:
            return translated_template.format(*args)
        return translated_template

    @staticmethod
    def detect_system_language() -> str:
        try:
            sys_lang = locale.getdefaultlocale()[0]
            if sys_lang and sys_lang.startswith("zh"):
                return "zhCN"
        except Exception:
            pass
        return "enUS"


_g_translator: Optional[GuiTranslator] = None


def get_gui_translator() -> GuiTranslator:
    global _g_translator
    if _g_translator is None:
        _g_translator = GuiTranslator()
    return _g_translator


def init_gui_translator(lang: str = None) -> GuiTranslator:
    global _g_translator
    if _g_translator is None:
        _g_translator = GuiTranslator()
    if lang:
        _g_translator.set_language(lang)
    return _g_translator


def tr(text: str) -> str:
    return get_gui_translator().tr(text)


def tr_format(template: str, *args) -> str:
    return get_gui_translator().tr_format(template, *args)
