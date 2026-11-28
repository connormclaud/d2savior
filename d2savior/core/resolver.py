"""Unified lookup, localization, and socket resolution facade for game data."""

from typing import TYPE_CHECKING, ClassVar
lazy import importlib.resources
lazy from importlib.resources.abc import Traversable
lazy from pathlib import Path

lazy from d2savior.core.enums import CLASS_NAMES
lazy from d2savior.core.loader import GameData
lazy from d2savior.core.localized_data import LocalizedDataLoader
lazy from d2savior.core.models import (
    GemInfo,
    GemMod,
    HirelingInfo,
    ItemMetaData,
    ItemTypeId,
    ItemTypeInfo,
    MagicAffixInfo,
    PropertyInfo,
    PropertyMetaDataItem,
    RuneWordInfo,
    SetBonusMod,
    SetInfo,
    SetItemInfo,
    StatInfo,
    UniqueItemInfo,
    VersionData,
)

if TYPE_CHECKING:
    from d2savior.core.item import D2Item


class GameDataResolver:
    """Facade unifying multi-version GameData lookups, localization, and modifiers."""

    def __init__(
        self,
        game_data_or_version: GameData | VersionData | int | None = None,
        game_data: GameData | None = None,
        loc: LocalizedDataLoader | None = None,
        lang_key: str = "enUS",
        version: int = 0x69,
    ) -> None:
        if game_data_or_version is None:
            if game_data is None:
                raise ValueError("game_data is required")
            game_data_or_version = game_data

        if isinstance(game_data_or_version, VersionData):
            if game_data is None:
                raise ValueError("game_data is required when constructing from a VersionData")
            self.data = game_data_or_version
            self.version = game_data_or_version.version
            self.game_data = game_data
        elif isinstance(game_data_or_version, int):
            self.version = game_data_or_version
            if game_data is None:
                raise ValueError("GameData instance is required when passing version as int")
            self.game_data = game_data
            self.data = game_data.for_version(self.version)
        elif isinstance(game_data_or_version, GameData):
            self.game_data = game_data_or_version
            self.version = version
            self.data = game_data_or_version.for_version(version)
        else:
            raise TypeError(f"Invalid game_data: {type(game_data_or_version)}")

        self.loc: LocalizedDataLoader | None = loc
        self.lang_key = lang_key

    @classmethod
    def load(
        cls,
        data_dir: str | Traversable | None = None,
        lang_key: str = "enUS",
        version: int = 0x69,
    ) -> GameDataResolver:
        if data_dir is None:
            data_res: Traversable = importlib.resources.files("d2savior").joinpath("data")
        elif isinstance(data_dir, str):
            data_res = Path(data_dir)
        else:
            data_res = data_dir

        game_data = GameData.load(data_res)

        local_dir = data_res.joinpath("d2r", "local")
        if not local_dir.is_dir():
            local_dir = data_res.joinpath("local")

        loc = LocalizedDataLoader.load(local_dir, lang_key=lang_key)

        return cls(
            game_data_or_version=game_data,
            loc=loc,
            lang_key=lang_key,
            version=version,
        )

    def for_version(self, version: int) -> GameDataResolver:
        if self.version == version:
            return self
        if self.game_data is None:
            return self
        return GameDataResolver(
            game_data_or_version=self.game_data,
            loc=self.loc,
            lang_key=self.lang_key,
            version=version,
        )

    def get_item(self, code: str) -> ItemTypeInfo | None:
        return self.data.get_item(code)

    def get_skill_name(self, skill_id: int) -> str:
        if self.loc:
            loc_name = self.loc.get_skill_name_by_id(skill_id)
            if loc_name and loc_name != "Unknown Skill":
                return loc_name
        return self.data.get_skill_name(skill_id)

    def get_runeword(self, runeword_id: int) -> RuneWordInfo | None:
        return self.data.get_runeword(runeword_id)

    def get_unique_item(self, unique_id: int) -> UniqueItemInfo | None:
        return self.data.get_unique_item(unique_id)

    def get_set_item(self, set_id: int) -> SetItemInfo | None:
        return self.data.get_set_item(set_id)

    def get_set(self, set_name: str) -> SetInfo | None:
        return self.data.get_set(set_name)

    def get_magic_prefix(self, prefix_id: int) -> MagicAffixInfo | None:
        return self.data.get_magic_prefix(prefix_id)

    def get_magic_suffix(self, suffix_id: int) -> MagicAffixInfo | None:
        return self.data.get_magic_suffix(suffix_id)

    def get_rare_prefix(self, prefix_id: int) -> str | None:
        return self.data.get_rare_prefix(prefix_id)

    def get_rare_suffix(self, suffix_id: int) -> str | None:
        return self.data.get_rare_suffix(suffix_id)

    def get_stat(self, stat_id: int) -> StatInfo | None:
        return self.data.get_stat(stat_id)

    def get_property(self, prop_id: int) -> PropertyInfo | None:
        return self.data.get_property(prop_id)

    def get_item_meta(self, type_id: ItemTypeId) -> ItemMetaData | None:
        return self.data.get_item_meta(type_id)

    def get_property_meta(
        self, prop_id: int, version: int | None = None
    ) -> PropertyMetaDataItem | None:
        return self.data.get_property_meta(prop_id, version)

    def is_beltable(self, item_code: str) -> bool:
        return self.data.is_beltable(item_code)

    def get_belt_rows(self, item_code: str) -> int:
        return self.data.get_belt_rows(item_code)

    def get_max_sockets(self, item_code: str, ilvl: int = 99) -> int:
        return self.data.get_max_sockets(item_code, ilvl)

    def is_descendant(self, item_type_code: str, ancestor_code: str) -> bool:
        return self.data.is_descendant(item_type_code, ancestor_code)

    def get_item_modifier(self, key: str) -> str:
        if self.loc is not None:
            return self.loc.get_item_modifier(key)
        return key

    def format_property(
        self,
        prop_id: int,
        params: list[int],
        version: int | None = None,
        char_level: int | None = None,
    ) -> str:
        from d2savior.core.property import format_property as _format_property

        return _format_property(
            prop_id, params, resolver=self, version=version or self.version, char_level=char_level
        )

    def get_gem_info(self, code: str) -> GemInfo | None:
        return self.data.get_gem_info(code)

    def get_hireling(self, hireling_id: int) -> HirelingInfo | None:
        return self.data.get_hireling(hireling_id)

    def get_socket_properties_for_code(
        self, parent_item: D2Item | None, code: str
    ) -> list[tuple[int, int, list[int]]]:
        """Return parsed properties granted by gem/rune `code` when socketed into `parent_item`."""
        norm_code = code.strip().lower()
        if not norm_code:
            return []

        gem_info = self.data.get_gem_info(norm_code)
        if not gem_info:
            return []

        parent_code = parent_item.code_str.lower() if parent_item else ""
        parent_info = self.data.items.get(parent_code)
        parent_type = (
            (parent_info.type or parent_info.item_type).lower().strip() if parent_info else ""
        )

        if self.data.is_descendant(parent_type, "shld"):
            mods = gem_info.shield_mods
        elif self.data.is_descendant(parent_type, "weap"):
            mods = gem_info.weapon_mods
        else:
            mods = gem_info.helm_mods

        result: list[tuple[int, int, list[int]]] = []
        for mod in mods:
            result.extend(self._gem_mod_to_properties(mod))

        return result

    def get_socket_properties(
        self, parent_item: D2Item | None, socket_item: D2Item | None
    ) -> list[tuple[int, int, list[int]]]:
        """Return parsed properties (prop_id, value, params) granted by socket_item to parent_item."""
        if socket_item is None:
            return []

        # If it's a Jewel with its own property_list:
        tp = socket_item.type_specific_info
        if tp and tp.property_list:
            props = tp.property_list.get_parsed_properties(self.version, data=self.data)
            if props:
                return props

        return self.get_socket_properties_for_code(parent_item, socket_item.code_str)

    def _resolve_ranged_mod(
        self, code: str, min_val: int, max_val: int, param_int: int, *, include_len: bool
    ) -> list[tuple[int, int, list[int]]] | None:
        prop = self.data.get_property_by_code(code)
        if not prop:
            return None
        pairs: tuple[tuple[str | None, int], ...] = (
            ((prop.stat1, min_val), (prop.stat2, max_val), (prop.stat3, param_int))
            if include_len
            else ((prop.stat1, min_val), (prop.stat2, max_val))
        )
        stats: list[tuple[int, int, list[int]]] = []
        for stat_name, val in pairs:
            stat_info = self.data.get_stat_by_name(stat_name) if stat_name else None
            if stat_info is None:
                return None
            stats.append((stat_info.stat_id, val, [val]))
        return stats

    def _resolve_prop_stats(
        self, prop: PropertyInfo, min_val: int, param_int: int
    ) -> list[tuple[int, int, list[int]]]:
        params = [param_int, min_val] if param_int else [min_val]
        return [
            (stat_info.stat_id, min_val, params)
            for stat_name in (prop.stat1, prop.stat2, prop.stat3, prop.stat4, prop.stat5)
            if stat_name and (stat_info := self.data.get_stat_by_name(stat_name))
        ]

    def _resolve_mod_to_properties(
        self,
        code: str,
        min_val: int,
        max_val: int,
        param_int: int,
        *,
        set_mod: SetBonusMod | None = None,
    ) -> list[tuple[int, int, list[int]]]:
        if code in ("dmg-fire", "dmg-ltng", "dmg-cold", "dmg-pois") and (
            ranged := self._resolve_ranged_mod(
                code,
                min_val,
                max_val,
                param_int,
                include_len=code in ("dmg-cold", "dmg-pois"),
            )
        ):
            return ranged

        fixed_mods: dict[str, list[tuple[int, int, list[int]]]] = {
            "dmg%": [(17, min_val, [min_val]), (18, min_val, [min_val])],
            "dmg-min": [(21, min_val, [min_val])],
            "dmg-max": [(22, min_val, [min_val])],
            "indestruct": [(152, 1, [1])],
        }
        if fixed := fixed_mods.get(code):
            return fixed

        if prop := self.data.get_property_by_code(code):
            if set_mod is not None:
                res = self._resolve_prop_set_mod(prop, set_mod, param_int)
                if res or prop.func1 in (11, 17, 21, 22, 24):
                    return res
            else:
                res = self._resolve_prop_stats(prop, min_val, param_int)
                if res:
                    return res

        if stat_info := self.data.get_stat_by_name(code):
            return [(stat_info.stat_id, min_val, [min_val])]
        return []

    def _gem_mod_to_properties(self, mod: GemMod) -> list[tuple[int, int, list[int]]]:
        return self._resolve_mod_to_properties(mod.code, mod.min_val, mod.max_val, mod.param)

    def _parse_skill_param(self, param: str) -> int | None:
        raw = param.strip()
        if not raw:
            return None
        try:
            return int(raw)
        except ValueError:
            return self.data.get_skill_id_by_name(raw)

    def _resolve_prop_set_mod(
        self, prop: PropertyInfo, mod: SetBonusMod, param_int: int
    ) -> list[tuple[int, int, list[int]]]:
        min_val = mod.min_val
        if prop.func1 == 24:
            return []
        if prop.func1 == 21 and prop.stat1:
            stat_info = self.data.get_stat_by_name(prop.stat1)
            return [(stat_info.stat_id, min_val, [prop.val1, min_val])] if stat_info else []
        if prop.func1 == 22 and prop.stat1:
            skill_id = self._parse_skill_param(mod.param)
            stat_info = self.data.get_stat_by_name(prop.stat1)
            return (
                [(stat_info.stat_id, min_val, [skill_id, min_val])]
                if skill_id is not None and stat_info
                else []
            )
        if prop.func1 == 17 and prop.stat1:
            val = param_int if param_int else min_val
            stat_info = self.data.get_stat_by_name(prop.stat1)
            return [(stat_info.stat_id, val, [val])] if stat_info else []
        if prop.func1 == 11 and prop.stat1:
            skill_id = self._parse_skill_param(mod.param)
            stat_info = self.data.get_stat_by_name(prop.stat1)
            return (
                [(stat_info.stat_id, mod.max_val, [mod.max_val, skill_id, min_val])]
                if skill_id is not None and stat_info
                else []
            )

        return self._resolve_prop_stats(prop, min_val, param_int)

    def set_mod_to_properties(self, mod: SetBonusMod) -> list[tuple[int, int, list[int]]]:
        try:
            param_int = int(mod.param.strip()) if mod.param.strip() else 0
        except ValueError:
            param_int = 0
        return self._resolve_mod_to_properties(
            mod.code, mod.min_val, mod.max_val, param_int, set_mod=mod
        )

    def get_set_bonus_tiers(
        self, set_name: str
    ) -> list[tuple[int, list[tuple[int, int, list[int]]]]]:
        """Return (req_pieces, parsed_props) for all set-wide partial and full bonuses."""
        set_info = self.get_set(set_name)
        if set_info is None:
            return []

        tiers: dict[int, list[tuple[int, int, list[int]]]] = {}
        for req_pieces, mods in set_info.partial_bonuses.items():
            props: list[tuple[int, int, list[int]]] = []
            for mod in mods:
                props.extend(self.set_mod_to_properties(mod))
            if props:
                tiers.setdefault(req_pieces, []).extend(props)

        if set_info.full_bonuses and set_info.piece_count >= 2:
            full_props: list[tuple[int, int, list[int]]] = []
            for mod in set_info.full_bonuses:
                full_props.extend(self.set_mod_to_properties(mod))
            if full_props:
                tiers.setdefault(set_info.piece_count, []).extend(full_props)

        return sorted(tiers.items())

    def get_active_set_bonuses(
        self, set_name: str, piece_count: int
    ) -> list[tuple[int, int, list[int]]]:
        """Return parsed properties for active set-wide partial/full bonuses at `piece_count`."""
        if piece_count < 2:
            return []
        result: list[tuple[int, int, list[int]]] = []
        for req_pieces, props in self.get_set_bonus_tiers(set_name):
            if piece_count >= req_pieces:
                result.extend(props)
        return result

    def get_localized_skill_tab_name(self, tab: int, class_id: int) -> str:
        if self.loc:
            name = self.loc.get_skill_tab_name(tab, class_id)
            if name:
                return name
        return f"SkillTab{tab}"

    def get_localized_monster_name(self, monster_id: int) -> str:
        """Resolve a monster's localized name from monstats.txt *hcIdx and localization tables."""
        name_str = self.data.monsters.get(monster_id)
        if name_str:
            if self.loc:
                for table in ("monsters.json", "npcs.json"):
                    loc_val = self.loc.get_string(table, name_str, "")
                    if loc_val:
                        return loc_val
            return name_str
        return f"Monster{monster_id}"

    def get_localized_item_name(self, code_or_name: str, fallback: str = "") -> str:
        if not self.loc:
            return fallback or code_or_name

        name = self.loc.get_item_name(code_or_name)
        if name and name != code_or_name:
            return name

        name = self.loc.get_item_nameaffix(code_or_name)
        if name and name != code_or_name:
            return name

        name = self.loc.get_rune_name(code_or_name)
        if name and name != code_or_name:
            return name

        if fallback and fallback != code_or_name:
            name = self.loc.get_item_name(fallback)
            if name and name != fallback:
                return name
            name = self.loc.get_item_nameaffix(fallback)
            if name and name != fallback:
                return name

        return fallback or code_or_name

    def get_localized_unique_name(self, unique_id: int) -> str:
        u_info = self.get_unique_item(unique_id)
        if not u_info:
            return ""
        if self.loc:
            name = self.loc.get_item_name(u_info.index)
            if name and name != u_info.index:
                return name
        return u_info.index

    def get_localized_set_name(self, set_id: int) -> str:
        s_info = self.get_set_item(set_id)
        if not s_info:
            return ""
        if self.loc:
            name = self.loc.get_item_name(s_info.name)
            if name and name != s_info.name:
                return name
        return s_info.name

    def get_localized_runeword_name(self, runeword_id: int) -> str:
        rw_info = self.get_runeword(runeword_id)
        if not rw_info:
            return ""
        if self.loc:
            name = self.loc.get_rune_name(rw_info.name)
            if name and name != rw_info.name:
                return name
            name = self.loc.get_rune_name(f"Runeword{runeword_id}")
            if name and name != f"Runeword{runeword_id}":
                return name
        return rw_info.name

    def get_localized_magic_prefix(self, prefix_id: int) -> str:
        p_info = self.get_magic_prefix(prefix_id)
        if not p_info:
            return ""
        if self.loc:
            name = self.loc.get_item_nameaffix(p_info.name)
            if name and name != p_info.name:
                return name
        return p_info.name

    def get_localized_magic_suffix(self, suffix_id: int) -> str:
        s_info = self.get_magic_suffix(suffix_id)
        if not s_info:
            return ""
        if self.loc:
            name = self.loc.get_item_nameaffix(s_info.name)
            if name and name != s_info.name:
                return name
        return s_info.name

    def get_localized_rare_prefix(self, prefix_id: int) -> str:
        key = self.get_rare_prefix(prefix_id)
        if not key:
            return ""
        if self.loc:
            name = self.loc.get_rare_affix_name(key)
            if name:
                return name
        return key

    def get_localized_rare_suffix(self, suffix_id: int) -> str:
        key = self.get_rare_suffix(suffix_id)
        if not key:
            return ""
        if self.loc:
            name = self.loc.get_rare_affix_name(key)
            if name:
                return name
        return key

    def get_localized_rare_name(self, name_1: int, name_2: int) -> str:
        prefix = self.get_localized_rare_prefix(name_1)
        suffix = self.get_localized_rare_suffix(name_2)
        if prefix and suffix:
            return f"{prefix} {suffix}"
        return prefix or suffix

    def get_localized_quality_name(self, quality_name: str) -> str:
        if not self.loc or self.loc.current_lang == "enUS":
            return quality_name
        name = self.loc.get_item_nameaffix(quality_name)
        if name and name != quality_name:
            return name
        ui_key = f"LootFilter{quality_name}Rarity"
        name = self.loc.get_clean_string("ui.json", ui_key, default="")
        if name:
            return name
        quality_fallbacks = {
            "ruRU": {"Crafted": "созданный", "Rare": "редкий"},
            "zhCN": {"Crafted": "手工艺", "Rare": "稀有"},
            "zhTW": {"Crafted": "手工艺", "Rare": "稀有"},
        }
        fb = quality_fallbacks.get(self.loc.current_lang, {}).get(quality_name)
        if fb:
            return fb
        return quality_name

    def get_localized_gem_type_name(self, gem_type: str) -> str:
        if not self.loc:
            return gem_type
        name = self.loc.get_item_name(gem_type)
        if name and name != gem_type:
            return name
        name = self.loc.get_item_nameaffix(gem_type)
        if name and name != gem_type:
            return name
        return gem_type

    def get_localized_rune_short_name(self, code_str: str) -> str:
        type_info = self.get_item(code_str)
        eng_name = type_info.name if type_info else code_str
        if not self.loc or self.loc.current_lang == "enUS":
            return eng_name[:-5] if eng_name.endswith(" Rune") else eng_name

        loc_name = self.loc.get_rune_name(code_str)
        if loc_name and loc_name != code_str:
            if loc_name.startswith("Руна "):
                return loc_name[len("Руна ") :]
            if loc_name.endswith("符文"):
                return loc_name[: -len("符文")]
            if loc_name.endswith(" Rune"):
                return loc_name[: -len(" Rune")]
            return loc_name
        return eng_name[:-5] if eng_name.endswith(" Rune") else eng_name

    def get_localized_class_name(self, class_id: int) -> str:
        default_name = CLASS_NAMES[class_id] if 0 <= class_id < len(CLASS_NAMES) else "Unknown"
        if self.loc:
            name = self.loc.get_class_name(class_id)
            if name:
                return name
        return default_name

    _MERC_ACT_ROMAN: ClassVar[frozendict[int, str]] = frozendict(
        {
            1: "Act I",
            2: "Act II",
            3: "Act III",
            4: "Act IV",
            5: "Act V",
        }
    )
    _MERC_DIFFICULTIES: ClassVar[frozendict[int, str]] = frozendict(
        {
            1: "Normal",
            2: "Nightmare",
            3: "Hell",
        }
    )
    _MERC_CLASS_LOC: ClassVar[frozendict[int, tuple[str, str]]] = frozendict(
        {
            1: ("monsters", "RogueScout"),
            2: ("ui", "DesertMerc"),
            3: ("monsters", "Iron Wolf"),
            5: ("ui", "Barbarian"),
        }
    )
    _MERC_DESC_FALLBACK: ClassVar[frozendict[str, str]] = frozendict(
        {
            "strhirespecial1": "Fire Arrow",
            "strhirespecial2": "Cold Arrow",
            "strhirespecial5": "Lightning",
            "strhirespecial6": "Cold",
            "strhirespecial7": "Fire",
        }
    )

    def get_localized_mercenary_name(self, hireling_id: int, name_index: int) -> str:
        """Resolve a mercenary's localized name from hireling_id and name_index."""
        info = self.get_hireling(hireling_id)
        if not info or not self.loc:
            return ""
        return self.loc.get_mercenary_name_in_range(info.name_first, info.name_last, name_index)

    def get_localized_mercenary_details(self, hireling_id: int) -> str:
        """Return localized 'Act <roman> <Type>, <Difficulty>, <Specialty>' for hireling_id."""
        info = self.get_hireling(hireling_id)
        if not info:
            return ""

        merc_class = "Iron Wolf" if info.hireling == "Eastern Sorceror" else info.hireling
        if self.loc and info.act in self._MERC_CLASS_LOC:
            table, key = self._MERC_CLASS_LOC[info.act]
            loc_val = (
                self.loc.get_monster_name(key)
                if table == "monsters"
                else self.loc.get_ui_string(key)
            )
            if loc_val and loc_val != key:
                merc_class = loc_val

        act_str = self._MERC_ACT_ROMAN.get(info.act, f"Act {info.act}" if info.act else "")
        head = f"{act_str} {merc_class}".strip()
        diff_str = self._MERC_DIFFICULTIES.get(info.difficulty, "")
        specialty = self._resolve_mercenary_specialty(info)

        return ", ".join(p for p in (head, diff_str, specialty) if p)

    def _resolve_mercenary_specialty(self, info: HirelingInfo) -> str:
        """Resolve a hireling's localized aura, element, or primary combat skill."""
        desc = info.hire_desc
        if desc:
            if self.loc:
                val = (
                    self.loc.get_skill_name(desc)
                    if desc.startswith("skillname")
                    else self.loc.get_ui_string(desc)
                )
                if val and val != desc:
                    return val
            if desc in self._MERC_DESC_FALLBACK:
                return self._MERC_DESC_FALLBACK[desc]
        if info.skill_1:
            if self.loc:
                skill_id = next(
                    (sid for sid, sname in self.data.skills.items() if sname == info.skill_1),
                    None,
                )
                if skill_id is not None:
                    loc_skill = self.loc.get_skill_name_by_id(skill_id)
                    if loc_skill:
                        return loc_skill
            return info.skill_1
        return ""


def resolve_version_data(
    data: VersionData | GameData | GameDataResolver | None,
    version: int,
    fallback: VersionData | None = None,
) -> VersionData | None:
    """Normalize a GameDataResolver, GameData, or VersionData for ``version``."""
    if isinstance(data, GameDataResolver):
        return data.for_version(version).data
    if isinstance(data, GameData):
        return data.for_version(version)
    return data if data is not None else fallback
