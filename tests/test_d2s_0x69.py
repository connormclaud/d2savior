import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from d2savior.core.d2s_struct import D2SStruct


class Test0x69GameVersionExpansionLogic:
    def test_game_version_1_not_expansion(self):
        d2s = D2SStruct()
        d2s.version = 0x69
        d2s.game_version = 1
        assert d2s.is_expansion() is False

    def test_game_version_2_is_expansion(self):
        d2s = D2SStruct()
        d2s.version = 0x69
        d2s.game_version = 2
        assert d2s.is_expansion() is True

    def test_game_version_3_is_expansion(self):
        d2s = D2SStruct()
        d2s.version = 0x69
        d2s.game_version = 3
        assert d2s.is_expansion() is True

    def test_game_version_0_not_expansion(self):
        d2s = D2SStruct()
        d2s.version = 0x69
        d2s.game_version = 0
        assert d2s.is_expansion() is False

    def test_charflags_expansion_bit_ignored_in_0x69(self):
        d2s = D2SStruct()
        d2s.version = 0x69
        d2s.char_flags = 0x20
        d2s.game_version = 1
        assert d2s.is_expansion() is False

    def test_charflags_no_expansion_but_gameversion_says_expansion(self):
        d2s = D2SStruct()
        d2s.version = 0x69
        d2s.char_flags = 0x0
        d2s.game_version = 3
        assert d2s.is_expansion() is True
