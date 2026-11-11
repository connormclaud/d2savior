"""Advanced stats calculation for Diablo II characters.

Calculates aggregated stats from active equipped gear and inventory charms:
- Gear resistances (Fire, Lightning, Cold, Poison)
- Faster Hit Recovery (FHR)
- Faster Cast Rate (FCR)
- Supports active partial and full set bonuses from equipped set items
"""

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from d2savior.core.d2data import GameDataResolver
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


def calculate_advanced_stats(
    char_data: D2SStruct, resolver: GameDataResolver | None = None
) -> AdvancedStats:
    """Calculate advanced stats (resistances, FHR, FCR) from active gear and inventory charms."""
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

    # Count equipped set items by set_id to activate partial/full set bonuses
    set_counts: Counter[int] = Counter()
    for it in equipped_items:
        ext = getattr(getattr(it, "item_info", None), "ext_info", None)
        if ext and ext.set_id is not None:
            set_counts[ext.set_id] += 1

    res = ResistanceStats()
    fhr = 0
    fcr = 0

    all_source_items: list[Any] = equipped_items + inventory_items

    for item in all_source_items:
        props = _get_item_properties(
            item, resolver=char_resolver, version=version, set_counts=set_counts
        )
        for prop_id, val, params in props:
            param_val = params[0] if params else val
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

                # FHR / FCR
                case 99:  # Faster Hit Recovery
                    fhr += param_val
                case 105:  # Faster Cast Rate
                    fcr += param_val

    return AdvancedStats(
        resistances=res,
        fhr=fhr,
        fcr=fcr,
    )
