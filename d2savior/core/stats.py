"""Advanced stats calculation for Diablo II characters.

Calculates aggregated stats from active equipped gear and inventory:
- Total resistances (Fire, Lightning, Cold, Poison)
- Faster Hit Recovery (FHR)
- Faster Cast Rate (FCR)
- Damage (Physical base + bonuses, plus elemental/magic/poison damages)
"""

from dataclasses import dataclass, field
from typing import Any

from d2savior.core.d2data import GameDataResolver
from d2savior.core.d2s_struct import D2SStruct
from d2savior.core.enums import EquipSlot, ItemLocation, StoredIn


@dataclass
class ElementalDamage:
    min_damage: int = 0
    max_damage: int = 0
    duration: int = 0  # duration in frames or seconds if applicable


@dataclass
class DamageStats:
    physical_min: int = 0
    physical_max: int = 0
    fire: ElementalDamage = field(default_factory=ElementalDamage)
    lightning: ElementalDamage = field(default_factory=ElementalDamage)
    cold: ElementalDamage = field(default_factory=ElementalDamage)
    poison: ElementalDamage = field(default_factory=ElementalDamage)
    magic: ElementalDamage = field(default_factory=ElementalDamage)

    def has_elemental(self) -> bool:
        return any(
            elem.max_damage > 0
            for elem in (self.fire, self.lightning, self.cold, self.poison, self.magic)
        )

    def format_summary(self) -> str:
        parts: list[str] = []
        if self.physical_max > 0:
            if self.physical_min == self.physical_max:
                parts.append(f"Physical: {self.physical_min}")
            else:
                parts.append(f"Physical: {self.physical_min}-{self.physical_max}")

        if self.fire.max_damage > 0:
            if self.fire.min_damage == self.fire.max_damage:
                parts.append(f"Fire: {self.fire.min_damage}")
            else:
                parts.append(f"Fire: {self.fire.min_damage}-{self.fire.max_damage}")

        if self.lightning.max_damage > 0:
            if self.lightning.min_damage == self.lightning.max_damage:
                parts.append(f"Lightning: {self.lightning.min_damage}")
            else:
                parts.append(f"Lightning: {self.lightning.min_damage}-{self.lightning.max_damage}")

        if self.cold.max_damage > 0:
            if self.cold.min_damage == self.cold.max_damage:
                parts.append(f"Cold: {self.cold.min_damage}")
            else:
                parts.append(f"Cold: {self.cold.min_damage}-{self.cold.max_damage}")

        if self.poison.max_damage > 0:
            if self.poison.min_damage == self.poison.max_damage:
                parts.append(f"Poison: {self.poison.min_damage}")
            else:
                parts.append(f"Poison: {self.poison.min_damage}-{self.poison.max_damage}")

        if self.magic.max_damage > 0:
            if self.magic.min_damage == self.magic.max_damage:
                parts.append(f"Magic: {self.magic.min_damage}")
            else:
                parts.append(f"Magic: {self.magic.min_damage}-{self.magic.max_damage}")

        return ", ".join(parts) if parts else "0"


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
    damage: DamageStats = field(default_factory=DamageStats)


def _get_item_properties(
    item: Any, resolver: GameDataResolver, version: int
) -> list[tuple[int, int, list[int]]]:
    """Retrieve all parsed properties for an item, including runewords and socketables."""
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
    return props


def calculate_advanced_stats(
    char_data: D2SStruct, resolver: GameDataResolver | None = None
) -> AdvancedStats:
    """Calculate advanced stats (resistances, FHR, FCR, damage) from active gear and inventory."""
    if resolver is None:
        resolver = GameDataResolver.load()

    version = char_data.version if char_data.version else 0x63
    char_resolver = resolver.for_version(version)

    active_weapon_slot = EquipSlot.WEAPON_I if char_data.weapon_set == 0 else EquipSlot.WEAPON_II
    inactive_weapon_slots = (
        (EquipSlot.WEAPON_II, EquipSlot.SHIELD_II)
        if char_data.weapon_set == 0
        else (EquipSlot.WEAPON_I, EquipSlot.SHIELD_I)
    )

    equipped_items: list[Any] = []
    inventory_items: list[Any] = []
    active_weapon: Any | None = None

    item_list = getattr(char_data, "item_list", None)
    if item_list and getattr(item_list, "magic", None) == 0x4D4A:
        for it in getattr(item_list, "items", []):
            loc = ItemLocation(it.location)
            if loc == ItemLocation.EQUIPPED:
                if it.position in inactive_weapon_slots:
                    continue
                equipped_items.append(it)
                if it.position == active_weapon_slot:
                    active_weapon = it
            elif loc == ItemLocation.STORED and it.stored_in == StoredIn.INVENTORY:
                tname = (
                    it.type_name.decode("ascii", errors="replace").strip().lower()
                    if it.type_name
                    else ""
                )
                # In Diablo II, only charms in inventory provide active bonuses
                if tname in ("cm1", "cm2", "cm3"):
                    inventory_items.append(it)

    all_props: list[tuple[int, int, list[int]]] = []
    for it in equipped_items:
        all_props.extend(_get_item_properties(it, resolver=char_resolver, version=version))
    for it in inventory_items:
        all_props.extend(_get_item_properties(it, resolver=char_resolver, version=version))

    res = ResistanceStats()
    fhr = 0
    fcr = 0

    flat_min_dam = 0
    flat_max_dam = 0
    enhanced_min_dam_pct = 0
    enhanced_max_dam_pct = 0

    fire_min = 0
    fire_max = 0
    ltng_min = 0
    ltng_max = 0
    cold_min = 0
    cold_max = 0
    cold_len = 0
    pois_min = 0
    pois_max = 0
    pois_len = 0
    mag_min = 0
    mag_max = 0

    for prop_id, val, params in all_props:
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

            # Physical Damage modifiers
            case 17:  # Enhanced Max Damage %
                enhanced_max_dam_pct += param_val
            case 18:  # Enhanced Min Damage %
                enhanced_min_dam_pct += param_val
            case 21 | 23:  # Min Damage / Secondary Min Damage
                flat_min_dam += param_val
            case 22 | 24:  # Max Damage / Secondary Max Damage
                flat_max_dam += param_val
            case 25:  # Damage % (Enhanced Damage overall)
                enhanced_min_dam_pct += param_val
                enhanced_max_dam_pct += param_val

            # Elemental damages
            case 48:  # Fire min dam
                fire_min += param_val
            case 49:  # Fire max dam
                fire_max += param_val
            case 50:  # Lightning min dam
                ltng_min += param_val
            case 51:  # Lightning max dam
                ltng_max += param_val
            case 52:  # Magic min dam
                mag_min += param_val
            case 53:  # Magic max dam
                mag_max += param_val
            case 54:  # Cold min dam
                cold_min += param_val
            case 55:  # Cold max dam
                cold_max += param_val
            case 56:  # Cold length
                cold_len += param_val
            case 57:  # Poison min dam
                pois_min += param_val
            case 58:  # Poison max dam
                pois_max += param_val
            case 59:  # Poison length
                pois_len += param_val

    # Calculate active weapon physical damage
    base_weapon_min = 0
    base_weapon_max = 0
    if active_weapon is not None:
        tname = (
            active_weapon.type_name.decode("ascii", errors="replace").strip().lower()
            if active_weapon.type_name
            else ""
        )
        item_data = char_resolver.data.items.get(tname)
        if item_data:
            base_weapon_min = getattr(item_data, "mindam", 0) or 0
            base_weapon_max = getattr(item_data, "maxdam", 0) or 0

    total_phys_min = base_weapon_min + flat_min_dam
    if enhanced_min_dam_pct > 0:
        total_phys_min = int(total_phys_min * (1.0 + enhanced_min_dam_pct / 100.0))

    total_phys_max = base_weapon_max + flat_max_dam
    if enhanced_max_dam_pct > 0:
        total_phys_max = int(total_phys_max * (1.0 + enhanced_max_dam_pct / 100.0))

    # In Diablo II, if total min damage exceeds max damage, max damage becomes min damage + 1
    if total_phys_max < total_phys_min:
        total_phys_max = total_phys_min

    damage_stats = DamageStats(
        physical_min=total_phys_min,
        physical_max=total_phys_max,
        fire=ElementalDamage(fire_min, fire_max),
        lightning=ElementalDamage(ltng_min, ltng_max),
        cold=ElementalDamage(cold_min, cold_max, cold_len),
        poison=ElementalDamage(pois_min, pois_max, pois_len),
        magic=ElementalDamage(mag_min, mag_max),
    )

    return AdvancedStats(
        resistances=res,
        fhr=fhr,
        fcr=fcr,
        damage=damage_stats,
    )
