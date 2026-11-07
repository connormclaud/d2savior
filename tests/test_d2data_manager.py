import os

from d2savior.core.d2data import (
    D2DataLoader,
    GameData,
    StatInfo,
    VersionData,
    get_game_data,
    init_d2data,
)


class TestD2DataManager:
    """测试多版本数据管理功能"""

    manager: GameData
    default_data: VersionData

    def setup_method(self):
        """设置测试环境"""
        self.data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "d2savior", "data")
        init_d2data(self.data_dir)
        mgr = get_game_data()
        assert mgr is not None
        self.manager = mgr
        default_data = mgr.for_version(0x63)
        assert default_data is not None
        self.default_data = default_data

    def test_manager_initialization(self):
        """测试数据管理器初始化"""
        assert self.manager is not None, "数据管理器初始化失败"
        assert self.default_data is not None, "版本数据初始化失败"

    def test_version_data_loading(self):
        """测试版本数据加载"""
        default_data = self.manager.for_version(0x63)
        assert default_data is not None, "默认版本数据加载失败"

        item = default_data.get_item("gsw")
        assert item is not None, "物品数据加载失败"
        assert item.name == "Diamond", "物品名称不正确"

    def test_version_specific_access(self):
        """测试版本特定的数据访问"""
        item_v63 = self.manager.for_version(0x63).get_item("gsw")
        assert item_v63 is not None, "0x63版本物品数据加载失败"

        item_v69 = self.manager.for_version(0x69).get_item("gsw")
        assert item_v69 is not None, "0x69版本物品数据加载失败"

    def test_version_data_isolation(self):
        """测试版本数据隔离：0x63和0x69的物品数量应该不同"""
        v63 = self.manager.for_version(0x63)
        v69 = self.manager.for_version(0x69)
        assert v63 is not None
        assert v69 is not None
        assert len(v63.items) != len(v69.items), "0x63和0x69的物品数量应该不同（0x69应该更多）"
        assert len(v69.items) > len(v63.items), "0x69版本应该有更多物品"
        assert len(v69.stats) > len(v63.stats), "0x69版本应该有更多属性"

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
        """测试回退机制：0x63缺失的文件应从根目录加载"""
        v63 = self.manager.for_version(0x63)
        assert v63 is not None
        # 0x63目录没有Properties.txt，应该从根目录回退加载
        assert len(v63.properties) > 0, "0x63属性数据应通过回退机制加载"
        assert len(v63.magic_prefixes) > 0, "0x63魔法前缀应通过回退机制加载"
        assert len(v63.magic_suffixes) > 0, "0x63魔法后缀应通过回退机制加载"
        assert len(v63.unique_items) > 0, "0x63唯一物品应通过回退机制加载"
        assert len(v63.skills) > 0, "0x63技能数据应通过回退机制加载"

    def test_resolve_path_fallback(self):
        """测试_resolve_path覆盖链回退逻辑"""
        from importlib.resources.abc import Traversable

        loader = D2DataLoader()

        v63_dir = os.path.join(self.data_dir, "0x63")
        d2r_dir = os.path.join(self.data_dir, "d2r")
        search_dirs = [v63_dir, d2r_dir]

        # 0x63目录中存在的文件优先
        path = loader._resolve_path("Armor.txt", search_dirs)
        assert isinstance(path, Traversable)
        assert str(path).startswith(v63_dir), "应优先从0x63目录加载"

        # 0x63中不存在但在d2r中存在的文件
        path = loader._resolve_path("Properties.txt", search_dirs)
        assert isinstance(path, Traversable)
        assert str(path).startswith(d2r_dir), "缺失文件应从d2r基础目录回退加载"
        assert "0x63" not in str(path)

        # Sequence search_dirs with explicit fallback_dir
        path = loader._resolve_path("Properties.txt", search_dirs=[v63_dir], fallback_dir=d2r_dir)
        assert isinstance(path, Traversable)
        assert str(path).startswith(d2r_dir)

        # 都不存在的文件抛出FileNotFoundError
        import pytest

        with pytest.raises(FileNotFoundError):
            loader._resolve_path("nonexistent.txt", search_dirs)

    def test_backward_compatibility(self):
        """测试向后兼容性"""
        item = self.default_data.get_item("gsw")
        assert item is not None, "物品数据加载失败"
        assert item.name == "Diamond", "物品名称不正确"

    def test_stat_access(self):
        """测试属性数据访问"""
        stat = self.manager.for_version(0x63).get_stat(1)
        assert stat is not None, "属性数据加载失败"

    def test_property_access(self):
        """测试属性数据访问"""
        prop = self.manager.for_version(0x63).get_property(1)
        assert prop is not None, "属性数据加载失败"

    def test_magic_affix_access(self):
        """测试魔法前缀后缀数据访问"""
        prefix = self.manager.for_version(0x63).get_magic_prefix(1)
        suffix = self.manager.for_version(0x63).get_magic_suffix(1)
        assert prefix is not None, "魔法前缀数据加载失败"
        assert suffix is not None, "魔法后缀数据加载失败"

    def test_unique_item_access(self):
        """测试唯一物品数据访问"""
        unique = self.manager.for_version(0x63).get_unique_item(1)
        assert unique is not None, "唯一物品数据加载失败"

    def test_skill_name_access(self):
        """测试技能名称访问"""
        skill_name = self.manager.for_version(0x63).get_skill_name(1)
        assert isinstance(skill_name, str), "技能名称返回类型不正确"

    def test_is_descendant(self):
        """测试类型继承关系"""
        is_armor = self.manager.for_version(0x63).is_descendant("shie", "armo")
        assert is_armor, "类型继承关系判断错误"

    def test_warlock_set_items_0x69(self):
        """测试0x69版本术士套装物品数据"""
        expected = {
            127: ("Warlord's Lust", 27388),
            128: ("Warlord's Conquest", 27389),
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

    def test_runeword_resolution_by_d2r_and_classic_id(self):
        """测试通过D2R字符串ID (20635) 和经典runes.txt索引 (130) 解析符文之语Spirit"""
        v69 = self.manager.for_version(0x69)
        rw_by_d2r = v69.get_runeword(20635)
        assert rw_by_d2r is not None
        assert rw_by_d2r.name == "Spirit"
        assert rw_by_d2r.key == "Runeword130"
        assert rw_by_d2r.rune_codes == ["r07", "r10", "r09", "r11"]

    def test_load_runes_txt_deprecated(self):
        """测试load_runes_txt发出DeprecationWarning"""
        import pytest

        loader = D2DataLoader()
        runes_path = os.path.join(self.data_dir, "d2r", "runes.txt")
        with pytest.deprecated_call():
            loader.load_runes_txt(runes_path, {})  # ty: ignore[deprecated]
