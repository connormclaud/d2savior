"""Save-format version constants and capability predicates."""

# Legacy Diablo II / Lord of Destruction save versions
VERSION_CLASSIC_100 = 0x47  # 71: Diablo II 1.00-1.06
VERSION_REALM_DATA = 0x56  # 86: D2R realm data threshold (> 86 uses realm data vs timestamp)
VERSION_CLASSIC_107 = 0x57  # 87: Diablo II 1.07-1.08
VERSION_CLASSIC_109 = 0x59  # 89: Diablo II 1.09
VERSION_LOD_109 = 0x5C  # 92: LoD 1.09 (> 92 adds compact quest difficulty check)
VERSION_REALM_3 = 0x5D  # 93: > 93 stores 3 realm dwords instead of 2
VERSION_LOD = 0x60  # 96: LoD 1.10-1.14d (> 96 stores 4 realm dwords, drops gem magic)

# Diablo II: Resurrected save versions
VERSION_D2R = 0x61  # 97: D2R 1.0 (Huffman item codes, ItemStatCost property widths)
VERSION_D2R_PTR24 = 0x62  # 98: D2R 2.4+ (8-bit UTF-8 character/ear/personalized names)
VERSION_D2R_1X = 0x63  # 99: D2R 2.5+ / v1.x (> 99 adds stash stack size)
VERSION_D2R_STASH_STACK_FLAG = 0x65  # 101: > 101 prefixes stash stack size with a presence bit
VERSION_D2R_3X = 0x69  # 105: D2R 3.x / Reign of the Warlock

VALID_VERSIONS: tuple[int, ...] = (
    VERSION_D2R_3X,
    VERSION_D2R_1X,
    VERSION_D2R_PTR24,
    VERSION_D2R,
    VERSION_LOD,
    VERSION_LOD_109,
    VERSION_CLASSIC_109,
    VERSION_CLASSIC_107,
    VERSION_CLASSIC_100,
)


def is_valid_version(version: int) -> bool:
    return version in VALID_VERSIONS


def is_d2r(version: int) -> bool:
    return version >= VERSION_D2R


def is_ptr24_and_above(version: int) -> bool:
    return version >= VERSION_D2R_PTR24


def is_d2r_3x(version: int) -> bool:
    return version >= VERSION_D2R_3X


def realm_data_word_count(version: int) -> int:
    """Return the number of 32-bit realm-data words stored for a given save version."""
    if version > VERSION_LOD:
        return 4
    if version > VERSION_REALM_3:
        return 3
    return 2
