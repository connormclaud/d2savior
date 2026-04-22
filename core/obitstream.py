class OBitStream():
	'''
	Little endian binary output stream,
	represents data in bit as string
	'''
	def __init__(self):
		self._v = ''
		self.bits_pos = 0

	def __str__(self):
		return self._v

	def __len__(self):
		return len(self._v)

	def getByteList(self):
		def chunk(s, n):
			return [s[i:i+8] for i in range(0, len(self._v), n)]

		return [int(bits[::-1], 2) for bits in chunk(self._v, 8)]

	def toHexString(self):
		return ' '.join(map('{0:02x}'.format, self.getByteList()))

	def append(self, value, num_bits):
		if num_bits == 0:
			return

		if num_bits < 0 or num_bits > 32:
			raise ValueError('[0, 32] bits only')

		self._v += '{0:032b}'.format(value)[::-1][:num_bits]
		self.bits_pos = len(self._v) % 8

	def write_bits(self, num_bits, value):
		self.append(value, num_bits)

	def write_byte(self, value):
		self.append(value, 8)

	def write_word(self, value):
		self.append(value & 0xFF, 8)
		self.append((value >> 8) & 0xFF, 8)

	def write_dword(self, value):
		self.append(value & 0xFF, 8)
		self.append((value >> 8) & 0xFF, 8)
		self.append((value >> 16) & 0xFF, 8)
		self.append((value >> 24) & 0xFF, 8)

	def appendString(self, str_value):
		for v in str_value:
			self._v += ('{0:08b}'.format(ord(v)))[::-1]
		self.bits_pos = len(self._v) % 8

	def writeBytes(self, writer):
		writer.write(bytearray(self.getByteList()))

	def align_byte(self):
		if self.bits_pos > 0:
			padding = 8 - self.bits_pos
			self._v += '0' * padding
			self.bits_pos = 0

	def get_data(self):
		return bytes(self.getByteList())
