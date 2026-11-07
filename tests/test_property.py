import os
import sys

import pytest

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


class TestLanguageData:
    def setup_method(self):
        self.lang_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "Generate Data",
            "language.txt",
        )

    def test_language_data_creation(self):
        lang = LanguageData()
        assert lang is not None

    def test_language_data_load_not_exists(self):
        lang = LanguageData()
        result = lang.load("nonexistent_file.txt")
        assert not result

    def test_language_data_load_exists(self):
        if not os.path.exists(self.lang_path):
            pytest.skip("language.txt not found")

        lang = LanguageData()
        result = lang.load(self.lang_path, lang_index=2)
        assert result

    def test_language_data_get_string(self):
        if not os.path.exists(self.lang_path):
            pytest.skip("language.txt not found")

        lang = LanguageData()
        lang.load(self.lang_path, lang_index=2)

        text = lang.get_section_string("class_name", 0)
        assert isinstance(text, str)

    def test_language_data_sections(self):
        if not os.path.exists(self.lang_path):
            pytest.skip("language.txt not found")

        lang = LanguageData()
        lang.load(self.lang_path, lang_index=2)

        size = lang.get_section_size("class_name")
        assert size > 0


class TestInitLanguage:
    def setup_method(self):
        self.lang_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "Generate Data",
            "language.txt",
        )

    def test_init_language(self):
        if not os.path.exists(self.lang_path):
            pytest.skip("language.txt not found")

        result = init_language(self.lang_path, lang_index=2)
        assert result

        lang = get_language()
        assert lang is not None


class TestGetClassName:
    def setup_method(self):
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
        local_dir = os.path.join(data_dir, "local")
        if os.path.exists(local_dir):
            init_localized_data(local_dir, lang_key="enUS")

    def test_get_class_name_amazon(self):
        name = get_class_name(0)
        assert name == "Amazon"

    def test_get_class_name_sorceress(self):
        name = get_class_name(1)
        assert name == "Sorceress"

    def test_get_class_name_barbarian(self):
        name = get_class_name(4)
        assert name == "Barbarian"

    def test_get_class_name_out_of_range(self):
        name = get_class_name(100)
        assert isinstance(name, str)


class TestGetSkillName:
    def setup_method(self):
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
        if os.path.exists(data_dir):
            init_d2data(data_dir)
            local_dir = os.path.join(data_dir, "local")
            if os.path.exists(local_dir):
                init_localized_data(local_dir, lang_key="enUS")

    def test_get_skill_name_class_skill(self):
        name, class_id = get_skill_name(6)
        assert name == "Magic Arrow"
        assert class_id == 0

    def test_get_skill_name_fire_bolt(self):
        name, class_id = get_skill_name(36)
        assert name == "Fire Bolt"
        assert class_id == 1

    def test_get_skill_name_normal_skill(self):
        name, _class_id = get_skill_name(217)
        assert isinstance(name, str)
        assert name != ""

    def test_get_skill_name_out_of_range(self):
        name, _class_id = get_skill_name(2000)
        assert isinstance(name, str)


class TestGetMonsterName:
    def setup_method(self):
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
        if os.path.exists(data_dir):
            init_d2data(data_dir)
            local_dir = os.path.join(data_dir, "local")
            if os.path.exists(local_dir):
                init_localized_data(local_dir, lang_key="enUS")

    def test_get_monster_name(self):
        name = get_monster_name(0)
        assert isinstance(name, str)


class TestGetTimeName:
    def test_get_time_name_daytime(self):
        name = get_time_name(0)
        assert isinstance(name, str)

    def test_get_time_name_dusk(self):
        name = get_time_name(1)
        assert isinstance(name, str)


class TestGetPropertyName:
    def setup_method(self):
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
        if os.path.exists(data_dir):
            init_d2data(data_dir)

    def test_get_property_name_strength(self):
        name = get_property_name(0)
        assert "strength" in name

    def test_get_property_name_energy(self):
        name = get_property_name(1)
        assert "energy" in name

    def test_get_property_name_dexterity(self):
        name = get_property_name(2)
        assert "dexterity" in name

    def test_get_property_name_vitality(self):
        name = get_property_name(3)
        assert "vitality" in name

    def test_get_property_name_fire_resist(self):
        name = get_property_name(39)
        assert "fireresist" in name


class TestFormatProperty:
    def setup_method(self):
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
        if os.path.exists(data_dir):
            init_d2data(data_dir)
            item_modifiers_file = os.path.join(data_dir, "local", "item-modifiers.json")
            if os.path.exists(item_modifiers_file):
                init_item_modifiers(item_modifiers_file, lang_key="enUS")

    def test_format_property_strength(self):
        result = format_property(0, [10])
        assert result == "+10 to Strength"

    def test_format_property_strength_negative(self):
        result = format_property(0, [-5])
        assert result == "-5 to Strength"

    def test_format_property_dexterity(self):
        result = format_property(2, [15])
        assert result == "+15 to Dexterity"

    def test_format_property_fire_resist(self):
        result = format_property(39, [30])
        assert "Fire Resist" in result

    def test_format_property_empty_params(self):
        result = format_property(0, [])
        assert "Strength" in result

    def test_format_property_max_life(self):
        result = format_property(7, [50])
        assert "Life" in result

    def test_format_property_max_mana(self):
        result = format_property(9, [30])
        assert "Mana" in result

    def test_format_property_enhanced_defense(self):
        result = format_property(16, [100])
        assert "Defense" in result

    def test_format_property_attack_rating(self):
        result = format_property(19, [500])
        assert "Attack Rating" in result

    def test_format_property_fire_damage(self):
        result = format_property(48, [10, 20])
        assert "Fire" in result

    def test_format_property_cold_damage(self):
        result = format_property(54, [10, 20, 100])
        assert "Cold" in result

    def test_format_property_life_steal(self):
        result = format_property(60, [5])
        assert "Life stolen" in result

    def test_format_property_mana_steal(self):
        result = format_property(62, [3])
        assert "Mana stolen" in result

    def test_format_property_faster_run_walk(self):
        result = format_property(96, [30])
        assert "Faster Run" in result

    def test_format_property_faster_cast_rate(self):
        result = format_property(105, [20])
        assert "Faster Cast" in result

    def test_format_property_crushing_blow(self):
        result = format_property(136, [25])
        assert "Crushing" in result

    def test_format_property_deadly_strike(self):
        result = format_property(141, [50])
        assert "Deadly" in result

    def test_format_property_indestructible(self):
        result = format_property(152, [1])
        assert "Indestructible" in result

    def test_format_property_cannot_be_frozen(self):
        result = format_property(153, [1])
        assert "Frozen" in result

    def test_format_property_extra_gold(self):
        result = format_property(79, [100])
        assert "Gold" in result

    def test_format_property_magic_find(self):
        result = format_property(80, [50])
        assert "Magic" in result

    def test_format_property_all_skills(self):
        result = format_property(127, [2])
        assert "All Skills" in result


class TestFormatPropertySpecialCases:
    def setup_method(self):
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
        if os.path.exists(data_dir):
            init_d2data(data_dir)
            item_modifiers_file = os.path.join(data_dir, "local", "item-modifiers.json")
            if os.path.exists(item_modifiers_file):
                init_item_modifiers(item_modifiers_file, lang_key="enUS")

    def test_format_property_class_skill(self):
        result = format_property(97, [6, 3])
        assert "Magic Arrow" in result

    def test_format_property_skill_tab(self):
        result = format_property(188, [2, 0, 3])
        assert "Javelin and Spear" in result

    def test_format_property_aura_when_equipped(self):
        result = format_property(151, [5, 10])
        assert "Aura" in result

    def test_format_property_float_g_format(self):
        result = format_property(214, [80])
        assert "Defense" in result
        assert "+" in result

    def test_format_property_float_g_negative(self):
        result = format_property(214, [-80])
        assert "-" in result

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
            assert expected_name in result, f"Class ID {class_id} should format to {expected_name}"


class TestFormatItemInfoSetProperties:
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
        assert isinstance(full_text, str)
        assert "Set Properties (2 Items):" in full_text
        assert "Set Properties (3 Items):" in full_text
        assert "Defense" in full_text
        assert "Faster Cast Rate" in full_text
