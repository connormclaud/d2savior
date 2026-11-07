"""Ear item representation."""

from typing import TYPE_CHECKING

from d2savior.core.bit_io import BitIO, BitReader, BitWriter

if TYPE_CHECKING:
    from d2savior.core.ibitstream import IBitStream
    from d2savior.core.obitstream import OBitStream


def is_ptr24_and_above(version: int) -> bool:
    return version >= 0x62


class Ear:
    def __init__(self, name: str = "") -> None:
        self.ear_class = 0
        self.ear_level = 1
        self.ear_name = name

    def codec(self, io: BitIO, version: int) -> None:
        self.ear_class = io.bits(3, self.ear_class)
        self.ear_level = io.bits(7, self.ear_level)
        bits_per_char = 8 if is_ptr24_and_above(version) else 7
        max_len = 15 if not is_ptr24_and_above(version) else 60

        if io.is_writing:
            name_bytes = (
                self.ear_name.encode("utf-8") if isinstance(self.ear_name, str) else self.ear_name
            )
            for c in name_bytes:
                io.bits(bits_per_char, c)
            io.bits(bits_per_char, 0)
        else:
            name_bytes = []
            for _ in range(max_len):
                c = io.bits(bits_per_char)
                if c == 0:
                    break
                name_bytes.append(c)
            try:
                self.ear_name = bytes(name_bytes).decode("utf-8")
            except UnicodeDecodeError:
                self.ear_name = bytes(name_bytes).decode("latin-1", errors="replace")

    def deserialize(self, bs: IBitStream, version: int) -> None:
        self.codec(BitReader(bs), version)

    def serialize(self, bs: OBitStream, version: int) -> None:
        self.codec(BitWriter(bs), version)

    def is_valid(self) -> bool:
        return self.ear_level > 0
