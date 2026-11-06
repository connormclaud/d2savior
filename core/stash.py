from typing import List, Optional, Tuple
from core.obitstream import OBitStream


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
    b'r01 ', b'r02 ', b'r03 ', b'r04 ', b'r05 ', b'r06 ', b'r07 ', b'r08 ', b'r09 ',
    b'r10 ', b'r11 ', b'r12 ', b'r13 ', b'r14 ', b'r15 ', b'r16 ', b'r17 ', b'r18 ',
    b'r19 ', b'r20 ', b'r21 ', b'r22 ', b'r23 ', b'r24 ', b'r25 ', b'r26 ', b'r27 ',
    b'r28 ', b'r29 ', b'r30 ', b'r31 ', b'r32 ', b'r33 ',
]

GEM_SLOT_ORDER = [
    b'gcv ', b'gcy ', b'gcb ', b'gcg ', b'gcr ', b'gcw ', b'skc ',
    b'gfv ', b'gfy ', b'gfb ', b'gfg ', b'gfr ', b'gfw ', b'skf ',
    b'gsv ', b'gsy ', b'gsb ', b'gsg ', b'gsr ', b'gsw ', b'sku ',
    b'gzv ', b'gly ', b'glb ', b'glg ', b'glr ', b'glw ', b'skl ',
    b'gpv ', b'gpy ', b'gpb ', b'gpg ', b'gpr ', b'gpw ', b'skz ',
]

MATERIAL_SLOT_ORDER = [
    b'rvs ', b'rvl ', b'pk1 ', b'pk2 ', b'pk3 ', b'dhn ', b'bey ', b'mbr ', b'toa ', b'tes ',
    b'ceh ', b'bet ', b'fed ', b'xa1 ', b'xa2 ', b'xa3 ', b'xa4 ', b'xa5 ', b'ua1 ', b'ua2 ',
    b'ua3 ', b'ua4 ', b'ua5 ',
]

RUNE_CODES = {b'r01 ', b'r02 ', b'r03 ', b'r04 ', b'r05 ', b'r06 ', b'r07 ', b'r08 ', b'r09 ',
              b'r10 ', b'r11 ', b'r12 ', b'r13 ', b'r14 ', b'r15 ', b'r16 ', b'r17 ', b'r18 ',
              b'r19 ', b'r20 ', b'r21 ', b'r22 ', b'r23 ', b'r24 ', b'r25 ', b'r26 ', b'r27 ',
              b'r28 ', b'r29 ', b'r30 ', b'r31 ', b'r32 ', b'r33 '}

GEM_CODES = {b'gcv ', b'gfv ', b'gsv ', b'gzv ', b'gpv ',
             b'gcy ', b'gfy ', b'gsy ', b'gly ', b'gpy ',
             b'gcb ', b'gfb ', b'gsb ', b'glb ', b'gpb ',
             b'gcg ', b'gfg ', b'gsg ', b'glg ', b'gpg ',
             b'gcr ', b'gfr ', b'gsr ', b'glr ', b'gpr ',
             b'gcw ', b'gfw ', b'gsw ', b'glw ', b'gpw ',
             b'skc ', b'skf ', b'sku ', b'skl ', b'skz '}

MATERIAL_CODES = {b'rvs ', b'rvl ', b'pk1 ', b'pk2 ', b'pk3 ',
                  b'dhn ', b'bey ', b'mbr ', b'toa ', b'tes ',
                  b'ceh ', b'bet ', b'fed ',
                  b'xa1 ', b'xa2 ', b'xa3 ', b'xa4 ', b'xa5 ',
                  b'ua1 ', b'ua2 ', b'ua3 ', b'ua4 ', b'ua5 '}


def classify_advanced_tab(items) -> int:
    if not items:
        return ADVANCED_SUBTYPE_UNKNOWN
    rune_count = 0
    gem_count = 0
    material_count = 0
    for item in items:
        tn = getattr(item, 'sTypeName', b'')
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
    return max(counts, key=counts.get)


def get_advanced_layout(subtype: int) -> Tuple[int, int]:
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


def compute_advanced_grid(items, subtype: int) -> Tuple[int, int, list]:
    if not items:
        layout = get_advanced_layout(subtype)
        return layout[0], layout[1], get_advanced_slot_order(subtype)

    slot_order = get_advanced_slot_order(subtype)
    base_layout = get_advanced_layout(subtype)
    cols = base_layout[0]

    item_type_set = set()
    for item in items:
        tn = getattr(item, 'sTypeName', b'')
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
    def __init__(self):
        self.StashFormat = 0
        self.ItemFormat = 0
        self.Gold = 0
        self.Season = 0
        self.TabType = STASH_TAB_TYPE_NORMAL
        self.Reserved = b'\x00' * 43
        self.Items = None
        self.Chronicle = None
        self._tab_size = 0

    def deserialize(self, bs, version=None):
        start_pos = bs.bytes_pos

        magic = bs.read_dword()
        if magic != STASH_TAB_MAGIC:
            raise ValueError(f"Invalid stash tab magic: 0x{magic:08X}")

        self.StashFormat = bs.read_dword()
        self.ItemFormat = bs.read_dword()
        self.Gold = bs.read_dword()
        self._tab_size = bs.read_word()
        self.Season = bs.read_word()
        self.TabType = bs.read_byte()
        self.Reserved = bytes(bs.read_byte() for _ in range(43))

        if self.StashFormat < 2:
            self.TabType = STASH_TAB_TYPE_NORMAL

        item_version = version if version else self.ItemFormat

        try:
            if self.TabType == STASH_TAB_TYPE_CHRONICLE:
                self._read_chronicle(bs)
            else:
                from core.item import ItemList
                self.Items = ItemList()
                self.Items.deserialize(bs, item_version)
        except Exception as e:
            import logging
            logging.warning(f"Failed to parse stash tab items (TabType={self.TabType}, "
                            f"ItemFormat={self.ItemFormat:#x}): {e}")

        end_pos = start_pos + self._tab_size
        bs.bytes_pos = end_pos

    def _read_chronicle(self, bs):
        body_size = max(0, self._tab_size - STASH_TAB_HEADER_SIZE)
        self.Chronicle = bytes(bs.read_byte() for _ in range(body_size))

    def serialize(self, bs, version=None):
        item_version = version if version else self.ItemFormat

        bs.write_dword(STASH_TAB_MAGIC)
        bs.write_dword(self.StashFormat)
        bs.write_dword(self.ItemFormat)
        bs.write_dword(self.Gold)
        bs.write_word(0)
        bs.write_word(self.Season)
        bs.write_byte(self.TabType)
        bs.write_bytes(self.Reserved)

        if self.TabType == STASH_TAB_TYPE_CHRONICLE and self.Chronicle:
            bs.write_bytes(self.Chronicle)
        elif self.Items:
            self.Items.serialize(bs, item_version)


class SharedStash:
    def __init__(self):
        self.tabs: List[StashTab] = []
        self.file_path = ""

    def deserialize(self, bs, version=None):
        self.tabs = []
        while bs.remaining() >= STASH_TAB_HEADER_SIZE * 8:
            try:
                tab = StashTab()
                tab.deserialize(bs, version)
                self.tabs.append(tab)
            except ValueError:
                break
            except Exception as e:
                import logging
                logging.warning(f"Failed to parse stash tab #{len(self.tabs)}: {e}")
                break

    def serialize(self, bs, version=None):
        import struct
        for tab in self.tabs:
            tab_bs = OBitStream()
            tab.serialize(tab_bs, version)
            tab_data = bytearray(tab_bs.get_data())
            tab_size = len(tab_data)
            struct.pack_into('<H', tab_data, 16, tab_size)
            bs.write_bytes(tab_data)

    def get_tab_count(self):
        return len(self.tabs)

    def get_tab(self, index):
        if 0 <= index < len(self.tabs):
            return self.tabs[index]
        return None

    def get_tab_items(self, index):
        tab = self.get_tab(index)
        if tab and tab.Items:
            return tab.Items.items
        return []

    def get_tab_gold(self, index):
        tab = self.get_tab(index)
        return tab.Gold if tab else 0
