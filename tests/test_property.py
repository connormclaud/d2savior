import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.d2data import init_d2data
from core.localized_data import init_localized_data
from core.property import (
    LanguageData,
    format_property,
    get_class_name,
    get_language,
    get_monster_name,
    get_property_name,
    get_skill_name,
    get_time_name,
    init_item_modifiers,
    init_language,
)


class TestLanguageData(unittest.TestCase):
    def setUp(self):
        self.lang_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "Generate Data",
            "language.txt",
        )

    def test_language_data_creation(self):
        lang = LanguageData()
        self.assertIsNotNone(lang)

    def test_language_data_load_not_exists(self):
        lang = LanguageData()
        result = lang.load("nonexistent_file.txt")
        self.assertFalse(result)

    def test_language_data_load_exists(self):
        if not os.path.exists(self.lang_path):
            self.skipTest("language.txt not found")

        lang = LanguageData()
        result = lang.load(self.lang_path, lang_index=2)
        self.assertTrue(result)

    def test_language_data_get_string(self):
        if not os.path.exists(self.lang_path):
            self.skipTest("language.txt not found")

        lang = LanguageData()
        lang.load(self.lang_path, lang_index=2)

        text = lang.get_section_string("class_name", 0)
        self.assertIsInstance(text, str)

    def test_language_data_sections(self):
        if not os.path.exists(self.lang_path):
            self.skipTest("language.txt not found")

        lang = LanguageData()
        lang.load(self.lang_path, lang_index=2)

        size = lang.get_section_size("class_name")
        self.assertGreater(size, 0)


class TestInitLanguage(unittest.TestCase):
    def setUp(self):
        self.lang_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "Generate Data",
            "language.txt",
        )

    def test_init_language(self):
        if not os.path.exists(self.lang_path):
            self.skipTest("language.txt not found")

        result = init_language(self.lang_path, lang_index=2)
        self.assertTrue(result)

        lang = get_language()
        self.assertIsNotNone(lang)


class TestGetClassName(unittest.TestCase):
    def setUp(self):
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
        local_dir = os.path.join(data_dir, "local")
        if os.path.exists(local_dir):
            init_localized_data(local_dir, lang_key="enUS")

    def test_get_class_name_amazon(self):
        name = get_class_name(0)
        self.assertEqual(name, "Amazon")

    def test_get_class_name_sorceress(self):
        name = get_class_name(1)
        self.assertEqual(name, "Sorceress")

    def test_get_class_name_barbarian(self):
        name = get_class_name(4)
        self.assertEqual(name, "Barbarian")

    def test_get_class_name_out_of_range(self):
        name = get_class_name(100)
        self.assertIsInstance(name, str)


class TestGetSkillName(unittest.TestCase):
    def setUp(self):
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
        if os.path.exists(data_dir):
            init_d2data(data_dir)
            local_dir = os.path.join(data_dir, "local")
            if os.path.exists(local_dir):
                init_localized_data(local_dir, lang_key="enUS")

    def test_get_skill_name_class_skill(self):
        name, class_id = get_skill_name(6)
        self.assertEqual(name, "Magic Arrow")
        self.assertEqual(class_id, 0)

    def test_get_skill_name_fire_bolt(self):
        name, class_id = get_skill_name(36)
        self.assertEqual(name, "Fire Bolt")
        self.assertEqual(class_id, 1)

    def test_get_skill_name_normal_skill(self):
        name, _class_id = get_skill_name(217)
        self.assertIsInstance(name, str)
        self.assertNotEqual(name, "")

    def test_get_skill_name_out_of_range(self):
        name, _class_id = get_skill_name(2000)
        self.assertIsInstance(name, str)


class TestGetMonsterName(unittest.TestCase):
    def setUp(self):
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
        if os.path.exists(data_dir):
            init_d2data(data_dir)
            local_dir = os.path.join(data_dir, "local")
            if os.path.exists(local_dir):
                init_localized_data(local_dir, lang_key="enUS")

    def test_get_monster_name(self):
        name = get_monster_name(0)
        self.assertIsInstance(name, str)


class TestGetTimeName(unittest.TestCase):
    def test_get_time_name_daytime(self):
        name = get_time_name(0)
        self.assertIsInstance(name, str)

    def test_get_time_name_dusk(self):
        name = get_time_name(1)
        self.assertIsInstance(name, str)


class TestGetPropertyName(unittest.TestCase):
    def setUp(self):
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
        if os.path.exists(data_dir):
            init_d2data(data_dir)

    def test_get_property_name_strength(self):
        name = get_property_name(0)
        self.assertIn("strength", name)

    def test_get_property_name_energy(self):
        name = get_property_name(1)
        self.assertIn("energy", name)

    def test_get_property_name_dexterity(self):
        name = get_property_name(2)
        self.assertIn("dexterity", name)

    def test_get_property_name_vitality(self):
        name = get_property_name(3)
        self.assertIn("vitality", name)

    def test_get_property_name_fire_resist(self):
        name = get_property_name(39)
        self.assertIn("fireresist", name)


class TestFormatProperty(unittest.TestCase):
    def setUp(self):
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
        if os.path.exists(data_dir):
            init_d2data(data_dir)
            item_modifiers_file = os.path.join(data_dir, "local", "item-modifiers.json")
            if os.path.exists(item_modifiers_file):
                init_item_modifiers(item_modifiers_file, lang_key="enUS")

    def test_format_property_strength(self):
        result = format_property(0, [10])
        self.assertEqual(result, "+10 to Strength")

    def test_format_property_strength_negative(self):
        result = format_property(0, [-5])
        self.assertEqual(result, "-5 to Strength")

    def test_format_property_dexterity(self):
        result = format_property(2, [15])
        self.assertEqual(result, "+15 to Dexterity")

    def test_format_property_fire_resist(self):
        result = format_property(39, [30])
        self.assertIn("Fire Resist", result)

    def test_format_property_empty_params(self):
        result = format_property(0, [])
        self.assertIn("Strength", result)

    def test_format_property_max_life(self):
        result = format_property(7, [50])
        self.assertIn("Life", result)

    def test_format_property_max_mana(self):
        result = format_property(9, [30])
        self.assertIn("Mana", result)

    def test_format_property_enhanced_defense(self):
        result = format_property(16, [100])
        self.assertIn("Defense", result)

    def test_format_property_attack_rating(self):
        result = format_property(19, [500])
        self.assertIn("Attack Rating", result)

    def test_format_property_fire_damage(self):
        result = format_property(48, [10, 20])
        self.assertIn("Fire", result)

    def test_format_property_cold_damage(self):
        result = format_property(54, [10, 20, 100])
        self.assertIn("Cold", result)

    def test_format_property_life_steal(self):
        result = format_property(60, [5])
        self.assertIn("Life stolen", result)

    def test_format_property_mana_steal(self):
        result = format_property(62, [3])
        self.assertIn("Mana stolen", result)

    def test_format_property_faster_run_walk(self):
        result = format_property(96, [30])
        self.assertIn("Faster Run", result)

    def test_format_property_faster_cast_rate(self):
        result = format_property(105, [20])
        self.assertIn("Faster Cast", result)

    def test_format_property_crushing_blow(self):
        result = format_property(136, [25])
        self.assertIn("Crushing", result)

    def test_format_property_deadly_strike(self):
        result = format_property(141, [50])
        self.assertIn("Deadly", result)

    def test_format_property_indestructible(self):
        result = format_property(152, [1])
        self.assertIn("Indestructible", result)

    def test_format_property_cannot_be_frozen(self):
        result = format_property(153, [1])
        self.assertIn("Frozen", result)

    def test_format_property_extra_gold(self):
        result = format_property(79, [100])
        self.assertIn("Gold", result)

    def test_format_property_magic_find(self):
        result = format_property(80, [50])
        self.assertIn("Magic", result)

    def test_format_property_all_skills(self):
        result = format_property(127, [2])
        self.assertIn("All Skills", result)


class TestFormatPropertySpecialCases(unittest.TestCase):
    def setUp(self):
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
        if os.path.exists(data_dir):
            init_d2data(data_dir)
            item_modifiers_file = os.path.join(data_dir, "local", "item-modifiers.json")
            if os.path.exists(item_modifiers_file):
                init_item_modifiers(item_modifiers_file, lang_key="enUS")

    def test_format_property_class_skill(self):
        result = format_property(97, [6, 3])
        self.assertIn("Magic Arrow", result)

    def test_format_property_skill_tab(self):
        result = format_property(188, [2, 0, 3])
        self.assertIn("Javelin and Spear", result)

    def test_format_property_aura_when_equipped(self):
        result = format_property(151, [5, 10])
        self.assertIn("Aura", result)

    def test_format_property_float_g_format(self):
        result = format_property(214, [80])
        self.assertIn("Defense", result)
        self.assertIn("+", result)

    def test_format_property_float_g_negative(self):
        result = format_property(214, [-80])
        self.assertIn("-", result)

    def test_format_property_class_skill_levels(self):
        # class_id: 0 Amazon, 1 Sorceress, 2 Necromancer, 3 Paladin, 4 Barbarian, 5 Druid, 6 Assassin, 7 Warlock
        expected = [
            (0, "Amazon"),
            (1, "Sorceress"),
            (2, "Necromancer"),
            (3, "Paladin"),
            (4, "Barbarian"),
            (5, "Druid"),
            (6, "Assassin"),
            (7, "Warlock"),
        ]
        for class_id, expected_name in expected:
            result = format_property(83, [class_id, 1])
            self.assertIn(
                expected_name, result, f"Class ID {class_id} should format to {expected_name}"
            )


class TestFormatItemInfoSetProperties(unittest.TestCase):
    def test_format_item_info_with_set_properties(self):
        from core.formatters import format_item_info
        from core.item import D2Item, ItemInfo, PropertyList, TypeSpecificInfo

        item = D2Item()
        item.item_info = ItemInfo()
        item.item_info.type_name = b"rin "
        item.item_info.type_specific_info = TypeSpecificInfo()

        p2 = PropertyList()
        p2.properties = [(31, 0, 60)]  # +60 Defense
        p3 = PropertyList()
        p3.properties = [(105, 0, 10)]  # +10% Faster Cast Rate

        item.item_info.type_specific_info.set_properties = [p2, p3, None, None, None]

        full_text = format_item_info(item)
        self.assertIsInstance(full_text, str)
        self.assertIn("Set Properties (2 Items):", full_text)
        self.assertIn("Set Properties (3 Items):", full_text)
        self.assertIn("Defense", full_text)
        self.assertIn("Faster Cast Rate", full_text)


if __name__ == "__main__":
    unittest.main()
