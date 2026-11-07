import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from d2savior.core.d2data import init_d2data
from d2savior.core.item import init_item_data
from d2savior.core.localized_data import init_localized_data
from d2savior.core.property import init_item_modifiers, init_language


@pytest.fixture(scope="session")
def init_data():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    data_dir = os.path.join(base_dir, "d2savior", "data")
    local_dir = os.path.join(data_dir, "local")

    init_item_data(os.path.join(data_dir, "itemdata.txt"))
    init_d2data(data_dir)
    init_localized_data(local_dir, lang_key="enUS")
    init_item_modifiers(os.path.join(local_dir, "item-modifiers.json"), lang_key="enUS")
    init_language(os.path.join(local_dir, "string.txt"), lang_index=1)


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
