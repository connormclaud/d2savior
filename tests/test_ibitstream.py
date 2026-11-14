import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from d2savior.core.ibitstream import IBitStream


class TestIBitStream:
    def test_init_empty(self):
        stream = IBitStream()
        assert stream.to_bit_string() == ""
        assert str(stream) == "<IBitStream offset=0 len=0>"
        assert len(stream) == 0
        assert stream.get_offset() == 0
        assert stream.remaining() == 0

    def test_init_with_data(self):
        stream = IBitStream(bytearray([0x76]))
        assert "01110110"[::-1] == stream.to_bit_string()
        assert str(stream) == "<IBitStream offset=0 len=8>"
        assert len(stream) == 8
        assert stream.get_offset() == 0
        assert stream.remaining() == 8

    def test_read_zero_bit(self):
        stream = IBitStream(bytearray([0x76]))
        result = stream.read(0)
        assert result == 0
        assert stream.get_offset() == 0

    def test_read_one_bit(self):
        stream = IBitStream(bytearray([0x01]))
        result = stream.read(1)
        assert result == 1
        assert stream.get_offset() == 1
        assert stream.remaining() == 7

    def test_read_one_bit_from_value(self):
        stream = IBitStream(bytearray([0x0F]))
        result = stream.read(1)
        assert result == 1
        assert stream.get_offset() == 1

    def test_read_8_bits(self):
        stream = IBitStream(bytearray([0x76]))
        result = stream.read(8)
        assert result == 118
        assert stream.get_offset() == 8
        assert stream.is_end()

    def test_read_9_bits(self):
        stream = IBitStream(bytearray([0x76, 0x01]))
        result = stream.read(9)
        assert result == 374
        assert stream.get_offset() == 9

    def test_read_9_bits_extracted(self):
        stream = IBitStream(bytearray([0x76, 0x07]))
        result = stream.read(9)
        assert result == 374

    def test_read_32bits(self):
        stream = IBitStream(bytearray([0xF8, 0xF4, 0xF2, 0xF1]))
        result = stream.read(32)
        assert result == 4059231480

    def test_read_multiple(self):
        stream = IBitStream(bytearray([0x0B]))
        result1 = stream.read(3)
        result2 = stream.read(2)
        assert result1 == 3
        assert result2 == 1
        assert stream.get_offset() == 5

    def test_read_3_6_4(self):
        stream = IBitStream(bytearray([0x19, 0x0E]))
        result1 = stream.read(3)
        result2 = stream.read(6)
        result3 = stream.read(4)
        assert int("001", 2) == result1
        assert int("000011", 2) == result2
        assert int("0111", 2) == result3

    def test_read_string(self):
        stream = IBitStream(bytearray([0x30, 0x31, 0x32, 0x20]))
        result = stream.read_string(4)
        assert result == "012 "
        assert stream.get_offset() == 32

    def test_peek(self):
        stream = IBitStream(bytearray([0x76]))
        result = stream.peek(8)
        assert result == 118
        assert stream.get_offset() == 0

    def test_peek_partial(self):
        stream = IBitStream(bytearray([0x76]))
        stream.read(4)
        result = stream.peek(4)
        assert result == 7
        assert stream.get_offset() == 4

    def test_skip(self):
        stream = IBitStream(bytearray([0x76, 0x01]))
        stream.skip(9)
        assert stream.get_offset() == 9
        result = stream.read(7)
        assert result == 0

    def test_is_end(self):
        stream = IBitStream(bytearray([0x76]))
        assert not stream.is_end()
        stream.read(8)
        assert stream.is_end()

    def test_not_enough_bits(self):
        stream = IBitStream(bytearray([0x76]))
        with pytest.raises(ValueError, match="not enough bits remaining"):
            stream.read(9)

    def test_skip_not_enough_bits(self):
        stream = IBitStream(bytearray([0x76]))
        with pytest.raises(ValueError, match="not enough bits remaining"):
            stream.skip(9)

    def test_peek_not_enough_bits(self):
        stream = IBitStream(bytearray([0x76]))
        with pytest.raises(ValueError, match="not enough bits remaining"):
            stream.peek(9)

    def test_negative_bits(self):
        stream = IBitStream(bytearray([0x76]))
        with pytest.raises(ValueError, match="num_bits must be >= 0"):
            stream.read(-1)

    def test_set_data(self):
        stream = IBitStream()
        stream.set_data(bytearray([0x76]))
        assert stream.read(8) == 118

    def test_set_data_resets_offset(self):
        stream = IBitStream(bytearray([0x76]))
        stream.read(4)
        assert stream.get_offset() == 4
        stream.set_data(bytearray([0x01]))
        assert stream.get_offset() == 0


class TestIBitStreamNewInterface:
    def test_bytes_pos_property(self):
        stream = IBitStream(bytearray([0x76, 0x01, 0x02]))
        assert stream.bytes_pos == 0
        stream.read(8)
        assert stream.bytes_pos == 1
        stream.read(4)
        assert stream.bytes_pos == 1
        stream.read(4)
        assert stream.bytes_pos == 2

    def test_bits_pos_property(self):
        stream = IBitStream(bytearray([0x76, 0x01]))
        assert stream.bits_pos == 0
        stream.read(3)
        assert stream.bits_pos == 3
        stream.read(5)
        assert stream.bits_pos == 0

    def test_bytes_pos_setter(self):
        stream = IBitStream(bytearray([0x76, 0x01, 0x02, 0x03]))
        stream.bytes_pos = 2
        assert stream.bytes_pos == 2
        result = stream.read(8)
        assert result == 2

    def test_bits_pos_setter(self):
        stream = IBitStream(bytearray([0x76, 0x01]))
        stream.read(8)
        stream.bits_pos = 4
        assert stream.bytes_pos == 1
        assert stream.bits_pos == 4

    def test_read_byte(self):
        stream = IBitStream(bytearray([0x76, 0x01]))
        result = stream.read_byte()
        assert result == 118
        assert stream.bytes_pos == 1

    def test_read_word(self):
        stream = IBitStream(bytearray([0x76, 0x01, 0x02, 0x03]))
        result = stream.read_word()
        assert result == 374
        assert stream.bytes_pos == 2

    def test_read_dword(self):
        stream = IBitStream(bytearray([0x76, 0x01, 0x02, 0x03]))
        result = stream.read_dword()
        assert result == 50463094
        assert stream.bytes_pos == 4

    def test_read_bits_alias(self):
        stream = IBitStream(bytearray([0x76]))
        result = stream.read_bits(8)
        assert result == 118

    def test_align_byte(self):
        stream = IBitStream(bytearray([0x76, 0x01]))
        stream.read(5)
        assert stream.bits_pos == 5
        stream.align_byte()
        assert stream.bits_pos == 0
        assert stream.bytes_pos == 1

    def test_seek_back_bytes(self):
        stream = IBitStream(b"\x76\x01\x02\x03")
        stream.read(24)
        assert stream.bytes_pos == 3
        stream.seek_back_bytes(2)
        assert stream.bytes_pos == 1
        assert stream.read_byte() == 1

    def test_seek_bits_and_seek_bytes(self):
        from d2savior.core.bit_io import BitReader, BitWriter
        from d2savior.core.obitstream import OBitStream

        stream = IBitStream(b"\x10\x20\x30\x40")
        reader = BitReader(stream)
        assert reader.remaining_bits() == 32
        reader.bits(5)
        assert reader.remaining_bits() == 27
        reader.seek_bytes(2)
        assert reader.remaining_bits() == 16
        assert reader.get_offset() == 16
        assert reader.byte() == 0x30

        reader.seek_bits(8)
        assert reader.get_offset() == 8
        assert reader.byte() == 0x20

        # Seeking to exact EOF is allowed
        reader.seek_bytes(4)
        assert reader.remaining_bits() == 0
        assert stream.is_end()

        with pytest.raises(ValueError, match="out of range"):
            reader.seek_bits(-1)
        with pytest.raises(ValueError, match="out of range"):
            reader.seek_bytes(5)

        writer = BitWriter(OBitStream())
        with pytest.raises(NotImplementedError):
            writer.seek_bits(0)
        with pytest.raises(NotImplementedError):
            writer.seek_bytes(0)
        with pytest.raises(NotImplementedError):
            writer.remaining_bits()

    def test_snake_case_aliases(self):
        stream = IBitStream(b"v\x01")
        assert stream.get_offset() == 0
        assert not stream.is_end()
        assert stream.read_string(1) == "v"
        assert stream.get_offset() == 8

    # test_good method removed since IBitStream no longer has good() method


class TestIBitStreamOBitStreamRoundTrip:
    def test_roundtrip_single_byte(self):
        from d2savior.core.obitstream import OBitStream

        ostream = OBitStream()
        ostream.append(0x76, 8)

        istream = IBitStream(bytearray(ostream.get_byte_list()))
        result = istream.read(8)
        assert result == 118

    def test_roundtrip_multiple_values(self):
        from d2savior.core.obitstream import OBitStream

        ostream = OBitStream()
        ostream.append(3, 3)
        ostream.append(1, 2)
        ostream.append(0x1F, 5)

        istream = IBitStream(bytearray(ostream.get_byte_list()))
        assert istream.read(3) == 3
        assert istream.read(2) == 1
        assert istream.read(5) == 31

    def test_roundtrip_string(self):
        from d2savior.core.obitstream import OBitStream

        ostream = OBitStream()
        ostream.write_string("AB")

        istream = IBitStream(bytearray(ostream.get_byte_list()))
        assert istream.read_string(2) == "AB"

    def test_roundtrip_9_bits(self):
        from d2savior.core.obitstream import OBitStream

        ostream = OBitStream()
        ostream.append(0x176, 9)

        istream = IBitStream(bytearray(ostream.get_byte_list()))
        assert istream.read(9) == 374

    def test_roundtrip_32_bits(self):
        from d2savior.core.obitstream import OBitStream

        ostream = OBitStream()
        ostream.append(0xF1F2F4F8, 32)

        istream = IBitStream(bytearray(ostream.get_byte_list()))
        assert istream.read(32) == 4059231480
