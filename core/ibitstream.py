"""Little endian binary input stream reading data from bytes as bits."""

from collections.abc import Buffer

type BitStreamData = Buffer


class IBitStream:
    """Little endian binary input stream, reads data from bytes as bits."""

    def __init__(self, data: BitStreamData | None = None) -> None:
        self._data: bytes = b""
        self.data: BitStreamData | None = None
        self._offset: int = 0
        if data is not None:
            self.set_data(data)

    def __repr__(self) -> str:
        return f"<IBitStream offset={self._offset} len={len(self)}>"

    def __str__(self) -> str:
        return self.__repr__()

    def __len__(self) -> int:
        return len(self._data) * 8

    def to_bit_string(self) -> str:
        """Construct the ASCII bit string representation ('0' and '1')."""
        return "".join([f"{b:08b}"[::-1] for b in self._data])

    def set_data(self, data: BitStreamData):
        self.data = data
        self._data = bytes(data) if data is not None else b""
        self._offset = 0

    @property
    def bytes_pos(self) -> int:
        return self._offset // 8

    @bytes_pos.setter
    def bytes_pos(self, value: int):
        self._offset = value * 8 + self.bits_pos

    @property
    def bits_pos(self) -> int:
        return self._offset % 8

    @bits_pos.setter
    def bits_pos(self, value: int):
        self._offset = (self._offset // 8) * 8 + value

    def seek_back_bytes(self, num_bytes: int):
        self._offset -= num_bytes * 8

    def get_offset(self) -> int:
        return self._offset

    def remaining(self) -> int:
        return len(self._data) * 8 - self._offset

    def is_end(self) -> bool:
        return self._offset >= len(self._data) * 8

    def read_bits(self, num_bits: int) -> int:
        if num_bits == 0:
            return 0
        if num_bits < 0:
            raise ValueError("num_bits must be >= 0")
        if self._offset + num_bits > len(self._data) * 8:
            raise ValueError("not enough bits remaining")

        byte_start = self._offset >> 3
        bit_shift = self._offset & 7
        byte_end = (self._offset + num_bits + 7) >> 3
        chunk = self._data[byte_start:byte_end]
        val = int.from_bytes(chunk, "little") >> bit_shift
        self._offset += num_bits
        return val & ((1 << num_bits) - 1)

    read = read_bits

    def read_byte(self) -> int:
        return self.read_bits(8)

    def read_word(self) -> int:
        return self.read_bits(16)

    def read_dword(self) -> int:
        return self.read_bits(32)

    def read_string(self, length: int) -> str:
        chars = []
        for _ in range(length):
            chars.append(chr(self.read_bits(8)))
        return "".join(chars)

    def peek(self, num_bits: int) -> int:
        if num_bits == 0:
            return 0
        if num_bits < 0:
            raise ValueError("num_bits must be >= 0")
        if self._offset + num_bits > len(self._data) * 8:
            raise ValueError("not enough bits remaining")

        byte_start = self._offset >> 3
        bit_shift = self._offset & 7
        byte_end = (self._offset + num_bits + 7) >> 3
        chunk = self._data[byte_start:byte_end]
        val = int.from_bytes(chunk, "little") >> bit_shift
        return val & ((1 << num_bits) - 1)

    def skip(self, num_bits: int):
        if num_bits < 0:
            raise ValueError("num_bits must be >= 0")
        if self._offset + num_bits > len(self._data) * 8:
            raise ValueError("not enough bits remaining")
        self._offset += num_bits

    def align_byte(self):
        if self.bits_pos > 0:
            self._offset = (self._offset // 8 + 1) * 8
