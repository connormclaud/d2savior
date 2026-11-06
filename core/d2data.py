import os
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field


@dataclass
class StatInfo:
    stat_id: int = 0
    stat_name: str = ''
    send_bits: int = 0
    send_param_bits: int = 0
    save_bits: int = 0
    save_add: int = 0
    save_param_bits: int = 0
    op: int = 0
    op_param: int = 0
    op_base: int = 0
    op_stat1: int = 0
    op_stat2: int = 0
    op_stat3: int = 0
    descpriority: int = 0
    descfunc: int = 0
    descval: int = 0
    descstrpos: str = ''
    descstrneg: str = ''
    descstr2: str = ''


@dataclass
class PropertyInfo:
    prop_id: int = 0
    code: str = ''
    func1: int = 0
    stat1: str = ''
    set1: int = 0
    val1: int = 0
    func2: int = 0
    stat2: str = ''
    set2: int = 0
    val2: int = 0
    func3: int = 0
    stat3: str = ''
    set3: int = 0
    val3: int = 0
    func4: int = 0
    stat4: str = ''
    set4: int = 0
    val4: int = 0
    func5: int = 0
    stat5: str = ''
    set5: int = 0
    val5: int = 0
    func6: int = 0
    stat6: str = ''
    set6: int = 0
    val6: int = 0
    func7: int = 0
    stat7: str = ''
    set7: int = 0
    val7: int = 0


@dataclass
class MagicAffixInfo:
    name: str = ''
    affix_id: int = 0
    level: int = 0
    levelreq: int = 0


@dataclass
class UniqueItemInfo:
    index: str = ''
    unique_id: int = 0
    code: str = ''


@dataclass
class SetItemInfo:
    name: str = ''
    set_id: int = 0


@dataclass
class RuneWordInfo:
    name: str = ''
    runeword_id: int = 0
    rune_codes: list = field(default_factory=list)
    key: str = ''


@dataclass
class ItemTypeInfo:
    code: str = ''
    name: str = ''
    item_type: str = ''
    item_type2: str = ''
    invwidth: int = 1
    invheight: int = 1
    hasinv: bool = False
    gemsockets: int = 0
    stackable: bool = False
    useable: bool = False
    throw: bool = False
    compactsave: bool = False
    version: int = 0
    rarity: int = 0
    spawnable: bool = False
    nodurability: bool = False
    durability: int = 0
    mindam: int = 0
    maxdam: int = 0
    minmisdam: int = 0
    maxmisdam: int = 0
    speed: int = 0
    reqstr: int = 0
    reqdex: int = 0
    level: int = 0
    levelreq: int = 0
    cost: int = 0
    component: int = 0
    type: str = ''
    type2: str = ''
    minstack: int = 0
    maxstack: int = 0
    spawnstack: int = 0
    quest: int = 0
    questdiffcheck: bool = False
    pSpell: int = 0
    spellicon: int = 0
    spell_id: int = 0
    belt_rows: int = 0


@dataclass
class VersionData:
    """存储单个版本的所有数据"""
    stats: Dict[int, StatInfo] = field(default_factory=dict)
    stats_by_name: Dict[str, StatInfo] = field(default_factory=dict)
    properties: Dict[int, PropertyInfo] = field(default_factory=dict)
    properties_by_code: Dict[str, PropertyInfo] = field(default_factory=dict)
    items: Dict[str, ItemTypeInfo] = field(default_factory=dict)
    magic_prefixes: Dict[int, MagicAffixInfo] = field(default_factory=dict)
    magic_suffixes: Dict[int, MagicAffixInfo] = field(default_factory=dict)
    unique_items: Dict[int, UniqueItemInfo] = field(default_factory=dict)
    set_items: Dict[int, SetItemInfo] = field(default_factory=dict)
    runewords: Dict[int, RuneWordInfo] = field(default_factory=dict)
    skills: Dict[int, str] = field(default_factory=dict)
    aura_skill_ids: Set[int] = field(default_factory=set)
    type_ancestors: Dict[str, Set[str]] = field(default_factory=dict)
    type_descendants: Dict[str, Set[str]] = field(default_factory=dict)
    type_bodyloc: Dict[str, Tuple[int, int]] = field(default_factory=dict)
    type_beltable: Set[str] = field(default_factory=set)
    item_manager: object = None
    prop_meta: Dict = field(default_factory=dict)
    stat_cost: Dict = field(default_factory=dict)
    
    def is_descendant(self, item_type_code: str, ancestor_code: str) -> bool:
        if not item_type_code or not ancestor_code:
            return False
        # 检查祖先集合中是否包含指定的祖先
        ancestors = self.type_ancestors.get(item_type_code.lower(), set())
        if ancestor_code.lower() in ancestors:
            return True
        # 检查后代集合中是否包含指定的类型
        descendants = self.type_descendants.get(ancestor_code.lower(), set())
        return item_type_code.lower() in descendants

    def is_beltable(self, item_code: str) -> bool:
        if not item_code:
            return False
        code = item_code.lower().strip()
        if code in self.type_beltable:
            return True
        for ancestor in self.type_ancestors.get(code, set()):
            if ancestor in self.type_beltable:
                return True
        item_info = self.items.get(code)
        if item_info:
            item_type = getattr(item_info, 'type', '') or getattr(item_info, 'item_type', '')
            if item_type:
                it = item_type.lower().strip()
                if it in self.type_beltable:
                    return True
                for ancestor in self.type_ancestors.get(it, set()):
                    if ancestor in self.type_beltable:
                        return True
        return False

    def get_belt_rows(self, item_code: str) -> int:
        if not item_code:
            return 0
        code = item_code.lower().strip()
        item_info = self.items.get(code)
        if item_info and item_info.belt_rows > 0:
            return item_info.belt_rows
        return 0


class D2DataLoader:
    """加载单个版本的数据"""
    def __init__(self):
        pass
    
    def load_itemstatcost(self, filepath: str) -> Tuple[Dict[int, StatInfo], Dict[str, StatInfo]]:
        stats = {}
        stats_by_name = {}
        
        if not os.path.exists(filepath):
            return stats
        
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
        
        if len(lines) < 1:
            return stats
        
        header = lines[0].strip().split('\t')
        col_map = {}
        for i, col in enumerate(header):
            col_map[col] = i
        
        for line in lines[1:]:
            line = line.strip()
            if not line or line.startswith('*'):
                continue
            
            parts = line.split('\t')
            
            def get_col(col_name: str, default: str = '') -> str:
                if col_name in col_map and col_map[col_name] < len(parts):
                    return parts[col_map[col_name]]
                return default
            
            def get_int(col_name: str, default: int = 0) -> int:
                val = get_col(col_name)
                if val:
                    try:
                        return int(val)
                    except ValueError:
                        return default
                return default
            
            stat_name = get_col('Stat')
            stat_id = get_int('*ID')
            
            if stat_id < 0:
                continue
            
            stat = StatInfo(
                stat_id=stat_id,
                stat_name=stat_name,
                send_bits=get_int('Send Bits'),
                send_param_bits=get_int('Send Param Bits'),
                save_bits=get_int('Save Bits'),
                save_add=get_int('Save Add'),
                save_param_bits=get_int('Save Param Bits'),
                op=get_int('op'),
                op_param=get_int('op param'),
                op_base=get_int('op base'),
                op_stat1=get_int('op stat1'),
                op_stat2=get_int('op stat2'),
                op_stat3=get_int('op stat3'),
                descpriority=get_int('descpriority'),
                descfunc=get_int('descfunc'),
                descval=get_int('descval'),
                descstrpos=get_col('descstrpos'),
                descstrneg=get_col('descstrneg'),
                descstr2=get_col('descstr2'),
            )
            
            stats[stat_id] = stat
            if stat_name:
                stats_by_name[stat_name] = stat
        
        return stats, stats_by_name
    
    def load_properties(self, filepath: str) -> Tuple[Dict[int, PropertyInfo], Dict[str, PropertyInfo]]:
        properties = {}
        properties_by_code = {}
        
        if not os.path.exists(filepath):
            return properties, properties_by_code
        
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
        
        if len(lines) < 1:
            return properties, properties_by_code
        
        header = lines[0].strip().split('\t')
        col_map = {}
        for i, col in enumerate(header):
            col_map[col] = i
        
        for line in lines[1:]:
            line = line.strip()
            if not line or line.startswith('*'):
                continue
            
            parts = line.split('\t')
            
            def get_col(col_name: str, default: str = '') -> str:
                if col_name in col_map and col_map[col_name] < len(parts):
                    return parts[col_map[col_name]]
                return default
            
            def get_int(col_name: str, default: int = 0) -> int:
                val = get_col(col_name)
                if val:
                    try:
                        return int(val)
                    except ValueError:
                        return default
                return default
            
            code = get_col('code')
            prop_id_str = get_col('*Id')
            
            if not prop_id_str or not code:
                continue
            
            try:
                prop_id = int(prop_id_str)
            except ValueError:
                continue
            
            if prop_id < 0:
                continue
            
            prop = PropertyInfo(
                prop_id=prop_id,
                code=code,
                func1=get_int('func1'),
                stat1=get_col('stat1'),
                set1=get_int('set1'),
                val1=get_int('val1'),
                func2=get_int('func2'),
                stat2=get_col('stat2'),
                set2=get_int('set2'),
                val2=get_int('val2'),
                func3=get_int('func3'),
                stat3=get_col('stat3'),
                set3=get_int('set3'),
                val3=get_int('val3'),
                func4=get_int('func4'),
                stat4=get_col('stat4'),
                set4=get_int('set4'),
                val4=get_int('val4'),
                func5=get_int('func5'),
                stat5=get_col('stat5'),
                set5=get_int('set5'),
                val5=get_int('val5'),
                func6=get_int('func6'),
                stat6=get_col('stat6'),
                set6=get_int('set6'),
                val6=get_int('val6'),
                func7=get_int('func7'),
                stat7=get_col('stat7'),
                set7=get_int('set7'),
                val7=get_int('val7'),
            )
            
            properties[prop_id] = prop
            properties_by_code[code] = prop
        
        return properties, properties_by_code
    
    def load_items_txt(self, filepath: str, item_category: str) -> Dict[str, ItemTypeInfo]:
        items = {}
        
        if not os.path.exists(filepath):
            return items
        
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
        
        if len(lines) < 1:
            return items
        
        header = lines[0].strip().split('\t')
        col_map = {}
        for i, col in enumerate(header):
            col_map[col] = i
        
        for line in lines[1:]:
            line = line.strip()
            if not line or line.startswith('*'):
                continue
            
            parts = line.split('\t')
            
            def get_col(col_name: str, default: str = '') -> str:
                if col_name in col_map and col_map[col_name] < len(parts):
                    return parts[col_map[col_name]]
                return default
            
            def get_int(col_name: str, default: int = 0) -> int:
                val = get_col(col_name)
                if val:
                    try:
                        return int(val)
                    except ValueError:
                        return default
                return default
            
            def get_bool(col_name: str) -> bool:
                val = get_col(col_name)
                return val == '1'
            
            code = get_col('code')
            if not code or code == 'xxx':
                continue
            
            BELT_COL_TO_ROWS = {0: 3, 1: 2, 3: 4, 4: 2, 5: 3, 6: 4}
            item_type_col = get_col('type').lower().strip()
            belt_rows = 0
            if item_type_col == 'belt':
                belt_col_val = get_int('belt', -1)
                belt_rows = BELT_COL_TO_ROWS.get(belt_col_val, 0)

            item = ItemTypeInfo(
                code=code,
                name=get_col('name'),
                item_type=item_category,
                item_type2=get_col('type'),
                invwidth=get_int('invwidth', 1),
                invheight=get_int('invheight', 1),
                hasinv=get_bool('hasinv'),
                gemsockets=get_int('gemsockets'),
                stackable=get_bool('stackable'),
                useable=get_bool('useable'),
                compactsave=get_bool('compactsave'),
                version=get_int('version'),
                rarity=get_int('rarity'),
                spawnable=get_bool('spawnable'),
                nodurability=get_bool('nodurability'),
                durability=get_int('durability'),
                mindam=get_int('mindam'),
                maxdam=get_int('maxdam'),
                minmisdam=get_int('minmisdam'),
                maxmisdam=get_int('maxmisdam'),
                speed=get_int('speed'),
                reqstr=get_int('reqstr'),
                reqdex=get_int('reqdex'),
                level=get_int('level'),
                levelreq=get_int('levelreq'),
                cost=get_int('cost'),
                component=get_int('component'),
                type=get_col('type'),
                type2=get_col('type2'),
                minstack=get_int('minstack'),
                maxstack=get_int('maxstack'),
                spawnstack=get_int('spawnstack'),
                quest=get_int('quest'),
                questdiffcheck=get_bool('questdiffcheck'),
                pSpell=get_int('pSpell'),
                spellicon=get_int('spellicon'),
                belt_rows=belt_rows,
            )
            
            items[code] = item
            
            normcode = get_col('normcode')
            if normcode and normcode != 'xxx' and normcode not in items:
                items[normcode] = item
            
            ubercode = get_col('ubercode')
            if ubercode and ubercode != 'xxx' and ubercode not in items:
                items[ubercode] = item
            
            ultracode = get_col('ultracode')
            if ultracode and ultracode != 'xxx' and ultracode not in items:
                items[ultracode] = item
        
        return items
    
    def load_magic_affix(self, filepath: str, is_prefix: bool) -> Dict[int, MagicAffixInfo]:
        affix_dict = {}
        
        if not os.path.exists(filepath):
            return affix_dict
        
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
        
        if len(lines) < 1:
            return affix_dict
        
        header = lines[0].strip().split('\t')
        col_map = {}
        for i, col in enumerate(header):
            col_map[col] = i
        
        for idx, line in enumerate(lines[1:]):
            line = line.strip()
            if not line or line.startswith('*'):
                continue
            
            parts = line.split('\t')
            
            def get_col(col_name: str, default: str = '') -> str:
                if col_name in col_map and col_map[col_name] < len(parts):
                    return parts[col_map[col_name]]
                return default
            
            def get_int(col_name: str, default: int = 0) -> int:
                val = get_col(col_name)
                if val:
                    try:
                        return int(val)
                    except ValueError:
                        return default
                return default
            
            name = get_col('Name')
            if not name:
                continue
            
            affix = MagicAffixInfo(
                name=name,
                affix_id=idx + 1,
                level=get_int('level'),
                levelreq=get_int('levelreq'),
            )
            affix_dict[idx + 1] = affix
        
        return affix_dict
    
    def load_unique_items(self, filepath: str) -> Dict[int, UniqueItemInfo]:
        unique_items = {}
        
        if not os.path.exists(filepath):
            return unique_items
        
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
        
        if len(lines) < 1:
            return unique_items
        
        header = lines[0].strip().split('\t')
        col_map = {}
        for i, col in enumerate(header):
            col_map[col] = i
        
        for line in lines[1:]:
            line = line.strip()
            if not line or line.startswith('*'):
                continue
            
            parts = line.split('\t')
            
            def get_col(col_name: str, default: str = '') -> str:
                if col_name in col_map and col_map[col_name] < len(parts):
                    return parts[col_map[col_name]]
                return default
            
            def get_int(col_name: str, default: int = 0) -> int:
                val = get_col(col_name)
                if val:
                    try:
                        return int(val)
                    except ValueError:
                        return default
                return default
            
            unique_id = get_int('*ID')
            if unique_id <= 0:
                continue
            
            item = UniqueItemInfo(
                index=get_col('index'),
                unique_id=unique_id,
                code=get_col('code'),
            )
            unique_items[unique_id] = item
        
        return unique_items
    
    def load_runewords(self, filepath: str) -> Dict[int, RuneWordInfo]:
        runewords = {}
        
        if not os.path.exists(filepath):
            return runewords
        
        import json
        try:
            with open(filepath, 'r', encoding='utf-8-sig') as f:
                data = json.load(f)
            
            for item in data:
                key = item.get('Key', '')
                if key.startswith('Runeword'):
                    runeword_id = item.get('id', 0)
                    name = item.get('enUS', '')
                    if runeword_id > 0 and name:
                        runewords[runeword_id] = RuneWordInfo(
                            name=name,
                            runeword_id=runeword_id,
                            key=key
                        )
        except Exception:
            pass
        
        return runewords
    
    def load_runes_txt(self, filepath: str, runewords: Dict[int, RuneWordInfo]) -> None:
        if not os.path.exists(filepath):
            return
        
        key_to_id = {}
        for rw_id, rw_info in runewords.items():
            if rw_info.key:
                key_to_id[rw_info.key] = rw_id
        
        try:
            with open(filepath, 'r', encoding='utf-8-sig') as f:
                lines = f.readlines()
            
            if not lines:
                return
            
            header = lines[0].strip().split('\t')
            name_idx = header.index('Name') if 'Name' in header else 0
            rune_fields = []
            for i in range(1, 7):
                field = f'Rune{i}'
                if field in header:
                    rune_fields.append(header.index(field))
            
            for line in lines[1:]:
                parts = line.strip().split('\t')
                if len(parts) <= name_idx:
                    continue
                name_val = parts[name_idx]
                if name_val not in key_to_id:
                    continue
                
                rw_id = key_to_id[name_val]
                rune_codes = []
                for idx in rune_fields:
                    if idx < len(parts) and parts[idx]:
                        rune_codes.append(parts[idx])
                
                if rune_codes and rw_id in runewords:
                    runewords[rw_id].rune_codes = rune_codes
        except Exception:
            pass
    
    def load_set_items(self, filepath: str) -> Dict[int, SetItemInfo]:
        set_items = {}
        
        if not os.path.exists(filepath):
            return set_items
        
        import json
        try:
            with open(filepath, 'r', encoding='utf-8-sig') as f:
                data = json.load(f)
            
            name_to_id = {}
            for item in data:
                if isinstance(item, dict):
                    key = item.get('Key', '')
                    item_id = item.get('id', 0)
                    if key and item_id:
                        name_to_id[key] = item_id
            
            set_item_names = [
                "Civerb's Ward", "Civerb's Icon", "Civerb's Cudgel",
                "Hsarus' Iron Heel", "Hsarus' Iron Fist", "Hsarus' Iron Stay",
                "Cleglaw's Tooth", "Cleglaw's Claw", "Cleglaw's Pincers",
                "Iratha's Collar", "Iratha's Cuff", "Iratha's Coil", "Iratha's Cord",
                "Isenhart's Lightbrand", "Isenhart's Parry", "Isenhart's Case", "Isenhart's Horns",
                "Vidala's Barb", "Vidala's Fetlock", "Vidala's Ambush", "Vidala's Snare",
                "Milabrega's Orb", "Milabrega's Rod", "Milabrega's Diadem", "Milabrega's Robe",
                "Cathan's Rule", "Cathan's Mesh", "Cathan's Visage", "Cathan's Sigil", "Cathan's Seal",
                "Tancred's Crowbill", "Tancred's Spine", "Tancred's Hobnails", "Tancred's Weird", "Tancred's Skull",
                "Sigon's Gage", "Sigon's Visor", "Sigon's Shelter", "Sigon's Sabot", "Sigon's Wrap", "Sigon's Guard",
                "Infernal Cranium", "Infernal Torch", "Infernal Sign",
                "Berserker's Headgear", "Berserker's Hauberk", "Berserker's Hatchet",
                "Death's Hand", "Death's Guard", "Death's Touch",
                "Angelic Sickle", "Angelic Mantle", "Angelic Halo", "Angelic Wings",
                "Arctic Horn", "Arctic Furs", "Arctic Binding", "Arctic Mitts",
                "Arcanna's Sign", "Arcanna's Deathwand", "Arcanna's Head", "Arcanna's Flesh",
                "Natalya's Totem", "Natalya's Mark", "Natalya's Shadow", "Natalya's Soul",
                "Aldur's Stony Gaze", "Aldur's Deception", "Aldur's Gauntlet", "Aldur's Advance",
                "Immortal King's Will", "Immortal King's Soul Cage", "Immortal King's Detail", "Immortal King's Forge", "Immortal King's Pillar", "Immortal King's Stone Crusher",
                "Tal Rasha's Fine-Spun Cloth", "Tal Rasha's Adjudication", "Tal Rasha's Lidless Eye", "Tal Rasha's Guardianship", "Tal Rasha's Horadric Crest",
                "Griswold's Valor", "Griswold's Heart", "Griswold's Redemption", "Griswold's Honor",
                "Trang-Oul's Guise", "Trang-Oul's Scales", "Trang-Oul's Wing", "Trang-Oul's Claws", "Trang-Oul's Girth",
                "M'avina's True Sight", "M'avina's Embrace", "M'avina's Icy Clutch", "M'avina's Tenet", "M'avina's Caster",
                "Telling of Beads", "Laying of Hands", "Rite of Passage", "Spiritual Custodian", "Credendum",
                "Dangoon's Teaching", "Heaven's Taebaek", "Haemosu's Adament", "Ondal's Almighty",
                "Guillaume's Face", "Wilhelm's Pride", "Magnus' Skin", "Wihtstan's Guard",
                "Hwanin's Splendor", "Hwanin's Refuge", "Hwanin's Seal", "Hwanin's Justice",
                "Sazabi's Cobalt Redeemer", "Sazabi's Ghost Liberator", "Sazabi's Mental Sheath",
                "Bul-Kathos' Sacred Charge", "Bul-Kathos' Tribal Guardian",
                "Cow King's Horns", "Cow King's Hide", "Cow King's Hoofs",
                "Naj's Puzzler", "Naj's Light Plate", "Naj's Circlet",
                "McAuley's Paragon", "McAuley's Riprap", "McAuley's Taboo", "McAuley's Superstition",
                "Warlord's Lust", "Warlord's Conquest", "Warlord's Mantle", "Warlord's Crushers", "Warlord's Authority",
                "Bane's Oathmaker", "Bane's Wraithskin", "Bane's Authority",
                "Horazon's Countenance", "Horazon's Dominion", "Horazon's Hold", "Horazon's Legacy", "Horazon's Secrets",
            ]
            
            for idx, name in enumerate(set_item_names):
                item_id = name_to_id.get(name, 0)
                set_items[idx] = SetItemInfo(
                    name=name,
                    set_id=item_id
                )
        except Exception:
            pass
        
        return set_items
    
    def load_skills(self, filepath: str) -> Tuple[Dict[int, str], Set[int]]:
        skills = {}
        aura_skill_ids = set()
        
        if not os.path.exists(filepath):
            return skills, aura_skill_ids
        
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
        
        if len(lines) < 1:
            return skills, aura_skill_ids
        
        header = lines[0].strip().split('\t')
        col_map = {}
        for i, col in enumerate(header):
            col_map[col] = i
        
        for line in lines[1:]:
            line = line.strip()
            if not line or line.startswith('*'):
                continue
            
            parts = line.split('\t')
            
            def get_col(col_name: str, default: str = '') -> str:
                if col_name in col_map and col_map[col_name] < len(parts):
                    return parts[col_map[col_name]]
                return default
            
            def get_int(col_name: str, default: int = 0) -> int:
                val = get_col(col_name)
                if val:
                    try:
                        return int(val)
                    except ValueError:
                        return default
                return default
            
            skill_name = get_col('skill')
            skill_id = get_int('*Id')
            
            if skill_id >= 0 and skill_name:
                skills[skill_id] = skill_name
            
            aura_val = get_int('aura')
            if aura_val == 1:
                aura_skill_ids.add(skill_id)
        
        return skills, aura_skill_ids
    
    BODYLOC_MAP = {
        'head': 1, 'neck': 2, 'tors': 3, 'rarm': 4, 'larm': 5,
        'rrin': 6, 'lrin': 7, 'belt': 8, 'feet': 9, 'glov': 10,
    }
    
    def load_itemtypes(self, filepath: str) -> Tuple[Dict[str, Set[str]], Dict[str, Set[str]], Dict[str, Tuple[int, int]], Set[str]]:
        type_ancestors = {}
        type_descendants = {}
        type_bodyloc = {}
        beltable_codes = set()
        
        if not os.path.exists(filepath):
            return type_ancestors, type_descendants, type_bodyloc, beltable_codes
        
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
        
        if len(lines) < 1:
            return type_ancestors, type_descendants
        
        header = lines[0].strip().split('\t')
        col_map = {}
        for i, col in enumerate(header):
            col_map[col.strip().lower()] = i
        
        type_equivs: Dict[str, Tuple[str, str]] = {}
        all_codes: Set[str] = set()
        for line in lines[1:]:
            line = line.strip()
            if not line or line.startswith('*') or line.startswith('Expansion'):
                continue
            parts = line.split('\t')
            
            def get_col(name: str, default: str = '') -> str:
                idx = col_map.get(name.strip().lower(), -1)
                return parts[idx].strip() if 0 <= idx < len(parts) else default
            
            type_name = get_col('itemtype')
            code = get_col('code')
            equiv1 = get_col('equiv1')
            equiv2 = get_col('equiv2')
            bodyloc1 = get_col('bodyloc1', '0')
            bodyloc2 = get_col('bodyloc2', '0')
            
            if not type_name:
                continue
            
            key = type_name.lower()
            type_equivs[key] = (equiv1.lower(), equiv2.lower())
            all_codes.add(key)
            bl1 = self.BODYLOC_MAP.get(bodyloc1.lower(), 0) if bodyloc1 else 0
            bl2 = self.BODYLOC_MAP.get(bodyloc2.lower(), 0) if bodyloc2 else 0
            type_bodyloc[key] = (bl1, bl2)
            if code:
                code_lower = code.lower()
                type_equivs[code_lower] = (equiv1.lower(), equiv2.lower())
                all_codes.add(code_lower)
                type_bodyloc[code_lower] = (bl1, bl2)
            
            beltable = get_col('beltable', '0')
            if beltable == '1':
                beltable_codes.add(key)
                if code:
                    beltable_codes.add(code.lower())
        
        # 构建祖先关系
        for key in all_codes:
            type_ancestors[key] = self._build_ancestors(key, type_equivs)
        
        # 构建后代关系
        for key in all_codes:
            type_descendants[key] = {key}
        for code, ancestors in type_ancestors.items():
            for ancestor in ancestors:
                if ancestor not in type_descendants:
                    type_descendants[ancestor] = set()
                type_descendants[ancestor].add(code)
        
        return type_ancestors, type_descendants, type_bodyloc, beltable_codes
    
    def _build_ancestors(self, code: str, type_equivs: Dict[str, Tuple[str, str]], visited: Set[str] = None) -> Set[str]:
        if visited is None:
            visited = set()
        if code in visited:
            return set()
        visited.add(code)
        
        ancestors = set()
        equivs = type_equivs.get(code)
        if equivs:
            for equiv in equivs:
                if equiv:
                    ancestors.add(equiv)
                    ancestors.update(self._build_ancestors(equiv, type_equivs, visited))
        return ancestors
    
    def _resolve_path(self, filename: str, data_dir: str, fallback_dir: str = None) -> str:
        """解析文件路径，优先从版本目录加载，缺失时回退到根目录"""
        path = os.path.join(data_dir, filename)
        if os.path.exists(path):
            return path
        if fallback_dir:
            fallback_path = os.path.join(fallback_dir, filename)
            if os.path.exists(fallback_path):
                return fallback_path
        return path

    def load_version_data(self, data_dir: str, fallback_dir: str = None) -> VersionData:
        """加载单个版本的所有数据
        
        Args:
            data_dir: 版本数据目录（如 data/0x63/）
            fallback_dir: 回退目录，当版本目录中缺失文件时从此目录加载（如 data/）
        """
        version_data = VersionData()
        
        # 加载itemtypes.txt（需要先加载，因为其他数据可能依赖它）
        itemtypes_path = self._resolve_path('itemtypes.txt', data_dir, fallback_dir)
        version_data.type_ancestors, version_data.type_descendants, version_data.type_bodyloc, version_data.type_beltable = self.load_itemtypes(itemtypes_path)
        
        # 加载ItemStatCost.txt
        itemstatcost_path = self._resolve_path('ItemStatCost.txt', data_dir, fallback_dir)
        version_data.stats, version_data.stats_by_name = self.load_itemstatcost(itemstatcost_path)
        
        # 加载Properties.txt
        properties_path = self._resolve_path('Properties.txt', data_dir, fallback_dir)
        version_data.properties, version_data.properties_by_code = self.load_properties(properties_path)
        
        # 加载Armor.txt
        armor_path = self._resolve_path('Armor.txt', data_dir, fallback_dir)
        armor_items = self.load_items_txt(armor_path, 'armor')
        version_data.items.update(armor_items)
        
        # 加载Weapons.txt
        weapons_path = self._resolve_path('Weapons.txt', data_dir, fallback_dir)
        weapons_items = self.load_items_txt(weapons_path, 'weapon')
        version_data.items.update(weapons_items)
        
        # 加载Misc.txt
        misc_path = self._resolve_path('Misc.txt', data_dir, fallback_dir)
        misc_items = self.load_items_txt(misc_path, 'misc')
        version_data.items.update(misc_items)
        
        # 加载magicprefix.txt
        magicprefix_path = self._resolve_path('magicprefix.txt', data_dir, fallback_dir)
        version_data.magic_prefixes = self.load_magic_affix(magicprefix_path, is_prefix=True)
        
        # 加载magicsuffix.txt
        magicsuffix_path = self._resolve_path('magicsuffix.txt', data_dir, fallback_dir)
        version_data.magic_suffixes = self.load_magic_affix(magicsuffix_path, is_prefix=False)
        
        # 加载uniqueitems.txt
        uniqueitems_path = self._resolve_path('uniqueitems.txt', data_dir, fallback_dir)
        version_data.unique_items = self.load_unique_items(uniqueitems_path)
        
        # 加载set items
        setitems_path = self._resolve_path(os.path.join('local', 'item-names.json'), data_dir, fallback_dir)
        version_data.set_items = self.load_set_items(setitems_path)
        
        # 加载runewords
        runewords_path = self._resolve_path(os.path.join('local', 'item-runes.json'), data_dir, fallback_dir)
        version_data.runewords = self.load_runewords(runewords_path)
        
        # 加载runes.txt补充符文列表
        runes_txt_path = self._resolve_path('runes.txt', data_dir, fallback_dir)
        self.load_runes_txt(runes_txt_path, version_data.runewords)
        
        # 加载skills.txt
        skills_path = self._resolve_path('skills.txt', data_dir, fallback_dir)
        version_data.skills, version_data.aura_skill_ids = self.load_skills(skills_path)
        
        # 加载itemdata.txt（物品元数据）
        from core.item import parse_itemdata_txt, parse_property_txt, parse_itemstatcost_txt
        itemdata_path = self._resolve_path('itemdata.txt', data_dir, fallback_dir)
        version_data.item_manager = parse_itemdata_txt(itemdata_path)
        
        # 加载property.txt（属性编码元数据）
        property_path = self._resolve_path('property.txt', data_dir, fallback_dir)
        version_data.prop_meta = parse_property_txt(property_path)
        
        # 加载ItemStatCost.txt（属性成本元数据）
        statcost_path = self._resolve_path('ItemStatCost.txt', data_dir, fallback_dir)
        version_data.stat_cost = parse_itemstatcost_txt(statcost_path)
        
        return version_data


class D2DataManager:
    """管理多个版本的数据"""
    def __init__(self):
        self.version_data: Dict[int, VersionData] = {}
        self.default_version: int = 0x63  # 默认版本
    
    def load_version(self, version: int, data_dir: str, fallback_dir: str = None) -> bool:
        """加载指定版本的数据
        
        Args:
            version: 版本号（如 0x63, 0x69）
            data_dir: 版本数据目录
            fallback_dir: 回退目录，当版本目录中缺失文件时从此目录加载
        """
        if not os.path.exists(data_dir):
            return False
        
        loader = D2DataLoader()
        version_data = loader.load_version_data(data_dir, fallback_dir)
        self.version_data[version] = version_data
        return True
    
    def load_all_versions(self, base_data_dir: str) -> bool:
        """加载所有版本的数据
        
        Args:
            base_data_dir: 基础数据目录，包含版本子目录（0x63/, 0x69/）和回退文件
        """
        success = True
        
        # 尝试加载0x63版本
        v63_dir = os.path.join(base_data_dir, '0x63')
        if os.path.exists(v63_dir):
            if not self.load_version(0x63, v63_dir, base_data_dir):
                success = False
        else:
            # 如果没有0x63子目录，尝试从根目录加载（保持向后兼容）
            if not self.load_version(0x63, base_data_dir):
                success = False
        
        # 尝试加载0x69版本
        v69_dir = os.path.join(base_data_dir, '0x69')
        if os.path.exists(v69_dir):
            if not self.load_version(0x69, v69_dir, base_data_dir):
                success = False
        
        return success
    
    def get_version_data(self, version: int) -> Optional[VersionData]:
        """获取指定版本的数据"""
        if version in self.version_data:
            return self.version_data[version]
        # 如果请求的版本不存在，返回默认版本
        return self.version_data.get(self.default_version)
    
    def get_stat(self, stat_id: int, version: int = None) -> Optional[StatInfo]:
        """获取指定版本的stat信息"""
        version = version or self.default_version
        data = self.get_version_data(version)
        if data:
            return data.stats.get(stat_id)
        return None
    
    def get_stat_by_name(self, stat_name: str, version: int = None) -> Optional[StatInfo]:
        """通过名称获取指定版本的stat信息"""
        version = version or self.default_version
        data = self.get_version_data(version)
        if data:
            return data.stats_by_name.get(stat_name)
        return None
    
    def get_property(self, prop_id: int, version: int = None) -> Optional[PropertyInfo]:
        """获取指定版本的property信息"""
        version = version or self.default_version
        data = self.get_version_data(version)
        if data:
            return data.properties.get(prop_id)
        return None
    
    def get_property_by_code(self, code: str, version: int = None) -> Optional[PropertyInfo]:
        """通过代码获取指定版本的property信息"""
        version = version or self.default_version
        data = self.get_version_data(version)
        if data:
            return data.properties_by_code.get(code)
        return None
    
    def get_item(self, code: str, version: int = None) -> Optional[ItemTypeInfo]:
        """获取指定版本的item信息"""
        version = version or self.default_version
        data = self.get_version_data(version)
        if data:
            return data.items.get(code)
        return None
    
    def get_magic_prefix(self, prefix_id: int, version: int = None) -> Optional[MagicAffixInfo]:
        """获取指定版本的magic prefix信息"""
        version = version or self.default_version
        data = self.get_version_data(version)
        if data:
            return data.magic_prefixes.get(prefix_id)
        return None
    
    def get_magic_suffix(self, suffix_id: int, version: int = None) -> Optional[MagicAffixInfo]:
        """获取指定版本的magic suffix信息"""
        version = version or self.default_version
        data = self.get_version_data(version)
        if data:
            return data.magic_suffixes.get(suffix_id)
        return None
    
    def get_unique_item(self, unique_id: int, version: int = None) -> Optional[UniqueItemInfo]:
        """获取指定版本的unique item信息"""
        version = version or self.default_version
        data = self.get_version_data(version)
        if data:
            return data.unique_items.get(unique_id)
        return None
    
    def get_set_item(self, set_id: int, version: int = None) -> Optional[SetItemInfo]:
        """获取指定版本的set item信息"""
        version = version or self.default_version
        data = self.get_version_data(version)
        if data:
            return data.set_items.get(set_id)
        return None
    
    def get_runeword(self, runeword_id: int, version: int = None) -> Optional[RuneWordInfo]:
        """获取指定版本的runeword信息"""
        version = version or self.default_version
        data = self.get_version_data(version)
        if data:
            return data.runewords.get(runeword_id)
        return None
    
    def get_skill_name(self, skill_id: int, version: int = None) -> str:
        """获取指定版本的skill名称"""
        version = version or self.default_version
        data = self.get_version_data(version)
        if data:
            return data.skills.get(skill_id, '')
        return ''
    
    def get_aura_skill_ids(self, version: int = None) -> Set[int]:
        """获取指定版本的aura技能ID集合"""
        version = version or self.default_version
        data = self.get_version_data(version)
        if data:
            return data.aura_skill_ids
        return set()
    
    def is_descendant(self, item_type_code: str, ancestor_code: str, version: int = None) -> bool:
        """检查item类型是否是指定祖先类型的后代"""
        version = version or self.default_version
        data = self.get_version_data(version)
        if data:
            return data.is_descendant(item_type_code, ancestor_code)
        return False
    
    def is_beltable(self, item_code: str, version: int = None) -> bool:
        """检查物品是否可以放入腰带"""
        version = version or self.default_version
        data = self.get_version_data(version)
        if data:
            return data.is_beltable(item_code)
        return False

    def get_belt_rows(self, item_code: str, version: int = None) -> int:
        version = version or self.default_version
        data = self.get_version_data(version)
        if data:
            return data.get_belt_rows(item_code)
        return 0
    
    def get_item_meta(self, type_id: bytes, version: int = 0) -> Optional[object]:
        """获取指定版本的物品元数据"""
        ver = version if version in self.version_data else self.default_version
        data = self.get_version_data(ver)
        if data and data.item_manager is not None:
            return data.item_manager.get_item(type_id, version)
        return None
    
    def get_property_meta(self, prop_id: int, version: int = 0) -> Optional[object]:
        """获取指定版本的属性编码元数据"""
        ver = version if version in self.version_data else self.default_version
        data = self.get_version_data(ver)
        if data and prop_id in data.prop_meta:
            return data.prop_meta[prop_id].find_data(version)
        return None
    
    def get_stat_cost(self, stat_id: int, version: int = None) -> Optional[object]:
        """获取指定版本的属性成本元数据"""
        ver = version if version in self.version_data else self.default_version
        data = self.get_version_data(ver)
        if data and stat_id in data.stat_cost:
            return data.stat_cost.get(stat_id)
        return None


# 全局数据管理器实例
_g_d2data_manager: Optional[D2DataManager] = None
# 向后兼容的全局数据加载器（包装器）
_g_d2data_wrapper: Optional['D2DataWrapper'] = None


class D2DataWrapper:
    """向后兼容的包装器，模拟旧的D2DataLoader接口"""
    def __init__(self, manager: D2DataManager):
        self.manager = manager
    
    def get_stat(self, stat_id: int) -> Optional[StatInfo]:
        return self.manager.get_stat(stat_id)
    
    def get_stat_by_name(self, stat_name: str) -> Optional[StatInfo]:
        return self.manager.get_stat_by_name(stat_name)
    
    def get_property(self, prop_id: int) -> Optional[PropertyInfo]:
        return self.manager.get_property(prop_id)
    
    def get_property_by_code(self, code: str) -> Optional[PropertyInfo]:
        return self.manager.get_property_by_code(code)
    
    def get_item(self, code: str) -> Optional[ItemTypeInfo]:
        return self.manager.get_item(code)
    
    def get_magic_prefix(self, prefix_id: int) -> Optional[MagicAffixInfo]:
        return self.manager.get_magic_prefix(prefix_id)
    
    def get_magic_suffix(self, suffix_id: int) -> Optional[MagicAffixInfo]:
        return self.manager.get_magic_suffix(suffix_id)
    
    def get_unique_item(self, unique_id: int) -> Optional[UniqueItemInfo]:
        return self.manager.get_unique_item(unique_id)
    
    def get_set_item(self, set_id: int, version: int = None) -> Optional[SetItemInfo]:
        return self.manager.get_set_item(set_id, version)
    
    def get_runeword(self, runeword_id: int) -> Optional[RuneWordInfo]:
        return self.manager.get_runeword(runeword_id)
    
    def get_skill_name(self, skill_id: int) -> str:
        return self.manager.get_skill_name(skill_id)
    
    def is_descendant(self, item_type_code: str, ancestor_code: str) -> bool:
        return self.manager.is_descendant(item_type_code, ancestor_code)
    
    def is_beltable(self, item_code: str, version: int = None) -> bool:
        return self.manager.is_beltable(item_code, version)


def init_d2data(data_dir: str) -> bool:
    """初始化数据，保持向后兼容"""
    global _g_d2data_manager, _g_d2data_wrapper
    
    _g_d2data_manager = D2DataManager()
    result = _g_d2data_manager.load_all_versions(data_dir)
    
    _g_d2data_wrapper = D2DataWrapper(_g_d2data_manager)
    
    from core.item import init_item_data
    
    itemdata_path = os.path.join(data_dir, 'itemdata.txt')
    if not os.path.exists(itemdata_path):
        itemdata_path = None
    
    property_path = os.path.join(data_dir, 'property.txt')
    if not os.path.exists(property_path):
        property_path = None

    statcost_path = os.path.join(data_dir, 'ItemStatCost.txt')
    if not os.path.exists(statcost_path):
        statcost_path = None

    if itemdata_path or property_path or statcost_path:
        init_item_data(itemdata_path=itemdata_path, property_path=property_path,
                       statcost_path=statcost_path)
    
    return result


def get_d2data() -> Optional[D2DataWrapper]:
    """获取数据加载器，保持向后兼容"""
    return _g_d2data_wrapper


def get_d2data_manager() -> Optional[D2DataManager]:
    """获取数据管理器"""
    return _g_d2data_manager


_UNSET = object()


class GameDataResolver:
    """Facade unifying versioned D2DataManager and fallback D2Data lookups."""

    def __init__(
        self,
        version: int = 0x63,
        mgr: Optional[D2DataManager] = _UNSET,
        legacy: Optional[D2DataWrapper] = _UNSET,
    ):
        self.version = version
        self._mgr = get_d2data_manager() if mgr is _UNSET else mgr
        self._legacy = get_d2data() if legacy is _UNSET else legacy

    def get_item(self, code: str) -> Optional[ItemTypeInfo]:
        if self._mgr:
            return self._mgr.get_item(code, self.version)
        return self._legacy.get_item(code) if self._legacy else None

    def get_skill_name(self, skill_id: int) -> str:
        from core.property import get_skill_name as prop_get_skill_name
        loc_name, _ = prop_get_skill_name(skill_id)
        if loc_name and loc_name != "Unknown Skill":
            return loc_name
        if self._mgr:
            name = self._mgr.get_skill_name(skill_id, self.version)
            if name:
                return name
        if self._legacy:
            name = self._legacy.get_skill_name(skill_id)
            if name:
                return name
        return ""

    def get_runeword(self, runeword_id: int) -> Optional[RuneWordInfo]:
        if self._mgr:
            return self._mgr.get_runeword(runeword_id, self.version)
        return self._legacy.get_runeword(runeword_id) if self._legacy else None

    def get_unique_item(self, unique_id: int) -> Optional[UniqueItemInfo]:
        if self._mgr:
            return self._mgr.get_unique_item(unique_id, self.version)
        return self._legacy.get_unique_item(unique_id) if self._legacy else None

    def get_set_item(self, set_id: int) -> Optional[SetItemInfo]:
        if self._mgr:
            return self._mgr.get_set_item(set_id, self.version)
        return self._legacy.get_set_item(set_id, self.version) if self._legacy else None

    def get_magic_prefix(self, prefix_id: int) -> Optional[MagicAffixInfo]:
        if self._mgr:
            return self._mgr.get_magic_prefix(prefix_id, self.version)
        return self._legacy.get_magic_prefix(prefix_id) if self._legacy else None

    def get_magic_suffix(self, suffix_id: int) -> Optional[MagicAffixInfo]:
        if self._mgr:
            return self._mgr.get_magic_suffix(suffix_id, self.version)
        return self._legacy.get_magic_suffix(suffix_id) if self._legacy else None

    def get_stat(self, stat_id: int) -> Optional[StatInfo]:
        if self._mgr:
            return self._mgr.get_stat(stat_id, self.version)
        return self._legacy.get_stat(stat_id) if self._legacy else None

    def get_property(self, prop_id: int) -> Optional[PropertyInfo]:
        if self._mgr:
            return self._mgr.get_property(prop_id, self.version)
        return self._legacy.get_property(prop_id) if self._legacy else None
