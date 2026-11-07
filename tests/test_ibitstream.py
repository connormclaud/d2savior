import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.ibitstream import IBitStream


class TestIBitStream(unittest.TestCase):
    def test_init_empty(self):
        stream = IBitStream()
        self.assertEqual("", stream.to_bit_string())
        self.assertEqual("<IBitStream offset=0 len=0>", str(stream))
        self.assertEqual(0, len(stream))
        self.assertEqual(0, stream.getOffset())
        self.assertEqual(0, stream.remaining())

    def test_init_with_data(self):
        stream = IBitStream(bytearray([0x76]))
        self.assertEqual("01110110"[::-1], stream.to_bit_string())
        self.assertEqual("<IBitStream offset=0 len=8>", str(stream))
        self.assertEqual(8, len(stream))
        self.assertEqual(0, stream.getOffset())
        self.assertEqual(8, stream.remaining())

    def test_read_zero_bit(self):
        stream = IBitStream(bytearray([0x76]))
        result = stream.read(0)
        self.assertEqual(0, result)
        self.assertEqual(0, stream.getOffset())

    def test_read_one_bit(self):
        stream = IBitStream(bytearray([0x01]))
        result = stream.read(1)
        self.assertEqual(1, result)
        self.assertEqual(1, stream.getOffset())
        self.assertEqual(7, stream.remaining())

    def test_read_one_bit_from_value(self):
        stream = IBitStream(bytearray([0x0F]))
        result = stream.read(1)
        self.assertEqual(1, result)
        self.assertEqual(1, stream.getOffset())

    def test_read_8_bits(self):
        stream = IBitStream(bytearray([0x76]))
        result = stream.read(8)
        self.assertEqual(0x76, result)
        self.assertEqual(8, stream.getOffset())
        self.assertTrue(stream.isEnd())

    def test_read_9_bits(self):
        stream = IBitStream(bytearray([0x76, 0x01]))
        result = stream.read(9)
        self.assertEqual(0x176, result)
        self.assertEqual(9, stream.getOffset())

    def test_read_9_bits_extracted(self):
        stream = IBitStream(bytearray([0x76, 0x07]))
        result = stream.read(9)
        self.assertEqual(0x176, result)

    def test_read_32bits(self):
        stream = IBitStream(bytearray([0xF8, 0xF4, 0xF2, 0xF1]))
        result = stream.read(32)
        self.assertEqual(0xF1F2F4F8, result)

    def test_read_multiple(self):
        stream = IBitStream(bytearray([0x0B]))
        result1 = stream.read(3)
        result2 = stream.read(2)
        self.assertEqual(3, result1)
        self.assertEqual(1, result2)
        self.assertEqual(5, stream.getOffset())

    def test_read_3_6_4(self):
        stream = IBitStream(bytearray([0x19, 0x0E]))
        result1 = stream.read(3)
        result2 = stream.read(6)
        result3 = stream.read(4)
        self.assertEqual(int("001", 2), result1)
        self.assertEqual(int("000011", 2), result2)
        self.assertEqual(int("0111", 2), result3)

    def test_read_string(self):
        stream = IBitStream(bytearray([0x30, 0x31, 0x32, 0x20]))
        result = stream.readString(4)
        self.assertEqual("012 ", result)
        self.assertEqual(32, stream.getOffset())

    def test_peek(self):
        stream = IBitStream(bytearray([0x76]))
        result = stream.peek(8)
        self.assertEqual(0x76, result)
        self.assertEqual(0, stream.getOffset())

    def test_peek_partial(self):
        stream = IBitStream(bytearray([0x76]))
        stream.read(4)
        result = stream.peek(4)
        self.assertEqual(7, result)
        self.assertEqual(4, stream.getOffset())

    def test_skip(self):
        stream = IBitStream(bytearray([0x76, 0x01]))
        stream.skip(9)
        self.assertEqual(9, stream.getOffset())
        result = stream.read(7)
        self.assertEqual(0, result)

    def test_is_end(self):
        stream = IBitStream(bytearray([0x76]))
        self.assertFalse(stream.isEnd())
        stream.read(8)
        self.assertTrue(stream.isEnd())

    def test_not_enough_bits(self):
        stream = IBitStream(bytearray([0x76]))
        with self.assertRaises(ValueError):
            stream.read(9)

    def test_skip_not_enough_bits(self):
        stream = IBitStream(bytearray([0x76]))
        with self.assertRaises(ValueError):
            stream.skip(9)

    def test_peek_not_enough_bits(self):
        stream = IBitStream(bytearray([0x76]))
        with self.assertRaises(ValueError):
            stream.peek(9)

    def test_negative_bits(self):
        stream = IBitStream(bytearray([0x76]))
        with self.assertRaises(ValueError):
            stream.read(-1)

    def test_set_data(self):
        stream = IBitStream()
        stream.setData(bytearray([0x76]))
        self.assertEqual(0x76, stream.read(8))

    def test_set_data_resets_offset(self):
        stream = IBitStream(bytearray([0x76]))
        stream.read(4)
        self.assertEqual(4, stream.getOffset())
        stream.setData(bytearray([0x01]))
        self.assertEqual(0, stream.getOffset())


class TestIBitStreamNewInterface(unittest.TestCase):
    def test_bytes_pos_property(self):
        stream = IBitStream(bytearray([0x76, 0x01, 0x02]))
        self.assertEqual(0, stream.bytes_pos)
        stream.read(8)
        self.assertEqual(1, stream.bytes_pos)
        stream.read(4)
        self.assertEqual(1, stream.bytes_pos)
        stream.read(4)
        self.assertEqual(2, stream.bytes_pos)

    def test_bits_pos_property(self):
        stream = IBitStream(bytearray([0x76, 0x01]))
        self.assertEqual(0, stream.bits_pos)
        stream.read(3)
        self.assertEqual(3, stream.bits_pos)
        stream.read(5)
        self.assertEqual(0, stream.bits_pos)

    def test_bytes_pos_setter(self):
        stream = IBitStream(bytearray([0x76, 0x01, 0x02, 0x03]))
        stream.bytes_pos = 2
        self.assertEqual(2, stream.bytes_pos)
        result = stream.read(8)
        self.assertEqual(0x02, result)

    def test_bits_pos_setter(self):
        stream = IBitStream(bytearray([0x76, 0x01]))
        stream.read(8)
        stream.bits_pos = 4
        self.assertEqual(1, stream.bytes_pos)
        self.assertEqual(4, stream.bits_pos)

    def test_read_byte(self):
        stream = IBitStream(bytearray([0x76, 0x01]))
        result = stream.read_byte()
        self.assertEqual(0x76, result)
        self.assertEqual(1, stream.bytes_pos)

    def test_read_word(self):
        stream = IBitStream(bytearray([0x76, 0x01, 0x02, 0x03]))
        result = stream.read_word()
        self.assertEqual(0x0176, result)
        self.assertEqual(2, stream.bytes_pos)

    def test_read_dword(self):
        stream = IBitStream(bytearray([0x76, 0x01, 0x02, 0x03]))
        result = stream.read_dword()
        self.assertEqual(0x03020176, result)
        self.assertEqual(4, stream.bytes_pos)

    def test_read_bits_alias(self):
        stream = IBitStream(bytearray([0x76]))
        result = stream.read_bits(8)
        self.assertEqual(0x76, result)

    def test_align_byte(self):
        stream = IBitStream(bytearray([0x76, 0x01]))
        stream.read(5)
        self.assertEqual(5, stream.bits_pos)
        stream.align_byte()
        self.assertEqual(0, stream.bits_pos)
        self.assertEqual(1, stream.bytes_pos)

    def test_seek_back_bytes(self):
        stream = IBitStream(b"\x76\x01\x02\x03")
        stream.read(24)
        self.assertEqual(3, stream.bytes_pos)
        stream.seek_back_bytes(2)
        self.assertEqual(1, stream.bytes_pos)
        self.assertEqual(0x01, stream.read_byte())

    def test_snake_case_aliases(self):
        stream = IBitStream(b"v\x01")
        self.assertEqual(0, stream.get_offset())
        self.assertFalse(stream.is_end())
        self.assertEqual("v", stream.read_string(1))
        self.assertEqual(8, stream.get_offset())

    # test_good method removed since IBitStream no longer has good() method


class TestIBitStreamOBitStreamRoundTrip(unittest.TestCase):
    def test_roundtrip_single_byte(self):
        from core.obitstream import OBitStream

        ostream = OBitStream()
        ostream.append(0x76, 8)

        istream = IBitStream(bytearray(ostream.getByteList()))
        result = istream.read(8)
        self.assertEqual(0x76, result)

    def test_roundtrip_multiple_values(self):
        from core.obitstream import OBitStream

        ostream = OBitStream()
        ostream.append(3, 3)
        ostream.append(1, 2)
        ostream.append(0x1F, 5)

        istream = IBitStream(bytearray(ostream.getByteList()))
        self.assertEqual(3, istream.read(3))
        self.assertEqual(1, istream.read(2))
        self.assertEqual(0x1F, istream.read(5))

    def test_roundtrip_string(self):
        from core.obitstream import OBitStream

        ostream = OBitStream()
        ostream.appendString("AB")

        istream = IBitStream(bytearray(ostream.getByteList()))
        self.assertEqual("AB", istream.readString(2))

    def test_roundtrip_9_bits(self):
        from core.obitstream import OBitStream

        ostream = OBitStream()
        ostream.append(0x176, 9)

        istream = IBitStream(bytearray(ostream.getByteList()))
        self.assertEqual(0x176, istream.read(9))

    def test_roundtrip_32_bits(self):
        from core.obitstream import OBitStream

        ostream = OBitStream()
        ostream.append(0xF1F2F4F8, 32)

        istream = IBitStream(bytearray(ostream.getByteList()))
        self.assertEqual(0xF1F2F4F8, istream.read(32))


if __name__ == "__main__":
    unittest.main()
