"""Little endian binary output stream writing data as bits."""

from typing import Any

type ByteInput = bytes | bytearray | list[int]


class OBitStream:
    """Little endian binary output stream, represents data in bits."""

    def __init__(self) -> None:
        self._bytes: bytearray = bytearray()
        self._buffer: int = 0
        self.bits_pos: int = 0

    def __repr__(self) -> str:
        return f"<OBitStream len={len(self)}>"

    def __str__(self) -> str:
        return self.__repr__()

    def __len__(self) -> int:
        return len(self._bytes) * 8 + self.bits_pos

    def to_bit_string(self) -> str:
        """Construct the ASCII bit string representation ('0' and '1')."""
        committed = "".join([f"{b:08b}"[::-1] for b in self._bytes])
        if self.bits_pos > 0:
            uncommitted = f"{self._buffer:08b}"[::-1][: self.bits_pos]
            return committed + uncommitted
        return committed

    def get_data(self) -> bytes:
        if self.bits_pos > 0:
            return bytes(self._bytes + bytes([self._buffer & 0xFF]))
        return bytes(self._bytes)

    def get_byte_list(self) -> list[int]:
        return list(self.get_data())

    def to_hex_string(self) -> str:
        return " ".join(f"{b:02x}" for b in self.get_byte_list())

    def write_bits(self, num_bits: int, value: int) -> None:
        if num_bits == 0:
            return
        if num_bits < 0 or num_bits > 32:
            raise ValueError("[0, 32] bits only")

        mask = (1 << num_bits) - 1
        self._buffer |= (value & mask) << self.bits_pos
        self.bits_pos += num_bits

        while self.bits_pos >= 8:
            self._bytes.append(self._buffer & 0xFF)
            self._buffer >>= 8
            self.bits_pos -= 8

    def append(self, value: int, num_bits: int) -> None:
        self.write_bits(num_bits, value)

    def write_byte(self, value: int) -> None:
        self.write_bits(8, value)

    def write_word(self, value: int) -> None:
        self.write_bits(16, value)

    def write_dword(self, value: int) -> None:
        self.write_bits(32, value)

    def write_bytes(self, data: ByteInput) -> None:
        for b in data:
            self.write_bits(8, b)

    def write_string(self, str_value: str) -> None:
        for ch in str_value:
            self.write_bits(8, ord(ch))

    def write_bytes_to(self, writer: Any) -> None:
        writer.write(bytearray(self.get_data()))

    def align_byte(self) -> None:
        if self.bits_pos > 0:
            self._bytes.append(self._buffer & 0xFF)
            self._buffer = 0
            self.bits_pos = 0
