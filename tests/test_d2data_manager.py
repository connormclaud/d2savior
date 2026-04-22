import os
import unittest
from core.d2data import init_d2data, get_d2data_manager, get_d2data, D2DataLoader


class TestD2DataManager(unittest.TestCase):
    """测试多版本数据管理功能"""
    
    def setUp(self):
        """设置测试环境"""
        self.data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
        init_d2data(self.data_dir)
        self.manager = get_d2data_manager()
        self.wrapper = get_d2data()
    
    def test_manager_initialization(self):
        """测试数据管理器初始化"""
        self.assertIsNotNone(self.manager, "数据管理器初始化失败")
        self.assertIsNotNone(self.wrapper, "数据包装器初始化失败")
    
    def test_version_data_loading(self):
        """测试版本数据加载"""
        default_data = self.manager.get_version_data(0x63)
        self.assertIsNotNone(default_data, "默认版本数据加载失败")
        
        item = self.manager.get_item('gsw', 0x63)
        self.assertIsNotNone(item, "物品数据加载失败")
        self.assertEqual(item.name, "Diamond", "物品名称不正确")
    
    def test_version_specific_access(self):
        """测试版本特定的数据访问"""
        item_v63 = self.manager.get_item('gsw', 0x63)
        self.assertIsNotNone(item_v63, "0x63版本物品数据加载失败")
        
        item_v69 = self.manager.get_item('gsw', 0x69)
        self.assertIsNotNone(item_v69, "0x69版本物品数据加载失败")
    
    def test_version_data_isolation(self):
        """测试版本数据隔离：0x63和0x69的物品数量应该不同"""
        v63 = self.manager.get_version_data(0x63)
        v69 = self.manager.get_version_data(0x69)
        self.assertNotEqual(len(v63.items), len(v69.items),
                            "0x63和0x69的物品数量应该不同（0x69应该更多）")
        self.assertGreater(len(v69.items), len(v63.items),
                           "0x69版本应该有更多物品")
        self.assertGreater(len(v69.stats), len(v63.stats),
                           "0x69版本应该有更多属性")
    
    def test_fallback_mechanism(self):
        """测试回退机制：0x63缺失的文件应从根目录加载"""
        v63 = self.manager.get_version_data(0x63)
        # 0x63目录没有Properties.txt，应该从根目录回退加载
        self.assertGreater(len(v63.properties), 0,
                           "0x63属性数据应通过回退机制加载")
        self.assertGreater(len(v63.magic_prefixes), 0,
                           "0x63魔法前缀应通过回退机制加载")
        self.assertGreater(len(v63.magic_suffixes), 0,
                           "0x63魔法后缀应通过回退机制加载")
        self.assertGreater(len(v63.unique_items), 0,
                           "0x63唯一物品应通过回退机制加载")
        self.assertGreater(len(v63.skills), 0,
                           "0x63技能数据应通过回退机制加载")
    
    def test_resolve_path_fallback(self):
        """测试_resolve_path回退逻辑"""
        loader = D2DataLoader()
        
        # 版本目录中存在的文件
        v63_dir = os.path.join(self.data_dir, '0x63')
        path = loader._resolve_path('Armor.txt', v63_dir, self.data_dir)
        self.assertTrue(path.startswith(v63_dir), "应优先从版本目录加载")
        
        # 版本目录中不存在但根目录存在的文件
        path = loader._resolve_path('Properties.txt', v63_dir, self.data_dir)
        self.assertTrue(path.startswith(self.data_dir) and '0x63' not in path,
                        "缺失文件应从根目录回退加载")
        
        # 两个目录都不存在的文件
        path = loader._resolve_path('nonexistent.txt', v63_dir, self.data_dir)
        self.assertIn('0x63', path, "都不存在时应返回版本目录路径")
    
    def test_backward_compatibility(self):
        """测试向后兼容性"""
        item = self.wrapper.get_item('gsw')
        self.assertIsNotNone(item, "旧接口物品数据加载失败")
        self.assertEqual(item.name, "Diamond", "旧接口物品名称不正确")
    
    def test_stat_access(self):
        """测试属性数据访问"""
        stat = self.manager.get_stat(1, 0x63)
        self.assertIsNotNone(stat, "属性数据加载失败")
    
    def test_property_access(self):
        """测试属性数据访问"""
        prop = self.manager.get_property(1, 0x63)
        self.assertIsNotNone(prop, "属性数据加载失败")
    
    def test_magic_affix_access(self):
        """测试魔法前缀后缀数据访问"""
        prefix = self.manager.get_magic_prefix(1, 0x63)
        suffix = self.manager.get_magic_suffix(1, 0x63)
        self.assertIsNotNone(prefix, "魔法前缀数据加载失败")
        self.assertIsNotNone(suffix, "魔法后缀数据加载失败")
    
    def test_unique_item_access(self):
        """测试唯一物品数据访问"""
        unique = self.manager.get_unique_item(1, 0x63)
        self.assertIsNotNone(unique, "唯一物品数据加载失败")
    
    def test_skill_name_access(self):
        """测试技能名称访问"""
        skill_name = self.manager.get_skill_name(1, 0x63)
        self.assertIsInstance(skill_name, str, "技能名称返回类型不正确")
    
    def test_is_descendant(self):
        """测试类型继承关系"""
        is_armor = self.manager.is_descendant('shie', 'armo', 0x63)
        self.assertTrue(is_armor, "类型继承关系判断错误")


if __name__ == '__main__':
    unittest.main()
