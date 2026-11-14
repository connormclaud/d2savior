import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from d2savior.core.resolver import GameDataResolver


@pytest.fixture(scope="session")
def init_data():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    data_dir = os.path.join(base_dir, "d2savior", "data")
    return GameDataResolver.load(data_dir, lang_key="enUS")


@pytest.fixture
def items_dir():
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "..", "items"
    )


@pytest.fixture
def examples_dir():
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "..",
        "examples",
    )


ITEM_TEST_CASES = [
    {
        "name": "unique_amulet_0x63",
        "file": "Rixots Keen.d2i",
        "version": 0x63,
        "expected": {
            "type_name": b"amu ",
            "quality": 7,
            "identified": True,
            "simple": False,
        },
    },
    {
        "name": "runeword_spirit_0x69",
        "file": "runeword/Spirit-crystal_sword.d2i",
        "version": 0x69,
        "expected": {
            "type_name": b"crs ",
            "quality": 4,
            "identified": True,
            "rune_word": True,
            "socketed": True,
        },
    },
]
