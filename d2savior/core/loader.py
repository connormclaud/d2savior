"""TSV/JSON table loaders and version overlay management for Diablo II game data."""

from collections.abc import Iterator, Sequence
from warnings import deprecated
lazy import importlib.resources
lazy import json
lazy from importlib.resources.abc import Traversable
lazy from itertools import batched
lazy from pathlib import Path
lazy from typing import IO, ClassVar

lazy from d2savior.core.models import (
    GemInfo,
    GemMod,
    HirelingInfo,
    HirelingLevelInfo,
    ItemMetaData,
    ItemMetaDataManager,
    ItemTypeInfo,
    MagicAffixInfo,
    PropertyField,
    PropertyInfo,
    PropertyMetaData,
    PropertyMetaDataItem,
    RuneWordInfo,
    SetItemInfo,
    StatInfo,
    UniqueItemInfo,
    VersionData,
)


def open_resource(
    filepath: str | Traversable,
    encoding: str = "utf-8",
    errors: str | None = None,
) -> IO[str]:
    p = Path(filepath) if isinstance(filepath, str) else filepath
    if not p.is_file():
        raise FileNotFoundError(f"Required data file not found: {filepath}")
    if errors is not None:
        return p.open("r", encoding=encoding, errors=errors)
    return p.open("r", encoding=encoding)


_open_resource = open_resource


class TsvRow:
    """Single row from a tab-separated D2 game table."""

    __slots__ = ("_col_map", "_parts", "_strip_cells", "index")

    def __init__(
        self,
        index: int,
        col_map: dict[str, int],
        parts: list[str],
        *,
        strip_cells: bool = True,
    ) -> None:
        self.index = index
        self._col_map = col_map
        self._parts = parts
        self._strip_cells = strip_cells

    def get(self, col_name: str, default: str = "") -> str:
        """Return cell value by case-insensitive column name, or default if missing."""
        idx = self._col_map.get(col_name.strip().lower(), -1)
        if 0 <= idx < len(self._parts):
            val = self._parts[idx]
            return val.strip() if self._strip_cells else val
        return default

    def get_int(self, col_name: str, default: int = 0) -> int:
        """Return cell value parsed as int, or default if empty or non-numeric."""
        raw = self.get(col_name).strip()
        if not raw:
            return default
        try:
            return int(raw)
        except ValueError:
            return default

    def get_bool(self, col_name: str) -> bool:
        """Return True if cell equals '1'."""
        return self.get(col_name) == "1"


class TsvReader:
    """Reader for tab-separated D2 game tables with normalized case-insensitive headers."""

    def __init__(
        self,
        filepath: str | Traversable,
        *,
        skip_expansion: bool = True,
        strip_cells: bool = True,
    ) -> None:
        self._skip_expansion = skip_expansion
        self._strip_cells = strip_cells

        with _open_resource(filepath, encoding="utf-8-sig", errors="replace") as f:
            lines = f.readlines()

        if not lines:
            self._col_map: dict[str, int] = {}
            self._data_lines: list[str] = []
            return

        header = lines[0].rstrip("\r\n").split("\t")
        self._col_map = {col.strip().lower(): i for i, col in enumerate(header)}
        self._data_lines = lines[1:]

    def has_columns(self, *col_names: str) -> bool:
        """Return True if all specified column names exist in the table header."""
        return all(name.strip().lower() in self._col_map for name in col_names)

    def __iter__(self) -> Iterator[TsvRow]:
        for idx, line in enumerate(self._data_lines):
            raw_line = line.rstrip("\r\n")
            stripped = raw_line.strip()
            if not stripped or stripped.startswith("*"):
                continue
            if self._skip_expansion and stripped.startswith("Expansion"):
                continue
            yield TsvRow(
                idx,
                self._col_map,
                raw_line.split("\t"),
                strip_cells=self._strip_cells,
            )


class D2DataLoader:
    """Load single version data."""

    def __init__(self) -> None:
        pass

    def load_itemstatcost(
        self, filepath: str | Traversable
    ) -> tuple[dict[int, StatInfo], dict[str, StatInfo]]:
        stats: dict[int, StatInfo] = {}
        stats_by_name: dict[str, StatInfo] = {}

        for row in TsvReader(filepath):
            stat_name = row.get("Stat")
            stat_id = row.get_int("*ID", -1)
            if stat_id < 0:
                continue

            stat = StatInfo(
                stat_id=stat_id,
                stat_name=stat_name,
                send_bits=row.get_int("Send Bits"),
                send_param_bits=row.get_int("Send Param Bits"),
                save_bits=row.get_int("Save Bits"),
                save_add=row.get_int("Save Add"),
                save_param_bits=row.get_int("Save Param Bits"),
                val_shift=row.get_int("ValShift"),
                op=row.get_int("op"),
                op_param=row.get_int("op param"),
                op_base=row.get_int("op base"),
                op_stat1=row.get_int("op stat1"),
                op_stat2=row.get_int("op stat2"),
                op_stat3=row.get_int("op stat3"),
                descpriority=row.get_int("descpriority"),
                descfunc=row.get_int("descfunc"),
                descval=row.get_int("descval"),
                descstrpos=row.get("descstrpos"),
                descstrneg=row.get("descstrneg"),
                descstr2=row.get("descstr2"),
            )

            stats[stat_id] = stat
            if stat_name:
                stats_by_name[stat_name] = stat

        return stats, stats_by_name

    def load_properties(
        self, filepath: str | Traversable
    ) -> tuple[dict[int, PropertyInfo], dict[str, PropertyInfo]]:
        properties: dict[int, PropertyInfo] = {}
        properties_by_code: dict[str, PropertyInfo] = {}

        for row in TsvReader(filepath):
            code = row.get("code")
            prop_id = row.get_int("*Id", -1)
            if not code or prop_id < 0:
                continue

            prop = PropertyInfo(
                prop_id=prop_id,
                code=code,
                func1=row.get_int("func1"),
                stat1=row.get("stat1"),
                set1=row.get_int("set1"),
                val1=row.get_int("val1"),
                func2=row.get_int("func2"),
                stat2=row.get("stat2"),
                set2=row.get_int("set2"),
                val2=row.get_int("val2"),
                func3=row.get_int("func3"),
                stat3=row.get("stat3"),
                set3=row.get_int("set3"),
                val3=row.get_int("val3"),
                func4=row.get_int("func4"),
                stat4=row.get("stat4"),
                set4=row.get_int("set4"),
                val4=row.get_int("val4"),
                func5=row.get_int("func5"),
                stat5=row.get("stat5"),
                set5=row.get_int("set5"),
                val5=row.get_int("val5"),
                func6=row.get_int("func6"),
                stat6=row.get("stat6"),
                set6=row.get_int("set6"),
                val6=row.get_int("val6"),
                func7=row.get_int("func7"),
                stat7=row.get("stat7"),
                set7=row.get_int("set7"),
                val7=row.get_int("val7"),
            )

            properties[prop_id] = prop
            properties_by_code[code] = prop

        return properties, properties_by_code

    def load_items_txt(
        self, filepath: str | Traversable, item_category: str
    ) -> dict[str, ItemTypeInfo]:
        items: dict[str, ItemTypeInfo] = {}
        belt_col_to_rows = {0: 3, 1: 2, 3: 4, 4: 2, 5: 3, 6: 4}

        for row in TsvReader(filepath, strip_cells=False):
            code = row.get("code")
            if not code or code == "xxx":
                continue

            item_type_col = row.get("type").lower().strip()
            belt_rows = 0
            if item_type_col == "belt":
                belt_col_val = row.get_int("belt", -1)
                belt_rows = belt_col_to_rows.get(belt_col_val, 0)

            item = ItemTypeInfo(
                code=code,
                name=row.get("name"),
                item_type=item_category,
                item_type2=row.get("type"),
                invwidth=row.get_int("invwidth", 1),
                invheight=row.get_int("invheight", 1),
                hasinv=row.get_bool("hasinv"),
                gemsockets=row.get_int("gemsockets"),
                stackable=row.get_bool("stackable"),
                useable=row.get_bool("useable"),
                compactsave=row.get_bool("compactsave"),
                version=row.get_int("version"),
                rarity=row.get_int("rarity"),
                spawnable=row.get_bool("spawnable"),
                nodurability=row.get_bool("nodurability"),
                durability=row.get_int("durability"),
                mindam=row.get_int("mindam"),
                maxdam=row.get_int("maxdam"),
                minmisdam=row.get_int("minmisdam"),
                maxmisdam=row.get_int("maxmisdam"),
                speed=row.get_int("speed"),
                reqstr=row.get_int("reqstr"),
                reqdex=row.get_int("reqdex"),
                level=row.get_int("level"),
                levelreq=row.get_int("levelreq"),
                cost=row.get_int("cost"),
                component=row.get_int("component"),
                type=row.get("type"),
                type2=row.get("type2"),
                minstack=row.get_int("minstack"),
                maxstack=row.get_int("maxstack"),
                spawnstack=row.get_int("spawnstack"),
                quest=row.get_int("quest"),
                questdiffcheck=row.get_bool("questdiffcheck"),
                spell_id=row.get_int("pSpell"),
                spellicon=row.get_int("spellicon"),
                belt_rows=belt_rows,
            )

            items[code] = item

            for alias_col in ("normcode", "ubercode", "ultracode"):
                alias = row.get(alias_col)
                if alias and alias != "xxx" and alias not in items:
                    items[alias] = item

        return items

    def load_magic_affix(
        self, filepath: str | Traversable, is_prefix: bool
    ) -> dict[int, MagicAffixInfo]:
        affix_dict: dict[int, MagicAffixInfo] = {}

        for row in TsvReader(filepath, skip_expansion=False):
            name = row.get("Name")
            if not name:
                continue

            affix_dict[row.index] = MagicAffixInfo(
                name=name,
                affix_id=row.index,
                level=row.get_int("level"),
                levelreq=row.get_int("levelreq"),
            )

        return affix_dict

    def load_rare_affix(self, filepath: str | Traversable, offset: int = 0) -> dict[int, str]:
        affix_dict: dict[int, str] = {}

        for row in TsvReader(filepath, skip_expansion=False):
            name = row.get("name")
            if name:
                affix_dict[offset + row.index + 1] = name

        return affix_dict

    def load_unique_items(self, filepath: str | Traversable) -> dict[int, UniqueItemInfo]:
        unique_items: dict[int, UniqueItemInfo] = {}

        for row in TsvReader(filepath):
            unique_id = row.get_int("*ID")
            if unique_id <= 0:
                continue

            unique_items[unique_id] = UniqueItemInfo(
                index=row.get("index"),
                unique_id=unique_id,
                code=row.get("code"),
            )

        return unique_items

    def load_runewords(
        self, runes_path: str | Traversable, json_path: str | Traversable | None = None
    ) -> dict[int, RuneWordInfo]:
        """Load runewords from game table (runes.txt) with localized names from item-runes.json."""
        name_str = runes_path if isinstance(runes_path, str) else runes_path.name
        if json_path is None and name_str.endswith(".json"):
            json_file: str | Traversable | None = runes_path
            runes_file: str | Traversable | None = None
        elif json_path is None:
            json_file = None
            runes_file = runes_path
        else:
            runes_file = runes_path
            json_file = json_path

        json_by_key: dict[str, dict] = {}
        if json_file:
            with _open_resource(json_file, encoding="utf-8-sig") as f:
                data = json.load(f)
            for item in data:
                key = item.get("Key", "")
                if key:
                    json_by_key[key] = item

        runewords: dict[int, RuneWordInfo] = {}

        if runes_file:
            for row in TsvReader(runes_file):
                key = row.get("Name")
                if not key.startswith("Runeword"):
                    continue

                canonical_name = row.get("*Rune Name") or key
                rune_codes = [code for i in range(1, 7) if (code := row.get(f"Rune{i}"))]

                try:
                    rw_num = int(key.replace("Runeword", ""))
                except ValueError:
                    rw_num = 0

                json_entry = json_by_key.get(key, {})
                d2r_id = json_entry.get("id", rw_num)
                display_name = json_entry.get("enUS", canonical_name)

                rw_info = RuneWordInfo(
                    name=display_name,
                    runeword_id=d2r_id,
                    key=key,
                    rune_codes=rune_codes,
                )

                if d2r_id > 0:
                    runewords[d2r_id] = rw_info
                if rw_num > 0 and rw_num not in runewords:
                    runewords[rw_num] = rw_info

        for key, item in json_by_key.items():
            if key.startswith("Runeword"):
                rw_id = item.get("id", 0)
                name = item.get("enUS", "")
                if rw_id > 0 and rw_id not in runewords:
                    runewords[rw_id] = RuneWordInfo(name=name, runeword_id=rw_id, key=key)

        return runewords

    def load_gems(self, filepath: str | Traversable) -> dict[str, GemInfo]:
        gems: dict[str, GemInfo] = {}

        for row in TsvReader(filepath):
            code = row.get("code").lower()
            if not code:
                continue

            mod_groups: dict[str, list[GemMod]] = {}
            for prefix in ("weaponmod", "helmmod", "shieldmod"):
                mods: list[GemMod] = []
                for i in range(1, 4):
                    mod_code = row.get(f"{prefix}{i}code")
                    if mod_code:
                        mods.append(
                            GemMod(
                                code=mod_code,
                                param=row.get_int(f"{prefix}{i}param"),
                                min_val=row.get_int(f"{prefix}{i}min"),
                                max_val=row.get_int(f"{prefix}{i}max"),
                            )
                        )
                mod_groups[prefix] = mods

            gems[code] = GemInfo(
                code=code,
                name=row.get("name"),
                weapon_mods=mod_groups["weaponmod"],
                helm_mods=mod_groups["helmmod"],
                shield_mods=mod_groups["shieldmod"],
            )

        return gems

    @deprecated("Use load_runewords instead")
    def load_runes_txt(
        self, filepath: str | Traversable, runewords: dict[int, RuneWordInfo]
    ) -> None:
        extra = self.load_runewords(filepath)
        for rw_id, rw in extra.items():
            if rw_id in runewords and rw.rune_codes and not runewords[rw_id].rune_codes:
                runewords[rw_id].rune_codes = rw.rune_codes

    SET_ITEM_NAMES: ClassVar[tuple[str, ...]] = (
        "Civerb's Ward",
        "Civerb's Icon",
        "Civerb's Cudgel",
        "Hsarus' Iron Heel",
        "Hsarus' Iron Fist",
        "Hsarus' Iron Stay",
        "Cleglaw's Tooth",
        "Cleglaw's Claw",
        "Cleglaw's Pincers",
        "Iratha's Collar",
        "Iratha's Cuff",
        "Iratha's Coil",
        "Iratha's Cord",
        "Isenhart's Lightbrand",
        "Isenhart's Parry",
        "Isenhart's Case",
        "Isenhart's Horns",
        "Vidala's Barb",
        "Vidala's Fetlock",
        "Vidala's Ambush",
        "Vidala's Snare",
        "Milabrega's Orb",
        "Milabrega's Rod",
        "Milabrega's Diadem",
        "Milabrega's Robe",
        "Cathan's Rule",
        "Cathan's Mesh",
        "Cathan's Visage",
        "Cathan's Sigil",
        "Cathan's Seal",
        "Tancred's Crowbill",
        "Tancred's Spine",
        "Tancred's Hobnails",
        "Tancred's Weird",
        "Tancred's Skull",
        "Sigon's Gage",
        "Sigon's Visor",
        "Sigon's Shelter",
        "Sigon's Sabot",
        "Sigon's Wrap",
        "Sigon's Guard",
        "Infernal Cranium",
        "Infernal Torch",
        "Infernal Sign",
        "Berserker's Headgear",
        "Berserker's Hauberk",
        "Berserker's Hatchet",
        "Death's Hand",
        "Death's Guard",
        "Death's Touch",
        "Angelic Sickle",
        "Angelic Mantle",
        "Angelic Halo",
        "Angelic Wings",
        "Arctic Horn",
        "Arctic Furs",
        "Arctic Binding",
        "Arctic Mitts",
        "Arcanna's Sign",
        "Arcanna's Deathwand",
        "Arcanna's Head",
        "Arcanna's Flesh",
        "Natalya's Totem",
        "Natalya's Mark",
        "Natalya's Shadow",
        "Natalya's Soul",
        "Aldur's Stony Gaze",
        "Aldur's Deception",
        "Aldur's Gauntlet",
        "Aldur's Advance",
        "Immortal King's Will",
        "Immortal King's Soul Cage",
        "Immortal King's Detail",
        "Immortal King's Forge",
        "Immortal King's Pillar",
        "Immortal King's Stone Crusher",
        "Tal Rasha's Fine-Spun Cloth",
        "Tal Rasha's Adjudication",
        "Tal Rasha's Lidless Eye",
        "Tal Rasha's Guardianship",
        "Tal Rasha's Horadric Crest",
        "Griswold's Valor",
        "Griswold's Heart",
        "Griswold's Redemption",
        "Griswold's Honor",
        "Trang-Oul's Guise",
        "Trang-Oul's Scales",
        "Trang-Oul's Wing",
        "Trang-Oul's Claws",
        "Trang-Oul's Girth",
        "M'avina's True Sight",
        "M'avina's Embrace",
        "M'avina's Icy Clutch",
        "M'avina's Tenet",
        "M'avina's Caster",
        "Telling of Beads",
        "Laying of Hands",
        "Rite of Passage",
        "Spiritual Custodian",
        "Credendum",
        "Dangoon's Teaching",
        "Heaven's Taebaek",
        "Haemosu's Adament",
        "Ondal's Almighty",
        "Guillaume's Face",
        "Wilhelm's Pride",
        "Magnus' Skin",
        "Wihtstan's Guard",
        "Hwanin's Splendor",
        "Hwanin's Refuge",
        "Hwanin's Seal",
        "Hwanin's Justice",
        "Sazabi's Cobalt Redeemer",
        "Sazabi's Ghost Liberator",
        "Sazabi's Mental Sheath",
        "Bul-Kathos' Sacred Charge",
        "Bul-Kathos' Tribal Guardian",
        "Cow King's Horns",
        "Cow King's Hide",
        "Cow King's Hoofs",
        "Naj's Puzzler",
        "Naj's Light Plate",
        "Naj's Circlet",
        "McAuley's Paragon",
        "McAuley's Riprap",
        "McAuley's Taboo",
        "McAuley's Superstition",
        "Warlord's Lust",
        "Warlord's Conquest",
        "Warlord's Mantle",
        "Warlord's Crushers",
        "Warlord's Authority",
        "Bane's Oathmaker",
        "Bane's Wraithskin",
        "Bane's Authority",
        "Horazon's Countenance",
        "Horazon's Dominion",
        "Horazon's Hold",
        "Horazon's Legacy",
        "Horazon's Secrets",
    )

    def load_set_items(
        self,
        setitems_path: str | Traversable,
        json_path: str | Traversable | None = None,
    ) -> dict[int, SetItemInfo]:
        """Load set items from game table (setitems.txt) with localized names from item-names.json."""
        name_str = setitems_path if isinstance(setitems_path, str) else setitems_path.name
        if json_path is None and name_str.endswith(".json"):
            json_file: str | Traversable | None = setitems_path
            table_file: str | Traversable | None = None
        elif json_path is None:
            json_file = None
            table_file = setitems_path
        else:
            table_file = setitems_path
            json_file = json_path

        json_by_key: dict[str, dict] = {}
        if json_file:
            with _open_resource(json_file, encoding="utf-8-sig") as f:
                data = json.load(f)
            for item in data:
                if isinstance(item, dict):
                    key = item.get("Key", "")
                    if key:
                        json_by_key[key] = item

        set_items: dict[int, SetItemInfo] = {}

        if table_file:
            entries = (
                (key, row_id)
                for row in TsvReader(table_file)
                if (key := row.get("index")) and (row_id := row.get_int("*ID", -1)) >= 0
            )
        else:
            entries = ((name, idx) for idx, name in enumerate(self.SET_ITEM_NAMES))

        for name, row_id in entries:
            json_entry = json_by_key.get(name, {})
            d2r_id = json_entry.get("id", 0)
            set_info = SetItemInfo(name=name, set_id=d2r_id)
            set_items[row_id] = set_info
            if d2r_id > 0 and d2r_id not in set_items:
                set_items[d2r_id] = set_info

        return set_items

    def _load_skills_with_metadata(
        self, filepath: str | Traversable
    ) -> tuple[dict[int, str], set[int], set[int]]:
        skills: dict[int, str] = {}
        aura_skill_ids: set[int] = set()
        fire_skill_ids: set[int] = set()

        for row in TsvReader(filepath):
            skill_id = row.get_int("*Id", -1)
            if skill_id < 0:
                continue

            skill_name = row.get("skill")
            if skill_name:
                skills[skill_id] = skill_name

            if row.get_int("aura") == 1:
                aura_skill_ids.add(skill_id)
            if row.get("EType") == "fire":
                fire_skill_ids.add(skill_id)

        return skills, aura_skill_ids, fire_skill_ids

    def load_skills(self, filepath: str | Traversable) -> tuple[dict[int, str], set[int]]:
        skills, aura_skill_ids, _fire_skill_ids = self._load_skills_with_metadata(filepath)
        return skills, aura_skill_ids

    def load_hirelings(self, filepath: str | Traversable) -> dict[int, HirelingInfo]:
        """Load hireling definitions from hireling.txt, preferring Version 100 entries."""
        grouped: dict[int, dict[int, tuple[HirelingInfo, list[HirelingLevelInfo]]]] = {}

        for row in TsvReader(filepath):
            hireling_id = row.get_int("Id", -1)
            if hireling_id < 0:
                continue

            version = row.get_int("Version")
            ver_map = grouped.setdefault(hireling_id, {})
            if version not in ver_map:
                info = HirelingInfo(
                    hireling_id=hireling_id,
                    hireling=row.get("Hireling"),
                    act=row.get_int("Act"),
                    difficulty=row.get_int("Difficulty"),
                    name_first=row.get("NameFirst"),
                    name_last=row.get("NameLast"),
                    hire_desc=row.get("HireDesc"),
                    skill_1=row.get("Skill1"),
                )
                ver_map[version] = (info, [])

            _, levels_list = ver_map[version]
            levels_list.append(
                HirelingLevelInfo(
                    level=row.get_int("Level"),
                    exp_per_lvl=row.get_int("Exp/Lvl"),
                    str_base=row.get_int("Str"),
                    str_per_lvl=row.get_int("Str/Lvl"),
                    dex_base=row.get_int("Dex"),
                    dex_per_lvl=row.get_int("Dex/Lvl"),
                    resist_fire=row.get_int("ResistFire"),
                    resist_fire_per_lvl=row.get_int("ResistFire/Lvl"),
                    resist_cold=row.get_int("ResistCold"),
                    resist_cold_per_lvl=row.get_int("ResistCold/Lvl"),
                    resist_lightning=row.get_int("ResistLightning"),
                    resist_lightning_per_lvl=row.get_int("ResistLightning/Lvl"),
                    resist_poison=row.get_int("ResistPoison"),
                    resist_poison_per_lvl=row.get_int("ResistPoison/Lvl"),
                )
            )

        hirelings: dict[int, HirelingInfo] = {}
        for hireling_id, ver_map in grouped.items():
            info, levels_list = ver_map[100] if 100 in ver_map else next(iter(ver_map.values()))
            levels_list.sort(key=lambda entry: entry.level)
            info.levels = levels_list
            hirelings[hireling_id] = info

        return hirelings

    def load_monsters(self, filepath: str | Traversable) -> dict[int, str]:
        """Load monster NameStr localization keys indexed by *hcIdx from monstats.txt."""
        monsters: dict[int, str] = {}
        reader = TsvReader(filepath)
        if not reader.has_columns("*hcIdx", "NameStr"):
            return monsters

        for row in reader:
            monster_id = row.get_int("*hcIdx", -1)
            if monster_id < 0:
                continue
            name_str = row.get("NameStr")
            if name_str and name_str != "unused":
                monsters[monster_id] = name_str

        return monsters

    BODYLOC_MAP: ClassVar[dict[str, int]] = {
        "head": 1,
        "neck": 2,
        "tors": 3,
        "rarm": 4,
        "larm": 5,
        "rrin": 6,
        "lrin": 7,
        "belt": 8,
        "feet": 9,
        "glov": 10,
    }

    def load_itemtypes(
        self, filepath: str | Traversable
    ) -> tuple[dict[str, set[str]], dict[str, set[str]], dict[str, tuple[int, int]], set[str]]:
        type_ancestors: dict[str, set[str]] = {}
        type_descendants: dict[str, set[str]] = {}
        type_bodyloc: dict[str, tuple[int, int]] = {}
        beltable_codes: set[str] = set()

        type_equivs: dict[str, tuple[str, str]] = {}
        all_codes: set[str] = set()
        for row in TsvReader(filepath):
            type_name = row.get("itemtype")
            if not type_name:
                continue

            code = row.get("code")
            equiv1 = row.get("equiv1").lower()
            equiv2 = row.get("equiv2").lower()
            bl1 = self.BODYLOC_MAP.get(row.get("bodyloc1").lower(), 0)
            bl2 = self.BODYLOC_MAP.get(row.get("bodyloc2").lower(), 0)

            key = type_name.lower()
            type_equivs[key] = (equiv1, equiv2)
            all_codes.add(key)
            type_bodyloc[key] = (bl1, bl2)
            if code:
                code_lower = code.lower()
                type_equivs[code_lower] = (equiv1, equiv2)
                all_codes.add(code_lower)
                type_bodyloc[code_lower] = (bl1, bl2)

            if row.get("beltable") == "1":
                beltable_codes.add(key)
                if code:
                    beltable_codes.add(code.lower())

        # Build ancestor relationships
        for key in all_codes:
            type_ancestors[key] = self._build_ancestors(key, type_equivs)

        # Build descendant relationships
        for key in all_codes:
            type_descendants[key] = {key}
        for code, ancestors in type_ancestors.items():
            for ancestor in ancestors:
                if ancestor not in type_descendants:
                    type_descendants[ancestor] = set()
                type_descendants[ancestor].add(code)

        return type_ancestors, type_descendants, type_bodyloc, beltable_codes

    def _build_ancestors(
        self, code: str, type_equivs: dict[str, tuple[str, str]], visited: set[str] | None = None
    ) -> set[str]:
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

    def _resolve_path(
        self,
        filename: str,
        search_dirs: Sequence[str | Traversable] | str | Traversable,
        fallback_dir: str | Traversable | None = None,
    ) -> Traversable:
        """Resolve a file path across overlay search directories in priority order."""
        if isinstance(search_dirs, (str, Traversable)):
            dirs: list[Traversable] = [
                Path(search_dirs) if isinstance(search_dirs, str) else search_dirs
            ]
        else:
            dirs = [Path(d) if isinstance(d, str) else d for d in search_dirs]

        if fallback_dir:
            fb = Path(fallback_dir) if isinstance(fallback_dir, str) else fallback_dir
            if fb not in dirs:
                dirs.append(fb)

        parts = filename.replace("\\", "/").split("/")
        for d in dirs:
            p = d.joinpath(*parts)
            if p.is_file():
                return p
        raise FileNotFoundError(
            f"Required data file '{filename}' not found in search paths: {[str(d) for d in dirs]}"
        )

    def load_version_data(
        self,
        search_dirs: Sequence[str | Traversable] | str | Traversable,
        fallback_dir: str | Traversable | None = None,
    ) -> VersionData:
        """Load game data across the overlay directory chain."""
        if isinstance(search_dirs, (str, Traversable)):
            dirs: list[Traversable] = [
                Path(search_dirs) if isinstance(search_dirs, str) else search_dirs
            ]
        else:
            dirs = [Path(d) if isinstance(d, str) else d for d in search_dirs]

        if fallback_dir:
            fb = Path(fallback_dir) if isinstance(fallback_dir, str) else fallback_dir
            if fb not in dirs:
                dirs.append(fb)

        version_data = VersionData()

        # Load itemtypes.txt (must be loaded first as other data may depend on it)
        itemtypes_path = self._resolve_path("itemtypes.txt", dirs)
        (
            version_data.type_ancestors,
            version_data.type_descendants,
            version_data.type_bodyloc,
            version_data.type_beltable,
        ) = self.load_itemtypes(itemtypes_path)

        # Load ItemStatCost.txt
        itemstatcost_path = self._resolve_path("ItemStatCost.txt", dirs)
        version_data.stats, version_data.stats_by_name = self.load_itemstatcost(itemstatcost_path)

        # Load Properties.txt
        properties_path = self._resolve_path("Properties.txt", dirs)
        version_data.properties, version_data.properties_by_code = self.load_properties(
            properties_path
        )

        # Load Armor.txt
        armor_path = self._resolve_path("Armor.txt", dirs)
        armor_items = self.load_items_txt(armor_path, "armor")
        version_data.items.update(armor_items)

        # Load Weapons.txt
        weapons_path = self._resolve_path("Weapons.txt", dirs)
        weapons_items = self.load_items_txt(weapons_path, "weapon")
        version_data.items.update(weapons_items)

        # Load Misc.txt
        misc_path = self._resolve_path("Misc.txt", dirs)
        misc_items = self.load_items_txt(misc_path, "misc")
        version_data.items.update(misc_items)

        # Load magicprefix.txt
        magicprefix_path = self._resolve_path("magicprefix.txt", dirs)
        version_data.magic_prefixes = self.load_magic_affix(magicprefix_path, is_prefix=True)

        # Load magicsuffix.txt
        magicsuffix_path = self._resolve_path("magicsuffix.txt", dirs)
        version_data.magic_suffixes = self.load_magic_affix(magicsuffix_path, is_prefix=False)

        # Load rareprefix.txt
        rareprefix_path = self._resolve_path("rareprefix.txt", dirs)
        version_data.rare_prefixes = self.load_rare_affix(rareprefix_path, offset=155)

        # Load raresuffix.txt
        raresuffix_path = self._resolve_path("raresuffix.txt", dirs)
        version_data.rare_suffixes = self.load_rare_affix(raresuffix_path, offset=0)

        # Load uniqueitems.txt
        uniqueitems_path = self._resolve_path("uniqueitems.txt", dirs)
        version_data.unique_items = self.load_unique_items(uniqueitems_path)

        # Load set items: parse setitems.txt table, resolve translations from item-names.json
        setitems_txt_path = self._resolve_path("setitems.txt", dirs)
        setnames_path = self._resolve_path("local/item-names.json", dirs)
        version_data.set_items = self.load_set_items(setitems_txt_path, setnames_path)

        # Load runewords: parse runes.txt table, resolve translations from item-runes.json
        runes_txt_path = self._resolve_path("runes.txt", dirs)
        runewords_path = self._resolve_path("local/item-runes.json", dirs)
        version_data.runewords = self.load_runewords(runes_txt_path, runewords_path)

        # Load gems.txt
        gems_path = self._resolve_path("gems.txt", dirs)
        version_data.gems = self.load_gems(gems_path)

        # Load hireling.txt
        hireling_path = self._resolve_path("hireling.txt", dirs)
        version_data.hirelings = self.load_hirelings(hireling_path)

        # Load monstats.txt
        monstats_path = self._resolve_path("monstats.txt", dirs)
        version_data.monsters = self.load_monsters(monstats_path)

        # Load skills.txt
        skills_path = self._resolve_path("skills.txt", dirs)
        version_data.skills, version_data.aura_skill_ids, version_data.fire_skill_ids = (
            self._load_skills_with_metadata(skills_path)
        )

        # Load itemdata.txt
        itemdata_path = self._resolve_path("itemdata.txt", dirs)
        version_data.item_manager = self.load_itemdata(itemdata_path)

        # Load property.txt
        property_path = self._resolve_path("property.txt", dirs)
        version_data.prop_meta = self.load_property_meta(property_path)

        return version_data

    def load_property_meta(self, filepath: str | Traversable) -> dict[int, PropertyMetaData]:
        properties: dict[int, PropertyMetaData] = {}

        with _open_resource(filepath, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        for line in lines:
            line = line.strip()
            if not line or line.startswith("*"):
                continue

            parts = line.split("\t")
            if len(parts) < 1:
                continue

            try:
                prop_id = int(parts[0])
            except ValueError:
                continue

            ver_min = 0
            if len(parts) > 1 and parts[1]:
                if parts[1].startswith("0x"):
                    ver_min = int(parts[1], 16)
                else:
                    try:
                        ver_min = int(parts[1])
                    except ValueError:
                        ver_min = 0

            default_value = 0
            if len(parts) > 2 and parts[2]:
                if parts[2].startswith("0x"):
                    default_value = int(parts[2], 16)
                else:
                    try:
                        default_value = int(parts[2])
                    except ValueError:
                        default_value = 0

            fields: list[PropertyField] = []
            bits_sum = 0

            for chunk in batched(parts[3:], 4, strict=False):
                bits_str = chunk[0]
                if not bits_str:
                    break

                try:
                    bits = int(bits_str)
                    base_str = chunk[1] if len(chunk) > 1 else ""
                    min_str = chunk[2] if len(chunk) > 2 else ""
                    max_str = chunk[3] if len(chunk) > 3 else ""

                    base = int(base_str) if base_str else 0
                    min_val = int(min_str) if min_str else 0
                    max_val = int(max_str) if max_str else 0

                    fields.append(PropertyField(bits, base, min_val, max_val))
                    bits_sum += bits
                except ValueError:
                    break

            while len(fields) < 4:
                fields.append(PropertyField())

            item = PropertyMetaDataItem(ver_min, fields, default_value, bits_sum)

            if prop_id not in properties:
                properties[prop_id] = PropertyMetaData()
            properties[prop_id].add_item(item)

        return properties

    def load_itemdata(self, filepath: str | Traversable) -> ItemMetaDataManager:
        manager = ItemMetaDataManager()

        with _open_resource(filepath, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        has_version_min = False
        for line in lines:
            if line.strip().startswith("*ID"):
                if "VersionMin" in line:
                    has_version_min = True
                break

        for line in lines:
            line = line.strip()
            if not line or line.startswith("*"):
                continue

            parts = line.split("\t")
            if len(parts) < 2:
                continue

            type_id = parts[0].ljust(4)[:4].encode("ascii")

            def parse_int(s: str, default: int = 0) -> int:
                if not s:
                    return default
                try:
                    return int(s)
                except ValueError:
                    return default

            def parse_bool(s: str) -> bool:
                return s == "1"

            def parse_version(s: str) -> int:
                if not s:
                    return 0
                if s.startswith("0x"):
                    return int(s, 16)
                try:
                    return int(s)
                except ValueError:
                    return 0

            idx_offset = 1 if has_version_min else 0
            ver_min = parse_version(parts[1]) if has_version_min and len(parts) > 1 else 0

            item = ItemMetaData(
                type_id=type_id,
                ver_min=ver_min,
                pic_index=parse_int(parts[1 + idx_offset]) if len(parts) > 1 + idx_offset else 0,
                name_index=parse_int(parts[2 + idx_offset]) if len(parts) > 2 + idx_offset else 0,
                range_val=parse_int(parts[3 + idx_offset]) if len(parts) > 3 + idx_offset else 0,
                equip=parse_int(parts[4 + idx_offset]) if len(parts) > 4 + idx_offset else 0,
                simple=parse_bool(parts[5 + idx_offset]) if len(parts) > 5 + idx_offset else False,
                normal=parse_bool(parts[6 + idx_offset]) if len(parts) > 6 + idx_offset else False,
                white=parse_bool(parts[7 + idx_offset]) if len(parts) > 7 + idx_offset else False,
                is_new=parse_bool(parts[8 + idx_offset]) if len(parts) > 8 + idx_offset else False,
                has_def=parse_bool(parts[9 + idx_offset]) if len(parts) > 9 + idx_offset else False,
                has_dur=parse_bool(parts[10 + idx_offset])
                if len(parts) > 10 + idx_offset
                else False,
                is_stacked=parse_bool(parts[11 + idx_offset])
                if len(parts) > 11 + idx_offset
                else False,
                has_monster_id=parse_bool(parts[12 + idx_offset])
                if len(parts) > 12 + idx_offset
                else False,
                is_charm=parse_bool(parts[13 + idx_offset])
                if len(parts) > 13 + idx_offset
                else False,
                spell_id=parse_int(parts[14 + idx_offset]) if len(parts) > 14 + idx_offset else 0,
                is_unique=parse_bool(parts[15 + idx_offset])
                if len(parts) > 15 + idx_offset
                else False,
                is_craft=parse_bool(parts[16 + idx_offset])
                if len(parts) > 16 + idx_offset
                else False,
                is_gem=parse_bool(parts[17 + idx_offset])
                if len(parts) > 17 + idx_offset
                else False,
                dmg1_min=parse_int(parts[18 + idx_offset]) if len(parts) > 18 + idx_offset else 0,
                dmg1_max=parse_int(parts[19 + idx_offset]) if len(parts) > 19 + idx_offset else 0,
                dmg2_min=parse_int(parts[20 + idx_offset]) if len(parts) > 20 + idx_offset else 0,
                dmg2_max=parse_int(parts[21 + idx_offset]) if len(parts) > 21 + idx_offset else 0,
                ipad_bits=parse_int(parts[22 + idx_offset]) if len(parts) > 22 + idx_offset else 0,
                ipad=parse_int(parts[23 + idx_offset]) if len(parts) > 23 + idx_offset else 0,
            )
            manager.add_item(item)

        return manager


class GameData:
    """Manages versioned data stores."""

    def __init__(self) -> None:
        self.version_data: dict[int, VersionData] = {}
        self.default_version: int = 0x63

    @classmethod
    def load(cls, base_data_dir: str | Traversable | None = None) -> GameData:
        mgr = cls()
        mgr.load_all_versions(base_data_dir)
        return mgr

    def for_version(self, version: int) -> VersionData:
        """Return VersionData for a given game version."""
        if version in self.version_data:
            return self.version_data[version]
        if version >= 0x69 and 0x69 in self.version_data:
            return self.version_data[0x69]
        if self.default_version in self.version_data:
            return self.version_data[self.default_version]
        if self.version_data:
            return next(iter(self.version_data.values()))
        raise KeyError(f"No game data loaded for version {version:#x}")

    OVERLAY_CHAIN: ClassVar[dict[int, list[str]]] = {
        0x63: ["0x63", "d2r"],
        0x69: ["d2r"],
    }
    DEFAULT_OVERLAYS: ClassVar[list[str]] = ["d2r"]

    def load_version(
        self,
        version: int,
        base_data_dir: str | Traversable | None = None,
        fallback_dir: str | Traversable | None = None,
    ) -> bool:
        if base_data_dir is None:
            base_dir: Traversable = importlib.resources.files("d2savior").joinpath("data")
        elif isinstance(base_data_dir, str):
            base_dir = Path(base_data_dir)
        else:
            base_dir = base_data_dir

        fb: Traversable | None = (
            Path(fallback_dir) if isinstance(fallback_dir, str) else fallback_dir
        )

        # If base_dir is already a specific overlay dir (e.g. data/0x63), use it directly with fallback
        if base_dir.name in ("0x63", "d2r", "0x69"):
            search_dirs: list[Traversable] = [base_dir]
            if fb:
                search_dirs.append(fb)
        else:
            overlays = self.OVERLAY_CHAIN.get(version, self.DEFAULT_OVERLAYS)
            search_dirs = [base_dir.joinpath(d) for d in overlays]
            if fb and fb not in search_dirs:
                search_dirs.append(fb)

        loader = D2DataLoader()
        version_data = loader.load_version_data(search_dirs)
        version_data.version = version
        self.version_data[version] = version_data
        return True

    def load_all_versions(self, base_data_dir: str | Traversable | None = None) -> bool:
        if base_data_dir is None:
            base_dir: Traversable = importlib.resources.files("d2savior").joinpath("data")
        elif isinstance(base_data_dir, str):
            base_dir = Path(base_data_dir)
        else:
            base_dir = base_data_dir

        if not base_dir.is_dir():
            raise FileNotFoundError(f"Base data directory not found: {base_dir}")

        for version in self.OVERLAY_CHAIN:
            self.load_version(version, base_dir)

        return True
