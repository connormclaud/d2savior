import pytest

from core.ibitstream import IBitStream


class TestInBitsStream:
    def test_read_byte(self):
        data = b"\x01\x02\x03"
        bs = IBitStream(data)
        assert bs.read_byte() == 1
        assert bs.read_byte() == 2
        assert bs.read_byte() == 3
        with pytest.raises(ValueError, match="not enough bits remaining"):
            bs.read_byte()

    def test_read_word(self):
        data = b"\x01\x02\x03\x04"
        bs = IBitStream(data)
        assert bs.read_word() == 513
        assert bs.read_word() == 1027
        with pytest.raises(ValueError, match="not enough bits remaining"):
            bs.read_word()

    def test_read_dword(self):
        data = b"\x01\x02\x03\x04\x05\x06\x07\x08"
        bs = IBitStream(data)
        assert bs.read_dword() == 67305985
        assert bs.read_dword() == 134678021
        with pytest.raises(ValueError, match="not enough bits remaining"):
            bs.read_dword()

    def test_read_bits(self):
        data = b"\xab"
        bs = IBitStream(data)
        assert bs.read_bits(3) == 3
        assert bs.read_bits(5) == 21
        bs.align_byte()
        assert bs.bytes_pos == 1
        assert bs.bits_pos == 0
