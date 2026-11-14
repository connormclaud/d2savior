"""Advanced stats calculation for Diablo II characters.

Calculates aggregated stats from active equipped gear, inventory charms, and quest rewards:
- Resistances (Fire, Lightning, Cold, Poison)
- Faster Hit Recovery (FHR)
- Faster Cast Rate (FCR)
- Magic Find (MF)
- Supports active partial and full set bonuses from equipped set items
"""

from collections import Counter
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

from d2savior.core.constants import (
    BASE_MAX_RESIST,
    CLASS_SKILL_BASES,
    DIFFICULTY_RESIST_PENALTIES_CLASSIC,
    DIFFICULTY_RESIST_PENALTIES_EXPANSION,
    HARD_MAX_RESIST,
    MIN_EFFECTIVE_RESIST,
    get_skill_tab_index,
)
from d2savior.core.d2s_struct import D2SStruct
from d2savior.core.enums import EquipSlot, ItemLocation, StoredIn
from d2savior.core.models import HirelingInfo
from d2savior.core.property import get_skill_class_id
from d2savior.core.resolver import GameDataResolver


def _default_max_resistances() -> ResistanceStats:
    return ResistanceStats(BASE_MAX_RESIST, BASE_MAX_RESIST, BASE_MAX_RESIST, BASE_MAX_RESIST)


@dataclass
class ResistanceStats:
    fire: int = 0
    cold: int = 0
    lightning: int = 0
    poison: int = 0

    def effective(
        self, penalty: int = 0, max_res: ResistanceStats | None = None
    ) -> ResistanceStats:
        """Compute difficulty-adjusted resistances clamped to [MIN_EFFECTIVE_RESIST, cap]."""
        cap = max_res if max_res is not None else _default_max_resistances()
        return ResistanceStats(
            fire=max(MIN_EFFECTIVE_RESIST, min(self.fire + penalty, cap.fire)),
            cold=max(MIN_EFFECTIVE_RESIST, min(self.cold + penalty, cap.cold)),
            lightning=max(MIN_EFFECTIVE_RESIST, min(self.lightning + penalty, cap.lightning)),
            poison=max(MIN_EFFECTIVE_RESIST, min(self.poison + penalty, cap.poison)),
        )

    def format_summary(
        self,
        penalty: int | None = None,
        max_res: ResistanceStats | None = None,
    ) -> str:
        if penalty is None:
            return (
                f"Fire: {self.fire:+d}%, Cold: {self.cold:+d}%, "
                f"Lightning: {self.lightning:+d}%, Poison: {self.poison:+d}%"
            )
        eff = self.effective(penalty, max_res)
        return (
            f"Fire: {eff.fire}% ({self.fire:+d}%), Cold: {eff.cold}% ({self.cold:+d}%), "
            f"Lightning: {eff.lightning}% ({self.lightning:+d}%), "
            f"Poison: {eff.poison}% ({self.poison:+d}%)"
        )


@dataclass
class AdvancedStats:
    resistances: ResistanceStats = field(default_factory=ResistanceStats)
    max_resistances: ResistanceStats = field(default_factory=_default_max_resistances)
    fhr: int = 0
    fcr: int = 0
    frw: int = 0
    ias: int = 0
    mf: int = 0
    all_skills: int = 0
    class_skills: int = 0
    skill_tab_bonuses: dict[int, int] = field(default_factory=dict)
    single_skill_bonuses: dict[int, int] = field(default_factory=dict)
    oskill_bonuses: dict[int, int] = field(default_factory=dict)
    fire_skills: int = 0

    def skill_bonus_for(
        self,
        char_class: int,
        skill_offset: int,
        resolver: GameDataResolver | None = None,
        version: int = 0x63,
    ) -> int:
        """Compute total active skill-level bonus for a character class skill slot."""
        bonus = self.all_skills + self.class_skills
        tab = get_skill_tab_index(char_class, skill_offset)
        if tab is not None:
            bonus += self.skill_tab_bonuses.get(tab, 0)
        if 0 <= char_class < len(CLASS_SKILL_BASES):
            skill_id = CLASS_SKILL_BASES[char_class] + skill_offset
            bonus += self.single_skill_bonuses.get(skill_id, 0)
            bonus += min(self.oskill_bonuses.get(skill_id, 0), 3)
            if self.fire_skills and resolver is not None:
                vd = resolver.for_version(version).data
                if skill_id in vd.fire_skill_ids:
                    bonus += self.fire_skills
        return bonus


@dataclass
class MercenaryStats:
    """Calculated mercenary level, attributes, and resistances from save data and gear."""

    level: int = 1
    strength: int = 0
    dexterity: int = 0
    resistances: ResistanceStats = field(default_factory=ResistanceStats)
    max_resistances: ResistanceStats = field(default_factory=_default_max_resistances)


_RESIST_STAT_FIELDS: dict[int, tuple[str, bool]] = {
    39: ("fire", False),  # fireresist
    41: ("lightning", False),  # lightresist
    43: ("cold", False),  # coldresist
    45: ("poison", False),  # poisonresist
    40: ("fire", True),  # maxfireresist
    42: ("lightning", True),  # maxlightresist
    44: ("cold", True),  # maxcoldresist
    46: ("poison", True),  # maxpoisonresist
}


def _apply_resist_stat(
    res: ResistanceStats, max_res: ResistanceStats, prop_id: int, param_val: int
) -> bool:
    entry = _RESIST_STAT_FIELDS.get(prop_id)
    if entry is None:
        return False
    field_name, is_max = entry
    target = max_res if is_max else res
    setattr(target, field_name, getattr(target, field_name) + param_val)
    return True


def _clamp_max_resistances(max_res: ResistanceStats) -> ResistanceStats:
    return ResistanceStats(
        fire=min(max_res.fire, HARD_MAX_RESIST),
        cold=min(max_res.cold, HARD_MAX_RESIST),
        lightning=min(max_res.lightning, HARD_MAX_RESIST),
        poison=min(max_res.poison, HARD_MAX_RESIST),
    )


def get_current_difficulty(char_data: D2SStruct) -> int:
    """Return the character's current difficulty index (0=Normal, 1=Nightmare, 2=Hell)."""
    town = getattr(char_data, "town", b"")
    if len(town) >= 3:
        for diff_idx in (2, 1, 0):
            if town[diff_idx] & 0x80:
                return diff_idx

    # Fallback when town bytes are unset (e.g., synthetic D2SStruct in unit tests).
    quests = getattr(char_data, "quests", None)
    if quests and getattr(quests, "magic", None) == 0x216F6F57:
        for diff_idx in (2, 1):
            if diff_idx < len(quests.qi_data):
                qd = quests.qi_data[diff_idx]
                if any(
                    w != 0
                    for words in (qd.act_1, qd.act_2, qd.act_3, qd.act_4, qd.act_5)
                    for w in words
                ):
                    return diff_idx

    waypoints = getattr(char_data, "waypoints", None)
    if waypoints and getattr(waypoints, "magic", None) == 0x5357:
        for diff_idx in (2, 1):
            if diff_idx < len(waypoints.wp):
                wp = waypoints.wp[diff_idx].waypoints
                if wp and ((wp[0] & ~1) != 0 or any(b != 0 for b in wp[1:])):
                    return diff_idx

    char_title = getattr(char_data, "char_title", 0)
    if char_title:
        if char_data.is_expansion():
            if char_title >= 10:
                return 2
            if char_title >= 5:
                return 1
        else:
            if char_title >= 8:
                return 2
            if char_title >= 4:
                return 1

    return 0


def get_difficulty_resist_penalty(char_data: D2SStruct, difficulty: int | None = None) -> int:
    """Return the resistance penalty (e.g. 0, -40, -100) for the character's difficulty."""
    diff_idx = get_current_difficulty(char_data) if difficulty is None else difficulty
    penalties = (
        DIFFICULTY_RESIST_PENALTIES_EXPANSION
        if char_data.is_expansion()
        else DIFFICULTY_RESIST_PENALTIES_CLASSIC
    )
    return penalties[max(0, min(diff_idx, len(penalties) - 1))]


def collect_item_properties(
    item: Any,
    resolver: GameDataResolver,
    version: int,
    set_counts: dict[int, int] | None = None,
    *,
    normalize_source: Callable[[list[tuple[int, int, list[int]]]], list[tuple[int, int, list[int]]]]
    | None = None,
) -> list[tuple[int, int, list[int]]]:
    """Retrieve parsed properties for an item, including runewords, socketables, and active set bonuses."""
    tp = getattr(getattr(item, "item_info", None), "type_specific_info", None)
    if not tp:
        return []

    sources: list[list[tuple[int, int, list[int]]]] = []
    if getattr(tp, "property_list", None):
        sources.append(tp.property_list.get_parsed_properties(version, data=resolver.data))
    if getattr(tp, "runeword_property_list", None):
        sources.append(tp.runeword_property_list.get_parsed_properties(version, data=resolver.data))
    if getattr(item, "gem_items", None):
        for gem in item.gem_items:
            sources.append(resolver.get_socket_properties(item, gem))

    # Each index i in set_properties requires (i + 2) pieces of the set to be equipped.
    if set_counts and getattr(tp, "set_properties", None):
        ext = getattr(getattr(item, "item_info", None), "ext_info", None)
        if ext and ext.set_id is not None:
            equipped_count = set_counts.get(ext.set_id, 0)
            for idx, set_prop_list in enumerate(tp.set_properties):
                if set_prop_list is not None and equipped_count >= idx + 2:
                    sources.append(set_prop_list.get_parsed_properties(version, data=resolver.data))

    if normalize_source is None:
        return [prop for source in sources for prop in source]
    return [prop for source in sources for prop in normalize_source(source)]


def _iter_item_properties(
    items: list[Any],
    resolver: GameDataResolver,
    version: int,
    *,
    set_items: list[Any] | None = None,
) -> Iterator[tuple[int, int, list[int]]]:
    """Yield (prop_id, val, params) across items, counting set bonuses from set_items."""
    set_counts: Counter[int] = Counter()
    for it in items if set_items is None else set_items:
        ext = getattr(getattr(it, "item_info", None), "ext_info", None)
        if ext and ext.set_id is not None:
            set_counts[ext.set_id] += 1

    for item in items:
        yield from collect_item_properties(
            item, resolver=resolver, version=version, set_counts=set_counts
        )


def _iter_item_stats(
    items: list[Any],
    resolver: GameDataResolver,
    version: int,
    *,
    set_items: list[Any] | None = None,
) -> Iterator[tuple[int, int]]:
    """Yield (prop_id, param_val) across items, counting set bonuses from set_items."""
    for prop_id, val, params in _iter_item_properties(
        items, resolver=resolver, version=version, set_items=set_items
    ):
        yield prop_id, params[0] if params else val


def calculate_advanced_stats(
    char_data: D2SStruct, resolver: GameDataResolver | None = None
) -> AdvancedStats:
    """Calculate advanced stats (resistances, FHR, FCR, MF) from active gear, inventory charms, and quest rewards."""
    if resolver is None:
        resolver = GameDataResolver.load()

    version = char_data.version if char_data.version else 0x63
    char_resolver = resolver.for_version(version)

    inactive_weapon_slots = (
        (EquipSlot.WEAPON_II, EquipSlot.SHIELD_II)
        if char_data.weapon_set == 0
        else (EquipSlot.WEAPON_I, EquipSlot.SHIELD_I)
    )

    equipped_items: list[Any] = []
    inventory_items: list[Any] = []

    item_list = getattr(char_data, "item_list", None)
    if item_list and getattr(item_list, "magic", None) == 0x4D4A:
        for it in getattr(item_list, "items", []):
            loc = ItemLocation(it.location)
            if loc == ItemLocation.EQUIPPED:
                if it.position in inactive_weapon_slots:
                    continue
                equipped_items.append(it)
            elif loc == ItemLocation.STORED and it.stored_in == StoredIn.INVENTORY:
                tname = (
                    it.type_name.decode("ascii", errors="replace").strip().lower()
                    if it.type_name
                    else ""
                )
                # In Diablo II, only charms in inventory provide active bonuses
                if tname in ("cm1", "cm2", "cm3"):
                    inventory_items.append(it)

    res = ResistanceStats()
    max_res = _default_max_resistances()
    fhr = 0
    fcr = 0
    frw = 0
    ias = 0
    mf = 0
    mf_per_level = 0
    all_skills = 0
    class_skills = 0
    skill_tab_bonuses: Counter[int] = Counter()
    single_skill_bonuses: Counter[int] = Counter()
    oskill_bonuses: Counter[int] = Counter()
    fire_skills = 0

    char_class = getattr(char_data, "char_class", -1)
    char_level = getattr(char_data, "char_level", 0)
    if not char_level:
        p_stats = getattr(char_data, "player_stats", None)
        if p_stats and getattr(p_stats, "is_valid", False):
            char_level = getattr(p_stats, "level", 0)

    all_source_items: list[Any] = equipped_items + inventory_items

    for prop_id, val, params in _iter_item_properties(
        all_source_items, char_resolver, version, set_items=equipped_items
    ):
        param_val = params[0] if params else val
        if _apply_resist_stat(res, max_res, prop_id, param_val):
            continue
        match prop_id:
            # Speeds & MF
            case 93:  # Increased Attack Speed
                ias += param_val
            case 96:  # Faster Run/Walk
                frw += param_val
            case 99:  # Faster Hit Recovery
                fhr += param_val
            case 105:  # Faster Cast Rate
                fcr += param_val
            case 80:  # Better Chance of Getting Magic Items
                mf += param_val
            case 240:  # Magic Find per level (eighths per level)
                mf_per_level += param_val
            # Skill bonuses
            case 127:  # All Skills
                all_skills += param_val
            case 83 if len(params) >= 2 and params[0] == char_class:  # Class Skill Levels
                class_skills += params[1]
            case 188 if len(params) >= 3 and params[1] == char_class:  # Skill Tab Levels
                skill_tab_bonuses[params[0]] += params[2]
            case 107 if len(params) >= 2 and get_skill_class_id(params[0]) == char_class:
                single_skill_bonuses[params[0]] += params[1]
            case 97 if len(params) >= 2:  # Oskills
                oskill_bonuses[params[0]] += params[1]
            case 126 if len(params) >= 2 and params[0] == 1:  # +X to Fire Skills
                fire_skills += params[1]

    mf += (mf_per_level * char_level) // 8

    # Paladin passive skills: Resist Fire (idx 4), Resist Cold (idx 9), Resist Lightning (idx 14)
    # grant +1% maximum resistance per 2 hard points invested.
    skills = getattr(char_data, "skills", None)
    if (
        getattr(char_data, "char_class", -1) == 3
        and skills
        and getattr(skills, "magic", None) == 0x6669
    ):
        levels = getattr(skills, "skill_levels", [])
        if len(levels) > 4:
            max_res.fire += levels[4] // 2
        if len(levels) > 9:
            max_res.cold += levels[9] // 2
        if len(levels) > 14:
            max_res.lightning += levels[14] // 2

    # Add quest resistance bonuses:
    # In Diablo II, completing the "Prison of Ice" quest (Anya, Act V quest index 2)
    # awards the Scroll of Resistance, which grants +10 to all resistances permanently.
    if (
        getattr(char_data, "quests", None)
        and getattr(char_data.quests, "magic", None) == 0x216F6F57
    ):
        for qd in getattr(char_data.quests, "qi_data", []):
            if len(qd.act_5) > 2 and (qd.act_5[2] & 1):
                res.fire += 10
                res.cold += 10
                res.lightning += 10
                res.poison += 10

    return AdvancedStats(
        resistances=res,
        max_resistances=_clamp_max_resistances(max_res),
        fhr=fhr,
        fcr=fcr,
        frw=frw,
        ias=ias,
        mf=mf,
        all_skills=all_skills,
        class_skills=class_skills,
        skill_tab_bonuses=dict(skill_tab_bonuses),
        single_skill_bonuses=dict(single_skill_bonuses),
        oskill_bonuses=dict(oskill_bonuses),
        fire_skills=fire_skills,
    )


def calculate_mercenary_level(experience: int, info: HirelingInfo, max_level: int = 98) -> int:
    """Resolve mercenary level from cumulative experience and hireling.txt progression."""
    level = 1
    while level < max_level:
        row = info.level_stats_for(level)
        if not row or row.exp_per_lvl <= 0:
            break
        next_level = level + 1
        required_exp = row.exp_per_lvl * next_level * next_level * (next_level + 1)
        if experience < required_exp:
            break
        level = next_level
    return level


def calculate_mercenary_stats(
    char_data: D2SStruct, resolver: GameDataResolver | None = None
) -> MercenaryStats | None:
    """Calculate mercenary level, strength, dexterity, and resistances from save data and gear."""
    if not char_data.is_expansion() or not char_data.has_mercenary():
        return None

    if resolver is None:
        resolver = GameDataResolver.load()

    version = char_data.version if char_data.version else 0x63
    char_resolver = resolver.for_version(version)

    hireling = char_resolver.get_hireling(char_data.merc_type_id)
    if not hireling or not hireling.levels:
        return None

    level = calculate_mercenary_level(char_data.merc_experience, hireling)
    row = hireling.level_stats_for(level)
    if not row:
        return None

    # Truncate toward zero on negative level_ups to match D2 engine integer division.
    level_ups = level - row.level
    strength = max(row.str_base + int((level_ups * row.str_per_lvl) / 8), 10)
    dexterity = max(row.dex_base + int((level_ups * row.dex_per_lvl) / 8), 10)
    res = ResistanceStats(
        fire=max(row.resist_fire + int((level_ups * row.resist_fire_per_lvl) / 4), 0),
        cold=max(row.resist_cold + int((level_ups * row.resist_cold_per_lvl) / 4), 0),
        lightning=max(
            row.resist_lightning + int((level_ups * row.resist_lightning_per_lvl) / 4), 0
        ),
        poison=max(row.resist_poison + int((level_ups * row.resist_poison_per_lvl) / 4), 0),
    )
    max_res = _default_max_resistances()

    merc_item_list = getattr(getattr(char_data, "mercenary", None), "items", None)
    merc_items = list(merc_item_list.items) if merc_item_list else []
    if merc_items:
        str_per_lvl = 0
        dex_per_lvl = 0
        fire_per_lvl = 0
        cold_per_lvl = 0
        light_per_lvl = 0
        poison_per_lvl = 0

        for prop_id, param_val in _iter_item_stats(merc_items, char_resolver, version):
            if _apply_resist_stat(res, max_res, prop_id, param_val):
                continue
            match prop_id:
                case 0:  # Strength
                    strength += param_val
                case 2:  # Dexterity
                    dexterity += param_val
                case 220:  # Strength per level (eighths)
                    str_per_lvl += param_val
                case 221:  # Dexterity per level (eighths)
                    dex_per_lvl += param_val
                case 230:  # Cold Resist per level (eighths)
                    cold_per_lvl += param_val
                case 231:  # Fire Resist per level (eighths)
                    fire_per_lvl += param_val
                case 232:  # Lightning Resist per level (eighths)
                    light_per_lvl += param_val
                case 233:  # Poison Resist per level (eighths)
                    poison_per_lvl += param_val

        strength += (str_per_lvl * level) // 8
        dexterity += (dex_per_lvl * level) // 8
        res.fire += (fire_per_lvl * level) // 8
        res.cold += (cold_per_lvl * level) // 8
        res.lightning += (light_per_lvl * level) // 8
        res.poison += (poison_per_lvl * level) // 8

    return MercenaryStats(
        level=level,
        strength=strength,
        dexterity=dexterity,
        resistances=res,
        max_resistances=_clamp_max_resistances(max_res),
    )
