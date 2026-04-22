import os
from typing import Dict, List, Optional, Tuple


class LanguageData:
    SECTION_MARKERS = {
        'class_name': '角色名字',
        'property_name': '以下是属性名称(Property Name)',
        'monster_name': '以下是怪物名称(Monster Names)',
        'skill_name': '角色技能名字',
        'normal_skill_name': '通用技能名字',
        'skill_tab_name': '角色技能树名字',
        'time_name': '时刻名字',
    }

    def __init__(self):
        self._strings: List[str] = []
        self._sections: Dict[str, Tuple[int, int]] = {}
        self._section_strings: Dict[str, Dict[int, str]] = {}
        self._lang_index: int = 1

    def load(self, filepath: str, lang_index: int = 1) -> bool:
        if not os.path.exists(filepath):
            return False
        
        self._lang_index = lang_index
        
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
        
        self._strings = []
        self._sections = {}
        self._section_strings = {}
        current_section_key = None
        section_base_index = 0
        section_index_map: Dict[int, str] = {}
        
        for line in lines:
            line = line.rstrip('\n\r')
            
            if line.startswith('*======================='):
                if current_section_key is not None:
                    self._sections[current_section_key] = (section_base_index, len(self._strings))
                    self._section_strings[current_section_key] = section_index_map
                
                section_title = line[len('*======================='):].strip()
                current_section_key = None
                for key, marker in self.SECTION_MARKERS.items():
                    if marker in section_title:
                        current_section_key = key
                        break
                section_base_index = len(self._strings)
                section_index_map = {}
                continue
            
            if line.startswith('*') and not line.startswith('*=='):
                continue
            
            parts = line.split('\t')
            
            gidx = -1
            text_parts = []
            for i, part in enumerate(parts):
                part = part.strip()
                if i == 0 and part.isdigit():
                    gidx = int(part)
                else:
                    text_parts.append(part)
            
            if len(text_parts) > lang_index:
                text = text_parts[lang_index].strip()
            elif len(text_parts) > 0:
                text = text_parts[0].strip() if text_parts[0] else (text_parts[1].strip() if len(text_parts) > 1 else '')
            else:
                text = ''
            
            self._strings.append(text)
            
            if gidx >= 0:
                section_index_map[gidx] = text
            else:
                section_index_map[len(self._strings) - 1 - section_base_index] = text
        
        if current_section_key is not None:
            self._sections[current_section_key] = (section_base_index, len(self._strings))
            self._section_strings[current_section_key] = section_index_map
        
        return True

    def get_section_string(self, section_key: str, index: int) -> str:
        if section_key in self._section_strings:
            return self._section_strings[section_key].get(index, '')
        start, end = self._sections.get(section_key, (0, 0))
        actual_index = start + index
        if start <= actual_index < end:
            return self._strings[actual_index]
        return ''

    def get_section_size(self, section_key: str) -> int:
        if section_key in self._section_strings:
            return len(self._section_strings[section_key])
        start, end = self._sections.get(section_key, (0, 0))
        return end - start


_g_language: Optional[LanguageData] = None
_g_item_modifiers: Dict[str, str] = {}


def init_language(filepath: str = None, lang_index: int = 1) -> bool:
    global _g_language
    _g_language = LanguageData()
    if filepath:
        return _g_language.load(filepath, lang_index)
    return True


def init_item_modifiers(filepath: str, lang_key: str = 'enUS') -> bool:
    global _g_item_modifiers
    import json
    if not os.path.exists(filepath):
        return False
    
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        data = json.load(f)
    
    _g_item_modifiers = {}
    for item in data:
        key = item.get('Key', '')
        text = item.get(lang_key, item.get('enUS', ''))
        if key and text:
            _g_item_modifiers[key] = text
    
    return True


def get_item_modifier(key: str) -> str:
    return _g_item_modifiers.get(key, key)


def get_language() -> Optional[LanguageData]:
    return _g_language


CLASS_NAME_SIZE = 7
CLASS_SKILL_NAME_SIZE = 30
CLASS_SKILL_TAB_SIZE = 3

_DEFAULT_CLASS_NAMES = {
    0: 'Amazon',
    1: 'Sorceress',
    2: 'Necromancer',
    3: 'Paladin',
    4: 'Barbarian',
    5: 'Druid',
    6: 'Assassin',
    7: 'Warlock',
}

_DEFAULT_SKILL_TAB_NAMES = {
    (0, 0): 'Bow and Crossbow Skills',
    (0, 1): 'Passive and Magic Skills',
    (0, 2): 'Javelin and Spear Skills',
    (1, 0): 'Fire Spells',
    (1, 1): 'Lightning Spells',
    (1, 2): 'Cold Spells',
    (2, 0): 'Curses',
    (2, 1): 'Poison and Bone Spells',
    (2, 2): 'Summoning Spells',
    (3, 0): 'Combat Skills',
    (3, 1): 'Offensive Auras',
    (3, 2): 'Defensive Auras',
    (4, 0): 'Combat Skills',
    (4, 1): 'Combat Masteries',
    (4, 2): 'Warcries',
    (5, 0): 'Summoning',
    (5, 1): 'Lycanthropy',
    (5, 2): 'Elemental',
    (6, 0): 'Traps',
    (6, 1): 'Shadow Disciplines',
    (6, 2): 'Martial Arts',
    (7, 0): 'Warlock Skills',
    (7, 1): 'Warlock Skills',
    (7, 2): 'Warlock Skills',
}


def get_class_name(class_id: int) -> str:
    lang = get_language()
    if lang:
        result = lang.get_section_string('class_name', class_id)
        if result:
            return result
    return _DEFAULT_CLASS_NAMES.get(class_id, f'Class{class_id}')


def get_skill_name(skill_id: int) -> Tuple[str, int]:
    from core.d2data import get_d2data
    d2data = get_d2data()
    
    if d2data:
        name = d2data.get_skill_name(skill_id)
        if name:
            lang = get_language()
            class_id = -1
            if 6 <= skill_id < 156:
                class_id = (skill_id - 6) // 30
            elif 221 <= skill_id < 281:
                class_id = (skill_id - 221) // 30 + 5
            return name, class_id
    
    lang = get_language()
    if 6 <= skill_id < 156:
        class_id = (skill_id - 6) // 30
        skill_index = (skill_id - 6) % 30
        name = lang.get_section_string('skill_name', class_id * CLASS_SKILL_NAME_SIZE + skill_index) if lang else ''
        return name, class_id
    elif 221 <= skill_id < 281:
        class_id = (skill_id - 221) // 30 + 5
        skill_index = (skill_id - 221) % 30
        name = lang.get_section_string('skill_name', class_id * CLASS_SKILL_NAME_SIZE + skill_index) if lang else ''
        return name, class_id
    else:
        name = lang.get_section_string('normal_skill_name', skill_id) if lang else ''
        if not name:
            name = lang.get_section_string('normal_skill_name', 1023) if lang else 'Unknown Skill'
        return name, -1


def get_skill_tab_name(tab: int, class_id: int) -> str:
    lang = get_language()
    if lang:
        result = lang.get_section_string('skill_tab_name', class_id * CLASS_SKILL_TAB_SIZE + tab)
        if result:
            return result
    return _DEFAULT_SKILL_TAB_NAMES.get((class_id, tab), f'SkillTab{tab}')


def get_monster_name(monster_id: int) -> str:
    lang = get_language()
    if lang:
        return lang.get_section_string('monster_name', monster_id)
    return f'Monster{monster_id}'


def get_time_name(time_id: int) -> str:
    lang = get_language()
    if lang:
        return lang.get_section_string('time_name', time_id)
    return f'Time{time_id}'


def get_property_name(stat_id: int) -> str:
    from core.d2data import get_d2data
    d2data = get_d2data()
    if d2data:
        stat = d2data.get_stat(stat_id)
        if stat and stat.stat_name:
            return stat.stat_name
    
    lang = get_language()
    if lang:
        return lang.get_section_string('property_name', stat_id)
    return f'Stat{stat_id}'


def get_property_tooltip(prop_id: int) -> str:
    from core.d2data import get_d2data
    d2data = get_d2data()
    if d2data:
        prop = d2data.get_property(prop_id)
        if prop:
            return prop.code
    return ''


def format_property(prop_id: int, params: List[int], version: int = 0x60) -> str:
    from core.d2data import get_d2data
    d2data = get_d2data()
    
    if not params:
        stat = d2data.get_stat(prop_id) if d2data else None
        if stat and stat.descstrpos:
            template = get_item_modifier(stat.descstrpos)
            if template and '%d' not in template and '%g' not in template:
                return template
        return get_property_name(prop_id)
    
    a = list(params)
    while len(a) < 4:
        a.append(0)
    
    prop_name = get_property_name(prop_id)
    
    if prop_id == 54:
        a[2] = a[2] // 25 if a[2] else 0
    elif prop_id == 56:
        frames = a[0] // 25 if a[0] else 0
        return f'{frames} seconds cold duration'
    elif prop_id == 59:
        frames = a[0] // 25 if a[0] else 0
        return f'{frames} seconds poison duration'
    elif prop_id == 57:
        a[0] = (a[0] * a[2] + 128) >> 8 if a[0] and a[2] else 0
        a[1] = (a[1] * a[2] + 128) >> 8 if a[1] and a[2] else 0
        a[2] = a[2] // 25 if a[2] else 0
    elif prop_id == 83:
        class_name = get_class_name(a[0])
        return f'+{a[1]} to {class_name} Skill Levels'
    elif prop_id == 97:
        skill_name, class_id = get_skill_name(a[0])
        return f'+{a[1]} to {skill_name}'
    elif prop_id == 151:
        skill_name, _ = get_skill_name(a[0])
        return f'Level {a[1]} {skill_name} Aura When Equipped'
    elif prop_id == 98:
        if 1 <= a[0] <= 5:
            time_name = get_time_name(4 + a[0])
        else:
            time_name = get_time_name(10) if get_language() and get_language().get_section_size('time_name') > 10 else ''
        if time_name:
            return time_name
        return prop_name
    elif prop_id == 73:
        return f'+{a[0]} to Maximum Durability'
    elif prop_id == 88:
        return 'Double Potion Duration'
    elif prop_id == 92:
        return f'Required Level: {a[0]}'
    elif prop_id == 107:
        skill_name, class_id = get_skill_name(a[0])
        class_name = get_class_name(class_id) if class_id >= 0 else ''
        if class_name:
            return f'+{a[1]} to {skill_name} ({class_name} Only)'
        return f'+{a[1]} to {skill_name}'
    elif prop_id == 112:
        a[0] = a[0] * 100 // 127 if a[0] else 0
    elif prop_id == 126:
        a[0], a[1] = a[1], a[0]
    elif prop_id == 155:
        monster_name = get_monster_name(a[0])
        return f'{a[1]}% Reanimate as: {monster_name}'
    elif prop_id == 159:
        return f'+{a[0]} to Minimum Throw Damage'
    elif prop_id == 160:
        return f'+{a[0]} to Maximum Throw Damage'
    elif prop_id in (179, 180):
        monster_name = get_monster_name(a[0])
        if prop_id == 179:
            return f'+{a[1]}% to Attack Rating versus {monster_name}'
        return f'+{a[1]}% to Damage versus {monster_name}'
    elif prop_id == 188:
        skill_tab_name = get_skill_tab_name(a[0], a[1])
        class_name = get_class_name(a[1])
        return f'+{a[2]} to {skill_tab_name} ({class_name} Only)'
    elif prop_id in (195, 196, 197, 198, 199, 201):
        skill_name, _ = get_skill_name(a[1])
        chance = a[0]
        level = a[2]
        if prop_id == 195:
            return f'{chance}% Chance to cast level {level} {skill_name} on attack'
        elif prop_id == 196:
            return f'{chance}% Chance to cast level {level} {skill_name} when you Kill an Enemy'
        elif prop_id == 197:
            return f'{chance}% Chance to cast level {level} {skill_name} when you Die'
        elif prop_id == 198:
            return f'{chance}% Chance to cast level {level} {skill_name} on striking'
        elif prop_id == 199:
            return f'{chance}% Chance to cast level {level} {skill_name} when you Level-Up'
        elif prop_id == 201:
            return f'{chance}% Chance to cast level {level} {skill_name} when struck'
    elif prop_id == 204:
        skill_name, _ = get_skill_name(a[1])
        return f'Level {a[0]} {skill_name} ({a[2]}/{a[3]} Charges)'
    elif prop_id in range(214, 251):
        from core.item import get_stat_cost
        sc = get_stat_cost(prop_id)
        if sc and sc.op_param > 0:
            a[0] = round(a[0] / sc.op_param, 2)
        elif sc and sc.val_shift > 0:
            a[0] = a[0] / (1 << sc.val_shift)
        if prop_id == 237:
            return f'+{a[0]:g} Poison Absorb (Based on Character Level)'
    elif prop_id in (252, 253):
        a[0] = 100 // a[0] if a[0] else 0
    elif prop_id in range(268, 304):
        time_name = get_time_name(a[0])
        if time_name:
            return f'{time_name} +{a[1]} to {prop_name}'
        return prop_name
    elif prop_id in (305, 306, 307, 308, 333, 334, 335, 336):
        a[0] = -a[0]
    
    stat = d2data.get_stat(prop_id) if d2data else None
    if stat and stat.descstrpos:
        template_key = stat.descstrpos if a[0] >= 0 else (stat.descstrneg or stat.descstrpos)
        template = get_item_modifier(template_key)
        if template:
            descfunc = stat.descfunc
            descval = stat.descval
            value = a[0]
            
            if descfunc == 1:
                result = template.replace('%+d', f'{value:+d}').replace('%d', str(value))
            elif descfunc == 2:
                result = template.replace('%+d', f'{value:+d}%').replace('%d', f'{value}%')
            elif descfunc == 3:
                result = template.replace('%+d', f'{value:+d}').replace('%d', str(value))
            elif descfunc == 4:
                result = template.replace('%+d', f'{value:+d}%').replace('%d', f'{value}%')
            elif descfunc == 5:
                result = template.replace('%+d', f'{value:+d}%').replace('%d', f'{value}%')
            elif descfunc == 6:
                result = template.replace('%+d', f'{value:+d}%').replace('%d', f'{value}%')
            elif descfunc == 7:
                result = template.replace('%+d', f'{value:+d}').replace('%d', str(value))
            elif descfunc == 8:
                result = template.replace('%+d', f'{value:+d}%').replace('%d', f'{value}%')
            elif descfunc == 9:
                result = template.replace('%+d', f'{value:+d}').replace('%d', str(value))
            elif descfunc == 10:
                result = template.replace('%+d', f'{value:+d}%').replace('%d', f'{value}%')
            elif descfunc == 11:
                result = template.replace('%+d', f'{value:+d}%').replace('%d', f'{value}%')
            elif descfunc == 12:
                result = template.replace('%+d', f'{value:+d}').replace('%d', str(value))
            elif descfunc == 13:
                result = template.replace('%+d', f'{value:+d}').replace('%d', str(value))
            elif descfunc == 14:
                result = template.replace('%+d', f'{value:+d}').replace('%d', str(value))
            elif descfunc == 15:
                result = template.replace('%+d', f'{value:+d}').replace('%d', str(value))
            elif descfunc == 16:
                result = template.replace('%+d', f'{value:+d}%').replace('%d', f'{value}%')
            elif descfunc == 17:
                result = template.replace('%+d', f'{value:+d}').replace('%d', str(value))
            elif descfunc == 18:
                result = template.replace('%+d', f'{value:+d}').replace('%d', str(value))
            elif descfunc == 19:
                if isinstance(value, float):
                    result = template.replace('%+d', f'{value:+g}').replace('%d', f'{value:g}')
                else:
                    result = template.replace('%+d', f'{value:+d}').replace('%d', str(value))
                if stat.descstr2:
                    extra = get_item_modifier(stat.descstr2)
                    if extra:
                        result = result + ' ' + extra
            elif descfunc == 20:
                result = template.replace('%+d', f'{value:+d}%').replace('%d', f'{value}%')
            elif descfunc == 21:
                result = template.replace('%+d', f'{value:+d}').replace('%d', str(value))
            elif descfunc == 22:
                result = template.replace('%+d', f'{value:+d}%').replace('%d', f'{value}%')
            elif descfunc == 23:
                result = template.replace('%+d', f'{value:+d}').replace('%d', str(value))
            elif descfunc == 24:
                result = template.replace('%+d', f'{value:+d}').replace('%d', str(value))
            else:
                result = template.replace('%+d', f'{value:+d}').replace('%d', str(value))
            
            if '%d' in result or '%+d' in result:
                result = result.replace('%+d', f'{a[1]:+d}').replace('%d', str(a[1]))
            
            result = result.replace('%%', '%')
            
            return result
    
    return _format_template(prop_name, [a[0], a[1], a[2], a[3]])


def _format_template(template: str, values: List) -> str:
    if not template:
        return ''
    
    try:
        if '%+g' in template or '%-g' in template:
            val = values[0]
            if isinstance(val, (int, float)):
                if '%+g' in template:
                    formatted = f'{val:+g}'
                    template = template.replace('%+g', formatted, 1)
                else:
                    formatted = f'{-val:g}'
                    template = template.replace('%-g', formatted, 1)
            return template
        
        if '%g' in template:
            val = values[0]
            if isinstance(val, (int, float)):
                formatted = f'{val:g}'
                template = template.replace('%g', formatted, 1)
            return template
        
        count = template.count('%d') + template.count('%+d') + template.count('%-d')
        
        if count == 0:
            return template
        elif count == 1:
            return template % values[0]
        elif count == 2:
            return template % (values[0], values[1])
        elif count == 3:
            return template % (values[0], values[1], values[2])
        elif count == 4:
            return template % (values[0], values[1], values[2], values[3])
        
        return template
    except (ValueError, TypeError):
        return template


def _format_with_strings(template: str, int_values: List[int], str_values: List[str]) -> str:
    if not template:
        return ''
    
    result = template
    int_idx = 0
    str_idx = 0
    
    i = 0
    while i < len(result):
        if result[i:i+2] == '%s':
            if str_idx < len(str_values):
                result = result[:i] + str_values[str_idx] + result[i+2:]
                str_idx += 1
            else:
                i += 2
        elif result[i:i+3] in ('%+d', '%-d'):
            if int_idx < len(int_values):
                val = int_values[int_idx]
                formatted = f'{val:+d}' if result[i:i+3] == '%+d' else f'{-val:d}'
                result = result[:i] + formatted + result[i+3:]
                int_idx += 1
            else:
                i += 3
        elif result[i:i+2] == '%d':
            if int_idx < len(int_values):
                result = result[:i] + str(int_values[int_idx]) + result[i+2:]
                int_idx += 1
            else:
                i += 2
        else:
            i += 1
    
    return result
