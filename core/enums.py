from enum import Enum, IntEnum


PLAYER_STATS_MAGIC = 0x6667
ITEM_LIST_MAGIC = 0x4D4A
MERCENARY_MAGIC = 0x666A
GOLEM_MAGIC_1 = 0x666B
GOLEM_MAGIC_2 = 0x6669
DEMON_MAGIC = 0x666C

PLAYER_STATS_BITS_COUNT = [10, 10, 10, 10, 10, 8, 21, 21, 21, 21, 21, 21, 7, 32, 25, 25]


class StoredIn(IntEnum):
    INVENTORY = 0
    EQUIP = 1
    TRADE = 2
    CUBE = 3
    STASH = 4
    BELT = 5
    
    def __str__(self) -> str:
        return self.name
    
    @classmethod
    def _missing_(cls, value):
        obj = int.__new__(cls, value)
        obj._name_ = f"Unknown({value})"
        obj._value_ = value
        return obj


class ItemLocation(IntEnum):
    STORED = 0
    EQUIPPED = 1
    BELT = 2
    CURSOR = 3
    ITEM = 4
    SOCKET = 6
    
    def __str__(self) -> str:
        return self.name
    
    @classmethod
    def _missing_(cls, value):
        obj = int.__new__(cls, value)
        obj._name_ = f"Unknown({value})"
        obj._value_ = value
        return obj


class ItemQuality(IntEnum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    MAGIC = 4
    SET = 5
    RARE = 6
    UNIQUE = 7
    CRAFTED = 8
    
    def __str__(self) -> str:
        return self.name
    
    @classmethod
    def _missing_(cls, value):
        obj = int.__new__(cls, value)
        obj._name_ = f"Unknown({value})"
        obj._value_ = value
        return obj
