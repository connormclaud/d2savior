import os

import pytest

from d2savior.core.d2data import D2DataLoader, GameData
from d2savior.core.localized_data import LocalizedDataLoader
from d2savior.core.property import init_item_modifiers


class TestDataGuard:
    @pytest.fixture(autouse=True)
    def setup_paths(self):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.data_dir = os.path.join(self.base_dir, "d2savior", "data")
        self.local_dir = os.path.join(self.data_dir, "d2r", "local")

    def test_loader_raises_on_missing_required_files(self):
        loader = D2DataLoader()
        bogus_path = os.path.join(self.data_dir, "nonexistent_file_xyz.txt")

        with pytest.raises(FileNotFoundError):
            loader.load_itemtypes(bogus_path)

        with pytest.raises(FileNotFoundError):
            loader.load_itemstatcost(bogus_path)

        with pytest.raises(FileNotFoundError):
            loader.load_properties(bogus_path)

        with pytest.raises(FileNotFoundError):
            loader.load_items_txt(bogus_path, "misc")

        with pytest.raises(FileNotFoundError):
            loader.load_magic_affix(bogus_path, is_prefix=True)

        with pytest.raises(FileNotFoundError):
            loader.load_unique_items(bogus_path)

        with pytest.raises(FileNotFoundError):
            loader.load_runewords(bogus_path)

        with pytest.raises(FileNotFoundError):
            loader.load_runes_txt(bogus_path, {})

        with pytest.raises(FileNotFoundError):
            loader.load_set_items(bogus_path)

        with pytest.raises(FileNotFoundError):
            loader.load_skills(bogus_path)

        with pytest.raises(FileNotFoundError):
            loader.load_property_meta(bogus_path)

        with pytest.raises(FileNotFoundError):
            loader.load_itemdata(bogus_path)

        loc_loader = LocalizedDataLoader()
        with pytest.raises(FileNotFoundError):
            loc_loader.load_json_file(bogus_path)

        with pytest.raises(FileNotFoundError):
            init_item_modifiers(bogus_path)

    def test_game_data_loaded_tables_non_empty(self):
        game_data = GameData.load(self.data_dir)
        for version in (0x63, 0x69):
            vd = game_data.for_version(version)
            assert vd is not None
            assert len(vd.items) > 0, f"version {version:#x} items table is empty"
            assert len(vd.stats) > 0, f"version {version:#x} stats table is empty"
            assert len(vd.properties) > 0, f"version {version:#x} properties table is empty"
            assert len(vd.magic_prefixes) > 0, f"version {version:#x} magic_prefixes is empty"
            assert len(vd.magic_suffixes) > 0, f"version {version:#x} magic_suffixes is empty"
            assert len(vd.unique_items) > 0, f"version {version:#x} unique_items is empty"
            assert len(vd.runewords) > 0, f"version {version:#x} runewords is empty"
            assert len(vd.set_items) > 0, f"version {version:#x} set_items is empty"
            assert len(vd.skills) > 0, f"version {version:#x} skills is empty"
            assert len(vd.prop_meta) > 0, f"version {version:#x} prop_meta is empty"
            assert vd.item_manager is not None

    def test_localized_data_all_required_files_loaded(self):
        loc_loader = LocalizedDataLoader()
        results = loc_loader.load_all_localized_data(self.local_dir, lang_key="enUS")
        assert len(results) == 17
        for fname, ok in results.items():
            assert ok is True, f"Failed to load localized file: {fname}"

    def test_no_uncatalogued_data_files(self):
        # Known files actively loaded by D2DataLoader / LocalizedDataLoader
        active_loader_files = {
            "0x63/Armor.txt",
            "0x63/ItemStatCost.txt",
            "0x63/Misc.txt",
            "0x63/Weapons.txt",
            "0x63/itemdata.txt",
            "0x63/itemtypes.txt",
            "0x63/property.txt",
            "d2r/Armor.txt",
            "d2r/ItemStatCost.txt",
            "d2r/Misc.txt",
            "d2r/Properties.txt",
            "d2r/Weapons.txt",
            "d2r/itemdata.txt",
            "d2r/itemtypes.txt",
            "d2r/magicprefix.txt",
            "d2r/magicsuffix.txt",
            "d2r/property.txt",
            "d2r/runes.txt",
            "d2r/skills.txt",
            "d2r/uniqueitems.txt",
            # Localized files
            "d2r/local/item-modifiers.json",
            "d2r/local/skills.json",
            "d2r/local/item-names.json",
            "d2r/local/item-nameaffixes.json",
            "d2r/local/item-gems.json",
            "d2r/local/item-runes.json",
            "d2r/local/monsters.json",
            "d2r/local/npcs.json",
            "d2r/local/quests.json",
            "d2r/local/shrines.json",
            "d2r/local/levels.json",
            "d2r/local/objects.json",
            "d2r/local/mercenaries.json",
            "d2r/local/commands.json",
            "d2r/local/keybinds.json",
            "d2r/local/tooltip-ui.json",
            "d2r/local/ui.json",
        }

        # Legacy files identified in survey pending cleanup in Step 3
        legacy_unloaded_files = {
            "README.py",
            "d2r/automagic.txt",
            "d2r/charstats.txt",
            "d2r/difficultylevels.txt",
            "d2r/experience.txt",
            "d2r/gems.txt",
            "d2r/itemratio.txt",
            "d2r/levels.txt",
            "d2r/lvlmaze.txt",
            "d2r/lvlprest.txt",
            "d2r/lvlwarp.txt",
            "d2r/missiles.txt",
            "d2r/monstats.txt",
            "d2r/rareprefix.txt",
            "d2r/raresuffix.txt",
            "d2r/runewords.txt",
            "d2r/sets.txt",
            "d2r/skilldesc.txt",
            "d2r/treasureclassex.txt",
            "d2r/local/bnet.json",
            "d2r/local/chinese-overlay.json",
            "d2r/local/presence-states.json",
            "d2r/local/ui-controller.json",
            "d2r/local/vo.json",
        }

        actual_files = set()
        for root, _dirs, files in os.walk(self.data_dir):
            for f in files:
                rel = os.path.relpath(os.path.join(root, f), self.data_dir)
                actual_files.add(rel)

        uncatalogued = actual_files - active_loader_files - legacy_unloaded_files
        assert not uncatalogued, f"Found uncatalogued files in data directory: {uncatalogued}"
