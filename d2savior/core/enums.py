from enum import IntEnum
from typing import Self

PLAYER_STATS_MAGIC = 0x6667
ITEM_LIST_MAGIC = 0x4D4A
MERCENARY_MAGIC = 0x666A
GOLEM_MAGIC_1 = 0x666B
GOLEM_MAGIC_2 = 0x6669
DEMON_MAGIC = 0x666C

PLAYER_STATS_BITS_COUNT = [10, 10, 10, 10, 10, 8, 21, 21, 21, 21, 21, 21, 7, 32, 25, 25]

CLASS_NAMES: tuple[str, ...] = (
    "Amazon",
    "Sorceress",
    "Necromancer",
    "Paladin",
    "Barbarian",
    "Druid",
    "Assassin",
    "Warlock",
)


class D2IntEnum(IntEnum):
    """Base integer enum for Diablo II constants with display name support and fallback for unknown values."""

    @property
    def display_name(self) -> str:
        names = self._display_names()
        return names.get(self.value, self.name) if names else self.name

    @classmethod
    def _display_names(cls) -> dict[int, str]:
        return {}

    def __str__(self) -> str:
        return self.display_name

    @classmethod
    def _missing_(cls, value: object) -> Self:
        val = int(value) if isinstance(value, int | str) else 0
        obj = int.__new__(cls, val)
        obj._name_ = f"Unknown({value})"
        obj._value_ = val
        return obj


class CharClass(D2IntEnum):
    """Diablo II playable character class IDs."""

    AMAZON = 0
    SORCERESS = 1
    NECROMANCER = 2
    PALADIN = 3
    BARBARIAN = 4
    DRUID = 5
    ASSASSIN = 6
    WARLOCK = 7

    @classmethod
    def _display_names(cls) -> dict[int, str]:
        return dict(enumerate(CLASS_NAMES))


class StoredIn(D2IntEnum):
    INVENTORY = 0
    EQUIP = 1
    TRADE = 2
    CUBE = 3
    STASH = 4
    BELT = 5


class ItemLocation(D2IntEnum):
    STORED = 0
    EQUIPPED = 1
    BELT = 2
    CURSOR = 3
    ITEM = 4
    SOCKET = 6


class ItemQuality(D2IntEnum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    MAGIC = 4
    SET = 5
    RARE = 6
    UNIQUE = 7
    CRAFTED = 8


class EquipSlot(D2IntEnum):
    HELMET = 1
    AMULET = 2
    ARMOR = 3
    WEAPON_I = 4
    SHIELD_I = 5
    RING_RIGHT = 6
    RING_LEFT = 7
    BELT = 8
    BOOTS = 9
    GLOVES = 10
    WEAPON_II = 11
    SHIELD_II = 12

    @classmethod
    def _display_names(cls) -> dict[int, str]:
        return {
            1: "Helmet",
            2: "Amulet",
            3: "Armor",
            4: "Weapon I",
            5: "Shield I",
            6: "Ring (Right)",
            7: "Ring (Left)",
            8: "Belt",
            9: "Boots",
            10: "Gloves",
            11: "Weapon II",
            12: "Shield II",
        }


class SkillId(IntEnum):
    """Canonical Diablo II skill IDs (matching skills.txt)."""

    CRITICAL_STRIKE = 9
    EXPLODING_ARROW = 16
    ICE_BOLT = 39
    FROZEN_ARMOR = 40
    STATIC_FIELD = 42
    ICE_BLAST = 45
    SHIVER_ARMOR = 50
    GLACIAL_SPIKE = 55
    BLIZZARD = 59
    CHILLING_ARMOR = 60
    FROZEN_ORB = 64
    COLD_MASTERY = 65
    LIFE_TAP = 82
    DECREPIFY = 87
    SACRIFICE = 96
    SMITE = 97
    HOLY_FIRE = 102
    ZEAL = 106
    CHARGE = 107
    BLESSED_AIM = 108
    VENGEANCE = 111
    HOLY_FREEZE = 114
    HOLY_SHIELD = 117
    HOLY_SHOCK = 118
    FANATICISM = 122
    CONVICTION = 123
    BATTLE_ORDERS = 149
    VENOM = 278


class StatId(IntEnum):
    """Canonical Diablo II item/character stat IDs (matching ItemStatCost.txt)."""

    ARMOR_PERCENT = 16
    MAX_DAMAGE_PERCENT = 17
    MIN_DAMAGE_PERCENT = 18
    MIN_DAMAGE = 21
    MAX_DAMAGE = 22
    SECONDARY_MIN_DAMAGE = 23
    SECONDARY_MAX_DAMAGE = 24
    DAMAGE_PERCENT = 25
    ARMOR_CLASS = 31
    POISON_MIN_DAM = 57
    POISON_MAX_DAM = 58
    POISON_LENGTH = 59
    CLASS_SKILLS = 83
    OSKILL = 97
    SINGLE_SKILL = 107
    NORMAL_DAMAGE = 111
    IGNORE_TARGET_AC = 115
    DEMON_TOHIT = 123
    UNDEAD_TOHIT = 124
    ELEM_SKILL = 126
    ALL_SKILLS = 127
    OPEN_WOUNDS = 135
    INDESTRUCTIBLE = 152
    CANNOT_BE_FROZEN = 153
    EXPLOSIVE_ARROW = 158
    SKILL_TAB = 188
    NUM_SOCKETS = 194
    SKILL_ON_ATTACK = 195
    SKILL_ON_HIT = 198
    ARMOR_PER_LEVEL = 214
    MAX_DAMAGE_PER_LEVEL = 218
    MAX_DAMAGE_PERCENT_PER_LEVEL = 219
    CRUSHING_BLOW_PER_LEVEL = 247
    OPEN_WOUNDS_PER_LEVEL = 248
    PASSIVE_COLD_MASTERY = 331
