import pytest

from d2savior.core.ibitstream import IBitStream


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

    def test_read_bytes(self):
        data = b"Hello, World!"
        bs = IBitStream(data)
        assert bs.read_bytes(5) == b"Hello"
        assert bs.read_bytes(2) == b", "
        assert bs.read_bytes(6) == b"World!"
        assert bs.read_bytes(5) == b""


class TestBitIOBytes:
    def test_bit_io_bytes_symmetric(self):
        from d2savior.core.bit_io import BitReader, BitWriter
        from d2savior.core.obitstream import OBitStream

        obs = OBitStream()
        writer = BitWriter(obs)
        assert writer.is_writing is True
        written = writer.bytes(10, b"short")
        assert written == b"short\x00\x00\x00\x00\x00"

        # Truncation when longer than count
        written2 = writer.bytes(4, b"toolongstring")
        assert written2 == b"tool"

        data = obs.get_data()
        assert len(data) == 14

        ibs = IBitStream(data)
        reader = BitReader(ibs)
        assert reader.is_writing is False
        assert reader.bytes(10) == b"short\x00\x00\x00\x00\x00"
        assert reader.bytes(4) == b"tool"
