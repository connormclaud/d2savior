"""Advanced stats calculation for Diablo II characters.

Calculates aggregated stats from active equipped gear, inventory charms, and quest rewards:
- Resistances (Fire, Lightning, Cold, Poison)
- Faster Hit Recovery (FHR)
- Faster Cast Rate (FCR)
- Magic Find (MF)
- Supports active partial and full set bonuses from equipped set items
"""

from collections import Counter
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from typing import NamedTuple

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
from d2savior.core.enums import CharClass, EquipSlot, StoredIn
from d2savior.core.item import D2Item
from d2savior.core.models import HirelingInfo
from d2savior.core.property import adjust_property_values, get_skill_class_id
from d2savior.core.resolver import GameDataResolver

type SummaryPropKey = tuple[int, ...]


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


_RESIST_STAT_FIELDS: frozendict[int, tuple[str, bool]] = frozendict(
    {
        39: ("fire", False),  # fireresist
        41: ("lightning", False),  # lightresist
        43: ("cold", False),  # coldresist
        45: ("poison", False),  # poisonresist
        40: ("fire", True),  # maxfireresist
        42: ("lightning", True),  # maxlightresist
        44: ("cold", True),  # maxcoldresist
        46: ("poison", True),  # maxpoisonresist
    }
)


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


def _difficulty_from_quests(char_data: D2SStruct) -> int | None:
    quests = char_data.quests
    if not (quests and quests.magic == 0x216F6F57):
        return None
    for diff_idx in (2, 1):
        if diff_idx < len(quests.qi_data):
            qd = quests.qi_data[diff_idx]
            if any(
                w != 0
                for words in (qd.act_1, qd.act_2, qd.act_3, qd.act_4, qd.act_5)
                for w in words
            ):
                return diff_idx
    return None


def _difficulty_from_waypoints(char_data: D2SStruct) -> int | None:
    waypoints = char_data.waypoints
    if waypoints.magic != 0x5357:
        return None
    for diff_idx in (2, 1):
        if diff_idx < len(waypoints.wp):
            wp = waypoints.wp[diff_idx].waypoints
            if wp and ((wp[0] & ~1) != 0 or any(b != 0 for b in wp[1:])):
                return diff_idx
    return None


def _difficulty_from_title(char_data: D2SStruct) -> int:
    char_title = char_data.char_title
    if not char_title:
        return 0
    hell_thresh, nm_thresh = (10, 5) if char_data.is_expansion() else (8, 4)
    if char_title >= hell_thresh:
        return 2
    return 1 if char_title >= nm_thresh else 0


def get_current_difficulty(char_data: D2SStruct) -> int:
    """Return the character's current difficulty index (0=Normal, 1=Nightmare, 2=Hell)."""
    town = char_data.town
    if len(town) >= 3:
        for diff_idx in (2, 1, 0):
            if town[diff_idx] & 0x80:
                return diff_idx

    # Fallback when town bytes are unset (e.g., synthetic D2SStruct in unit tests).
    if (quest_diff := _difficulty_from_quests(char_data)) is not None:
        return quest_diff
    if (wp_diff := _difficulty_from_waypoints(char_data)) is not None:
        return wp_diff
    return _difficulty_from_title(char_data)


def get_difficulty_resist_penalty(char_data: D2SStruct, difficulty: int | None = None) -> int:
    """Return the resistance penalty (e.g. 0, -40, -100) for the character's difficulty."""
    diff_idx = get_current_difficulty(char_data) if difficulty is None else difficulty
    penalties = (
        DIFFICULTY_RESIST_PENALTIES_EXPANSION
        if char_data.is_expansion()
        else DIFFICULTY_RESIST_PENALTIES_CLASSIC
    )
    return penalties[max(0, min(diff_idx, len(penalties) - 1))]


def resolve_set_group_key(item: D2Item, resolver: GameDataResolver) -> str | None:
    """Return canonical parent-set key (set name if known, else 'set:<set_id>')."""
    ext = item.ext_info
    if ext is None or ext.set_id is None:
        return None
    info = resolver.get_set_item(ext.set_id)
    return info.set_name if info is not None and info.set_name else f"set:{ext.set_id}"


def compute_set_counts(items: Sequence[D2Item], resolver: GameDataResolver) -> dict[str, int]:
    """Count distinct set pieces equipped per parent set across `items`."""
    seen: dict[str, set[tuple[int, str]]] = {}
    for it in items:
        group_key = resolve_set_group_key(it, resolver)
        if group_key is None or it.ext_info is None or it.ext_info.set_id is None:
            continue
        seen.setdefault(group_key, set()).add((it.ext_info.set_id, it.code_str.strip().lower()))
    return {group_key: len(pairs) for group_key, pairs in seen.items()}


def collect_item_properties(
    item: D2Item,
    resolver: GameDataResolver,
    version: int,
    set_counts: Mapping[str, int] | None = None,
    *,
    normalize_source: Callable[[list[tuple[int, int, list[int]]]], list[tuple[int, int, list[int]]]]
    | None = None,
) -> list[tuple[int, int, list[int]]]:
    """Retrieve parsed properties for an item, including runewords, socketables, and active set bonuses."""
    tp = item.type_specific_info
    if not tp:
        return []

    sources: list[list[tuple[int, int, list[int]]]] = []
    if tp.property_list:
        sources.append(tp.property_list.get_parsed_properties(version, data=resolver.data))
    if tp.runeword_property_list:
        sources.append(tp.runeword_property_list.get_parsed_properties(version, data=resolver.data))
    if item.gem_items:
        for gem in item.gem_items:
            sources.append(resolver.get_socket_properties(item, gem))

    # Each index i in set_properties requires (i + 2) pieces of the set to be equipped.
    if set_counts and tp.set_properties:
        group_key = resolve_set_group_key(item, resolver)
        equipped_count = set_counts.get(group_key, 0) if group_key is not None else 0
        for idx, set_prop_list in enumerate(tp.set_properties):
            if set_prop_list is not None and equipped_count >= idx + 2:
                sources.append(set_prop_list.get_parsed_properties(version, data=resolver.data))

    if normalize_source is None:
        return [*source for source in sources]
    return [*normalize_source(source) for source in sources]


def _iter_item_properties(
    items: Sequence[D2Item],
    resolver: GameDataResolver,
    version: int,
    *,
    set_items: Sequence[D2Item] | None = None,
) -> Iterator[tuple[int, int, list[int]]]:
    """Yield (prop_id, val, params) across items, counting set bonuses from set_items."""
    set_counts = compute_set_counts(items if set_items is None else set_items, resolver)

    for item in items:
        yield from collect_item_properties(
            item, resolver=resolver, version=version, set_counts=set_counts
        )

    for set_name, count in set_counts.items():
        if count >= 2:
            yield from resolver.get_active_set_bonuses(set_name, count)


def _iter_item_stats(
    items: Sequence[D2Item],
    resolver: GameDataResolver,
    version: int,
    *,
    set_items: Sequence[D2Item] | None = None,
) -> Iterator[tuple[int, int]]:
    """Yield (prop_id, param_val) across items, counting set bonuses from set_items."""
    for prop_id, val, params in _iter_item_properties(
        items, resolver=resolver, version=version, set_items=set_items
    ):
        yield prop_id, params[0] if params else val


@dataclass
class _AdvancedStatAcc:
    res: ResistanceStats = field(default_factory=ResistanceStats)
    max_res: ResistanceStats = field(default_factory=_default_max_resistances)
    fhr: int = 0
    fcr: int = 0
    frw: int = 0
    ias: int = 0
    mf: int = 0
    mf_per_level: int = 0
    all_skills: int = 0
    class_skills: int = 0
    skill_tab_bonuses: Counter[int] = field(default_factory=Counter)
    single_skill_bonuses: Counter[int] = field(default_factory=Counter)
    oskill_bonuses: Counter[int] = field(default_factory=Counter)
    fire_skills: int = 0


_SIMPLE_ACC_FIELDS: frozendict[int, str] = frozendict(
    {
        93: "ias",
        96: "frw",
        99: "fhr",
        105: "fcr",
        80: "mf",
        240: "mf_per_level",
        127: "all_skills",
    }
)


def _apply_advanced_prop(
    acc: _AdvancedStatAcc,
    prop_id: int,
    param_val: int,
    params: list[int],
    char_class: int,
) -> None:
    if _apply_resist_stat(acc.res, acc.max_res, prop_id, param_val):
        return
    if attr := _SIMPLE_ACC_FIELDS.get(prop_id):
        setattr(acc, attr, getattr(acc, attr) + param_val)
        return
    if prop_id == 83 and len(params) >= 2 and params[0] == char_class:
        acc.class_skills += params[1]
    elif prop_id == 188 and len(params) >= 3 and params[1] == char_class:
        acc.skill_tab_bonuses[params[0]] += params[2]
    elif prop_id == 107 and len(params) >= 2 and get_skill_class_id(params[0]) == char_class:
        acc.single_skill_bonuses[params[0]] += params[1]
    elif prop_id == 97 and len(params) >= 2:
        acc.oskill_bonuses[params[0]] += params[1]
    elif prop_id == 126 and len(params) >= 2 and params[0] == 1:
        acc.fire_skills += params[1]


class PaladinPassiveMaxRes(NamedTuple):
    """Passive Paladin max resist bonuses from Resist Fire/Lightning/Cold hard points."""

    fire: int
    lightning: int
    cold: int


def compute_paladin_passive_max_res(char_data: D2SStruct) -> PaladinPassiveMaxRes:
    """Return passive Paladin (+1 max res per 2 hard points) bonuses for (FR, LR, CR).

    Per D2R `skills.txt` (IDs 100, 105, 110: Resist Fire/Cold/Lightning),
    `passivestat1 = max*resist` with `passivecalc1 = skill('<Aura>'.blvl)/2`
    scales strictly with hard base points (`.blvl`); `+skills` do not apply.
    """
    skills = char_data.skills
    if char_data.char_class != CharClass.PALADIN or not skills or skills.magic != 0x6669:
        return PaladinPassiveMaxRes(0, 0, 0)
    levels = skills.skill_levels
    return PaladinPassiveMaxRes(
        fire=levels[4] // 2 if len(levels) > 4 else 0,
        lightning=levels[14] // 2 if len(levels) > 14 else 0,
        cold=levels[9] // 2 if len(levels) > 9 else 0,
    )


def compute_anya_resist_bonus(char_data: D2SStruct) -> int:
    """Return total Anya 'Prison of Ice' (+10 all resistances per completed difficulty) bonus."""
    if not (char_data.quests and char_data.quests.magic == 0x216F6F57):
        return 0
    bonus = 0
    for qd in char_data.quests.qi_data:
        if len(qd.act_5) > 2 and (qd.act_5[2] & 1):
            bonus += 10
    return bonus


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

    cats = char_data.item_list.categorize()
    equipped_items: list[D2Item] = [
        it for pos, it in cats.equipped.items() if pos not in inactive_weapon_slots
    ]
    # In Diablo II, only charms in inventory provide active bonuses
    inventory_items: list[D2Item] = [
        it
        for it in cats.inventory
        if it.stored_in == StoredIn.INVENTORY
        and it.code_str.strip().lower() in ("cm1", "cm2", "cm3", "cs2")
    ]

    acc = _AdvancedStatAcc()
    char_class = char_data.char_class
    char_level = char_data.char_level
    if not char_level and char_data.player_stats.is_valid:
        char_level = char_data.player_stats.level

    all_source_items: list[D2Item] = equipped_items + inventory_items
    for prop_id, val, params in _iter_item_properties(
        all_source_items, char_resolver, version, set_items=equipped_items
    ):
        _apply_advanced_prop(acc, prop_id, params[0] if params else val, params, char_class)

    acc.mf += (acc.mf_per_level * char_level) // 8
    pal_max = compute_paladin_passive_max_res(char_data)
    acc.max_res.fire += pal_max.fire
    acc.max_res.lightning += pal_max.lightning
    acc.max_res.cold += pal_max.cold
    anya_bonus = compute_anya_resist_bonus(char_data)
    if anya_bonus:
        acc.res.fire += anya_bonus
        acc.res.cold += anya_bonus
        acc.res.lightning += anya_bonus
        acc.res.poison += anya_bonus

    return AdvancedStats(
        resistances=acc.res,
        max_resistances=_clamp_max_resistances(acc.max_res),
        fhr=acc.fhr,
        fcr=acc.fcr,
        frw=acc.frw,
        ias=acc.ias,
        mf=acc.mf,
        all_skills=acc.all_skills,
        class_skills=acc.class_skills,
        skill_tab_bonuses=dict(acc.skill_tab_bonuses),
        single_skill_bonuses=dict(acc.single_skill_bonuses),
        oskill_bonuses=dict(acc.oskill_bonuses),
        fire_skills=acc.fire_skills,
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

    merc_item_list = char_data.mercenary.items
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


_DAMAGE_VARIANT_GROUPS: tuple[tuple[int, int, int], ...] = (
    (21, 23, 159),  # 1H / 2H / Throw minimum damage
    (22, 24, 160),  # 1H / 2H / Throw maximum damage
)
_DAMAGE_STAT_IDS: frozenset[int] = frozenset({21, 22, 23, 24, 159, 160})

_ELEMENTAL_STAT_GROUPS: tuple[tuple[int, int, int | None, bool], ...] = (
    (48, 49, None, False),  # Fire
    (50, 51, None, False),  # Lightning
    (52, 53, None, False),  # Magic
    (54, 55, 56, False),  # Cold
    (57, 58, 59, True),  # Poison (min/frame, max/frame, length frames)
)
_GROUPED_DAMAGE_STAT_IDS: frozenset[int] = frozenset(
    {48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 17, 18}
)


class GroupedElementalDamage(NamedTuple):
    """Resolved numeric min/max/(poison duration) values for a paired elemental stat group."""

    min_id: int
    d_min: int
    d_max: int
    seconds: int | None
    present_ids: tuple[int, ...]


class GroupedDamageValues(NamedTuple):
    """Numeric elemental damage ranges and equal min/max enhanced damage extracted from stats."""

    elemental: list[GroupedElementalDamage]
    equal_enhanced_damage: int | None
    ed_present_ids: tuple[int, ...]


class AggregatedSummaryProps(NamedTuple):
    """Aggregated item summary stats with collapsed 1H/2H/Throw damage and all-resistance floor."""

    ordered_keys: list[SummaryPropKey]
    aggregated: dict[SummaryPropKey, list[int]]
    prop_id_map: dict[SummaryPropKey, int]
    raw_val_map: dict[SummaryPropKey, int]
    dmg_pair_map: dict[SummaryPropKey, tuple[SummaryPropKey, int, int]]
    min_all_res: int
    res_keys: tuple[tuple[int], ...]


def calculate_effective_defence(
    base_defence: int,
    parsed_props: Sequence[tuple[int, int, list[int]]],
    *,
    char_level: int | None = None,
    resolver: GameDataResolver | None = None,
) -> int:
    """Compute effective defense from base defense, %ED (16, 215), and +Def (31, 214)."""
    ed_pct = 0
    flat_def = 0
    for prop_id, value, params in parsed_props:
        val = params[0] if params else value
        if prop_id == 16:
            ed_pct += val
        elif prop_id == 31:
            flat_def += val
        elif prop_id in (214, 215) and char_level is not None and char_level > 0:
            stat = resolver.data.get_stat(prop_id) if resolver is not None else None
            scaled = (
                adjust_property_values(prop_id, [val], stat, char_level=char_level)
                if stat is not None
                else (val * char_level) >> 3
            )
            if isinstance(scaled, int):
                if prop_id == 214:
                    flat_def += scaled
                else:
                    ed_pct += scaled
    return (base_defence * max(0, 100 + ed_pct) // 100) + flat_def


def convert_poison_damage(d_min: int, d_max: int, frames: int) -> tuple[int, int, int] | None:
    """Convert per-frame poison damage to (total_min, total_max, duration_seconds)."""
    if frames <= 0:
        return None
    p_min = (d_min * frames + 128) >> 8 if d_min > 0 else 0
    p_max = (d_max * frames + 128) >> 8 if d_max > 0 else 0
    seconds = frames // 25
    if p_max <= 0 or seconds <= 0:
        return None
    return p_min, p_max, seconds


def _resolve_damage_group(
    p_val: int | None,
    s_val: int | None,
    t_val: int | None,
) -> tuple[int | None, int | None]:
    """Collapse 1H/2H/Throw damage variants into canonical primary + optional throw values."""
    non_throw = [v for v in (p_val, s_val) if v is not None]
    if not non_throw:
        return None, t_val
    canonical = max(non_throw)
    kept_throw = None if (t_val is not None and t_val in non_throw) else t_val
    return canonical, kept_throw


def normalize_damage_props(
    parsed_props: list[tuple[int, int, list[int]]],
) -> list[tuple[int, int, list[int]]]:
    """Canonicalize flat damage stats within one property source before cross-source summing."""
    if not any(prop_id in _DAMAGE_STAT_IDS for prop_id, _, _ in parsed_props):
        return parsed_props

    totals: dict[int, int] = {}
    for prop_id, value, params in parsed_props:
        if prop_id in _DAMAGE_STAT_IDS:
            val = params[0] if params else value
            totals[prop_id] = totals.get(prop_id, 0) + val

    resolved: dict[int, int] = {}
    for primary_id, secondary_id, throw_id in _DAMAGE_VARIANT_GROUPS:
        canon, throw_val = _resolve_damage_group(
            totals.get(primary_id),
            totals.get(secondary_id),
            totals.get(throw_id),
        )
        if canon is not None:
            resolved[primary_id] = canon
        if throw_val is not None:
            resolved[throw_id] = throw_val

    emitted_ids: set[int] = set()
    normalized: list[tuple[int, int, list[int]]] = []
    for prop_id, value, params in parsed_props:
        if prop_id not in _DAMAGE_STAT_IDS:
            normalized.append((prop_id, value, params))
            continue
        group_idx = 0 if prop_id in (21, 23, 159) else 1
        primary_id, _, throw_id = _DAMAGE_VARIANT_GROUPS[group_idx]
        target_id = throw_id if prop_id == throw_id else primary_id
        if target_id not in emitted_ids and target_id in resolved:
            emitted_ids.add(target_id)
            val = resolved[target_id]
            normalized.append((target_id, val, [val]))
    return normalized


def collapse_damage_stats(
    aggregated: dict[SummaryPropKey, list[int]],
    ordered_keys: list[SummaryPropKey],
    prop_id_map: dict[SummaryPropKey, int],
    raw_val_map: dict[SummaryPropKey, int],
) -> dict[SummaryPropKey, tuple[SummaryPropKey, int, int]]:
    """Canonicalize 1H/2H/Throw damage variants in-place and return combinable min+max pairs."""
    for primary_id, secondary_id, throw_id in _DAMAGE_VARIANT_GROUPS:
        p_key = (primary_id,)
        s_key = (secondary_id,)
        t_key = (throw_id,)
        canon, throw_val = _resolve_damage_group(
            aggregated[p_key][0] if p_key in aggregated else None,
            aggregated[s_key][0] if s_key in aggregated else None,
            aggregated[t_key][0] if t_key in aggregated else None,
        )
        if s_key in aggregated:
            if p_key not in aggregated and p_key not in prop_id_map:
                idx = ordered_keys.index(s_key)
                ordered_keys[idx] = p_key
                prop_id_map[p_key] = primary_id
                if s_key in raw_val_map:
                    raw_val_map[p_key] = raw_val_map[s_key]
            del aggregated[s_key]
        if canon is not None:
            aggregated[p_key] = [canon]
        if t_key in aggregated and throw_val is None:
            del aggregated[t_key]

    pair_map: dict[SummaryPropKey, tuple[SummaryPropKey, int, int]] = {}
    min_key, max_key = (21,), (22,)
    if min_key in aggregated and max_key in aggregated:
        d_min = aggregated[min_key][0]
        d_max = aggregated[max_key][0]
        if 0 < d_min < d_max:
            pair_map[min_key] = (max_key, d_min, d_max)
            pair_map[max_key] = (min_key, d_min, d_max)
    return pair_map


def _collect_grouped_totals(
    parsed_props: list[tuple[int, int, list[int]]],
) -> tuple[dict[int, int], dict[int, list[int]], int]:
    totals: dict[int, int] = {}
    first_params: dict[int, list[int]] = {}
    poison_len_count = 0
    for prop_id, value, params in parsed_props:
        if prop_id not in _GROUPED_DAMAGE_STAT_IDS:
            continue
        val = params[0] if params else value
        totals[prop_id] = totals.get(prop_id, 0) + val
        if prop_id not in first_params and params:
            first_params[prop_id] = params
        if prop_id == 59 and val > 0:
            poison_len_count += 1
    return totals, first_params, poison_len_count


def _resolve_elemental_group(
    group: tuple[int, int, int | None, bool],
    totals: dict[int, int],
    first_params: dict[int, list[int]],
    poison_len_count: int,
) -> GroupedElementalDamage | None:
    min_id, max_id, len_id, is_poison = group
    if min_id not in totals:
        return None

    if max_id in totals:
        d_min = totals[min_id]
        d_max = totals[max_id]
        raw_frames = totals.get(len_id, 0) if len_id is not None else 0
        frames = (
            raw_frames // poison_len_count if is_poison and poison_len_count > 1 else raw_frames
        )
    else:
        # Handle legacy (<=0x60) multi-field single tuple [min, max, (frames)].
        p = first_params.get(min_id, [])
        if len(p) < 2:
            return None
        d_min, d_max = p[0], p[1]
        frames = p[2] if len(p) >= 3 else 0
        if (is_poison and frames == 0) or (not is_poison and d_max == 0):
            return None

    seconds: int | None = None
    if is_poison:
        converted = convert_poison_damage(d_min, d_max, frames)
        if converted is None:
            return None
        d_min, d_max, seconds = converted
    elif d_max <= 0:
        return None

    if d_min != d_max and not (0 < d_min < d_max):
        return None

    present = tuple(sid for sid in (min_id, max_id, len_id) if sid is not None and sid in totals)
    return GroupedElementalDamage(min_id, d_min, d_max, seconds, present)


def _resolve_equal_ed(
    totals: dict[int, int], first_params: dict[int, list[int]]
) -> tuple[int | None, tuple[int, ...]]:
    if 17 in totals and 18 in totals:
        if totals[17] == totals[18]:
            return totals[17], (17, 18)
        return None, ()
    if 17 in totals:
        p = first_params.get(17, [])
        if len(p) >= 2 and p[0] == p[1] and p[0] != 0:
            return p[0], (17,)
    return None, ()


def extract_grouped_damage_values(
    parsed_props: list[tuple[int, int, list[int]]],
) -> GroupedDamageValues:
    """Sum grouped elemental and enhanced-damage stats and resolve numeric display ranges."""
    totals, first_params, poison_len_count = _collect_grouped_totals(parsed_props)
    if not totals:
        return GroupedDamageValues([], None, ())

    elemental = [
        resolved
        for group in _ELEMENTAL_STAT_GROUPS
        if (resolved := _resolve_elemental_group(group, totals, first_params, poison_len_count))
        is not None
    ]
    equal_ed, ed_present = _resolve_equal_ed(totals, first_params)
    return GroupedDamageValues(elemental, equal_ed, ed_present)


def aggregate_summary_properties(
    parsed_props: list[tuple[int, int, list[int]]],
    resolver: GameDataResolver,
) -> AggregatedSummaryProps:
    """Stack identical summary stats, collapse 1H/2H/Throw damage, and compute min resistance."""
    ordered_keys: list[SummaryPropKey] = []
    aggregated: dict[SummaryPropKey, list[int]] = {}
    prop_id_map: dict[SummaryPropKey, int] = {}
    raw_val_map: dict[SummaryPropKey, int] = {}

    for idx, (prop_id, value, params) in enumerate(parsed_props):
        p_list = list(params) if params else [value]
        stat = resolver.data.get_stat(prop_id)
        if stat is None:
            key = (prop_id, idx)
            ordered_keys.append(key)
            aggregated[key] = p_list
            prop_id_map[key] = prop_id
            raw_val_map[key] = value
        elif prop_id in (83, 97, 107):
            key = (prop_id, p_list[0])
            if key not in aggregated:
                ordered_keys.append(key)
                aggregated[key] = p_list
                prop_id_map[key] = prop_id
                raw_val_map[key] = value
            else:
                aggregated[key][1] += p_list[1]
        elif prop_id == 188:
            key = (prop_id, p_list[0], p_list[1])
            if key not in aggregated:
                ordered_keys.append(key)
                aggregated[key] = p_list
                prop_id_map[key] = prop_id
                raw_val_map[key] = value
            else:
                aggregated[key][2] += p_list[2]
        elif prop_id in (179, 180):
            key = (prop_id, p_list[0])
            if key not in aggregated:
                ordered_keys.append(key)
                aggregated[key] = p_list
                prop_id_map[key] = prop_id
                raw_val_map[key] = value
            else:
                aggregated[key][1] += p_list[1]
        elif prop_id in (98, 151, 155, 195, 196, 197, 198, 199, 201, 204):
            key = (prop_id, idx)
            ordered_keys.append(key)
            aggregated[key] = p_list
            prop_id_map[key] = prop_id
            raw_val_map[key] = value
        else:
            val = p_list[0]
            key = (prop_id,)
            if key not in aggregated:
                ordered_keys.append(key)
                aggregated[key] = [val]
                prop_id_map[key] = prop_id
                raw_val_map[key] = value
            else:
                aggregated[key][0] += val

    dmg_pair_map = collapse_damage_stats(aggregated, ordered_keys, prop_id_map, raw_val_map)

    res_keys = ((39,), (41,), (43,), (45,))
    min_all_res = 0
    if all(k in aggregated for k in res_keys):
        res_vals = [aggregated[k][0] for k in res_keys]
        if all(v > 0 for v in res_vals):
            min_all_res = min(res_vals)

    return AggregatedSummaryProps(
        ordered_keys=ordered_keys,
        aggregated=aggregated,
        prop_id_map=prop_id_map,
        raw_val_map=raw_val_map,
        dmg_pair_map=dmg_pair_map,
        min_all_res=min_all_res,
        res_keys=res_keys,
    )
