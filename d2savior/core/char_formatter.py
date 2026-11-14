"""Full, summary, list, and search text formatting for Diablo II character saves."""

import datetime
from typing import Any

from d2savior.core.constants import (
    CLASS_SKILL_BASES,
    DIFFICULTY_NAMES,
    QUEST_REWARDS,
    QUESTS_BY_ACT,
    WAYPOINTS_BY_ACT,
)
from d2savior.core.d2s_struct import CharStatus, D2SStruct
from d2savior.core.enums import EquipSlot, ItemLocation, StoredIn
from d2savior.core.item_formatter import (
    FormattedLines,
    _format_item_lines,
    format_item_summary,
    item_matches_pattern,
)
from d2savior.core.resolver import GameDataResolver
from d2savior.core.stats import (
    AdvancedStats,
    calculate_advanced_stats,
    calculate_mercenary_stats,
    get_current_difficulty,
    get_difficulty_resist_penalty,
)

type SkillInfo = tuple[int, str, int, int]


def get_char_type_name(char_type: int) -> str:
    status = CharStatus(char_type)
    flags = [f.name.capitalize() for f in status]
    return " | ".join(flags) if flags else "Normal"


def get_char_status_summary(char_data: D2SStruct) -> str:
    status_parts = []
    is_lad = (
        char_data.is_ladder()
        if hasattr(char_data, "is_ladder")
        else bool(getattr(char_data, "char_flags", 0) & 0x40)
    )
    if is_lad:
        status_parts.append("Ladder")

    is_hc = (
        char_data.is_hardcore()
        if hasattr(char_data, "is_hardcore")
        else bool(getattr(char_data, "char_flags", 0) & 0x04)
    )
    status_parts.append("Hardcore" if is_hc else "Softcore")

    is_died = (
        char_data.is_died_before()
        if hasattr(char_data, "is_died_before")
        else bool(getattr(char_data, "char_flags", 0) & 0x08)
    )
    if is_died:
        status_parts.append("Died before")

    return " | ".join(status_parts)


def get_char_title_name(char_title: int, char_class: int) -> str:
    if char_title == 0:
        return "None"
    elif char_title >= 0xF:
        if char_class in [0, 1]:
            return "Matriarch"
        else:
            return "Patriarch"
    elif char_title >= 0xA:
        return "Champion"
    elif char_title >= 5:
        return "Slayer"
    else:
        return f"Unknown({char_title})"


def format_timestamp(ts: int) -> str:
    if not ts or ts == 0xFFFFFFFF or ts < 0:
        return "N/A"
    try:
        dt = datetime.datetime.fromtimestamp(ts, tz=datetime.UTC)
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except OSError, OverflowError, ValueError:
        return f"Unknown({ts})"


def format_duration(seconds: int) -> str:
    if seconds == 0xFFFFFFFF or seconds < 0:
        return "N/A"
    if seconds == 0:
        return "0s"
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if secs > 0 or not parts:
        parts.append(f"{secs}s")
    return " ".join(parts)


def _format_waypoints_lines(char_data: D2SStruct, resolver: GameDataResolver) -> FormattedLines:
    loc = resolver.loc
    result = []
    result.append("=== Waypoints ===")
    if char_data.waypoints.magic == 0x5357:
        for diff_idx, diff_name in enumerate(DIFFICULTY_NAMES):
            if diff_idx >= len(char_data.waypoints.wp):
                break
            wp_data = char_data.waypoints.wp[diff_idx]
            global_idx = 0
            total_unlocked = 0
            act_stats = []
            for act_name, wp_names in WAYPOINTS_BY_ACT:
                unlocked_in_act = 0
                missing = []
                for name in wp_names:
                    b = wp_data.waypoints[global_idx // 8]
                    if b & (1 << (global_idx % 8)):
                        total_unlocked += 1
                        unlocked_in_act += 1
                    else:
                        loc_wp = loc.get_level_name(name) if loc else name
                        missing.append(loc_wp)
                    global_idx += 1
                act_stats.append((act_name, len(wp_names), unlocked_in_act, missing))

            # Check if this difficulty has been started (has waypoints beyond starter town or has quest activity)
            has_wp_progress = (wp_data.waypoints[0] & ~1) != 0 or any(
                b != 0 for b in wp_data.waypoints[1:]
            )
            has_quest_progress = False
            if (
                char_data.quests
                and char_data.quests.magic == 0x216F6F57
                and diff_idx < len(char_data.quests.qi_data)
            ):
                qd = char_data.quests.qi_data[diff_idx]
                has_quest_progress = any(
                    w != 0
                    for words in [qd.act_1, qd.act_2, qd.act_3, qd.act_4, qd.act_5]
                    for w in words
                )

            if not has_wp_progress and not has_quest_progress:
                result.append(f"{diff_name}: Not started")
                continue

            total_missing = 39 - total_unlocked
            if total_unlocked == 39:
                result.append(f"{diff_name} (39/39 unlocked): All unlocked")
            else:
                result.append(
                    f"{diff_name} ({total_unlocked}/39 unlocked, {total_missing} missing):"
                )
                for act_name, total_act, unlocked_act, missing in act_stats:
                    if unlocked_act == total_act:
                        result.append(f"  {act_name} ({total_act}/{total_act}): All unlocked")
                    elif unlocked_act == 0:
                        result.append(f"  {act_name} (0/{total_act}): None unlocked")
                    else:
                        result.append(
                            f"  {act_name} ({unlocked_act}/{total_act}): Missing {', '.join(missing)}"
                        )
    return result


def format_waypoints_info(char_data: D2SStruct, resolver: GameDataResolver) -> str:
    return "\n".join(_format_waypoints_lines(char_data, resolver))


def _format_quests_lines(char_data: D2SStruct, resolver: GameDataResolver) -> FormattedLines:
    loc = resolver.loc
    result = []
    result.append("=== Quests ===")
    if char_data.quests and char_data.quests.magic == 0x216F6F57:
        for diff_idx, diff_name in enumerate(DIFFICULTY_NAMES):
            if diff_idx >= len(char_data.quests.qi_data):
                break
            qd = char_data.quests.qi_data[diff_idx]
            act_words = [qd.act_1, qd.act_2, qd.act_3, qd.act_4, qd.act_5]
            has_quest_progress = any(w != 0 for words in act_words for w in words)
            if not has_quest_progress and qd.reset_stats == 0:
                result.append(f"{diff_name}: Not started")
                continue

            reset_status = (
                "Available"
                if qd.reset_stats == 2
                else ("Used" if qd.reset_stats == 1 else "Locked")
            )
            total_completed = sum(1 for words in act_words for w in words if (w & 1) or (w & 2))
            rewards_unclaimed = sum(
                1 for words in act_words for w in words if (w & 2) and not (w & 1)
            )
            reward_str = (
                f", {rewards_unclaimed} reward{'s' if rewards_unclaimed > 1 else ''} unclaimed"
                if rewards_unclaimed
                else ""
            )

            result.append(
                f"{diff_name} ({total_completed}/27 completed{reward_str}) — Akara Reset: {reset_status}"
            )
            for (act_name, quest_defs), words in zip(QUESTS_BY_ACT, act_words, strict=False):
                words_ordered = [words[idx] for _, idx in quest_defs]
                if all(w & 1 for w in words_ordered):
                    result.append(f"  {act_name}: {' '.join('[x]' for _ in quest_defs)}")
                elif all(not (w & 1) and not (w & 2) for w in words_ordered):
                    result.append(f"  {act_name}: {' '.join('[ ]' for _ in quest_defs)}")
                else:
                    parts = []
                    for (name, _idx), w in zip(quest_defs, words_ordered, strict=False):
                        loc_qname = loc.get_quest_name(name) if loc else name
                        if w & 1:
                            parts.append("[x]")
                        elif w & 2:
                            reward = QUEST_REWARDS.get(name, "reward")
                            parts.append(f"[!] {loc_qname} ({reward} unclaimed)")
                        else:
                            parts.append(f"[ ] {loc_qname}")
                    result.append(f"  {act_name}: {' '.join(parts)}")
    return result


def format_quests_info(char_data: D2SStruct, resolver: GameDataResolver) -> str:
    return "\n".join(_format_quests_lines(char_data, resolver))


def _get_character_skills(
    char_data: D2SStruct,
    resolver: GameDataResolver,
    adv_stats: AdvancedStats | None = None,
) -> list[SkillInfo]:
    """Return invested skills as a list of (skill_index, skill_name, base_level, effective_level) tuples."""
    if not getattr(char_data, "skills", None) or char_data.skills.magic != 0x6669:
        return []
    version = char_data.version if char_data.version else 0x63
    skills: list[SkillInfo] = []
    for i, level in enumerate(char_data.skills.skill_levels):
        if level > 0:
            skill_name = ""
            if 0 <= char_data.char_class < len(CLASS_SKILL_BASES):
                skill_id = CLASS_SKILL_BASES[char_data.char_class] + i
                skill_name = resolver.get_skill_name(skill_id)
            bonus = (
                adv_stats.skill_bonus_for(
                    char_data.char_class, i, resolver=resolver, version=version
                )
                if adv_stats is not None
                else 0
            )
            skills.append((i, skill_name, level, level + bonus))
    return skills


def _format_skill_level(base_level: int, effective_level: int) -> str:
    return f"{base_level} ({effective_level})" if effective_level != base_level else str(base_level)


def _format_advanced_stats_lines(
    char_data: D2SStruct,
    char_resolver: GameDataResolver,
    adv_stats: AdvancedStats,
    *,
    diff_name: str,
    resist_penalty: int,
) -> FormattedLines:
    char_class = char_resolver.get_localized_class_name(char_data.char_class)
    skill_parts = [
        f"All Skills: {adv_stats.all_skills:+d}",
        f"{char_class} Skills: {adv_stats.class_skills:+d}",
    ]
    for tab_idx, bonus in sorted(adv_stats.skill_tab_bonuses.items()):
        if bonus:
            tab_name = char_resolver.get_localized_skill_tab_name(tab_idx, char_data.char_class)
            label = tab_name if tab_name else f"Skill Tab {tab_idx}"
            skill_parts.append(f"{label}: {bonus:+d}")
    if adv_stats.fire_skills:
        skill_parts.append(f"Fire Skills: {adv_stats.fire_skills:+d}")

    return [
        "=== Advanced Stats ===",
        f"Resistances ({diff_name}): {adv_stats.resistances.format_summary(resist_penalty, adv_stats.max_resistances)}",
        " | ".join(skill_parts),
        (
            f"Faster Hit Recovery: +{adv_stats.fhr}% | Faster Cast Rate: +{adv_stats.fcr}% | "
            f"Faster Run/Walk: +{adv_stats.frw}% | Increased Attack Speed: +{adv_stats.ias}% | "
            f"Magic Find: +{adv_stats.mf}%"
        ),
    ]


def _format_mercenary_header(
    char_data: D2SStruct, resolver: GameDataResolver, *, summary: bool
) -> str:
    """Format the mercenary header line for summary or full character output."""
    name_id = char_data.merc_name_id
    type_id = char_data.merc_type_id
    details = resolver.get_localized_mercenary_details(type_id)
    merc_name = resolver.get_localized_mercenary_name(type_id, name_id) if details else ""

    if summary:
        dead_suffix = " (Dead)" if char_data.merc_is_dead else ""
        if not details:
            return f"Mercenary: Name Index {name_id}, Type {type_id}{dead_suffix}"
        if merc_name:
            return f"Mercenary: {merc_name} ({details}){dead_suffix}"
        return f"Mercenary: {details}{dead_suffix}"

    if not details:
        return f"Has mercenary (Name: {name_id}, Type: {type_id})"
    if merc_name:
        return f"Has mercenary: {merc_name} ({details}; Name: {name_id}, Type: {type_id})"
    return f"Has mercenary: {details} (Name: {name_id}, Type: {type_id})"


def format_char_info(char_data: D2SStruct, resolver: GameDataResolver) -> str:
    result = []
    result.append("=== Diablo II Character Info ===")
    char_name = char_data.get_char_name()
    result.append(f"Name: {char_name}")
    char_resolver = resolver.for_version(char_data.version)
    result.append(f"Class: {char_resolver.get_localized_class_name(char_data.char_class)}")
    result.append(f"Level: {char_data.char_level}")
    result.append(f"Version: 0x{char_data.version:X}")
    result.append(f"Hardcore: {'Yes' if char_data.is_hardcore() else 'No'}")
    result.append(f"Ladder: {'Yes' if char_data.is_ladder() else 'No'}")
    result.append(f"Expansion: {'Yes' if char_data.is_expansion() else 'No'}")
    result.append(f"Died before: {'Yes' if char_data.is_died_before() else 'No'}")

    char_type_name = get_char_type_name(char_data.char_flags)
    result.append(f"Character Flags: 0x{char_data.char_flags:X} ({char_type_name})")

    char_title = getattr(char_data, "char_title", 0)
    char_title_name = get_char_title_name(char_title, char_data.char_class)
    result.append(f"Character Title: 0x{char_title:X} ({char_title_name})")

    result.append(f"Weapon Set: {'I' if char_data.weapon_set == 0 else 'II'}")

    create_time = getattr(char_data, "create_time", 0)
    last_save_time = getattr(char_data, "last_save_time", 0) or getattr(char_data, "dw_time", 0)
    play_time = getattr(char_data, "play_time", 0)

    result.append(f"Create Time: {format_timestamp(create_time)}")
    result.append(f"Last Save Time: {format_timestamp(last_save_time)}")
    result.append(f"Play Time: {format_duration(play_time)}")

    if char_data.version >= 0x69:
        result.append(f"Game Version: {getattr(char_data, 'game_version', 0)}")
    else:
        result.append(f"NumStats/NumSkills: 0x{getattr(char_data, 'num_stats_num_skills', 0):04X}")
        result.append(f"Merc Dead: {'Yes' if getattr(char_data, 'merc_dead', 0) else 'No'}")
        result.append(
            f"Merc Flags: 0x{getattr(char_data, 'merc_flags_low', 0):04X}{getattr(char_data, 'merc_flags_high', 0):02X}"
        )

    result.append("")
    result.append("=== Player Stats ===")
    stats = char_data.player_stats
    if stats.is_valid:
        result.append(f"Strength: {stats.strength}")
        result.append(f"Energy: {stats.energy}")
        result.append(f"Dexterity: {stats.dexterity}")
        result.append(f"Vitality: {stats.vitality}")
        result.append(f"Stat Points Remaining: {stats.stat_points_remaining}")
        result.append(f"Skill Points Remaining: {stats.skill_points_remaining}")
        result.append(f"Current Life: {stats.current_life}")
        result.append(f"Maximum Life: {stats.max_life}")
        result.append(f"Current Mana: {stats.current_mana}")
        result.append(f"Maximum Mana: {stats.max_mana}")
        result.append(f"Current Stamina: {stats.current_stamina}")
        result.append(f"Maximum Stamina: {stats.max_stamina}")
        result.append(f"Level: {stats.level}")
        result.append(f"Experience: {stats.experience}")
        result.append(f"Gold on Person: {stats.gold}")
        result.append(f"Gold in Stash: {stats.gold_stash}")
    diff_idx = get_current_difficulty(char_data)
    diff_name = DIFFICULTY_NAMES[diff_idx]
    resist_penalty = get_difficulty_resist_penalty(char_data, diff_idx)
    adv_stats = calculate_advanced_stats(char_data, resolver=resolver)

    result.append("")
    result.append("=== Skills ===")
    skills = _get_character_skills(char_data, char_resolver, adv_stats=adv_stats)
    if skills:
        result.append("Skill levels:")
        for i, skill_name, level, effective in skills:
            lvl_str = _format_skill_level(level, effective)
            if skill_name:
                result.append(f"Skill {i} ({skill_name}): {lvl_str}")
            else:
                result.append(f"Skill {i}: {lvl_str}")
    result.append("")
    result.extend(_format_waypoints_lines(char_data, char_resolver))
    result.append("")
    result.extend(_format_quests_lines(char_data, char_resolver))
    result.append("")
    result.extend(
        _format_advanced_stats_lines(
            char_data, char_resolver, adv_stats, diff_name=diff_name, resist_penalty=resist_penalty
        )
    )
    result.append("")
    result.append("=== Items ===")
    item_list = getattr(char_data, "item_list", None)
    if item_list and getattr(item_list, "magic", None) == 0x4D4A:
        items = getattr(item_list, "items", [])
        result.append(f"Total items: {len(items)}")
        for i, item in enumerate(items):
            result.append(f"--- Item {i} ---")
            result.extend(
                _format_item_lines(item, resolver=char_resolver, version=char_data.version)
            )
    result.append("")
    result.append("=== Corpse ===")
    if char_data.corpse.has_corpse():
        result.append("Has corpse")
        if char_data.corpse.corpse_data and char_data.corpse.corpse_data.items:
            result.append(f"Corpse items: {char_data.corpse.corpse_data.items.count}")
    else:
        result.append("No corpse")
    result.append("")
    result.append("=== Mercenary ===")
    if char_data.is_expansion():
        if char_data.has_mercenary():
            result.append(_format_mercenary_header(char_data, char_resolver, summary=False))
            if char_data.version >= 0x69:
                merc_seed = getattr(char_data, "merc_seed", 0)
                merc_flags = getattr(char_data, "merc_flags", 0)
                result.append(f"Mercenary Seed: 0x{merc_seed:08X}")
                result.append(f"Mercenary Exp: {char_data.merc_experience}")
                result.append(f"Mercenary Flags: 0x{merc_flags:08X}")
            else:
                result.append(f"Mercenary Exp: {char_data.merc_experience}")
                result.append(f"Merc Dead: {'Yes' if char_data.merc_is_dead else 'No'}")
            merc_stats = calculate_mercenary_stats(char_data, resolver=char_resolver)
            if merc_stats is not None:
                result.append(f"Mercenary Level: {merc_stats.level}")
                result.append(f"Mercenary Strength: {merc_stats.strength}")
                result.append(f"Mercenary Dexterity: {merc_stats.dexterity}")
                result.append(
                    f"Mercenary Resistances ({diff_name}): {merc_stats.resistances.format_summary(resist_penalty, merc_stats.max_resistances)}"
                )
            if char_data.mercenary.items:
                result.append(f"Mercenary items: {char_data.mercenary.items.count}")
                for i, item in enumerate(char_data.mercenary.items.items):
                    result.append(f"--- Mercenary Item {i} ---")
                    result.extend(
                        _format_item_lines(item, resolver=char_resolver, version=char_data.version)
                    )
        else:
            result.append("No mercenary")
    else:
        result.append("Not expansion character")
    result.append("")
    result.append("=== Golem ===")
    if char_data.is_expansion():
        if char_data.golem.has_golem:
            result.append("Has golem")
        else:
            result.append("No golem")
    else:
        result.append("Not expansion character")
    result.append("")
    result.append("=== Demon ===")
    if char_data.demon.has_demon:
        result.append(f"Has demon (Magic: 0x{char_data.demon.magic:X})")
    else:
        result.append("No demon")
    return "\n".join(result)


def format_char_summary(char_data: D2SStruct, resolver: GameDataResolver) -> str:
    result = []
    result.append("=== Diablo II Character Summary ===")
    char_name = char_data.get_char_name()
    version = char_data.version if char_data.version else 0x63
    char_resolver = resolver.for_version(version)
    char_class = char_resolver.get_localized_class_name(char_data.char_class)
    flags_str = get_char_status_summary(char_data)
    char_title = getattr(char_data, "char_title", 0)
    title_str = get_char_title_name(char_title, char_data.char_class)
    weapon_set = "I" if char_data.weapon_set == 0 else "II"

    result.append(
        f"Name: {char_name} | Class: {char_class} | Level: {char_data.char_level} | Title: {title_str}"
    )
    result.append(f"Status: {flags_str} | Weapon Set: {weapon_set}")

    last_save_time = getattr(char_data, "last_save_time", 0) or getattr(char_data, "dw_time", 0)
    play_time = getattr(char_data, "play_time", 0)
    time_parts = []
    if last_save_time:
        time_parts.append(f"Last Saved: {format_timestamp(last_save_time)}")
    if 0 < play_time < 0xFFFFFFFF:
        time_parts.append(f"Play Time: {format_duration(play_time)}")
    if time_parts:
        result.append(" | ".join(time_parts))

    stats = char_data.player_stats
    if stats.is_valid:
        result.append(
            f"Attributes: Str: {stats.strength}, Dex: {stats.dexterity}, Vit: {stats.vitality}, Ene: {stats.energy}"
        )
        result.append(
            f"Life: {stats.current_life}/{stats.max_life} | Mana: {stats.current_mana}/{stats.max_mana} | Gold: {stats.gold} (Person), {stats.gold_stash} (Stash)"
        )
        if stats.stat_points_remaining > 0 or stats.skill_points_remaining > 0:
            result.append(
                f"Remaining Points: {stats.stat_points_remaining} Stat, {stats.skill_points_remaining} Skill"
            )

    diff_idx = get_current_difficulty(char_data)
    diff_name = DIFFICULTY_NAMES[diff_idx]
    resist_penalty = get_difficulty_resist_penalty(char_data, diff_idx)
    adv_stats = calculate_advanced_stats(char_data, resolver=resolver)

    result.append("")
    result.append("=== Skills ===")
    skills = _get_character_skills(char_data, char_resolver, adv_stats=adv_stats)
    if skills:
        active_skills = [
            f"{skill_name if skill_name else f'Skill {i}'}: {_format_skill_level(level, effective)}"
            for i, skill_name, level, effective in skills
        ]
        result.append(", ".join(active_skills))
    else:
        result.append("None")

    result.append("")
    result.extend(_format_waypoints_lines(char_data, char_resolver))
    result.append("")
    result.extend(_format_quests_lines(char_data, char_resolver))
    result.append("")
    result.extend(
        _format_advanced_stats_lines(
            char_data, char_resolver, adv_stats, diff_name=diff_name, resist_penalty=resist_penalty
        )
    )
    result.append("")

    result.append("=== Equipped Gear ===")
    equipped_items = {}
    inventory_items = []
    stash_items = []
    cube_items = []
    belt_items = []
    cursor_items = []

    item_list = getattr(char_data, "item_list", None)
    if item_list and getattr(item_list, "magic", None) == 0x4D4A:
        items = getattr(item_list, "items", [])
        for item in items:
            loc = ItemLocation(item.location)
            match (loc, item.stored_in):
                case (ItemLocation.EQUIPPED, _):
                    equipped_items[item.position] = item
                case (ItemLocation.BELT, _):
                    belt_items.append(item)
                case (ItemLocation.STORED, StoredIn.INVENTORY):
                    inventory_items.append(item)
                case (ItemLocation.STORED, StoredIn.STASH):
                    stash_items.append(item)
                case (ItemLocation.STORED, StoredIn.CUBE):
                    cube_items.append(item)
                case (ItemLocation.STORED, _):
                    inventory_items.append(item)
                case (ItemLocation.CURSOR, _):
                    cursor_items.append(item)

    has_equipped = False
    for slot in EquipSlot:
        if slot.value in equipped_items:
            has_equipped = True
            it = equipped_items[slot.value]
            result.append(
                f"- {slot.display_name}: {format_item_summary(it, resolver=char_resolver, version=version)}"
            )
    if not has_equipped:
        result.append("None")

    result.append("")
    result.append("=== Mercenary ===")
    if char_data.is_expansion() and char_data.has_mercenary():
        result.append(_format_mercenary_header(char_data, char_resolver, summary=True))
        merc_stats = calculate_mercenary_stats(char_data, resolver=char_resolver)
        if merc_stats is not None:
            result.append(
                f"Level: {merc_stats.level} | Attributes: Str: {merc_stats.strength}, Dex: {merc_stats.dexterity}"
            )
            result.append(
                f"Resistances ({diff_name}): {merc_stats.resistances.format_summary(resist_penalty, merc_stats.max_resistances)}"
            )
        if char_data.mercenary.items and char_data.mercenary.items.items:
            result.append("Equipped:")
            for m_item in char_data.mercenary.items.items:
                loc = ItemLocation(m_item.location)
                slot_str = ""
                if loc == ItemLocation.EQUIPPED and m_item.position in EquipSlot:
                    slot_str = f"{EquipSlot(m_item.position).display_name}: "
                result.append(
                    f"  - {slot_str}{format_item_summary(m_item, resolver=char_resolver, version=version)}"
                )
        else:
            result.append("Equipped: None")
    else:
        result.append("No mercenary")

    result.append("")
    result.append("=== Inventory & Stash ===")
    stored_lines = []
    for it in inventory_items:
        stored_lines.append(
            f"- [Inventory] {format_item_summary(it, resolver=char_resolver, version=version)}"
        )
    for it in stash_items:
        stored_lines.append(
            f"- [Stash] {format_item_summary(it, resolver=char_resolver, version=version)}"
        )
    for it in cube_items:
        stored_lines.append(
            f"- [Cube] {format_item_summary(it, resolver=char_resolver, version=version)}"
        )

    if belt_items:
        belt_counts = {}
        for it in belt_items:
            summary = format_item_summary(it, resolver=char_resolver, version=version)
            belt_counts[summary] = belt_counts.get(summary, 0) + 1
        for summary, count in belt_counts.items():
            stored_lines.append(f"- [Belt] {summary}{f' (x{count})' if count > 1 else ''}")

    for it in cursor_items:
        stored_lines.append(
            f"- [Cursor] {format_item_summary(it, resolver=char_resolver, version=version)}"
        )

    if stored_lines:
        result.extend(stored_lines)
    else:
        result.append("No stored items")

    return "\n".join(result).rstrip()


def format_char_list(records: list[dict[str, Any]]) -> str:
    """Format a list of character records into a column-aligned table."""
    if not records:
        return ""
    headers = ("NAME", "CLASS", "LEVEL", "MODE", "LAST PLAYED")
    col_name = max(len(headers[0]), max((len(r["name"]) for r in records), default=0))
    col_class = max(len(headers[1]), max((len(r["class"]) for r in records), default=0))
    col_level = max(len(headers[2]), max((len(str(r["level"])) for r in records), default=0))
    col_mode = max(len(headers[3]), max((len(r["mode"]) for r in records), default=0))
    col_last_played = max(len(headers[4]), max((len(r["last_played"]) for r in records), default=0))

    header_line = (
        f"{headers[0]:<{col_name}}  "
        f"{headers[1]:<{col_class}}  "
        f"{headers[2]:>{col_level}}  "
        f"{headers[3]:<{col_mode}}  "
        f"{headers[4]:<{col_last_played}}"
    ).rstrip()

    lines = [header_line]
    for r in records:
        line = (
            f"{r['name']:<{col_name}}  "
            f"{r['class']:<{col_class}}  "
            f"{r['level']!s:>{col_level}}  "
            f"{r['mode']:<{col_mode}}  "
            f"{r['last_played']:<{col_last_played}}"
        ).rstrip()
        lines.append(line)
    return "\n".join(lines)


def format_char_find(
    char_data: D2SStruct,
    pattern: str,
    resolver: GameDataResolver,
    summary: bool = True,
) -> str | None:
    """Format matching items found in a character save file."""
    version = char_data.version
    char_resolver = resolver.for_version(version)

    equipped_matches: list[tuple[EquipSlot, Any]] = []
    merc_matches: list[tuple[str, Any]] = []
    corpse_matches: list[Any] = []
    stored_matches: list[tuple[str, Any]] = []

    item_list = getattr(char_data, "item_list", None)
    if item_list and getattr(item_list, "magic", None) == 0x4D4A:
        for it in getattr(item_list, "items", []):
            if not item_matches_pattern(it, pattern, resolver=char_resolver, version=version):
                continue
            loc = ItemLocation(it.location)
            match (loc, it.stored_in):
                case (ItemLocation.EQUIPPED, _):
                    if it.position in EquipSlot:
                        equipped_matches.append((EquipSlot(it.position), it))
                case (ItemLocation.STORED, StoredIn.INVENTORY):
                    stored_matches.append(("[Inventory]", it))
                case (ItemLocation.STORED, StoredIn.STASH):
                    stored_matches.append(("[Stash]", it))
                case (ItemLocation.STORED, StoredIn.CUBE):
                    stored_matches.append(("[Cube]", it))
                case (ItemLocation.STORED, _):
                    stored_matches.append(("[Inventory]", it))
                case (ItemLocation.BELT, _):
                    stored_matches.append(("[Belt]", it))
                case (ItemLocation.CURSOR, _):
                    stored_matches.append(("[Cursor]", it))

    slot_order = {slot: idx for idx, slot in enumerate(EquipSlot)}
    equipped_matches.sort(key=lambda pair: slot_order.get(pair[0], 999))

    if (
        char_data.is_expansion()
        and char_data.has_mercenary()
        and char_data.mercenary.items
        and char_data.mercenary.items.items
    ):
        for m_item in char_data.mercenary.items.items:
            if item_matches_pattern(m_item, pattern, resolver=char_resolver, version=version):
                loc = ItemLocation(m_item.location)
                slot_str = ""
                if loc == ItemLocation.EQUIPPED and m_item.position in EquipSlot:
                    slot_str = f"{EquipSlot(m_item.position).display_name}: "
                merc_matches.append((slot_str, m_item))

    if (
        char_data.corpse.has_corpse()
        and char_data.corpse.corpse_data
        and char_data.corpse.corpse_data.items
    ):
        for c_item in char_data.corpse.corpse_data.items.items:
            if item_matches_pattern(c_item, pattern, resolver=char_resolver, version=version):
                corpse_matches.append(c_item)

    if not equipped_matches and not merc_matches and not corpse_matches and not stored_matches:
        return None

    char_name = char_data.get_char_name().strip() or "Unknown"
    char_class = char_resolver.get_localized_class_name(char_data.char_class)
    char_level = char_data.char_level

    result = []
    header_mode = "Summary" if summary else "Info"
    result.append(
        f"=== Diablo II Character {header_mode}: {char_name} ({char_class}, Level {char_level}) ==="
    )

    if summary:
        if equipped_matches:
            result.append("=== Equipped Gear ===")
            for slot, it in equipped_matches:
                result.append(
                    f"- {slot.display_name}: {format_item_summary(it, resolver=char_resolver, version=version)}"
                )
        if merc_matches:
            result.append("=== Mercenary ===")
            result.append("Equipped:")
            for slot_str, m_it in merc_matches:
                result.append(
                    f"  - {slot_str}{format_item_summary(m_it, resolver=char_resolver, version=version)}"
                )
        if corpse_matches:
            result.append("=== Corpse ===")
            for c_it in corpse_matches:
                result.append(
                    f"- [Corpse] {format_item_summary(c_it, resolver=char_resolver, version=version)}"
                )
        if stored_matches:
            result.append("=== Inventory & Stash ===")
            for label, it in stored_matches:
                result.append(
                    f"- {label} {format_item_summary(it, resolver=char_resolver, version=version)}"
                )
    else:
        if equipped_matches:
            result.append("=== Equipped Gear ===")
            for slot, it in equipped_matches:
                result.append(f"--- Equipped: {slot.display_name} ---")
                result.extend(_format_item_lines(it, resolver=char_resolver, version=version))
        if merc_matches:
            result.append("=== Mercenary ===")
            for slot_str, m_it in merc_matches:
                slot_label = slot_str.rstrip(": ") or "Item"
                result.append(f"--- Mercenary: {slot_label} ---")
                result.extend(_format_item_lines(m_it, resolver=char_resolver, version=version))
        if corpse_matches:
            result.append("=== Corpse ===")
            for c_it in corpse_matches:
                result.append("--- Corpse Item ---")
                result.extend(_format_item_lines(c_it, resolver=char_resolver, version=version))
        if stored_matches:
            result.append("=== Inventory & Stash ===")
            for label, it in stored_matches:
                result.append(f"--- {label} ---")
                result.extend(_format_item_lines(it, resolver=char_resolver, version=version))

    return "\n".join(result).rstrip()
