import unittest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.localized_data import (
    LocalizedDataLoader, 
    init_localized_data, 
    get_localized_data,
    clean_d2_text
)


class TestLocalizedDataLoader(unittest.TestCase):
    def setUp(self):
        self.data_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "local"
        )
        self.loader = LocalizedDataLoader()
    
    def test_load_single_file(self):
        filepath = os.path.join(self.data_dir, "item-modifiers.json")
        result = self.loader.load_json_file(filepath, lang_key='enUS')
        self.assertTrue(result, "Failed to load item-modifiers.json")
        
        # 测试获取数据
        text = self.loader.get_item_modifier('ModitemAura')
        self.assertIn('Aura', text)
    
    def test_load_all_files(self):
        results = self.loader.load_all_localized_data(self.data_dir, lang_key='enUS')
        
        # 检查至少有一些文件成功加载
        loaded_count = sum(1 for success in results.values() if success)
        self.assertGreater(loaded_count, 0, "No files were loaded")
        
        # 检查特定文件是否加载成功
        self.assertTrue(results.get('item-modifiers.json', False))
        self.assertTrue(results.get('skills.json', False))
        self.assertTrue(results.get('item-names.json', False))
    
    def test_different_languages(self):
        filepath = os.path.join(self.data_dir, "item-modifiers.json")
        
        # 测试英文
        self.loader.load_json_file(filepath, lang_key='enUS')
        text_en = self.loader.get_item_modifier('ModitemAura')
        self.assertIn('Aura', text_en)
        
        # 测试简体中文
        self.loader.load_json_file(filepath, lang_key='zhCN')
        text_zhcn = self.loader.get_item_modifier('ModitemAura')
        self.assertIn('光环', text_zhcn)
        
        # 测试繁体中文
        self.loader.load_json_file(filepath, lang_key='zhTW')
        text_zhtw = self.loader.get_item_modifier('ModitemAura')
        self.assertIn('靈氣', text_zhtw)
    
    def test_get_string_default(self):
        filepath = os.path.join(self.data_dir, "item-modifiers.json")
        self.loader.load_json_file(filepath, lang_key='enUS')
        
        # 测试不存在的键返回默认值
        result = self.loader.get_string('item-modifiers.json', 'NonExistentKey', 'DefaultText')
        self.assertEqual(result, 'DefaultText')
        
        # 测试不存在的键返回键本身
        result = self.loader.get_string('item-modifiers.json', 'NonExistentKey')
        self.assertEqual(result, 'NonExistentKey')
    
    def test_item_names(self):
        filepath = os.path.join(self.data_dir, "item-names.json")
        self.loader.load_json_file(filepath, lang_key='enUS')
        
        # 测试物品名称
        item_name = self.loader.get_item_name('qf1')
        self.assertIn('Khalim', item_name)
        self.assertIn('Flail', item_name)
    
    def test_monster_names(self):
        filepath = os.path.join(self.data_dir, "monsters.json")
        self.loader.load_json_file(filepath, lang_key='enUS')
        
        # 测试怪物名称
        monster_name = self.loader.get_monster_name('Fallen')
        self.assertEqual(monster_name, 'Fallen')

    def test_clean_d2_text(self):
        self.assertEqual(clean_d2_text("[ms]наголовник"), "наголовник")
        self.assertEqual(clean_d2_text("[ns]шако"), "шако")
        self.assertEqual(
            clean_d2_text("[ms]украшенный розой[fs]украшенная розой[ns]украшенное розой"),
            "украшенный розой"
        )
        self.assertEqual(clean_d2_text("Шутовской капюшон"), "Шутовской капюшон")
        self.assertEqual(clean_d2_text(""), "")
        self.assertEqual(clean_d2_text(None), "")

    def test_ru_localization(self):
        self.loader.load_all_localized_data(self.data_dir, lang_key='ruRU')
        self.assertEqual(self.loader.get_item_name('cap'), "наголовник")
        self.assertEqual(self.loader.get_rune_name('r08'), "Руна Рал")
        self.assertEqual(self.loader.get_class_name(1), "Волшебница")
        self.assertEqual(self.loader.get_quest_name('Den of Evil'), "Логово зла")
        self.assertEqual(self.loader.get_level_name('Rogue Encampment'), "Лагерь разбойниц")


class TestGlobalLocalizedData(unittest.TestCase):
    def setUp(self):
        self.data_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "local"
        )
    
    def test_init_localized_data(self):
        results = init_localized_data(self.data_dir, lang_key='enUS')
        
        # 检查至少有一些文件成功加载
        loaded_count = sum(1 for success in results.values() if success)
        self.assertGreater(loaded_count, 0)
    
    def test_get_localized_data_singleton(self):
        loader1 = get_localized_data()
        loader2 = get_localized_data()
        
        # 应该返回同一个实例
        self.assertIs(loader1, loader2)
    
    def test_language_switching(self):
        # 测试英文
        init_localized_data(self.data_dir, lang_key='enUS')
        loader = get_localized_data()
        text_en = loader.get_item_modifier('ModitemAura')
        self.assertIn('Aura', text_en)
        
        # 测试简体中文
        init_localized_data(self.data_dir, lang_key='zhCN')
        loader = get_localized_data()
        text_zhcn = loader.get_item_modifier('ModitemAura')
        self.assertIn('光环', text_zhcn)

    def tearDown(self):
        init_localized_data(self.data_dir, lang_key='enUS')


if __name__ == '__main__':
    unittest.main()
