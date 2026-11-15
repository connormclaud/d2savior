from collections.abc import Callable

from d2savior.core.models import StatInfo
from d2savior.core.resolver import GameDataResolver

CLASS_NAME_SIZE = 7
CLASS_SKILL_NAME_SIZE = 30
CLASS_SKILL_TAB_SIZE = 3

_CLASS_SKILL_LEVEL_KEYS = frozendict(
    {
        0: "ModStr3a",  # Amazon
        1: "ModStr3d",  # Sorceress
        2: "ModStr3c",  # Necromancer
        3: "ModStr3b",  # Paladin
        4: "ModStr3e",  # Barbarian
        5: "ModStre8a",  # Druid
        6: "ModStre8b",  # Assassin
        7: "ModStrge9",  # Warlock
    }
)

_CLASS_ONLY_KEYS = frozendict(
    {
        0: "AmaOnly",  # (Amazon Only)
        1: "SorOnly",  # (Sorceress Only)
        2: "NecOnly",  # (Necromancer Only)
        3: "PalOnly",  # (Paladin Only)
        4: "BarOnly",  # (Barbarian Only)
        5: "DruOnly",  # (Druid Only)
        6: "AssOnly",  # (Assassin Only)
        7: "WarOnly",  # (Warlock Only)
    }
)

_SKILL_TAB_MODIFIER_KEYS: frozendict[tuple[int, int], str] = frozendict(
    {
        (0, 0): "StrSklTabItem3",  # Bow and Crossbow Skills
        (0, 1): "StrSklTabItem2",  # Passive and Magic Skills
        (0, 2): "StrSklTabItem1",  # Javelin and Spear Skills
        (1, 0): "StrSklTabItem15",  # Fire Skills
        (1, 1): "StrSklTabItem14",  # Lightning Skills
        (1, 2): "StrSklTabItem13",  # Cold Skills
        (2, 0): "StrSklTabItem8",  # Curses
        (2, 1): "StrSklTabItem7",  # Poison and Bone Skills
        (2, 2): "StrSklTabItem9",  # Summoning Skills
        (3, 0): "StrSklTabItem6",  # Combat Skills (Paladin)
        (3, 1): "StrSklTabItem5",  # Offensive Auras
        (3, 2): "StrSklTabItem4",  # Defensive Auras
        (4, 0): "StrSklTabItem11",  # Combat Skills (Barbarian)
        (4, 1): "StrSklTabItem12",  # Masteries
        (4, 2): "StrSklTabItem10",  # Warcries
        (5, 0): "StrSklTabItem16",  # Summoning Skills (Druid)
        (5, 1): "StrSklTabItem17",  # Shape Shifting Skills
        (5, 2): "StrSklTabItem18",  # Elemental Skills
        (6, 0): "StrSklTabItem19",  # Traps
        (6, 1): "StrSklTabItem20",  # Shadow Disciplines
        (6, 2): "StrSklTabItem21",  # Martial Arts
        (7, 0): "StrSklTabItem24",  # Demon Skills
        (7, 1): "StrSklTabItem22",  # Eldritch Skills
        (7, 2): "StrSklTabItem23",  # Chaos Skills
    }
)

_CHANCE_CAST_KEYS = frozendict(
    {
        195: "ItemExpansiveChancX",
        196: "ModitemskonKill",
        197: "Moditemskondeath",
        198: "ItemExpansiveChanc1",
        199: "ModitemskonLevel",
        201: "ItemExpansiveChanc2",
    }
)


def get_skill_class_id(skill_id: int) -> int:
    if 6 <= skill_id < 156:
        return (skill_id - 6) // 30
    elif 221 <= skill_id < 281:
        return (skill_id - 221) // 30 + 5
    elif 373 <= skill_id < 403:
        return 7
    return -1


def get_time_name(time_id: int) -> str:
    return f"Time{time_id}"


_CHANCE_CAST_FALLBACKS: frozendict[int, str] = frozendict(
    {
        195: "%d%% Chance to cast level %d %s on attack",
        196: "%d%% Chance to cast level %d %s when you Kill an Enemy",
        197: "%d%% Chance to cast level %d %s when you Die",
        198: "%d%% Chance to cast level %d %s on striking",
        199: "%d%% Chance to cast level %d %s when you Level-Up",
        201: "%d%% Chance to cast level %d %s when struck",
    }
)

_SIMPLE_STAT_FALLBACKS: frozendict[int, str] = frozendict(
    {
        73: "+%d to Maximum Durability",
        159: "+%d to Minimum Throw Damage",
        160: "+%d to Maximum Throw Damage",
    }
)


def _apply_num_placeholder(tpl: str, val: int | float, suffix: str = "") -> str:
    """Replace %+d/%d/%+g/%g placeholders in a D2 modifier template with val."""
    if isinstance(val, float):
        return (
            tpl.replace("%+g", f"{val:+g}{suffix}")
            .replace("%g", f"{val:g}{suffix}")
            .replace("%+d", f"{val:+g}{suffix}")
            .replace("%d", f"{val:g}{suffix}")
        )
    return tpl.replace("%+d", f"{val:+d}{suffix}").replace("%d", f"{val}{suffix}")


def format_modifier_template(
    resolver: GameDataResolver,
    key: str | None,
    fallback: str,
    *values: int | float | str,
    signed_first: bool = False,
) -> str:
    """Resolve a localized modifier key (or fallback) and substitute positional placeholders."""
    tpl = resolver.get_item_modifier(key) if key else ""
    has_placeholder = any(p in tpl for p in ("%d", "%+d", "%g", "%+g", "%s", "%0"))
    if not tpl or tpl == key or not has_placeholder:
        tpl = fallback
    result = tpl
    if "%0" in result:
        for i, val in enumerate(values):
            result = result.replace(f"%{i}", str(val))
    else:
        for i, val in enumerate(values):
            if isinstance(val, str):
                result = result.replace("%s", val, 1)
            elif i == 0 and signed_first and ("%+d" in result or "%+g" in result):
                fmt = f"{val:+g}" if isinstance(val, float) else f"{val:+d}"
                result = result.replace("%+g", fmt, 1).replace("%+d", fmt, 1)
            else:
                fmt = f"{val:g}" if isinstance(val, float) else str(val)
                result = result.replace("%g", fmt, 1).replace("%d", fmt, 1)
    return result.replace("%%", "%")


def _get_class_only_str(class_id: int, resolver: GameDataResolver) -> str:
    """Return localized class restriction string such as '(Warlock Only)', or '' if unknown."""
    class_only_key = _CLASS_ONLY_KEYS.get(class_id)
    if class_only_key:
        loc_str = resolver.get_item_modifier(class_only_key)
        if loc_str and loc_str != class_only_key:
            return loc_str
    if class_id >= 0:
        class_name = resolver.get_localized_class_name(class_id)
        if class_name and class_name != "Unknown":
            return f"({class_name} Only)"
    return ""


type _PropHandler = Callable[[int, list[int], StatInfo | None, str, GameDataResolver], str | None]


def _fmt_duration(
    prop_id: int, a: list[int], _stat: StatInfo | None, _prop_name: str, _resolver: GameDataResolver
) -> str:
    elem = "cold" if prop_id == 56 else "poison"
    frames = a[0] // 25 if a[0] else 0
    return f"{frames} seconds {elem} duration"


def _fmt_class_skill_levels(
    _prop_id: int, a: list[int], _stat: StatInfo | None, _prop_name: str, resolver: GameDataResolver
) -> str:
    class_name = resolver.get_localized_class_name(a[0])
    return format_modifier_template(
        resolver,
        _CLASS_SKILL_LEVEL_KEYS.get(a[0]),
        f"+{a[1]} to {class_name} Skill Levels",
        a[1],
        signed_first=True,
    )


def _fmt_oskill(
    _prop_id: int, a: list[int], stat: StatInfo | None, _prop_name: str, resolver: GameDataResolver
) -> str:
    skill_name = resolver.get_skill_name(a[0])
    return format_modifier_template(
        resolver,
        stat.descstrpos if stat else None,
        f"+{a[1]} to {skill_name}",
        a[1],
        skill_name,
        signed_first=True,
    )


def _fmt_aura(
    _prop_id: int, a: list[int], _stat: StatInfo | None, _prop_name: str, resolver: GameDataResolver
) -> str:
    skill_name = resolver.get_skill_name(a[0])
    return format_modifier_template(
        resolver,
        "ModitemAura",
        f"Level {a[1]} {skill_name} Aura When Equipped",
        a[1],
        skill_name,
    )


def _fmt_simple_stat(
    prop_id: int, a: list[int], stat: StatInfo | None, _prop_name: str, resolver: GameDataResolver
) -> str:
    return format_modifier_template(
        resolver,
        stat.descstrpos if stat else None,
        _SIMPLE_STAT_FALLBACKS[prop_id],
        a[0],
        signed_first=True,
    )


def _fmt_class_skill(
    _prop_id: int, a: list[int], stat: StatInfo | None, _prop_name: str, resolver: GameDataResolver
) -> str:
    skill_name = resolver.get_skill_name(a[0])
    class_only_str = _get_class_only_str(get_skill_class_id(a[0]), resolver)
    tpl_key = stat.descstrpos if stat else None
    tpl = resolver.get_item_modifier(tpl_key) if tpl_key else ""
    if (
        tpl
        and tpl != tpl_key
        and "(%s)" in tpl
        and class_only_str.startswith("(")
        and class_only_str.endswith(")")
    ):
        class_only_str = class_only_str[1:-1]
    fallback = f"+{a[1]} to {skill_name} {class_only_str}".strip()
    return format_modifier_template(
        resolver, tpl_key, fallback, a[1], skill_name, class_only_str, signed_first=True
    ).strip()


def _fmt_vs_monster(
    prop_id: int, a: list[int], stat: StatInfo | None, _prop_name: str, resolver: GameDataResolver
) -> str:
    monster_name = resolver.get_localized_monster_name(a[0])
    noun = "Attack Rating" if prop_id == 179 else "Damage"
    fallback = f"+{a[1]}% to {noun} versus {monster_name}"
    tpl_key = stat.descstrpos if stat else None
    tpl = resolver.get_item_modifier(tpl_key) if tpl_key else ""
    if tpl and tpl != tpl_key and ("%+d" in tpl or "%d" in tpl or "%s" in tpl):
        res = format_modifier_template(
            resolver, tpl_key, fallback, a[1], monster_name, signed_first=True
        )
        return res if "%s" in tpl else f"{res} {monster_name}"
    return fallback


def _fmt_skill_tab(
    _prop_id: int, a: list[int], _stat: StatInfo | None, _prop_name: str, resolver: GameDataResolver
) -> str | None:
    tab, class_id, level = a[0], a[1], a[2]
    class_only_str = _get_class_only_str(class_id, resolver)
    tpl_key = _SKILL_TAB_MODIFIER_KEYS.get((class_id, tab))
    skill_tab_name = resolver.get_localized_skill_tab_name(tab, class_id)
    fallback = f"+{level} to {skill_tab_name}" if skill_tab_name else ""
    formatted = format_modifier_template(resolver, tpl_key, fallback, level, signed_first=True)
    return f"{formatted} {class_only_str}".strip() if formatted else None


def _fmt_chance_cast(
    prop_id: int, a: list[int], _stat: StatInfo | None, _prop_name: str, resolver: GameDataResolver
) -> str:
    return format_modifier_template(
        resolver,
        _CHANCE_CAST_KEYS.get(prop_id),
        _CHANCE_CAST_FALLBACKS[prop_id],
        a[2],
        a[0],
        resolver.get_skill_name(a[1]),
    )


def _fmt_charges(
    _prop_id: int, a: list[int], stat: StatInfo | None, _prop_name: str, resolver: GameDataResolver
) -> str:
    level = a[0]
    skill_name = resolver.get_skill_name(a[1])
    return format_modifier_template(
        resolver,
        stat.descstrpos if stat else None,
        f"Level {level} {skill_name} ({a[2]}/{a[3]} Charges)",
        level,
        skill_name,
        a[2],
        a[3],
    )


def _fmt_timed_stat(
    _prop_id: int, a: list[int], _stat: StatInfo | None, prop_name: str, _resolver: GameDataResolver
) -> str:
    time_name = get_time_name(a[0])
    return f"{time_name} +{a[1]} to {prop_name}" if time_name else prop_name


_PROP_HANDLERS: dict[int, _PropHandler] = {
    56: _fmt_duration,
    59: _fmt_duration,
    73: _fmt_simple_stat,
    83: _fmt_class_skill_levels,
    88: lambda _pid, _a, _s, _n, _r: "Double Potion Duration",
    92: lambda _pid, a, _s, _n, r: format_modifier_template(
        r, "ItemStats1p", f"Required Level: {a[0]}", a[0]
    ),
    97: _fmt_oskill,
    98: lambda _pid, a, _s, n, _r: get_time_name(a[0]) or n,
    107: _fmt_class_skill,
    151: _fmt_aura,
    155: lambda _pid, a, _s, _n, r: format_modifier_template(
        r,
        "Moditemreanimas",
        f"{a[1]}% Reanimate as: {(m := r.get_localized_monster_name(a[0]))}",
        a[1],
        m,
    ),
    159: _fmt_simple_stat,
    160: _fmt_simple_stat,
    179: _fmt_vs_monster,
    180: _fmt_vs_monster,
    188: _fmt_skill_tab,
    195: _fmt_chance_cast,
    196: _fmt_chance_cast,
    197: _fmt_chance_cast,
    198: _fmt_chance_cast,
    199: _fmt_chance_cast,
    201: _fmt_chance_cast,
    204: _fmt_charges,
    **dict.fromkeys(range(268, 304), _fmt_timed_stat),
}

_NEGATE_PROP_IDS = frozenset({305, 306, 307, 308, 333, 334, 335, 336})
_PERCENT_DESCFUNC = frozenset({2, 4, 5, 6, 8, 10, 11, 16, 20, 22})


def _adjust_property_values(
    prop_id: int, a: list[int], stat: StatInfo | None, char_level: int | None = None
) -> int | float | None:
    if prop_id == 54:
        a[2] = a[2] // 25 if a[2] else 0
    elif prop_id == 57 and a[2]:
        a[0] = (a[0] * a[2] + 128) >> 8 if a[0] else 0
        a[1] = (a[1] * a[2] + 128) >> 8 if a[1] else 0
        a[2] = a[2] // 25
    elif prop_id == 112:
        a[0] = a[0] * 100 // 127 if a[0] else 0
    elif prop_id == 126:
        a[0], a[1] = a[1], a[0]
    elif prop_id in range(214, 251):
        shift = stat.op_param if stat and stat.op_param > 0 else (stat.val_shift if stat else 0)
        if shift > 0:
            if char_level is not None:
                return (a[0] * char_level) >> shift
            return round(a[0] / (1 << shift), 3)
    elif prop_id in (252, 253):
        a[0] = 100 // a[0] if a[0] else 0
    elif prop_id in _NEGATE_PROP_IDS:
        a[0] = -a[0]
    return None


def _format_empty_params(stat: StatInfo | None, prop_name: str, resolver: GameDataResolver) -> str:
    if stat and stat.descstrpos:
        template = resolver.get_item_modifier(stat.descstrpos)
        if template and "%d" not in template and "%g" not in template:
            return template
    return prop_name


def format_property(
    prop_id: int,
    params: list[int],
    resolver: GameDataResolver,
    version: int = 0x60,
    char_level: int | None = None,
) -> str:
    vd = (
        resolver.game_data.for_version(version) if resolver.game_data is not None else resolver.data
    )
    stat = vd.get_stat(prop_id)
    prop_name = stat.stat_name if stat and stat.stat_name else f"Stat{prop_id}"

    if not params:
        return _format_empty_params(stat, prop_name, resolver)

    a: list[int] = list(params)
    while len(a) < 4:
        a.append(0)

    if (handler := _PROP_HANDLERS.get(prop_id)) is not None and (
        handled := handler(prop_id, a, stat, prop_name, resolver)
    ) is not None:
        return handled

    scaled_val = _adjust_property_values(prop_id, a, stat, char_level=char_level)
    if prop_id == 237:
        val = scaled_val if scaled_val is not None else a[0]
        return format_modifier_template(
            resolver,
            stat.descstrpos if stat else None,
            f"+{val:g} Poison Absorb (Based on Character Level)",
            float(val),
            signed_first=True,
        )

    value: int | float = scaled_val if scaled_val is not None else a[0]
    if stat and stat.descstrpos:
        template_key = stat.descstrpos if value >= 0 else (stat.descstrneg or stat.descstrpos)
        if template := resolver.get_item_modifier(template_key):
            suffix = "%" if stat.descfunc in _PERCENT_DESCFUNC else ""
            result = _apply_num_placeholder(template, value, suffix)
            if (
                stat.descfunc == 19
                and stat.descstr2
                and (extra := resolver.get_item_modifier(stat.descstr2))
            ):
                result = f"{result} {extra}"
            if "%d" in result or "%+d" in result:
                result = _apply_num_placeholder(result, a[1])
            return result.replace("%%", "%")

    return _format_template(prop_name, [value, a[1], a[2], a[3]])


def _format_template(template: str, values: list[int | float]) -> str:
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
