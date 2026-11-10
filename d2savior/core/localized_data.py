import importlib.resources
import json
import re
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import ClassVar

from d2savior.core.d2data import open_resource


def clean_d2_text(text: str | None) -> str:
    """Clean Diablo II localized text by extracting the first grammatical form from tags like [ms]..."""
    if not text:
        return ""
    m = re.search(r"\[(?:ms|fs|ns|pl|mp|fp|nl)\]([^\[]+)", text)
    if m:
        return m.group(1).strip()
    return text.strip()


class LocalizedDataLoader:
    LANG_KEYS: ClassVar[list[str]] = ["enUS", "zhCN"]

    def __init__(self) -> None:
        self._raw: dict[str, list[dict]] = {}
        self._data: dict[str, dict[str, str]] = {}
        self._current_lang: str = "enUS"
        self._data_dir: str | Traversable = ""

    def load_json_file(self, filepath: str | Traversable, lang_key: str = "enUS") -> bool:
        p = Path(filepath) if isinstance(filepath, str) else filepath
        with open_resource(p, encoding="utf-8-sig") as f:
            raw_data = json.load(f)

        file_key = p.name
        self._raw[file_key] = raw_data
        self._build_index(file_key, lang_key)
        return True

    def _build_index(self, file_key: str, lang_key: str) -> None:
        self._data[file_key] = {}
        raw = self._raw.get(file_key, [])
        fallback_lang = "zhTW" if lang_key == "zhCN" else ("zhCN" if lang_key == "zhTW" else None)
        for item in raw:
            key = item.get("Key", "")
            if not key:
                continue
            text = item.get(lang_key, "")
            if not text and fallback_lang:
                text = item.get(fallback_lang, "")
            if not text:
                text = item.get("enUS", "")
            if text:
                self._data[file_key][key] = text
            en_us = item.get("enUS", "")
            if en_us and en_us != key and lang_key != "enUS":
                translated = item.get(lang_key, "")
                if not translated and fallback_lang:
                    translated = item.get(fallback_lang, "")
                if translated:
                    self._data[file_key][en_us] = translated

    def _rebuild_all_indexes(self) -> None:
        for file_key in self._raw:
            self._build_index(file_key, self._current_lang)

    def load_all_localized_data(
        self, data_dir: str | Traversable | None = None, lang_key: str = "enUS"
    ) -> dict[str, bool]:
        if data_dir is None:
            dir_res: Traversable = importlib.resources.files("d2savior").joinpath(
                "data", "d2r", "local"
            )
        elif isinstance(data_dir, str):
            dir_res = Path(data_dir)
        else:
            dir_res = data_dir

        self._data_dir = dir_res
        self._current_lang = lang_key
        results = {}

        json_files = [
            "item-modifiers.json",
            "skills.json",
            "item-names.json",
            "item-nameaffixes.json",
            "item-gems.json",
            "item-runes.json",
            "monsters.json",
            "npcs.json",
            "quests.json",
            "shrines.json",
            "levels.json",
            "objects.json",
            "mercenaries.json",
            "commands.json",
            "keybinds.json",
            "tooltip-ui.json",
            "ui.json",
        ]

        for json_file in json_files:
            filepath = dir_res.joinpath(json_file)
            results[json_file] = self.load_json_file(filepath, lang_key)

        return results

    def set_language(self, lang_key: str) -> None:
        if lang_key == self._current_lang:
            return
        self._current_lang = lang_key
        self._rebuild_all_indexes()

    @property
    def current_lang(self) -> str:
        return self._current_lang

    def get_string(self, file_key: str, key: str, default: str | None = None) -> str:
        if file_key in self._data and key in self._data[file_key]:
            return self._data[file_key][key]
        return default if default is not None else key

    def get_clean_string(self, file_key: str, key: str, default: str | None = None) -> str:
        s = self.get_string(file_key, key, default)
        return clean_d2_text(s)

    def get_item_modifier(self, key: str) -> str:
        return self.get_string("item-modifiers.json", key)

    def get_skill_name(self, key: str) -> str:
        return self.get_string("skills.json", key)

    def get_item_name(self, key: str, clean: bool = True) -> str:
        s = self.get_string("item-names.json", key)
        return clean_d2_text(s) if clean else s

    def get_item_name_by_id(self, item_id: int) -> str:
        file_key = "item-names.json"
        if file_key in self._raw:
            for item in self._raw[file_key]:
                if item.get("id") == item_id:
                    return item.get(self._current_lang, item.get("enUS", f"Item#{item_id}"))
        return f"Item#{item_id}"

    def get_item_nameaffix(self, key: str, clean: bool = True) -> str:
        s = self.get_string("item-nameaffixes.json", key)
        return clean_d2_text(s) if clean else s

    def get_rare_affix_name(self, key: str, clean: bool = True) -> str:
        """Resolve a rare affix key from item-nameaffixes, item-names, monsters, or ui tables."""
        for file_key in (
            "item-nameaffixes.json",
            "item-names.json",
            "monsters.json",
            "ui.json",
        ):
            if file_key in self._data and key in self._data[file_key]:
                s = self._data[file_key][key]
                return clean_d2_text(s) if clean else s
        return key

    def get_rune_name(self, key: str, clean: bool = True) -> str:
        s = self.get_string("item-runes.json", key)
        return clean_d2_text(s) if clean else s

    def get_monster_name(self, key: str) -> str:
        return self.get_string("monsters.json", key)

    def get_npc_name(self, key: str) -> str:
        return self.get_string("npcs.json", key)

    def get_quest_name(self, key: str, clean: bool = True) -> str:
        s = self.get_string("quests.json", key)
        return clean_d2_text(s) if clean else s

    def get_shrine_name(self, key: str) -> str:
        return self.get_string("shrines.json", key)

    def get_level_name(self, key: str, clean: bool = True) -> str:
        s = self.get_string("levels.json", key)
        return clean_d2_text(s) if clean else s

    def get_object_name(self, key: str) -> str:
        return self.get_string("objects.json", key)

    def get_mercenary_name(self, key: str) -> str:
        return self.get_string("mercenaries.json", key)

    def get_command_name(self, key: str) -> str:
        return self.get_string("commands.json", key)

    def get_keybind_name(self, key: str) -> str:
        return self.get_string("keybinds.json", key)

    def get_tooltip_ui(self, key: str) -> str:
        return self.get_string("tooltip-ui.json", key)

    def get_ui_string(self, key: str) -> str:
        return self.get_string("ui.json", key)

    def get_class_name(self, class_id: int) -> str:
        class_keys = [
            "Amazon",
            "Sorceress",
            "Necromancer",
            "Paladin",
            "Barbarian",
            "Druid",
            "Assassin",
            "Warlock",
        ]
        if 0 <= class_id < len(class_keys):
            result = self.get_ui_string(class_keys[class_id])
            if result and result != class_keys[class_id]:
                return result
        return ""

    def get_skill_name_by_id(self, skill_id: int) -> str:
        key = f"skillname{skill_id}"
        result = self.get_skill_name(key)
        if result and result != key:
            return result
        key2 = f"skillan{skill_id}"
        result2 = self.get_skill_name(key2)
        if result2 and result2 != key2:
            return result2
        return ""

    _SKILL_TAB_KEYS: ClassVar[dict[tuple[int, int], str]] = {
        (0, 0): "SkillCategoryAm3",
        (0, 1): "SkillCategoryAm2",
        (0, 2): "SkillCategoryAm1",
        (1, 0): "SkillCategorySo3",
        (1, 1): "SkillCategorySo2",
        (1, 2): "SkillCategorySo1",
        (2, 0): "SkillCategoryNe3",
        (2, 1): "SkillCategoryNe2",
        (2, 2): "SkillCategoryNe1",
        (3, 0): "SkillCategoryPa3",
        (3, 1): "SkillCategoryPa2",
        (3, 2): "SkillCategoryPa1",
        (4, 0): "SkillCategoryBa3",
        (4, 1): "SkillCategoryBa2",
        (4, 2): "SkillCategoryBa1",
        (5, 0): "SkillCategoryDr2",
        (5, 1): "SkillCategoryDr1",
        (5, 2): "SkillCategoryDr3",
        (6, 0): "SkillCategoryAs3",
        (6, 1): "SkillCategoryAs2",
        (6, 2): "SkillCategoryAs1",
        (7, 0): "SkillCategoryWa1",
        (7, 1): "SkillCategoryWa2",
        (7, 2): "SkillCategoryWa3",
    }

    def get_skill_tab_name(self, tab: int, class_id: int) -> str:
        key = self._SKILL_TAB_KEYS.get((class_id, tab))
        if key:
            result = self.get_skill_name(key)
            if result and result != key:
                return result
        return ""

    @classmethod
    def load(
        cls, data_dir: str | Traversable | None = None, lang_key: str = "enUS"
    ) -> LocalizedDataLoader:
        loader = cls()
        loader.load_all_localized_data(data_dir, lang_key)
        return loader
