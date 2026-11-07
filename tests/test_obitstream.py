import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from d2savior.core.obitstream import OBitStream


class MemWriter:
    def __init__(self):
        self.buf = bytearray()

    def write(self, bytes):
        self.buf.extend(bytes)

    def __str__(self):
        return " ".join(map("{0:02x}".format, self.buf))


class TestOBitStream:
    def setup_method(self):
        self.stream = OBitStream()

    def test_append_empty(self):
        assert self.stream.to_bit_string() == ""
        assert str(self.stream) == "<OBitStream len=0>"
        assert self.stream.to_hex_string() == ""

    def test_append_zero_bit(self):
        self.stream.append(0xF, 0)
        assert self.stream.to_bit_string() == ""
        assert self.stream.to_hex_string() == ""

    def test_append_one_bit(self):
        self.stream.append(1, 1)
        assert self.stream.to_bit_string() == "1"
        assert str(self.stream) == "<OBitStream len=1>"
        assert self.stream.to_hex_string() == "01"

    def test_append_one_bit_extracted(self):
        self.stream.append(0xF, 1)
        assert self.stream.to_bit_string() == "1"
        assert self.stream.to_hex_string() == "01"

    def test_append_8_bits(self):
        self.stream.append(0x76, 8)
        assert "01110110"[::-1] == self.stream.to_bit_string()
        assert self.stream.to_hex_string() == "76"

    def test_append_9_bits(self):
        self.stream.append(0x176, 9)
        assert "101110110"[::-1] == self.stream.to_bit_string()
        assert self.stream.to_hex_string() == "76 01"

    def test_append_9_bits_extracted(self):
        self.stream.append(0x776, 9)
        assert "101110110"[::-1] == self.stream.to_bit_string()
        assert self.stream.to_hex_string() == "76 01"

    def test_append_32bits(self):
        self.stream.append(0x1F1F2F4F8, 32)
        assert "11110001111100101111010011111000"[::-1] == self.stream.to_bit_string()
        assert self.stream.to_hex_string() == "f8 f4 f2 f1"

    def test_append_3_2(self):
        self.stream.append(3, 3)
        self.stream.append(1, 2)
        assert "01011"[::-1] == self.stream.to_bit_string()
        assert self.stream.to_hex_string() == "0b"

    def test_append_3_6_4(self):
        self.stream.append(int("001", 2), 3)
        self.stream.append(int("000011", 2), 6)
        self.stream.append(int("0111", 2), 4)
        assert "0111000011001"[::-1] == self.stream.to_bit_string()
        assert self.stream.to_hex_string() == "19 0e"

    def test_append_string(self):
        self.stream.write_string("012 ")
        assert self.stream.to_hex_string() == "30 31 32 20"
        w = MemWriter()
        self.stream.write_bytes_to(w)
        assert str(w) == "30 31 32 20"

    def test_write_bytes(self):
        self.stream.append(int("1110101", 2), 7)
        assert self.stream.to_hex_string() == "75"
        w = MemWriter()
        self.stream.write_bytes_to(w)
        assert str(w) == "75"

    def test_write_bytes_long(self):
        self.stream.append(int("10100001111", 2), 11)
        assert self.stream.to_hex_string() == "0f 05"
        w = MemWriter()
        self.stream.write_bytes_to(w)
        assert str(w) == "0f 05"


class TestOBitStreamNewInterface:
    def setup_method(self):
        self.stream = OBitStream()

    def test_bits_pos(self):
        assert self.stream.bits_pos == 0
        self.stream.append(0x76, 8)
        assert self.stream.bits_pos == 0
        self.stream.append(0x01, 3)
        assert self.stream.bits_pos == 3

    def test_write_bits(self):
        self.stream.write_bits(8, 0x76)
        assert self.stream.to_hex_string() == "76"

    def test_write_byte(self):
        self.stream.write_byte(0x76)
        assert self.stream.to_hex_string() == "76"
        assert self.stream.bits_pos == 0

    def test_write_word(self):
        self.stream.write_word(0x0176)
        assert self.stream.to_hex_string() == "76 01"

    def test_write_dword(self):
        self.stream.write_dword(0x03020176)
        assert self.stream.to_hex_string() == "76 01 02 03"

    def test_align_byte(self):
        self.stream.append(0x01, 3)
        assert self.stream.bits_pos == 3
        self.stream.align_byte()
        assert self.stream.bits_pos == 0
        assert self.stream.to_hex_string() == "01"

    def test_get_data(self):
        self.stream.append(0x76, 8)
        self.stream.append(0x01, 8)
        data = self.stream.get_data()
        assert data == b"v\x01"

    def test_write_bits_multiple(self):
        self.stream.write_bits(3, 3)
        self.stream.write_bits(2, 1)
        self.stream.write_bits(5, 0x1F)
        assert self.stream.to_hex_string() == "eb 03"

    def test_snake_case_aliases(self):
        self.stream.write_string("OK")
        assert self.stream.to_hex_string() == "4f 4b"
        assert self.stream.get_byte_list() == [79, 75]
        assert self.stream.get_data() == b"OK"
