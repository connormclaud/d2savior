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
        self.local_dir = os.path.join(self.data_dir, "local")

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
            "0x69/Armor.txt",
            "0x69/ItemStatCost.txt",
            "0x69/Misc.txt",
            "0x69/Properties.txt",
            "0x69/Weapons.txt",
            "0x69/itemdata.txt",
            "0x69/itemtypes.txt",
            "0x69/magicprefix.txt",
            "0x69/magicsuffix.txt",
            "0x69/property.txt",
            "0x69/runes.txt",
            "0x69/skills.txt",
            "0x69/uniqueitems.txt",
            "Armor.txt",
            "ItemStatCost.txt",
            "Misc.txt",
            "Properties.txt",
            "Weapons.txt",
            "itemdata.txt",
            "itemtypes.txt",
            "magicprefix.txt",
            "magicsuffix.txt",
            "runes.txt",
            "skills.txt",
            "uniqueitems.txt",
            # Localized files
            "local/item-modifiers.json",
            "local/skills.json",
            "local/item-names.json",
            "local/item-nameaffixes.json",
            "local/item-gems.json",
            "local/item-runes.json",
            "monsters.json",
            "npcs.json",
            "quests.json",
            "shrines.json",
            "levels.json",
            "objects.json",
            "mercenaries.json",
            "commands.json",
            "keybinds.json",
            "tooltip-ui.json",
            "ui.json",
            "0x69/local/item-modifiers.json",
            "0x69/local/skills.json",
            "0x69/local/item-names.json",
            "0x69/local/item-nameaffixes.json",
            "0x69/local/item-gems.json",
            "0x69/local/item-runes.json",
        }

        # Legacy files identified in survey pending cleanup in Step 2/3
        legacy_unloaded_files = {
            "README.py",
            "automagic.txt",
            "charstats.txt",
            "difficultylevels.txt",
            "experience.txt",
            "gems.txt",
            "itemdata_merged.txt",
            "itemratio.txt",
            "levels.txt",
            "lvlmaze.txt",
            "lvlprest.txt",
            "lvlwarp.txt",
            "missiles.txt",
            "monstats.txt",
            "property_merged.txt",
            "rareprefix.txt",
            "raresuffix.txt",
            "runewords.txt",
            "sets.txt",
            "skilldesc.txt",
            "treasureclassex.txt",
            "0x69/automagic.txt",
            "0x69/charstats.txt",
            "0x69/difficultylevels.txt",
            "0x69/experience.txt",
            "0x69/gems.txt",
            "0x69/itemratio.txt",
            "0x69/levels.txt",
            "0x69/lvlmaze.txt",
            "0x69/lvlprest.txt",
            "0x69/lvlwarp.txt",
            "0x69/missiles.txt",
            "0x69/monstats.txt",
            "0x69/rareprefix.txt",
            "0x69/raresuffix.txt",
            "0x69/runewords.txt",
            "0x69/sets.txt",
            "0x69/skilldesc.txt",
            "0x69/treasureclassex.txt",
            "local/bnet.json",
            "local/chinese-overlay.json",
            "local/presence-states.json",
            "local/ui-controller.json",
            "local/vo.json",
            "0x69/local/bnet.json",
            "0x69/local/chinese-overlay.json",
            "0x69/local/commands.json",
            "0x69/local/keybinds.json",
            "0x69/local/levels.json",
            "0x69/local/mercenaries.json",
            "0x69/local/monsters.json",
            "0x69/local/npcs.json",
            "0x69/local/objects.json",
            "0x69/local/presence-states.json",
            "0x69/local/quests.json",
            "0x69/local/shrines.json",
            "0x69/local/ui-controller.json",
            "0x69/local/ui.json",
            "0x69/local/vo.json",
        }

        # Gather actual files relative to data_dir
        actual_files = set()
        for root, _dirs, files in os.walk(self.data_dir):
            for f in files:
                rel = os.path.relpath(os.path.join(root, f), self.data_dir)
                actual_files.add(rel)

        # Normalize localized files that might appear under local/
        normalized_active = set()
        for f in active_loader_files:
            if not f.startswith("local/") and not f.startswith("0x") and f.endswith(".json"):
                normalized_active.add(f"local/{f}")
            else:
                normalized_active.add(f)

        uncatalogued = actual_files - normalized_active - legacy_unloaded_files
        assert not uncatalogued, f"Found uncatalogued files in data directory: {uncatalogued}"
