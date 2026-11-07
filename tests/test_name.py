#!/usr/bin/env python3
import unittest

from core.d2s_struct import D2SStruct
from core.ibitstream import IBitStream


class TestCharacterNameEncoding(unittest.TestCase):
    """测试角色名称的编码和解码功能"""

    def _create_test_data(self, version, name_bytes, nameptr_bytes):
        """创建测试数据"""
        return bytes(
            [
                0x55,
                0xAA,
                0x55,
                0xAA,  # magic
                version & 0xFF,
                (version >> 8) & 0xFF,
                (version >> 16) & 0xFF,
                (version >> 24) & 0xFF,  # version (小端序)
                0x00,
                0x01,
                0x00,
                0x00,  # dwSize
                0x00,
                0x00,
                0x00,
                0x00,  # dwCRC
                0x00,
                0x00,
                0x00,
                0x00,  # dwWeaponSet
                # Name (16 bytes)
                *name_bytes.ljust(16, b"\x00"),
                0x00,  # charType
                0x00,  # charTitle
                0x00,
                0x00,  # unknown1
                0x00,  # charClass
                0x00,
                0x00,  # unknown2
                0x01,  # charLevel
                0x00,
                0x00,
                0x00,
                0x00,  # unknown3
                0x00,
                0x00,
                0x00,
                0x00,  # dwTime
                0x00,
                0x00,
                0x00,
                0x00,  # unknown4
                # dwSkillKey (16*4 bytes)
                *[0x00] * 64,
                0x00,
                0x00,
                0x00,
                0x00,  # dwLeftSkill1
                0x00,
                0x00,
                0x00,
                0x00,  # dwRightSkill1
                0x00,
                0x00,
                0x00,
                0x00,  # dwLeftSkill2
                0x00,
                0x00,
                0x00,
                0x00,  # dwRightSkill2
                # outfit (16 bytes)
                *[0x00] * 16,
                # colors (16 bytes)
                *[0x00] * 16,
                # Town (3 bytes)
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,  # dwMapSeed
                0x00,
                0x00,  # unknown5
                0x00,  # bMercDead
                0x00,  # unknown6
                0x00,
                0x00,
                0x00,
                0x00,  # dwMercControl
                0x00,
                0x00,  # wMercName
                0x00,
                0x00,  # wMercType
                0x00,
                0x00,
                0x00,
                0x00,  # dwMercExp
                # unknown7 (0x4C bytes)
                *[0x00] * 76,
                # NamePTR (0x40 bytes)
                *nameptr_bytes.ljust(64, b"\x00"),
                0x00,
                0x00,
                0x00,
                0x00,  # unknown8
                # QuestInfo
                0x51,
                0x55,
                0x45,
                0x53,  # magic
                0x05,
                0x00,
                0x00,
                0x00,  # dwActs
                0x7C,
                0x00,  # wSize
                # QIData (3 instances)
                *[0x00] * 3 * 124,
                # Waypoints
                0x53,
                0x57,  # magic
                0x00,
                0x00,
                0x00,
                0x00,  # unknown
                0x60,
                0x00,  # wSize
                # wp (3 instances)
                *[0x00] * 3 * 24,
                # NPC (0x34 bytes)
                *[0x00] * 52,
                # PlayerStats
                0x66,
                0x67,  # magic
                *[0x00] * 40,  # stat_values
                0x00,
                0x00,  # iEnd
                # Skills
                0x66,
                0x69,  # wMagic
                *[0x00] * 30,  # bSkillLevel
            ]
        )

    def test_ascii_name_old_version(self):
        """测试旧版本（< 0x62）的ASCII名称"""
        test_data = self._create_test_data(
            version=0x61,  # 旧版本
            name_bytes=b"TestChar",
            nameptr_bytes=b"TestCharPTR",
        )

        bs = IBitStream(test_data)
        char_data = D2SStruct()
        char_data.deserialize(bs)

        name = char_data.get_char_name()
        self.assertEqual(name, "TestChar")
        self.assertIsInstance(name, str)

    def test_utf8_name_new_version(self):
        """测试新版本（>= 0x62）的UTF-8名称"""
        test_data = self._create_test_data(
            version=0x62,  # 新版本
            name_bytes=b"OldName",
            nameptr_bytes="测试角色".encode(),
        )

        bs = IBitStream(test_data)
        char_data = D2SStruct()
        char_data.deserialize(bs)

        name = char_data.get_char_name()
        self.assertEqual(name, "测试角色")
        self.assertIsInstance(name, str)

    def test_empty_name(self):
        """测试空名称"""
        test_data = self._create_test_data(version=0x62, name_bytes=b"", nameptr_bytes=b"")

        bs = IBitStream(test_data)
        char_data = D2SStruct()
        char_data.deserialize(bs)

        name = char_data.get_char_name()
        self.assertEqual(name, "")
        self.assertIsInstance(name, str)

    def test_name_with_null_bytes(self):
        """测试包含空字节的名称"""
        test_data = self._create_test_data(
            version=0x62, name_bytes=b"Test\x00Char", nameptr_bytes=b"Test\x00CharPTR"
        )

        bs = IBitStream(test_data)
        char_data = D2SStruct()
        char_data.deserialize(bs)

        name = char_data.get_char_name()
        self.assertEqual(name, "Test")
        self.assertIsInstance(name, str)

    def test_utf8_special_characters(self):
        """测试包含特殊UTF-8字符的名称"""
        special_name = "测试角色 🌟✨"
        test_data = self._create_test_data(
            version=0x62, name_bytes=b"OldName", nameptr_bytes=special_name.encode("utf-8")
        )

        bs = IBitStream(test_data)
        char_data = D2SStruct()
        char_data.deserialize(bs)

        name = char_data.get_char_name()
        self.assertEqual(name, special_name)
        self.assertIsInstance(name, str)


if __name__ == "__main__":
    unittest.main()
