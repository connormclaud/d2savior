from typing import Any

from d2savior.core.bit_io import BitIO, BitReader, BitWriter
from d2savior.core.d2data import GameData
from d2savior.core.obitstream import OBitStream

STASH_TAB_MAGIC = 0xAA55AA55
STASH_TAB_HEADER_SIZE = 64

STASH_TAB_TYPE_NORMAL = 0
STASH_TAB_TYPE_ADVANCED = 1
STASH_TAB_TYPE_CHRONICLE = 2

ADVANCED_SUBTYPE_GEM = 0
ADVANCED_SUBTYPE_RUNE = 1
ADVANCED_SUBTYPE_MATERIAL = 2
ADVANCED_SUBTYPE_UNKNOWN = -1

GEM_LAYOUT = (7, 5)
RUNE_LAYOUT = (9, 4)
MATERIAL_LAYOUT = (10, 3)
NORMAL_LAYOUT = (10, 10)

RUNE_SLOT_ORDER = [
    b"r01 ",
    b"r02 ",
    b"r03 ",
    b"r04 ",
    b"r05 ",
    b"r06 ",
    b"r07 ",
    b"r08 ",
    b"r09 ",
    b"r10 ",
    b"r11 ",
    b"r12 ",
    b"r13 ",
    b"r14 ",
    b"r15 ",
    b"r16 ",
    b"r17 ",
    b"r18 ",
    b"r19 ",
    b"r20 ",
    b"r21 ",
    b"r22 ",
    b"r23 ",
    b"r24 ",
    b"r25 ",
    b"r26 ",
    b"r27 ",
    b"r28 ",
    b"r29 ",
    b"r30 ",
    b"r31 ",
    b"r32 ",
    b"r33 ",
]

GEM_SLOT_ORDER = [
    b"gcv ",
    b"gcy ",
    b"gcb ",
    b"gcg ",
    b"gcr ",
    b"gcw ",
    b"skc ",
    b"gfv ",
    b"gfy ",
    b"gfb ",
    b"gfg ",
    b"gfr ",
    b"gfw ",
    b"skf ",
    b"gsv ",
    b"gsy ",
    b"gsb ",
    b"gsg ",
    b"gsr ",
    b"gsw ",
    b"sku ",
    b"gzv ",
    b"gly ",
    b"glb ",
    b"glg ",
    b"glr ",
    b"glw ",
    b"skl ",
    b"gpv ",
    b"gpy ",
    b"gpb ",
    b"gpg ",
    b"gpr ",
    b"gpw ",
    b"skz ",
]

MATERIAL_SLOT_ORDER = [
    b"rvs ",
    b"rvl ",
    b"pk1 ",
    b"pk2 ",
    b"pk3 ",
    b"dhn ",
    b"bey ",
    b"mbr ",
    b"toa ",
    b"tes ",
    b"ceh ",
    b"bet ",
    b"fed ",
    b"xa1 ",
    b"xa2 ",
    b"xa3 ",
    b"xa4 ",
    b"xa5 ",
    b"ua1 ",
    b"ua2 ",
    b"ua3 ",
    b"ua4 ",
    b"ua5 ",
]

RUNE_CODES = {
    b"r01 ",
    b"r02 ",
    b"r03 ",
    b"r04 ",
    b"r05 ",
    b"r06 ",
    b"r07 ",
    b"r08 ",
    b"r09 ",
    b"r10 ",
    b"r11 ",
    b"r12 ",
    b"r13 ",
    b"r14 ",
    b"r15 ",
    b"r16 ",
    b"r17 ",
    b"r18 ",
    b"r19 ",
    b"r20 ",
    b"r21 ",
    b"r22 ",
    b"r23 ",
    b"r24 ",
    b"r25 ",
    b"r26 ",
    b"r27 ",
    b"r28 ",
    b"r29 ",
    b"r30 ",
    b"r31 ",
    b"r32 ",
    b"r33 ",
}

GEM_CODES = {
    b"gcv ",
    b"gfv ",
    b"gsv ",
    b"gzv ",
    b"gpv ",
    b"gcy ",
    b"gfy ",
    b"gsy ",
    b"gly ",
    b"gpy ",
    b"gcb ",
    b"gfb ",
    b"gsb ",
    b"glb ",
    b"gpb ",
    b"gcg ",
    b"gfg ",
    b"gsg ",
    b"glg ",
    b"gpg ",
    b"gcr ",
    b"gfr ",
    b"gsr ",
    b"glr ",
    b"gpr ",
    b"gcw ",
    b"gfw ",
    b"gsw ",
    b"glw ",
    b"gpw ",
    b"skc ",
    b"skf ",
    b"sku ",
    b"skl ",
    b"skz ",
}

MATERIAL_CODES = {
    b"rvs ",
    b"rvl ",
    b"pk1 ",
    b"pk2 ",
    b"pk3 ",
    b"dhn ",
    b"bey ",
    b"mbr ",
    b"toa ",
    b"tes ",
    b"ceh ",
    b"bet ",
    b"fed ",
    b"xa1 ",
    b"xa2 ",
    b"xa3 ",
    b"xa4 ",
    b"xa5 ",
    b"ua1 ",
    b"ua2 ",
    b"ua3 ",
    b"ua4 ",
    b"ua5 ",
}


def classify_advanced_tab(items: list[Any] | None) -> int:
    if not items:
        return ADVANCED_SUBTYPE_UNKNOWN
    rune_count = 0
    gem_count = 0
    material_count = 0
    for item in items:
        tn = getattr(item, "type_name", b"")
        if tn in RUNE_CODES:
            rune_count += 1
        elif tn in GEM_CODES:
            gem_count += 1
        elif tn in MATERIAL_CODES:
            material_count += 1
    if rune_count == 0 and gem_count == 0 and material_count == 0:
        return ADVANCED_SUBTYPE_UNKNOWN
    if rune_count > 0 and gem_count == 0 and material_count == 0:
        return ADVANCED_SUBTYPE_RUNE
    if gem_count > 0 and rune_count == 0 and material_count == 0:
        return ADVANCED_SUBTYPE_GEM
    if material_count > 0 and rune_count == 0 and gem_count == 0:
        return ADVANCED_SUBTYPE_MATERIAL
    counts = {
        ADVANCED_SUBTYPE_RUNE: rune_count,
        ADVANCED_SUBTYPE_GEM: gem_count,
        ADVANCED_SUBTYPE_MATERIAL: material_count,
    }
    return max(counts, key=lambda k: counts[k])


def get_advanced_layout(subtype: int) -> tuple[int, int]:
    if subtype == ADVANCED_SUBTYPE_GEM:
        return GEM_LAYOUT
    elif subtype == ADVANCED_SUBTYPE_RUNE:
        return RUNE_LAYOUT
    elif subtype == ADVANCED_SUBTYPE_MATERIAL:
        return MATERIAL_LAYOUT
    return NORMAL_LAYOUT


COMBINED_SLOT_ORDER = GEM_SLOT_ORDER + RUNE_SLOT_ORDER + MATERIAL_SLOT_ORDER


def get_advanced_slot_order(subtype: int) -> list:
    if subtype == ADVANCED_SUBTYPE_GEM:
        return GEM_SLOT_ORDER
    elif subtype == ADVANCED_SUBTYPE_RUNE:
        return RUNE_SLOT_ORDER
    elif subtype == ADVANCED_SUBTYPE_MATERIAL:
        return MATERIAL_SLOT_ORDER
    return COMBINED_SLOT_ORDER


def compute_advanced_grid(items: list[Any], subtype: int) -> tuple[int, int, list]:
    if not items:
        layout = get_advanced_layout(subtype)
        return layout[0], layout[1], get_advanced_slot_order(subtype)

    slot_order = get_advanced_slot_order(subtype)
    base_layout = get_advanced_layout(subtype)
    cols = base_layout[0]

    item_type_set = set()
    for item in items:
        tn = getattr(item, "type_name", b"")
        if tn:
            item_type_set.add(tn)

    matched = sum(1 for code in slot_order if code in item_type_set)
    unmatched = len(item_type_set) - matched
    total_slots_needed = matched + unmatched

    base_rows = base_layout[1]
    min_rows = (total_slots_needed + cols - 1) // cols
    rows = max(base_rows, min_rows)

    return cols, rows, slot_order


class StashTab:
    def __init__(self) -> None:
        self.stash_format = 0
        self.item_format = 0
        self.gold = 0
        self.season = 0
        self.tab_type = STASH_TAB_TYPE_NORMAL
        self.reserved = b"\x00" * 43
        self.items = None
        self.chronicle = None
        self._tab_size = 0
        self._data: Any = None

    def codec(self, io: BitIO, version: int | None = None, data: Any = None) -> None:
        start_pos = io.bs.bytes_pos if isinstance(io, BitReader) else 0

        magic = io.dword(STASH_TAB_MAGIC)
        if io.is_reading and magic != STASH_TAB_MAGIC:
            raise ValueError(f"Invalid stash tab magic: 0x{magic:08X}")

        self.stash_format = io.dword(self.stash_format)
        self.item_format = io.dword(self.item_format)
        self.gold = io.dword(self.gold)
        self._tab_size = io.word(self._tab_size if io.is_writing else 0)
        self.season = io.word(self.season)
        self.tab_type = io.byte(self.tab_type)
        self.reserved = io.bytes(43, self.reserved)

        if io.is_reading and self.stash_format < 2:
            self.tab_type = STASH_TAB_TYPE_NORMAL

        item_version = version if version else self.item_format
        vd = data.for_version(item_version) if isinstance(data, GameData) else (data or self._data)
        self._data = vd

        if self.tab_type == STASH_TAB_TYPE_CHRONICLE:
            if io.is_writing:
                if self.chronicle:
                    io.bytes(len(self.chronicle), self.chronicle)
            else:
                body_size = max(0, self._tab_size - STASH_TAB_HEADER_SIZE)
                self.chronicle = io.bytes(body_size)
        else:
            if io.is_writing:
                if self.items:
                    self.items.codec(io, item_version, data=vd)
            else:
                from d2savior.core.item import ItemList

                try:
                    self.items = ItemList()
                    self.items.codec(io, item_version, data=vd)
                except Exception as e:
                    import logging

                    logging.warning(
                        f"Failed to parse stash tab items (TabType={self.tab_type}, "
                        f"ItemFormat={self.item_format:#x}): {e}"
                    )

        if isinstance(io, BitReader):
            end_pos = start_pos + self._tab_size
            io.bs.bytes_pos = end_pos

    def deserialize(self, bs: Any, version: int | None = None, data: Any = None) -> None:
        reader = bs if isinstance(bs, BitIO) else BitReader(bs)
        self.codec(reader, version, data=data)

    def serialize(self, bs: Any, version: int | None = None, data: Any = None) -> None:
        writer = bs if isinstance(bs, BitIO) else BitWriter(bs)
        self.codec(writer, version, data=data)


class SharedStash:
    def __init__(self) -> None:
        self.tabs: list[StashTab] = []
        self.file_path = ""

    def codec(self, io: BitIO, version: int | None = None, data: Any = None) -> None:
        import struct

        if io.is_writing:
            for tab in self.tabs:
                tab_bs = OBitStream()
                tab.codec(BitWriter(tab_bs), version, data=data)
                tab_data = bytearray(tab_bs.get_data())
                tab_size = len(tab_data)
                struct.pack_into("<H", tab_data, 16, tab_size)
                io.bytes(len(tab_data), tab_data)
        else:
            assert isinstance(io, BitReader)
            self.tabs = []
            while io.bs.remaining() >= STASH_TAB_HEADER_SIZE * 8:
                try:
                    tab = StashTab()
                    tab.codec(io, version, data=data)
                    self.tabs.append(tab)
                except ValueError:
                    break
                except Exception as e:
                    import logging

                    logging.warning(f"Failed to parse stash tab #{len(self.tabs)}: {e}")
                    break

    def deserialize(self, bs: Any, version: int | None = None, data: Any = None) -> None:
        reader = bs if isinstance(bs, BitIO) else BitReader(bs)
        self.codec(reader, version, data=data)

    def serialize(self, bs: Any, version: int | None = None, data: Any = None) -> None:
        writer = bs if isinstance(bs, BitIO) else BitWriter(bs)
        self.codec(writer, version, data=data)

    def get_tab_count(self) -> int:
        return len(self.tabs)

    def get_tab(self, index: int) -> StashTab | None:
        if 0 <= index < len(self.tabs):
            return self.tabs[index]
        return None

    def get_tab_items(self, index: int) -> list[Any]:
        tab = self.get_tab(index)
        if tab and tab.items:
            return tab.items.items
        return []

    def get_tab_gold(self, index: int) -> int:
        tab = self.get_tab(index)
        return tab.gold if tab else 0
