"""Unified BitIO abstraction for symmetrical reading and writing of bitstreams."""

import builtins
from abc import ABC, abstractmethod

from d2savior.core.ibitstream import IBitStream
from d2savior.core.obitstream import OBitStream


class BitIO(ABC):
    """Abstract bidirectional bit-level stream interface."""

    @property
    @abstractmethod
    def is_writing(self) -> bool:
        """Return True if writing to stream, False if reading."""
        ...

    @property
    def is_reading(self) -> bool:
        """Return True if reading from stream, False if writing."""
        return not self.is_writing

    @abstractmethod
    def bits(self, count: int, value: int = 0) -> int:
        """Read count bits or write value with count bits."""
        ...

    @abstractmethod
    def bit(self, value: bool = False) -> bool:
        """Read 1 bit as bool or write bool as 1 bit."""
        ...

    @abstractmethod
    def byte(self, value: int = 0) -> int:
        """Read or write an 8-bit byte."""
        ...

    @abstractmethod
    def word(self, value: int = 0) -> int:
        """Read or write a 16-bit word."""
        ...

    @abstractmethod
    def dword(self, value: int = 0) -> int:
        """Read or write a 32-bit dword."""
        ...

    @abstractmethod
    def qword(self, value: int = 0) -> int:
        """Read or write a 64-bit qword."""
        ...

    @abstractmethod
    def bytes(self, count: int, value: builtins.bytes | bytearray = b"") -> builtins.bytes:
        """Read count bytes or write value bytes."""
        ...

    @abstractmethod
    def align_byte(self) -> None:
        """Align bit position to next byte boundary."""
        ...

    @abstractmethod
    def get_offset(self) -> int:
        """Return current bit offset in stream."""
        ...

    @abstractmethod
    def seek_back_bytes(self, num_bytes: int) -> None:
        """Rewind the stream position by num_bytes bytes."""
        ...

    @abstractmethod
    def seek_bits(self, bit_offset: int) -> None:
        """Seek stream position to absolute bit_offset."""
        ...

    @abstractmethod
    def seek_bytes(self, byte_offset: int) -> None:
        """Seek stream position to absolute byte_offset."""
        ...

    def opt_bits(self, count: int, value: int | None = None) -> int | None:
        """Read/write a 1-bit presence flag followed by count bits if present."""
        if self.is_writing:
            present = value is not None
            self.bit(present)
            if present:
                self.bits(count, value)
            return value
        else:
            present = self.bit()
            if present:
                return self.bits(count)
            return None

    def huffman_char(self, ch: int = 0) -> int:
        """Read or write a single Huffman-coded ASCII character."""
        from d2savior.core.huffman import DEFAULT_HUFFMAN

        if self.is_writing:
            DEFAULT_HUFFMAN.write_char(self, ch)
            return ch
        else:
            return DEFAULT_HUFFMAN.read_char(self)


class BitReader(BitIO):
    """BitIO reader wrapping an IBitStream."""

    def __init__(self, bs: IBitStream) -> None:
        self.bs = bs

    @property
    def is_writing(self) -> bool:
        return False

    def bits(self, count: int, value: int = 0) -> int:
        if count == 0:
            return 0
        return self.bs.read_bits(count)

    read_bits = bits

    def bit(self, value: bool = False) -> bool:
        return self.bs.read_bits(1) != 0

    def byte(self, value: int = 0) -> int:
        return self.bs.read_byte()

    def word(self, value: int = 0) -> int:
        return self.bs.read_word()

    def dword(self, value: int = 0) -> int:
        return self.bs.read_dword()

    def qword(self, value: int = 0) -> int:
        return self.bs.read_bits(64)

    def bytes(self, count: int, value: builtins.bytes | bytearray = b"") -> builtins.bytes:
        return self.bs.read_bytes(count)

    def align_byte(self) -> None:
        self.bs.align_byte()

    def get_offset(self) -> int:
        return self.bs.get_offset()

    def seek_back_bytes(self, num_bytes: int) -> None:
        self.bs.seek_back_bytes(num_bytes)

    def seek_bits(self, bit_offset: int) -> None:
        self.bs.seek_bits(bit_offset)

    def seek_bytes(self, byte_offset: int) -> None:
        self.bs.seek_bytes(byte_offset)


class BitWriter(BitIO):
    """BitIO writer wrapping an OBitStream."""

    def __init__(self, bs: OBitStream) -> None:
        self.bs = bs

    @property
    def is_writing(self) -> bool:
        return True

    def bits(self, count: int, value: int = 0) -> int:
        if count == 0:
            return 0
        val = value
        remaining = count
        while remaining > 32:
            self.bs.write_bits(32, val & 0xFFFFFFFF)
            val >>= 32
            remaining -= 32
        self.bs.write_bits(remaining, val)
        return value

    def write_bits(self, count: int, value: int) -> None:
        self.bits(count, value)

    def bit(self, value: bool = False) -> bool:
        self.bs.write_bits(1, 1 if value else 0)
        return value

    def byte(self, value: int = 0) -> int:
        self.bs.write_byte(value)
        return value

    def word(self, value: int = 0) -> int:
        self.bs.write_word(value)
        return value

    def dword(self, value: int = 0) -> int:
        self.bs.write_dword(value)
        return value

    def qword(self, value: int = 0) -> int:
        self.bits(64, value)
        return value

    def bytes(self, count: int, value: builtins.bytes | bytearray = b"") -> builtins.bytes:
        val = builtins.bytes(value) if value is not None else b""
        val = val.ljust(count, b"\x00")[:count]
        self.bs.write_bytes(val)
        return val

    def align_byte(self) -> None:
        self.bs.align_byte()

    def get_offset(self) -> int:
        return len(self.bs)

    def seek_back_bytes(self, num_bytes: int) -> None:
        raise NotImplementedError("Cannot seek back in BitWriter")

    def seek_bits(self, bit_offset: int) -> None:
        raise NotImplementedError("Cannot seek in BitWriter")

    def seek_bytes(self, byte_offset: int) -> None:
        raise NotImplementedError("Cannot seek in BitWriter")
