import unittest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.obitstream import OBitStream

class MemWriter():
	def __init__(self):
		self.buf = bytearray()

	def write(self, bytes):
		self.buf.extend(bytes)

	def __str__(self):
		return ' '.join(map('{0:02x}'.format, self.buf))

class TestOBitStream(unittest.TestCase):
	def setUp(self):
		self.stream = OBitStream()


	def test_append_empty(self):
		self.assertEqual('', str(self.stream))
		self.assertEqual('', self.stream.toHexString())

	def test_append_zero_bit(self):
		self.stream.append(0xf, 0)
		self.assertEqual('', str(self.stream))
		self.assertEqual('', self.stream.toHexString())

	def test_append_one_bit(self):
		self.stream.append(1, 1)
		self.assertEqual('1', str(self.stream))
		self.assertEqual('01', self.stream.toHexString())

	def test_append_one_bit_extracted(self):
		self.stream.append(0xf, 1)
		self.assertEqual('1', str(self.stream))
		self.assertEqual('01', self.stream.toHexString())

	def test_append_8_bits(self):
		self.stream.append(0x76, 8)
		self.assertEqual('01110110'[::-1], str(self.stream))
		self.assertEqual('76', self.stream.toHexString())

	def test_append_9_bits(self):
		self.stream.append(0x176, 9)
		self.assertEqual('101110110'[::-1], str(self.stream))
		self.assertEqual('76 01', self.stream.toHexString())

	def test_append_9_bits_extracted(self):
		self.stream.append(0x776, 9)
		self.assertEqual('101110110'[::-1], str(self.stream))
		self.assertEqual('76 01', self.stream.toHexString())

	def test_append_32bits(self):
		self.stream.append(0x1F1F2F4F8, 32)
		self.assertEqual('11110001111100101111010011111000'[::-1], str(self.stream))
		self.assertEqual('f8 f4 f2 f1', self.stream.toHexString())

	def test_append_3_2(self):
		self.stream.append(3, 3)
		self.stream.append(1, 2)
		self.assertEqual('01011'[::-1], str(self.stream))
		self.assertEqual('0b', self.stream.toHexString())

	def test_append_3_6_4(self):
		self.stream.append(int('001', 2), 3)
		self.stream.append(int('000011', 2), 6)
		self.stream.append(int('0111', 2), 4)
		self.assertEqual('0111000011001'[::-1], str(self.stream))
		self.assertEqual('19 0e', self.stream.toHexString())

	def test_append_string(self):
		self.stream.appendString("012 ")
		self.assertEqual('30 31 32 20', self.stream.toHexString())
		w = MemWriter()
		self.stream.writeBytes(w)
		self.assertEqual('30 31 32 20', str(w))


	def test_write_bytes(self):
		self.stream.append(int('1110101', 2), 7)
		self.assertEqual('75', self.stream.toHexString())
		w = MemWriter()
		self.stream.writeBytes(w)
		self.assertEqual('75', str(w))

	def test_write_bytes_long(self):
		self.stream.append(int('10100001111', 2), 11)
		self.assertEqual('0f 05', self.stream.toHexString())
		w = MemWriter()
		self.stream.writeBytes(w)
		self.assertEqual('0f 05', str(w))


class TestOBitStreamNewInterface(unittest.TestCase):
	def setUp(self):
		self.stream = OBitStream()

	def test_bits_pos(self):
		self.assertEqual(0, self.stream.bits_pos)
		self.stream.append(0x76, 8)
		self.assertEqual(0, self.stream.bits_pos)
		self.stream.append(0x01, 3)
		self.assertEqual(3, self.stream.bits_pos)

	def test_write_bits(self):
		self.stream.write_bits(8, 0x76)
		self.assertEqual('76', self.stream.toHexString())

	def test_write_byte(self):
		self.stream.write_byte(0x76)
		self.assertEqual('76', self.stream.toHexString())
		self.assertEqual(0, self.stream.bits_pos)

	def test_write_word(self):
		self.stream.write_word(0x0176)
		self.assertEqual('76 01', self.stream.toHexString())

	def test_write_dword(self):
		self.stream.write_dword(0x03020176)
		self.assertEqual('76 01 02 03', self.stream.toHexString())

	def test_align_byte(self):
		self.stream.append(0x01, 3)
		self.assertEqual(3, self.stream.bits_pos)
		self.stream.align_byte()
		self.assertEqual(0, self.stream.bits_pos)
		self.assertEqual('01', self.stream.toHexString())

	def test_get_data(self):
		self.stream.append(0x76, 8)
		self.stream.append(0x01, 8)
		data = self.stream.get_data()
		self.assertEqual(b'\x76\x01', data)

	def test_write_bits_multiple(self):
		self.stream.write_bits(3, 3)
		self.stream.write_bits(2, 1)
		self.stream.write_bits(5, 0x1F)
		self.assertEqual('eb 03', self.stream.toHexString())


if __name__ == '__main__':
	unittest.main()
