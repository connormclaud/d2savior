import os

from d2savior.core.d2data import (
    D2DataLoader,
    GameData,
    StatInfo,
    TsvReader,
    VersionData,
)


class TestD2DataManager:
    """Test multi-version game data management."""

    manager: GameData
    default_data: VersionData

    def setup_method(self):
        """Set up test environment."""
        self.data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "d2savior", "data")
        self.manager = GameData.load(self.data_dir)
        default_data = self.manager.for_version(0x63)
        assert default_data is not None
        self.default_data = default_data

    def test_manager_initialization(self):
        """Test data manager initialization."""
        assert self.manager is not None, "Data manager initialization failed"
        assert self.default_data is not None, "Version data initialization failed"

    def test_version_data_loading(self):
        """Test version data loading."""
        default_data = self.manager.for_version(0x63)
        assert default_data is not None, "Default version data loading failed"

        item = default_data.get_item("gsw")
        assert item is not None, "Item data loading failed"
        assert item.name == "Diamond", "Item name incorrect"

    def test_version_specific_access(self):
        """Test version-specific data access."""
        item_v63 = self.manager.for_version(0x63).get_item("gsw")
        assert item_v63 is not None, "Version 0x63 item data loading failed"

        item_v69 = self.manager.for_version(0x69).get_item("gsw")
        assert item_v69 is not None, "Version 0x69 item data loading failed"

    def test_version_data_isolation(self):
        """Test version data isolation: 0x63 and 0x69 item counts should differ."""
        v63 = self.manager.for_version(0x63)
        v69 = self.manager.for_version(0x69)
        assert v63 is not None
        assert v69 is not None
        assert len(v63.items) != len(v69.items), (
            "0x63 and 0x69 item counts should differ (0x69 should have more)"
        )
        assert len(v69.items) > len(v63.items), "Version 0x69 should have more items"
        assert len(v69.stats) > len(v63.stats), "Version 0x69 should have more stats"

    def test_version_data_stat_cost_property_and_setter(self):
        v63 = self.manager.for_version(0x63)
        assert v63.stat_cost is v63.stats
        dummy_stats = {9999: StatInfo(stat_id=9999, stat_name="dummy")}
        original_stats = v63.stats
        try:
            v63.stat_cost = dummy_stats
            assert v63.stat_cost is dummy_stats
            assert v63.stats is dummy_stats
        finally:
            v63.stats = original_stats

    def test_fallback_mechanism(self):
        """Test fallback mechanism: missing files in 0x63 should load from root directory."""
        v63 = self.manager.for_version(0x63)
        assert v63 is not None
        # Directory 0x63 does not have Properties.txt, should fall back to base directory
        assert len(v63.properties) > 0, "0x63 properties should be loaded via fallback"
        assert len(v63.magic_prefixes) > 0, "0x63 magic prefixes should be loaded via fallback"
        assert len(v63.magic_suffixes) > 0, "0x63 magic suffixes should be loaded via fallback"
        assert len(v63.unique_items) > 0, "0x63 unique items should be loaded via fallback"
        assert len(v63.skills) > 0, "0x63 skills should be loaded via fallback"

    def test_resolve_path_fallback(self):
        """Test _resolve_path search chain fallback logic."""
        from importlib.resources.abc import Traversable

        loader = D2DataLoader()

        v63_dir = os.path.join(self.data_dir, "0x63")
        d2r_dir = os.path.join(self.data_dir, "d2r")
        search_dirs = [v63_dir, d2r_dir]

        # File existing in 0x63 takes priority
        path = loader._resolve_path("Armor.txt", search_dirs)
        assert isinstance(path, Traversable)
        assert str(path).startswith(v63_dir), "Should prioritize loading from 0x63 directory"

        # File missing in 0x63 but existing in d2r
        path = loader._resolve_path("Properties.txt", search_dirs)
        assert isinstance(path, Traversable)
        assert str(path).startswith(d2r_dir), "Missing file should fall back to d2r base directory"
        assert "0x63" not in str(path)

        # Sequence search_dirs with explicit fallback_dir
        path = loader._resolve_path("Properties.txt", search_dirs=[v63_dir], fallback_dir=d2r_dir)
        assert isinstance(path, Traversable)
        assert str(path).startswith(d2r_dir)

        # File not existing anywhere raises FileNotFoundError
        import pytest

        with pytest.raises(FileNotFoundError):
            loader._resolve_path("nonexistent.txt", search_dirs)

    def test_backward_compatibility(self):
        """Test backward compatibility."""
        item = self.default_data.get_item("gsw")
        assert item is not None, "Item data loading failed"
        assert item.name == "Diamond", "Item name incorrect"

    def test_stat_access(self):
        """Test stat data access."""
        stat = self.manager.for_version(0x63).get_stat(1)
        assert stat is not None, "Stat data loading failed"

    def test_property_access(self):
        """Test property data access."""
        prop = self.manager.for_version(0x63).get_property(1)
        assert prop is not None, "Property data loading failed"

    def test_magic_affix_access(self):
        """Test magic prefix and suffix data access (0-based index)."""
        prefix_0 = self.manager.for_version(0x63).get_magic_prefix(0)
        prefix_1 = self.manager.for_version(0x63).get_magic_prefix(1)
        suffix_0 = self.manager.for_version(0x63).get_magic_suffix(0)
        suffix_1 = self.manager.for_version(0x63).get_magic_suffix(1)

        # Row 0 in magicprefix.txt is empty; row 1 is Sturdy
        assert prefix_0 is None
        assert prefix_1 is not None
        assert prefix_1.name == "Sturdy"
        # Row 0 in magicsuffix.txt is of Health; row 1 is of Protection
        assert suffix_0 is not None
        assert suffix_0.name == "of Health"
        assert suffix_1 is not None
        assert suffix_1.name == "of Protection"

    def test_rare_affix_access(self):
        """Test rare prefix and suffix data access with Diablo II unified indexing."""
        vd_63 = self.manager.for_version(0x63)
        vd_69 = self.manager.for_version(0x69)

        for vd in (vd_63, vd_69):
            # Prefixes start at 156 (offset by 155 entries of raresuffix.txt)
            assert vd.get_rare_prefix(156) == "Beast"
            assert vd.get_rare_prefix(164) == "Doom"
            assert vd.get_rare_prefix(167) == "Death"
            assert vd.get_rare_prefix(201) == "Corruption"

            # 1-based row index fallback
            assert vd.get_rare_prefix(1) == "Beast"
            assert vd.get_rare_prefix(9) == "Doom"
            assert vd.get_rare_prefix(12) == "Death"

            # Suffixes are 1-based (1..155)
            assert vd.get_rare_suffix(1) == "bite"
            assert vd.get_rare_suffix(128) == "gyre"
            assert vd.get_rare_suffix(132) == "heart"
            assert vd.get_rare_suffix(155) == "flange"

            # Out of bounds
            assert vd.get_rare_prefix(0) is None
            assert vd.get_rare_prefix(999) is None
            assert vd.get_rare_suffix(0) is None
            assert vd.get_rare_suffix(999) is None

    def test_unique_item_access(self):
        """Test unique item data access."""
        unique = self.manager.for_version(0x63).get_unique_item(1)
        assert unique is not None, "Unique item data loading failed"

    def test_skill_name_access(self):
        """Test skill name access."""
        skill_name = self.manager.for_version(0x63).get_skill_name(1)
        assert isinstance(skill_name, str), "Skill name return type incorrect"

    def test_is_descendant(self):
        """Test type inheritance relationship."""
        is_armor = self.manager.for_version(0x63).is_descendant("shie", "armo")
        assert is_armor, "Type inheritance check failed"

    def test_warlock_set_items_0x69(self):
        """Test version 0x69 warlock set item data."""
        expected = {
            76: ("Tal Rasha's Fire-Spun Cloth", 21816),
            79: ("Tal Rasha's Howling Wind", 21818),
            127: ("Warlord's Conquest", 27389),
            128: ("Warlord's Lust", 27388),
            132: ("Bane's Oathmaker", 27641),
            135: ("Horazon's Countenance", 27644),
            136: ("Horazon's Dominion", 27645),
            137: ("Horazon's Hold", 27646),
            138: ("Horazon's Legacy", 27647),
            139: ("Horazon's Secrets", 27648),
        }
        for idx, (name, item_id) in expected.items():
            info = self.manager.for_version(0x69).get_set_item(idx)
            assert info is not None, f"Missing set item at index {idx}"
            assert info.name == name
            assert info.set_id == item_id

            # Resolution by D2R string ID as well
            info_by_id = self.manager.for_version(0x69).get_set_item(item_id)
            assert info_by_id is not None, f"Missing set item by D2R id {item_id}"
            assert info_by_id.name == name

        # Localized set names from item-names.json via GameDataResolver
        from d2savior.core.d2data import GameDataResolver
        from d2savior.core.localized_data import LocalizedDataLoader

        loc = LocalizedDataLoader.load(os.path.join(self.data_dir, "d2r", "local"), lang_key="enUS")
        resolver = GameDataResolver(game_data=self.manager, loc=loc, version=0x69)
        assert resolver.get_localized_set_name(76) == "Tal Rasha's Fine-Spun Cloth"
        assert resolver.get_localized_set_name(79) == "Tal Rasha's Guardianship"
        assert resolver.get_localized_set_name(68) == "Aldur's Rhythm"
        assert resolver.get_localized_set_name(126) == "Sander's Superstition"

    def test_runeword_resolution_by_d2r_and_classic_id(self):
        """Test resolving Spirit runeword via D2R string ID (20635) and classic runes.txt index (130)."""
        v69 = self.manager.for_version(0x69)
        rw_by_d2r = v69.get_runeword(20635)
        assert rw_by_d2r is not None
        assert rw_by_d2r.name == "Spirit"
        assert rw_by_d2r.key == "Runeword130"
        assert rw_by_d2r.rune_codes == ["r07", "r10", "r09", "r11"]

    def test_load_runes_txt_deprecated(self):
        """Test that load_runes_txt emits DeprecationWarning."""
        import pytest

        loader = D2DataLoader()
        runes_path = os.path.join(self.data_dir, "d2r", "runes.txt")
        with pytest.deprecated_call():
            loader.load_runes_txt(runes_path, {})  # ty: ignore[deprecated]


class TestTsvReader:
    """Unit tests for shared TSV table parsing semantics."""

    def test_bom_crlf_case_insensitive_and_defaults(self, tmp_path):
        tsv = tmp_path / "sample.txt"
        tsv.write_bytes(
            b"\xef\xbb\xbf Name \t*Id\tFlag\r\n"
            b"\r\n"
            b"*comment\t99\t1\r\n"
            b"Alpha \t 10 \t1\r\n"
            b"Beta\tbad\t0\r\n"
        )

        reader = TsvReader(tsv)
        assert reader.has_columns("name", "*id", "FLAG")
        assert not reader.has_columns("name", "missing")

        rows = list(reader)
        assert len(rows) == 2
        assert rows[0].index == 2
        assert rows[0].get("NAME") == "Alpha"
        assert rows[0].get_int("*id") == 10
        assert rows[0].get_bool("flag") is True

        assert rows[1].index == 3
        assert rows[1].get("name") == "Beta"
        assert rows[1].get_int("*ID", -1) == -1
        assert rows[1].get_int("missing", 42) == 42
        assert rows[1].get_bool("flag") is False

    def test_skip_expansion_and_row_index(self, tmp_path):
        tsv = tmp_path / "affixes.txt"
        tsv.write_text(
            "Name\tlevel\n\t0\nClassic\t5\nExpansion\t\nLoD\t12\n",
            encoding="utf-8",
        )

        default_rows = [(r.index, r.get("Name")) for r in TsvReader(tsv)]
        assert default_rows == [(0, ""), (1, "Classic"), (3, "LoD")]

        with_expansion = [(r.index, r.get("Name")) for r in TsvReader(tsv, skip_expansion=False)]
        assert with_expansion == [(0, ""), (1, "Classic"), (2, "Expansion"), (3, "LoD")]

    def test_strip_cells_false_preserves_trailing_space_and_leading_tab(self, tmp_path):
        tsv = tmp_path / "items.txt"
        tsv.write_text("name\tcode\nStudded Leather \tstu\n\tblankfirst\n", encoding="utf-8")

        rows = list(TsvReader(tsv, strip_cells=False))
        assert [(r.get("name"), r.get("code")) for r in rows] == [
            ("Studded Leather ", "stu"),
            ("", "blankfirst"),
        ]

    def test_empty_file_yields_no_rows(self, tmp_path):
        tsv = tmp_path / "empty.txt"
        tsv.write_text("", encoding="utf-8")

        reader = TsvReader(tsv)
        assert not reader.has_columns("name")
        assert list(reader) == []
