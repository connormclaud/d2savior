from d2savior.core.d2data import GameDataResolver
from d2savior.core.formatters import format_item_info
from d2savior.core.item import D2Item, ItemInfo, TypeSpecificInfo
from d2savior.core.property import format_property, get_time_name
from d2savior.core.property_list import PropertyList


class TestGetTimeName:
    def test_get_time_name_daytime(self):
        name = get_time_name(0)
        assert isinstance(name, str)

    def test_get_time_name_dusk(self):
        name = get_time_name(1)
        assert isinstance(name, str)


class TestFormatProperty:
    def test_format_property_strength(self, game_data_resolver: GameDataResolver):
        result = format_property(0, [10], resolver=game_data_resolver)
        assert result == "+10 to Strength"

    def test_format_property_strength_negative(self, game_data_resolver: GameDataResolver):
        result = format_property(0, [-5], resolver=game_data_resolver)
        assert result == "-5 to Strength"

    def test_format_property_dexterity(self, game_data_resolver: GameDataResolver):
        result = format_property(2, [15], resolver=game_data_resolver)
        assert result == "+15 to Dexterity"

    def test_format_property_fire_resist(self, game_data_resolver: GameDataResolver):
        result = format_property(39, [30], resolver=game_data_resolver)
        assert "Fire Resist" in result

    def test_format_property_empty_params(self, game_data_resolver: GameDataResolver):
        result = format_property(0, [], resolver=game_data_resolver)
        assert "Strength" in result

    def test_format_property_max_life(self, game_data_resolver: GameDataResolver):
        result = format_property(7, [50], resolver=game_data_resolver)
        assert "Life" in result

    def test_format_property_max_mana(self, game_data_resolver: GameDataResolver):
        result = format_property(9, [30], resolver=game_data_resolver)
        assert "Mana" in result

    def test_format_property_enhanced_defense(self, game_data_resolver: GameDataResolver):
        result = format_property(16, [100], resolver=game_data_resolver)
        assert "Defense" in result

    def test_format_property_attack_rating(self, game_data_resolver: GameDataResolver):
        result = format_property(19, [500], resolver=game_data_resolver)
        assert "Attack Rating" in result

    def test_format_property_fire_damage(self, game_data_resolver: GameDataResolver):
        result = format_property(48, [10, 20], resolver=game_data_resolver)
        assert "Fire" in result

    def test_format_property_cold_damage(self, game_data_resolver: GameDataResolver):
        result = format_property(54, [10, 20, 100], resolver=game_data_resolver)
        assert "Cold" in result

    def test_format_property_life_steal(self, game_data_resolver: GameDataResolver):
        result = format_property(60, [5], resolver=game_data_resolver)
        assert "Life stolen" in result

    def test_format_property_mana_steal(self, game_data_resolver: GameDataResolver):
        result = format_property(62, [3], resolver=game_data_resolver)
        assert "Mana stolen" in result

    def test_format_property_faster_run_walk(self, game_data_resolver: GameDataResolver):
        result = format_property(96, [30], resolver=game_data_resolver)
        assert "Faster Run" in result

    def test_format_property_faster_cast_rate(self, game_data_resolver: GameDataResolver):
        result = format_property(105, [20], resolver=game_data_resolver)
        assert "Faster Cast" in result

    def test_format_property_crushing_blow(self, game_data_resolver: GameDataResolver):
        result = format_property(136, [25], resolver=game_data_resolver)
        assert "Crushing" in result

    def test_format_property_deadly_strike(self, game_data_resolver: GameDataResolver):
        result = format_property(141, [50], resolver=game_data_resolver)
        assert "Deadly" in result

    def test_format_property_indestructible(self, game_data_resolver: GameDataResolver):
        result = format_property(152, [1], resolver=game_data_resolver)
        assert "Indestructible" in result

    def test_format_property_cannot_be_frozen(self, game_data_resolver: GameDataResolver):
        result = format_property(153, [1], resolver=game_data_resolver)
        assert "Frozen" in result

    def test_format_property_extra_gold(self, game_data_resolver: GameDataResolver):
        result = format_property(79, [100], resolver=game_data_resolver)
        assert "Gold" in result

    def test_format_property_magic_find(self, game_data_resolver: GameDataResolver):
        result = format_property(80, [50], resolver=game_data_resolver)
        assert "Magic" in result

    def test_format_property_all_skills(self, game_data_resolver: GameDataResolver):
        result = format_property(127, [2], resolver=game_data_resolver)
        assert "All Skills" in result


class TestFormatPropertySpecialCases:
    def test_format_property_class_skill(self, game_data_resolver: GameDataResolver):
        result = format_property(97, [6, 3], resolver=game_data_resolver)
        assert "Magic Arrow" in result

    def test_format_property_skill_tab(self, game_data_resolver: GameDataResolver):
        result = format_property(188, [2, 0, 3], resolver=game_data_resolver)
        assert "Javelin and Spear" in result

    def test_format_property_aura_when_equipped(self, game_data_resolver: GameDataResolver):
        result = format_property(151, [5, 10], resolver=game_data_resolver)
        assert "Aura" in result

    def test_format_property_float_g_format(self, game_data_resolver: GameDataResolver):
        result = format_property(214, [80], resolver=game_data_resolver)
        assert "Defense" in result
        assert "+" in result

    def test_format_property_float_g_negative(self, game_data_resolver: GameDataResolver):
        result = format_property(214, [-80], resolver=game_data_resolver)
        assert "-" in result

    def test_format_property_class_skill_levels(self, game_data_resolver: GameDataResolver):
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
            result = format_property(83, [class_id, 1], resolver=game_data_resolver)
            assert expected_name in result, f"Class ID {class_id} should format to {expected_name}"


class TestFormatItemInfoSetProperties:
    def test_format_item_info_with_set_properties(self, game_data_resolver: GameDataResolver):
        item = D2Item()
        item.item_info = ItemInfo()
        item.item_info.type_name = b"rin "
        item.item_info.type_specific_info = TypeSpecificInfo()

        p2 = PropertyList()
        p2.properties = [(31, 0, 60)]  # +60 Defense
        p3 = PropertyList()
        p3.properties = [(105, 0, 10)]  # +10% Faster Cast Rate

        item.item_info.type_specific_info.set_properties = [p2, p3, None, None, None]

        full_text = format_item_info(item, resolver=game_data_resolver)
        assert isinstance(full_text, str)
        assert "Set Properties (2 Items):" in full_text
        assert "Set Properties (3 Items):" in full_text
        assert "Defense" in full_text
        assert "Faster Cast Rate" in full_text
