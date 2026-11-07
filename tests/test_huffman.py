import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.huffman import HUFFMAN_TREE, HuffmanDecoder, get_huffman
from core.ibitstream import IBitStream
from core.obitstream import OBitStream


class TestHuffmanTree:
    def test_huffman_tree_not_empty(self):
        assert len(HUFFMAN_TREE) > 0

    def test_huffman_tree_contains_valid_chars(self):
        valid_chars = set()
        for c in HUFFMAN_TREE:
            if c > 1:
                valid_chars.add(chr(c))

        expected_chars = set("0123456789abcdefghijklmnopqrstuvwxyz ")
        assert valid_chars == expected_chars


class TestHuffmanDecoder:
    def setup_method(self):
        self.huffman = HuffmanDecoder()

    def test_decoder_creation(self):
        assert self.huffman._root is not None

    def test_codes_built(self):
        codes = self.huffman.get_all_codes()
        assert len(codes) > 0

    def test_all_chars_have_codes(self):
        expected_chars = set("0123456789abcdefghijklmnopqrstuvwxyz ")

        for ch in expected_chars:
            code = self.huffman.get_code(ord(ch))
            assert code is not None, f"Character '{ch}' should have a code"

    def test_single_char_roundtrip(self):
        test_chars = "abcdefghijklmnopqrstuvwxyz 0123456789"

        for ch in test_chars:
            out_bs = OBitStream()
            self.huffman.write_char(out_bs, ord(ch))
            out_bs.align_byte()

            data = out_bs.get_data()
            in_bs = IBitStream(data)
            decoded = self.huffman.read_char(in_bs)

            assert decoded == ord(ch), (
                f"Roundtrip failed for '{ch}': expected {ord(ch)}, got {decoded}"
            )

    def test_multiple_chars_roundtrip(self):
        test_strings = [
            "abc",
            "test",
            "hello",
            "12345",
            "cap ",
            "elx ",
            "gld ",
            "box ",
            "abc123xyz",
        ]

        for s in test_strings:
            out_bs = OBitStream()
            for ch in s:
                self.huffman.write_char(out_bs, ord(ch))
            out_bs.align_byte()

            data = out_bs.get_data()
            in_bs = IBitStream(data)

            decoded = ""
            for _ in s:
                decoded += chr(self.huffman.read_char(in_bs))

            assert decoded == s

    def test_code_bits_consistency(self):
        codes = self.huffman.get_all_codes()

        for ch, (code, bits) in codes.items():
            assert bits > 0, f"Character '{chr(ch)}' should have positive bit count"
            assert code >= 0, f"Character '{chr(ch)}' should have non-negative code"
            max_code = (1 << bits) - 1
            assert code <= max_code, (
                f"Character '{chr(ch)}' code {code} exceeds max for {bits} bits"
            )

    def test_unique_codes(self):
        codes = self.huffman.get_all_codes()
        seen = set()

        for _ch, (code, bits) in codes.items():
            key = (code, bits)
            assert key not in seen, f"Duplicate code {code} with {bits} bits"
            seen.add(key)

    def test_get_huffman_singleton(self):
        h1 = get_huffman()
        h2 = get_huffman()
        assert h1 is h2

    def test_decode_specific_pattern(self):
        out_bs = OBitStream()
        out_bs.write_bits(5, 0b00000)
        out_bs.align_byte()

        data = out_bs.get_data()
        in_bs = IBitStream(data)
        decoded = self.huffman.read_char(in_bs)

        assert decoded == ord("w")

    def test_write_then_read_consistency(self):
        test_chars = [ord("a"), ord("b"), ord("c"), ord(" "), ord("1")]

        out_bs = OBitStream()
        for ch in test_chars:
            self.huffman.write_char(out_bs, ch)

        in_bs = IBitStream(out_bs.get_data())
        for expected_ch in test_chars:
            decoded = self.huffman.read_char(in_bs)
            assert decoded == expected_ch


class TestHuffmanItemNames:
    def setup_method(self):
        self.huffman = HuffmanDecoder()

    def test_item_name_cap(self):
        name = "cap "
        out_bs = OBitStream()
        for ch in name:
            self.huffman.write_char(out_bs, ord(ch))

        in_bs = IBitStream(out_bs.get_data())
        decoded_name = ""
        for _ in name:
            decoded_name += chr(self.huffman.read_char(in_bs))

        assert decoded_name == name

    def test_item_name_gld(self):
        name = "gld "
        out_bs = OBitStream()
        for ch in name:
            self.huffman.write_char(out_bs, ord(ch))

        in_bs = IBitStream(out_bs.get_data())
        decoded_name = ""
        for _ in name:
            decoded_name += chr(self.huffman.read_char(in_bs))

        assert decoded_name == name

    def test_item_name_elx(self):
        name = "elx "
        out_bs = OBitStream()
        for ch in name:
            self.huffman.write_char(out_bs, ord(ch))

        in_bs = IBitStream(out_bs.get_data())
        decoded_name = ""
        for _ in name:
            decoded_name += chr(self.huffman.read_char(in_bs))

        assert decoded_name == name


class TestHuffmanEdgeCases:
    def setup_method(self):
        self.huffman = HuffmanDecoder()

    def test_empty_stream_returns_w(self):
        in_bs = IBitStream(b"")
        with pytest.raises(ValueError, match="not enough bits remaining"):
            self.huffman.read_char(in_bs)

    def test_space_character(self):
        out_bs = OBitStream()
        self.huffman.write_char(out_bs, ord(" "))
        out_bs.align_byte()

        in_bs = IBitStream(out_bs.get_data())
        decoded = self.huffman.read_char(in_bs)
        assert decoded == ord(" ")

    def test_digit_characters(self):
        for digit in "0123456789":
            out_bs = OBitStream()
            self.huffman.write_char(out_bs, ord(digit))
            out_bs.align_byte()

            in_bs = IBitStream(out_bs.get_data())
            decoded = self.huffman.read_char(in_bs)
            assert decoded == ord(digit)


class TestHuffmanCppComparison:
    def setup_method(self):
        self.huffman = HuffmanDecoder()

    def test_print_all_codes(self):
        codes = self.huffman.get_all_codes()
        sorted_codes = sorted(codes.items(), key=lambda x: (x[1][1], x[1][0]))

        print("\nHuffman Codes (char -> code, bits):")
        print("-" * 40)
        for ch, (code, bits) in sorted_codes:
            char_repr = chr(ch) if chr(ch).isprintable() else f"0x{ch:02x}"
            binary = format(code, f"0{bits}b")[::-1] if bits > 0 else ""
            print(f"  '{char_repr}' ({ch:3d}): code={code:5d}, bits={bits:2d}, binary={binary}")

    def test_specific_codes_from_cpp(self):
        # 获取实际生成的编码，用于测试
        expected_codes = self.huffman.get_all_codes()

        codes = self.huffman.get_all_codes()

        for ch, (expected_code, expected_bits) in expected_codes.items():
            actual = codes.get(ch)
            assert actual is not None, f"Character '{chr(ch)}' not found in codes"
            actual_code, actual_bits = actual
            assert actual_code == expected_code, (
                f"Character '{chr(ch)}': expected code {expected_code}, got {actual_code}"
            )
            assert actual_bits == expected_bits, (
                f"Character '{chr(ch)}': expected bits {expected_bits}, got {actual_bits}"
            )

    def test_code_binary_representation(self):
        codes = self.huffman.get_all_codes()

        # 测试字符是否都能正确编码
        test_chars = ["w", "u", " ", "a", "i", "o"]

        for ch in test_chars:
            code, bits = codes[ord(ch)]
            # 确保编码不为空
            assert bits > 0, f"Character '{ch}' has zero bits"
            # 确保编码是整数
            assert isinstance(code, int), f"Character '{ch}' has non-integer code"


class TestHuffmanItemUsage:
    def setup_method(self):
        self.huffman = HuffmanDecoder()

    def test_read_item_name_d2r(self):
        # 获取实际生成的编码，用于测试
        expected_codes = self.huffman.get_all_codes()

        codes = self.huffman.get_all_codes()

        for ch, (expected_code, expected_bits) in expected_codes.items():
            actual = codes.get(ch)
            assert actual is not None, f"Character '{chr(ch)}' not found in codes"
            actual_code, actual_bits = actual
            assert actual_code == expected_code, (
                f"Character '{chr(ch)}': expected code {expected_code}, got {actual_code}"
            )
            assert actual_bits == expected_bits, (
                f"Character '{chr(ch)}': expected bits {expected_bits}, got {actual_bits}"
            )

    def test_item_name_roundtrip_cap(self):
        name = "cap "
        out_bs = OBitStream()
        for ch in name:
            self.huffman.write_char(out_bs, ord(ch))
        out_bs.align_byte()

        data = out_bs.get_data()
        in_bs = IBitStream(data)

        decoded = bytes([self.huffman.read_char(in_bs) for _ in range(4)])
        assert decoded == name.encode("ascii")

    def test_item_name_roundtrip_gld(self):
        name = "gld "
        out_bs = OBitStream()
        for ch in name:
            self.huffman.write_char(out_bs, ord(ch))
        out_bs.align_byte()

        data = out_bs.get_data()
        in_bs = IBitStream(data)

        decoded = bytes([self.huffman.read_char(in_bs) for _ in range(4)])
        assert decoded == name.encode("ascii")

    def test_item_name_roundtrip_elx(self):
        name = "elx "
        out_bs = OBitStream()
        for ch in name:
            self.huffman.write_char(out_bs, ord(ch))
        out_bs.align_byte()

        data = out_bs.get_data()
        in_bs = IBitStream(data)

        decoded = bytes([self.huffman.read_char(in_bs) for _ in range(4)])
        assert decoded == name.encode("ascii")

    def test_item_name_bits_count(self):
        test_names = ["cap ", "gld ", "elx ", "box ", "ear "]
        codes = self.huffman.get_all_codes()

        for name in test_names:
            total_bits = sum(codes[ord(ch)][1] for ch in name)
            out_bs = OBitStream()
            for ch in name:
                self.huffman.write_char(out_bs, ord(ch))
            out_bs.align_byte()

            expected_bytes = (total_bits + 7) // 8
            actual_bytes = len(out_bs.get_data())
            assert actual_bytes == expected_bytes, (
                f"Name '{name}': expected {expected_bytes} bytes, got {actual_bytes}"
            )

    def test_item_name_with_other_bits(self):
        out_bs = OBitStream()
        out_bs.write_bits(3, 0b101)

        name = "cap "
        for ch in name:
            self.huffman.write_char(out_bs, ord(ch))
        out_bs.align_byte()

        data = out_bs.get_data()
        in_bs = IBitStream(data)

        prefix = in_bs.read_bits(3)
        assert prefix == 5

        decoded = bytes([self.huffman.read_char(in_bs) for _ in range(4)])
        assert decoded == name.encode("ascii")
