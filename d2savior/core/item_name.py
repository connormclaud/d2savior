"""Item name structures (LongName for Rare/Crafted items) and Gold quantity."""

from typing import TYPE_CHECKING

from d2savior.core.bit_io import BitIO, BitReader, BitWriter

if TYPE_CHECKING:
    from d2savior.core.ibitstream import IBitStream
    from d2savior.core.obitstream import OBitStream


class LongName:
    """Rare and crafted item affix name structure."""

    def __init__(self) -> None:
        self.name_1: int = 0
        self.name_2: int = 0
        self.pref_1: int | None = None
        self.suff_1: int | None = None
        self.pref_2: int | None = None
        self.suff_2: int | None = None
        self.pref_3: int | None = None
        self.suff_3: int | None = None

    def codec(self, io: BitIO) -> None:
        self.name_1 = io.bits(8, self.name_1)
        self.name_2 = io.bits(8, self.name_2)
        self.pref_1 = io.opt_bits(11, self.pref_1)
        self.suff_1 = io.opt_bits(11, self.suff_1)
        self.pref_2 = io.opt_bits(11, self.pref_2)
        self.suff_2 = io.opt_bits(11, self.suff_2)
        self.pref_3 = io.opt_bits(11, self.pref_3)
        self.suff_3 = io.opt_bits(11, self.suff_3)

    def deserialize(self, bs: IBitStream) -> None:
        self.codec(BitReader(bs))

    def serialize(self, bs: OBitStream) -> None:
        self.codec(BitWriter(bs))


RareName = LongName
CraftName = LongName


class GoldQuantity:
    """Gold pile quantity structure."""

    def __init__(self) -> None:
        self.is_not_gold = False
        self.quantity = 0

    def codec(self, io: BitIO) -> None:
        self.is_not_gold = io.bit(self.is_not_gold)
        self.quantity = io.bits(12, self.quantity)

    def deserialize(self, bs: IBitStream) -> None:
        self.codec(BitReader(bs))

    def serialize(self, bs: OBitStream) -> None:
        self.codec(BitWriter(bs))
