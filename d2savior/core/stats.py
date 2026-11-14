"""Advanced stats calculation for Diablo II characters.

Calculates aggregated stats from active equipped gear, inventory charms, and quest rewards:
- Resistances (Fire, Lightning, Cold, Poison)
- Faster Hit Recovery (FHR)
- Faster Cast Rate (FCR)
- Magic Find (MF)
- Supports active partial and full set bonuses from equipped set items
"""

from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from d2savior.core.d2data import GameDataResolver, HirelingInfo
from d2savior.core.d2s_struct import D2SStruct
from d2savior.core.enums import EquipSlot, ItemLocation, StoredIn


@dataclass
class ResistanceStats:
    fire: int = 0
    cold: int = 0
    lightning: int = 0
    poison: int = 0

    def format_summary(self) -> str:
        return (
            f"Fire: {self.fire:+d}%, Cold: {self.cold:+d}%, "
            f"Lightning: {self.lightning:+d}%, Poison: {self.poison:+d}%"
        )


@dataclass
class AdvancedStats:
    resistances: ResistanceStats = field(default_factory=ResistanceStats)
    fhr: int = 0
    fcr: int = 0
    mf: int = 0


@dataclass
class MercenaryStats:
    """Calculated mercenary level, attributes, and resistances from save data and gear."""

    level: int = 1
    strength: int = 0
    dexterity: int = 0
    resistances: ResistanceStats = field(default_factory=ResistanceStats)


def _get_item_properties(
    item: Any,
    resolver: GameDataResolver,
    version: int,
    set_counts: dict[int, int] | None = None,
) -> list[tuple[int, int, list[int]]]:
    """Retrieve all parsed properties for an item, including runewords, socketables, and active set bonuses."""
    props: list[tuple[int, int, list[int]]] = []
    tp = getattr(getattr(item, "item_info", None), "type_specific_info", None)
    if tp:
        if getattr(tp, "property_list", None):
            props.extend(tp.property_list.get_parsed_properties(version, data=resolver.data))
        if getattr(tp, "runeword_property_list", None):
            props.extend(
                tp.runeword_property_list.get_parsed_properties(version, data=resolver.data)
            )
        if getattr(item, "gem_items", None):
            for gem in item.gem_items:
                props.extend(resolver.get_socket_properties(item, gem))

        # Check for activated set item properties:
        # Each index i in set_properties requires (i + 2) pieces of the set to be equipped.
        if set_counts and getattr(tp, "set_properties", None):
            ext = getattr(getattr(item, "item_info", None), "ext_info", None)
            if ext and ext.set_id is not None:
                equipped_count = set_counts.get(ext.set_id, 0)
                for idx, set_prop_list in enumerate(tp.set_properties):
                    if set_prop_list is not None and equipped_count >= idx + 2:
                        props.extend(
                            set_prop_list.get_parsed_properties(version, data=resolver.data)
                        )
    return props


def _iter_item_stats(
    items: list[Any],
    resolver: GameDataResolver,
    version: int,
    *,
    set_items: list[Any] | None = None,
) -> Iterator[tuple[int, int]]:
    """Yield (prop_id, param_val) across items, counting set bonuses from set_items."""
    set_counts: Counter[int] = Counter()
    for it in items if set_items is None else set_items:
        ext = getattr(getattr(it, "item_info", None), "ext_info", None)
        if ext and ext.set_id is not None:
            set_counts[ext.set_id] += 1

    for item in items:
        props = _get_item_properties(
            item, resolver=resolver, version=version, set_counts=set_counts
        )
        for prop_id, val, params in props:
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
    fhr = 0
    fcr = 0
    mf = 0
    mf_per_level = 0

    char_level = getattr(char_data, "char_level", 0)
    if not char_level:
        p_stats = getattr(char_data, "player_stats", None)
        if p_stats and getattr(p_stats, "is_valid", False):
            char_level = getattr(p_stats, "level", 0)

    all_source_items: list[Any] = equipped_items + inventory_items

    for prop_id, param_val in _iter_item_stats(
        all_source_items, char_resolver, version, set_items=equipped_items
    ):
        match prop_id:
            # Resistances
            case 39:  # Fire Resist
                res.fire += param_val
            case 41:  # Lightning Resist
                res.lightning += param_val
            case 43:  # Cold Resist
                res.cold += param_val
            case 45:  # Poison Resist
                res.poison += param_val

            # FHR / FCR / MF
            case 99:  # Faster Hit Recovery
                fhr += param_val
            case 105:  # Faster Cast Rate
                fcr += param_val
            case 80:  # Better Chance of Getting Magic Items
                mf += param_val
            case 240:  # Magic Find per level (eighths per level)
                mf_per_level += param_val

    mf += (mf_per_level * char_level) // 8

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
        fhr=fhr,
        fcr=fcr,
        mf=mf,
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
            match prop_id:
                case 0:  # Strength
                    strength += param_val
                case 2:  # Dexterity
                    dexterity += param_val
                case 39:  # Fire Resist
                    res.fire += param_val
                case 41:  # Lightning Resist
                    res.lightning += param_val
                case 43:  # Cold Resist
                    res.cold += param_val
                case 45:  # Poison Resist
                    res.poison += param_val
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
    )
