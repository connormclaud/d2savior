"""Constants for Diablo II save and stash parsing and formatting."""

from d2savior.core.stash import (
    COMBINED_SLOT_ORDER,
    GEM_CODES,
    MATERIAL_CODES,
    RUNE_CODES,
    STASH_TAB_TYPE_ADVANCED,
    STASH_TAB_TYPE_CHRONICLE,
    STASH_TAB_TYPE_NORMAL,
)

TAB_TYPE_NAMES = {
    STASH_TAB_TYPE_NORMAL: "Normal",
    STASH_TAB_TYPE_ADVANCED: "Advanced (Currency)",
    STASH_TAB_TYPE_CHRONICLE: "Chronicle",
}

GEM_TYPE_NAMES = ["Amethyst", "Topaz", "Sapphire", "Emerald", "Ruby", "Diamond", "Skull"]

GEM_CODE_MAP = {
    # Amethyst
    b"gcv": ("Amethyst", "o"),
    b"gfv": ("Amethyst", "o"),
    b"gsv": ("Amethyst", "o"),
    b"gzv": ("Amethyst", "f"),
    b"gpv": ("Amethyst", "p"),
    # Topaz
    b"gcy": ("Topaz", "o"),
    b"gfy": ("Topaz", "o"),
    b"gsy": ("Topaz", "o"),
    b"gly": ("Topaz", "f"),
    b"gpy": ("Topaz", "p"),
    # Sapphire
    b"gcb": ("Sapphire", "o"),
    b"gfb": ("Sapphire", "o"),
    b"gsb": ("Sapphire", "o"),
    b"glb": ("Sapphire", "f"),
    b"gpb": ("Sapphire", "p"),
    # Emerald
    b"gcg": ("Emerald", "o"),
    b"gfg": ("Emerald", "o"),
    b"gsg": ("Emerald", "o"),
    b"glg": ("Emerald", "f"),
    b"gpg": ("Emerald", "p"),
    # Ruby
    b"gcr": ("Ruby", "o"),
    b"gfr": ("Ruby", "o"),
    b"gsr": ("Ruby", "o"),
    b"glr": ("Ruby", "f"),
    b"gpr": ("Ruby", "p"),
    # Diamond
    b"gcw": ("Diamond", "o"),
    b"gfw": ("Diamond", "o"),
    b"gsw": ("Diamond", "o"),
    b"glw": ("Diamond", "f"),
    b"gpw": ("Diamond", "p"),
    # Skull
    b"skc": ("Skull", "o"),
    b"skf": ("Skull", "o"),
    b"sku": ("Skull", "o"),
    b"skl": ("Skull", "f"),
    b"skz": ("Skull", "p"),
}

RUNE_CODES_STRIPPED = {c.strip() for c in RUNE_CODES}
GEM_CODES_STRIPPED = {c.strip() for c in GEM_CODES}
MATERIAL_CODES_STRIPPED = {c.strip() for c in MATERIAL_CODES}
COMBINED_SLOT_ORDER_STRIPPED = [c.strip() for c in COMBINED_SLOT_ORDER]

CLASS_SKILL_BASES = [
    6,  # Amazon (0)
    36,  # Sorceress (1)
    66,  # Necromancer (2)
    96,  # Paladin (3)
    126,  # Barbarian (4)
    221,  # Druid (5)
    251,  # Assassin (6)
    373,  # Warlock (7)
]

# Skill tab index (0, 1, 2) for each class's 30 skill slots (matching stat 188 tab indices).
SKILL_TAB_MAP: tuple[tuple[int, ...], ...] = (
    # 0 Amazon: 0=Bow & Crossbow, 1=Passive & Magic, 2=Javelin & Spear
    (0, 0, 1, 1, 2, 0, 0, 1, 2, 2, 0, 1, 1, 2, 2, 0, 0, 1, 2, 2, 0, 0, 1, 1, 2, 0, 1, 1, 2, 2),
    # 1 Sorceress: 0=Fire, 1=Lightning, 2=Cold
    (0, 0, 1, 2, 2, 0, 1, 1, 2, 2, 0, 0, 1, 1, 2, 0, 0, 1, 1, 2, 0, 1, 1, 2, 2, 0, 0, 1, 2, 2),
    # 2 Necromancer: 0=Curses, 1=Poison & Bone, 2=Summoning
    (0, 1, 1, 2, 2, 0, 0, 1, 1, 2, 0, 0, 1, 2, 2, 0, 0, 1, 1, 2, 0, 0, 1, 2, 2, 0, 1, 1, 2, 2),
    # 3 Paladin: 0=Combat, 1=Offensive Auras, 2=Defensive Auras
    (0, 0, 1, 2, 2, 0, 1, 1, 2, 2, 0, 0, 1, 2, 2, 0, 0, 1, 1, 2, 0, 0, 1, 1, 2, 0, 1, 1, 2, 2),
    # 4 Barbarian: 0=Combat, 1=Masteries, 2=Warcries
    (0, 1, 1, 1, 2, 2, 0, 0, 1, 1, 1, 2, 2, 0, 0, 1, 2, 0, 0, 1, 2, 0, 1, 2, 2, 0, 0, 1, 2, 2),
    # 5 Druid: 0=Summoning, 1=Shape Shifting, 2=Elemental
    (0, 0, 1, 1, 2, 0, 0, 1, 2, 2, 0, 1, 1, 2, 2, 0, 0, 1, 1, 2, 0, 1, 1, 2, 2, 0, 0, 1, 2, 2),
    # 6 Assassin: 0=Traps, 1=Shadow Disciplines, 2=Martial Arts
    (0, 1, 1, 2, 2, 0, 0, 1, 2, 2, 0, 0, 1, 1, 2, 0, 1, 1, 2, 2, 0, 0, 1, 2, 2, 0, 0, 1, 1, 2),
    # 7 Warlock: 0=Demon, 1=Eldritch, 2=Chaos
    (0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2),
)


def get_skill_tab_index(char_class: int, skill_offset: int) -> int | None:
    """Return the skill tab index (0..2) for a class skill offset (0..29), or None."""
    if 0 <= char_class < len(SKILL_TAB_MAP) and 0 <= skill_offset < len(SKILL_TAB_MAP[char_class]):
        return SKILL_TAB_MAP[char_class][skill_offset]
    return None


DIFFICULTY_NAMES = ["Normal", "Nightmare", "Hell"]
DIFFICULTY_RESIST_PENALTIES_EXPANSION = (0, -40, -100)
DIFFICULTY_RESIST_PENALTIES_CLASSIC = (0, -20, -50)
BASE_MAX_RESIST = 75
HARD_MAX_RESIST = 95
MIN_EFFECTIVE_RESIST = -100

WAYPOINTS_BY_ACT = [
    (
        "Act I",
        [
            "Rogue Encampment",
            "Cold Plains",
            "Stony Field",
            "Dark Wood",
            "Black Marsh",
            "Outer Cloister",
            "Jail Level 1",
            "Inner Cloister",
            "Catacombs Level 2",
        ],
    ),
    (
        "Act II",
        [
            "Lut Gholein",
            "Sewers Level 2",
            "Dry Hills",
            "Halls of the Dead Level 2",
            "Far Oasis",
            "Lost City",
            "Palace Cellar Level 1",
            "Arcane Sanctuary",
            "Canyon of the Magi",
        ],
    ),
    (
        "Act III",
        [
            "Kurast Docks",
            "Spider Forest",
            "Great Marsh",
            "Flayer Jungle",
            "Lower Kurast",
            "Kurast Bazaar",
            "Upper Kurast",
            "Travincal",
            "Durance of Hate Level 2",
        ],
    ),
    ("Act IV", ["The Pandemonium Fortress", "City of the Damned", "River of Flame"]),
    (
        "Act V",
        [
            "Harrogath",
            "Frigid Highlands",
            "Arreat Plateau",
            "Crystalline Passage",
            "Glacial Trail",
            "Halls of Pain",
            "Frozen Tundra",
            "The Ancients' Way",
            "Worldstone Keep Level 2",
        ],
    ),
]

QUESTS_BY_ACT = [
    (
        "Act I",
        [
            ("Den of Evil", 0),
            ("Sisters' Burial Grounds", 1),
            ("The Search for Cain", 3),
            ("The Forgotten Tower", 4),
            ("Tools of the Trade", 2),
            ("Sisters to the Slaughter", 5),
        ],
    ),
    (
        "Act II",
        [
            ("Radament's Lair", 0),
            ("The Horadric Staff", 1),
            ("Tainted Sun", 2),
            ("Arcane Sanctuary", 3),
            ("The Summoner", 4),
            ("The Seven Tombs", 5),
        ],
    ),
    (
        "Act III",
        [
            ("The Golden Bird", 3),
            ("Blade of the Old Religion", 2),
            ("Khalim's Will", 1),
            ("Lam Esen's Tome", 0),
            ("The Blackened Temple", 4),
            ("The Guardian", 5),
        ],
    ),
    (
        "Act IV",
        [
            ("The Fallen Angel", 0),
            ("Hell's Forge", 2),
            ("Terror's End", 1),
        ],
    ),
    (
        "Act V",
        [
            ("Siege on Harrogath", 0),
            ("Rescue on Mount Arreat", 1),
            ("Prison of Ice", 2),
            ("Betrayal of Harrogath", 3),
            ("Rite of Passage", 4),
            ("Eve of Destruction", 5),
        ],
    ),
]

QUEST_REWARDS: dict[str, str] = {
    "Den of Evil": "+1 Skill & Reset",
    "Sisters' Burial Grounds": "Rogue Merc",
    "The Search for Cain": "Rare Ring",
    "Tools of the Trade": "Imbue",
    "Radament's Lair": "+1 Skill",
    "The Golden Bird": "+20 Life",
    "Blade of the Old Religion": "Rare Ring",
    "Lam Esen's Tome": "+5 Stats",
    "The Fallen Angel": "+2 Skills",
    "Siege on Harrogath": "Socket",
    "Rescue on Mount Arreat": "Ral+Ort+Tal",
    "Prison of Ice": "+10 All Res",
    "Betrayal of Harrogath": "Personalize",
}
