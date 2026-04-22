class IBitStream():
	'''
	Little endian binary input stream,
	reads data from bytes as bits
	'''
	def __init__(self, data=None):
		self._v = ''
		self._offset = 0
		self.data = None
		if data is not None:
			self.setData(data)

	def __str__(self):
		return self._v

	def __len__(self):
		return len(self._v)

	def setData(self, data):
		self.data = data
		self._v = ''.join(["{0:08b}".format(b)[::-1] for b in data])
		self._offset = 0

	@property
	def bytes_pos(self):
		return self._offset // 8

	@bytes_pos.setter
	def bytes_pos(self, value):
		self._offset = value * 8 + self.bits_pos

	@property
	def bits_pos(self):
		return self._offset % 8

	@bits_pos.setter
	def bits_pos(self, value):
		self._offset = (self._offset // 8) * 8 + value

	def seek_back_bytes(self, num_bytes):
		self._offset -= num_bytes * 8

	def getOffset(self):
		return self._offset

	def remaining(self):
		return len(self._v) - self._offset

	def isEnd(self):
		return self._offset >= len(self._v)

	def read(self, num_bits):
		if num_bits == 0:
			return 0

		if num_bits < 0:
			raise ValueError('num_bits must be >= 0')

		if self._offset + num_bits > len(self._v):
			raise ValueError('not enough bits remaining')

		bits = self._v[self._offset:self._offset + num_bits]
		self._offset += num_bits
		return int(bits[::-1], 2)

	def read_bits(self, num_bits):
		return self.read(num_bits)

	def read_byte(self):
		return self.read(8)

	def read_word(self):
		return self.read(8) | (self.read(8) << 8)

	def read_dword(self):
		return (self.read(8) | 
				(self.read(8) << 8) | 
				(self.read(8) << 16) | 
				(self.read(8) << 24))

	def readString(self, length):
		result = ''
		for _ in range(length):
			bits = self._v[self._offset:self._offset + 8]
			self._offset += 8
			result += chr(int(bits[::-1], 2))
		return result

	def peek(self, num_bits):
		if num_bits == 0:
			return 0

		if num_bits < 0:
			raise ValueError('num_bits must be >= 0')

		if self._offset + num_bits > len(self._v):
			raise ValueError('not enough bits remaining')

		bits = self._v[self._offset:self._offset + num_bits]
		return int(bits[::-1], 2)

	def skip(self, num_bits):
		if num_bits < 0:
			raise ValueError('num_bits must be >= 0')

		if self._offset + num_bits > len(self._v):
			raise ValueError('not enough bits remaining')

		self._offset += num_bits

	def align_byte(self):
		if self.bits_pos > 0:
			self._offset = (self._offset // 8 + 1) * 8
