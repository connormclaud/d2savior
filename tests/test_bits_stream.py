import unittest

import pytest

from core.ibitstream import IBitStream


class TestInBitsStream(unittest.TestCase):
    def test_read_byte(self):
        data = b"\x01\x02\x03"
        bs = IBitStream(data)
        self.assertEqual(bs.read_byte(), 0x01)
        self.assertEqual(bs.read_byte(), 0x02)
        self.assertEqual(bs.read_byte(), 0x03)
        with pytest.raises(ValueError, match="not enough bits remaining"):
            bs.read_byte()

    def test_read_word(self):
        data = b"\x01\x02\x03\x04"
        bs = IBitStream(data)
        self.assertEqual(bs.read_word(), 0x0201)
        self.assertEqual(bs.read_word(), 0x0403)
        with pytest.raises(ValueError, match="not enough bits remaining"):
            bs.read_word()

    def test_read_dword(self):
        data = b"\x01\x02\x03\x04\x05\x06\x07\x08"
        bs = IBitStream(data)
        self.assertEqual(bs.read_dword(), 0x04030201)
        self.assertEqual(bs.read_dword(), 0x08070605)
        with pytest.raises(ValueError, match="not enough bits remaining"):
            bs.read_dword()

    def test_read_bits(self):
        data = b"\xab"
        bs = IBitStream(data)
        self.assertEqual(bs.read_bits(3), 0x03)
        self.assertEqual(bs.read_bits(5), 0x15)
        bs.align_byte()
        self.assertEqual(bs.bytes_pos, 1)
        self.assertEqual(bs.bits_pos, 0)


if __name__ == "__main__":
    unittest.main()
