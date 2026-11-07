from typing import Any

CLASS_NAME_SIZE = 7
CLASS_SKILL_NAME_SIZE = 30
CLASS_SKILL_TAB_SIZE = 3

_CLASS_SKILL_LEVEL_KEYS = {
    0: "ModStr3a",  # Amazon
    1: "ModStr3d",  # Sorceress
    2: "ModStr3c",  # Necromancer
    3: "ModStr3b",  # Paladin
    4: "ModStr3e",  # Barbarian
    5: "ModStre8a",  # Druid
    6: "ModStre8b",  # Assassin
    7: "ModStrge9",  # Warlock
}

_CHANCE_CAST_KEYS = {
    195: "ItemExpansiveChancX",
    196: "ModitemskonKill",
    197: "Moditemskondeath",
    198: "ItemExpansiveChanc1",
    199: "ModitemskonLevel",
    201: "ItemExpansiveChanc2",
}


def get_skill_class_id(skill_id: int) -> int:
    if 6 <= skill_id < 156:
        return (skill_id - 6) // 30
    elif 221 <= skill_id < 281:
        return (skill_id - 221) // 30 + 5
    return -1


def get_time_name(time_id: int) -> str:
    return f"Time{time_id}"


def format_property(
    prop_id: int,
    params: list[int],
    resolver: Any,
    version: int = 0x60,
) -> str:
    vd = (
        resolver.game_data.for_version(version)
        if getattr(resolver, "game_data", None) is not None
        else getattr(resolver, "data", None)
    )

    stat = vd.get_stat(prop_id) if vd else None
    prop_name = stat.stat_name if stat and stat.stat_name else f"Stat{prop_id}"

    if not params:
        if stat and stat.descstrpos:
            template = resolver.get_item_modifier(stat.descstrpos)
            if template and "%d" not in template and "%g" not in template:
                return template
        return prop_name

    a: list[Any] = list(params)
    while len(a) < 4:
        a.append(0)

    match prop_id:
        case 54:
            a[2] = a[2] // 25 if a[2] else 0
        case 56:
            frames = a[0] // 25 if a[0] else 0
            return f"{frames} seconds cold duration"
        case 59:
            frames = a[0] // 25 if a[0] else 0
            return f"{frames} seconds poison duration"
        case 57:
            a[0] = (a[0] * a[2] + 128) >> 8 if a[0] and a[2] else 0
            a[1] = (a[1] * a[2] + 128) >> 8 if a[1] and a[2] else 0
            a[2] = a[2] // 25 if a[2] else 0
        case 83:
            class_name = resolver.get_localized_class_name(a[0])
            tpl_key = _CLASS_SKILL_LEVEL_KEYS.get(a[0])
            if tpl_key:
                tpl = resolver.get_item_modifier(tpl_key)
                if tpl and ("%+d" in tpl or "%d" in tpl):
                    return tpl.replace("%+d", f"{a[1]:+d}").replace("%d", str(a[1]))
            return f"+{a[1]} to {class_name} Skill Levels"
        case 97:
            skill_name = resolver.get_skill_name(a[0])
            if stat and stat.descstrpos:
                tpl = resolver.get_item_modifier(stat.descstrpos)
                if tpl and ("%+d" in tpl or "%d" in tpl or "%s" in tpl):
                    return (
                        tpl.replace("%+d", f"{a[1]:+d}")
                        .replace("%d", str(a[1]))
                        .replace("%s", skill_name)
                    )
            return f"+{a[1]} to {skill_name}"
        case 151:
            skill_name = resolver.get_skill_name(a[0])
            tpl = resolver.get_item_modifier("ModitemAura")
            if tpl and ("%d" in tpl or "%s" in tpl):
                return tpl.replace("%d", str(a[1])).replace("%s", skill_name)
            return f"Level {a[1]} {skill_name} Aura When Equipped"
        case 98:
            time_name = get_time_name(a[0])
            return time_name or prop_name
        case 73:
            if stat and stat.descstrpos:
                tpl = resolver.get_item_modifier(stat.descstrpos)
                if tpl and ("%+d" in tpl or "%d" in tpl):
                    return tpl.replace("%+d", f"{a[0]:+d}").replace("%d", str(a[0]))
            return f"+{a[0]} to Maximum Durability"
        case 88:
            return "Double Potion Duration"
        case 92:
            tpl = resolver.get_item_modifier("ItemStats1p")
            if tpl and "%d" in tpl:
                return tpl % a[0]
            return f"Required Level: {a[0]}"
        case 107:
            skill_name = resolver.get_skill_name(a[0])
            class_id = get_skill_class_id(a[0])
            class_name = resolver.get_localized_class_name(class_id) if class_id >= 0 else ""
            if stat and stat.descstrpos:
                tpl = resolver.get_item_modifier(stat.descstrpos)
                if tpl and ("%+d" in tpl or "%d" in tpl or "%s" in tpl):
                    return (
                        tpl.replace("%+d", f"{a[1]:+d}")
                        .replace("%d", str(a[1]))
                        .replace("%s", skill_name)
                    )
            if class_name:
                return f"+{a[1]} to {skill_name} ({class_name} Only)"
            return f"+{a[1]} to {skill_name}"
        case 112:
            a[0] = a[0] * 100 // 127 if a[0] else 0
        case 126:
            a[0], a[1] = a[1], a[0]
        case 155:
            monster_name = resolver.get_localized_monster_name(a[0])
            tpl = resolver.get_item_modifier("Moditemreanimas")
            if tpl and ("%0" in tpl or "%1" in tpl):
                return (
                    tpl.replace("%0%%", f"{a[1]}%%")
                    .replace("%1", monster_name)
                    .replace("%0", str(a[1]))
                )
            return f"{a[1]}% Reanimate as: {monster_name}"
        case 159:
            if stat and stat.descstrpos:
                tpl = resolver.get_item_modifier(stat.descstrpos)
                if tpl and ("%+d" in tpl or "%d" in tpl):
                    return tpl.replace("%+d", f"{a[0]:+d}").replace("%d", str(a[0]))
            return f"+{a[0]} to Minimum Throw Damage"
        case 160:
            if stat and stat.descstrpos:
                tpl = resolver.get_item_modifier(stat.descstrpos)
                if tpl and ("%+d" in tpl or "%d" in tpl):
                    return tpl.replace("%+d", f"{a[0]:+d}").replace("%d", str(a[0]))
            return f"+{a[0]} to Maximum Throw Damage"
        case 179 | 180:
            monster_name = resolver.get_localized_monster_name(a[0])
            if stat and stat.descstrpos:
                tpl = resolver.get_item_modifier(stat.descstrpos)
                if tpl and ("%+d" in tpl or "%d" in tpl or "%s" in tpl):
                    return (
                        tpl.replace("%+d", f"{a[1]:+d}")
                        .replace("%d", str(a[1]))
                        .replace("%s", monster_name)
                    )
            if prop_id == 179:
                return f"+{a[1]}% to Attack Rating versus {monster_name}"
            return f"+{a[1]}% to Damage versus {monster_name}"
        case 188:
            skill_tab_name = resolver.get_localized_skill_tab_name(a[0], a[1])
            if skill_tab_name:
                return f"+{a[2]} to {skill_tab_name}"
        case 195 | 196 | 197 | 198 | 199 | 201:
            level = a[0]
            skill_name = resolver.get_skill_name(a[1])
            chance = a[2]
            tpl_key = _CHANCE_CAST_KEYS.get(prop_id)
            if tpl_key:
                tpl = resolver.get_item_modifier(tpl_key)
                if tpl and ("%d" in tpl or "%s" in tpl):
                    result = tpl
                    if "%0" in result:
                        result = result.replace("%0%%", f"{chance}%%").replace("%0", str(chance))
                        result = result.replace("%1", str(level)).replace("%2", skill_name)
                    else:
                        result = result.replace("%d%%", f"{chance}%").replace("%d", str(level))
                        result = result.replace("%s", skill_name)
                    return result
            match prop_id:
                case 195:
                    return f"{chance}% Chance to cast level {level} {skill_name} on attack"
                case 196:
                    return f"{chance}% Chance to cast level {level} {skill_name} when you Kill an Enemy"
                case 197:
                    return f"{chance}% Chance to cast level {level} {skill_name} when you Die"
                case 198:
                    return f"{chance}% Chance to cast level {level} {skill_name} on striking"
                case 199:
                    return f"{chance}% Chance to cast level {level} {skill_name} when you Level-Up"
                case 201:
                    return f"{chance}% Chance to cast level {level} {skill_name} when struck"
        case 204:
            level = a[0]
            skill_name = resolver.get_skill_name(a[1])
            if stat and stat.descstrpos:
                tpl = resolver.get_item_modifier(stat.descstrpos)
                if tpl and ("%d" in tpl or "%s" in tpl):
                    result = tpl
                    if "%0" in result:
                        result = result.replace("%0", str(level)).replace("%1", skill_name)
                        result = result.replace("%2", str(a[2])).replace("%3", str(a[3]))
                    else:
                        result = result.replace("%d", str(level), 1)
                        result = result.replace("%s", skill_name, 1)
                        remaining = result
                        for val in [a[2], a[3]]:
                            if "%d" in remaining:
                                remaining = remaining.replace("%d", str(val), 1)
                        result = remaining
                    return result
            return f"Level {level} {skill_name} ({a[2]}/{a[3]} Charges)"
        case _ if prop_id in range(214, 251):
            sc = vd.get_stat(prop_id) if vd else None
            if sc and sc.op_param > 0:
                a[0] = round(a[0] / sc.op_param, 2)
            elif sc and sc.val_shift > 0:
                a[0] = a[0] / (1 << sc.val_shift)
            if prop_id == 237:
                if stat and stat.descstrpos:
                    tpl = resolver.get_item_modifier(stat.descstrpos)
                    if tpl and ("%+d" in tpl or "%d" in tpl or "%g" in tpl or "%+g" in tpl):
                        val = a[0]
                        return (
                            tpl.replace("%+g", f"{val:+g}")
                            .replace("%g", f"{val:g}")
                            .replace("%+d", f"{val:+g}")
                            .replace("%d", f"{val:g}")
                        )
                return f"+{a[0]:g} Poison Absorb (Based on Character Level)"
        case 252 | 253:
            a[0] = 100 // a[0] if a[0] else 0
        case _ if prop_id in range(268, 304):
            time_name = get_time_name(a[0])
            if time_name:
                return f"{time_name} +{a[1]} to {prop_name}"
            return prop_name
        case 305 | 306 | 307 | 308 | 333 | 334 | 335 | 336:
            a[0] = -a[0]
        case _:
            pass

    if stat and stat.descstrpos:
        template_key = stat.descstrpos if a[0] >= 0 else (stat.descstrneg or stat.descstrpos)
        template = resolver.get_item_modifier(template_key)
        if template:
            descfunc = stat.descfunc
            value = a[0]

            match descfunc:
                case 1 | 3 | 7 | 9 | 12 | 13 | 14 | 15 | 17 | 18 | 21 | 23 | 24:
                    result = template.replace("%+d", f"{value:+d}").replace("%d", str(value))
                case 2 | 4 | 5 | 6 | 8 | 10 | 11 | 16 | 20 | 22:
                    result = template.replace("%+d", f"{value:+d}%").replace("%d", f"{value}%")
                case 19:
                    if isinstance(value, float):
                        result = template.replace("%+d", f"{value:+g}").replace("%d", f"{value:g}")
                    else:
                        result = template.replace("%+d", f"{value:+d}").replace("%d", str(value))
                    if stat.descstr2:
                        extra = resolver.get_item_modifier(stat.descstr2)
                        if extra:
                            result = result + " " + extra
                case _:
                    result = template.replace("%+d", f"{value:+d}").replace("%d", str(value))

            if "%d" in result or "%+d" in result:
                result = result.replace("%+d", f"{a[1]:+d}").replace("%d", str(a[1]))

            result = result.replace("%%", "%")

            return result

    return _format_template(prop_name, [a[0], a[1], a[2], a[3]])


def _format_template(template: str, values: list) -> str:
    if not template:
        return ""

    try:
        count = template.count("%d")
        if count == 0:
            return template
        elif count == 1:
            return template % values[0]
        elif count == 2:
            return template % (values[0], values[1])
        elif count == 3:
            return template % (values[0], values[1], values[2])
        elif count == 4:
            return template % (values[0], values[1], values[2], values[3])
        return template
    except TypeError, ValueError:
        return template


def _format_with_strings(template: str, int_values: list[int], str_values: list[str]) -> str:
    if not template:
        return ""

    result = template
    for val in int_values:
        if "%d" in result:
            result = result.replace("%d", str(val), 1)
    for val in str_values:
        if "%s" in result:
            result = result.replace("%s", val, 1)

    return result
