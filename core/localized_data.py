import os
import json
from typing import Dict, Optional


class LocalizedDataLoader:
    def __init__(self):
        self._data: Dict[str, Dict[str, str]] = {}
        self._current_lang: str = 'enUS'
    
    def load_json_file(self, filepath: str, lang_key: str = 'enUS') -> bool:
        if not os.path.exists(filepath):
            return False
        
        try:
            with open(filepath, 'r', encoding='utf-8-sig') as f:
                data = json.load(f)
            
            file_key = os.path.basename(filepath)
            self._data[file_key] = {}
            
            for item in data:
                key = item.get('Key', '')
                if not key:
                    continue
                
                text = item.get(lang_key, item.get('enUS', ''))
                if text:
                    self._data[file_key][key] = text
            
            return True
        except Exception as e:
            print(f"Error loading {filepath}: {e}")
            return False
    
    def load_all_localized_data(self, data_dir: str, lang_key: str = 'enUS') -> Dict[str, bool]:
        results = {}
        
        json_files = [
            'item-modifiers.json',
            'skills.json',
            'item-names.json',
            'item-nameaffixes.json',
            'item-gems.json',
            'item-runes.json',
            'monsters.json',
            'npcs.json',
            'quests.json',
            'shrines.json',
            'levels.json',
            'objects.json',
            'mercenaries.json',
            'commands.json',
            'keybinds.json',
        ]
        
        for json_file in json_files:
            filepath = os.path.join(data_dir, json_file)
            results[json_file] = self.load_json_file(filepath, lang_key)
        
        return results
    
    def set_language(self, lang_key: str):
        self._current_lang = lang_key
    
    def get_string(self, file_key: str, key: str, default: str = None) -> str:
        if file_key in self._data and key in self._data[file_key]:
            return self._data[file_key][key]
        return default if default is not None else key
    
    def get_item_modifier(self, key: str) -> str:
        return self.get_string('item-modifiers.json', key)
    
    def get_skill_name(self, key: str) -> str:
        return self.get_string('skills.json', key)
    
    def get_item_name(self, key: str) -> str:
        return self.get_string('item-names.json', key)
    
    def get_monster_name(self, key: str) -> str:
        return self.get_string('monsters.json', key)
    
    def get_npc_name(self, key: str) -> str:
        return self.get_string('npcs.json', key)
    
    def get_quest_name(self, key: str) -> str:
        return self.get_string('quests.json', key)
    
    def get_shrine_name(self, key: str) -> str:
        return self.get_string('shrines.json', key)
    
    def get_level_name(self, key: str) -> str:
        return self.get_string('levels.json', key)
    
    def get_object_name(self, key: str) -> str:
        return self.get_string('objects.json', key)
    
    def get_mercenary_name(self, key: str) -> str:
        return self.get_string('mercenaries.json', key)
    
    def get_command_name(self, key: str) -> str:
        return self.get_string('commands.json', key)
    
    def get_keybind_name(self, key: str) -> str:
        return self.get_string('keybinds.json', key)


_g_localized_data: Optional[LocalizedDataLoader] = None


def get_localized_data() -> LocalizedDataLoader:
    global _g_localized_data
    if _g_localized_data is None:
        _g_localized_data = LocalizedDataLoader()
    return _g_localized_data


def init_localized_data(data_dir: str, lang_key: str = 'enUS') -> Dict[str, bool]:
    global _g_localized_data
    if _g_localized_data is None:
        _g_localized_data = LocalizedDataLoader()
    _g_localized_data.set_language(lang_key)
    return _g_localized_data.load_all_localized_data(data_dir, lang_key)
