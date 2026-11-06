import unittest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.ibitstream import IBitStream
from core.obitstream import OBitStream
from core.item import D2Item, init_item_data


class TestItemSerialization(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        data_dir = os.path.join(base_dir, 'data')
        init_item_data(
            os.path.join(data_dir, 'itemdata.txt'),
            os.path.join(data_dir, 'property.txt'),
            os.path.join(data_dir, 'ItemStatCost.txt')
        )
        cls.examples_dir = os.path.join(base_dir, '..', 'examples')
        cls.items_dir = os.path.join(base_dir, '..', 'items')
    
    def _deserialize_item(self, file_path: str, version: int = None):
        if not os.path.exists(file_path):
            self.skipTest(f"Test file not found: {file_path}")
        with open(file_path, 'rb') as f:
            data = f.read()
        
        bs = IBitStream(data)
        item = D2Item()
        
        if version is not None:
            item.deserialize(bs, version, read_magic=False)
        else:
            item.deserialize(bs, 0x63, read_magic=True)
        
        return item
    
    def _serialize_item(self, item: D2Item, version: int):
        bs = OBitStream()
        item.serialize(bs, version, write_magic=False)
        return bs.get_data()
    
    def _compare_items(self, item1: D2Item, item2: D2Item):
        self.assertEqual(item1.type_name, item2.type_name)
        self.assertEqual(item1.quality(), item2.quality())
        self.assertEqual(item1.is_identified, item2.is_identified)
        self.assertEqual(item1.is_simple, item2.is_simple)
        self.assertEqual(item1.is_socketed, item2.is_socketed)
        self.assertEqual(item1.is_runeword, item2.is_runeword)
        self.assertEqual(item1.is_ethereal, item2.is_ethereal)
        self.assertEqual(item1.is_personalized, item2.is_personalized)

        if item1.item_info and item1.item_info.ext_info and \
           item2.item_info and item2.item_info.ext_info:
            ext1 = item1.item_info.ext_info
            ext2 = item2.item_info.ext_info
            self.assertEqual(ext1.quality, ext2.quality)
            self.assertEqual(ext1.guid, ext2.guid)
            self.assertEqual(ext1.gems, ext2.gems)
    
    def _compare_properties(self, item1: D2Item, item2: D2Item):
        if not item1.item_info or not item2.item_info:
            return
        
        tp1 = item1.item_info.type_specific_info
        tp2 = item2.item_info.type_specific_info
        
        if not tp1 or not tp2:
            return
        
        props1 = tp1.property_list.mProperty
        props2 = tp2.property_list.mProperty
        
        self.assertEqual(len(props1), len(props2), 
                        f"Property count mismatch: {len(props1)} vs {len(props2)}")
        
        for i, (p1, p2) in enumerate(zip(props1, props2)):
            self.assertEqual(p1[0], p2[0], f"Property {i}: ID mismatch")
            self.assertEqual(p1[1], p2[1], f"Property {i}: Layer mismatch")
            self.assertEqual(p1[2], p2[2], f"Property {i}: Value mismatch")
        
        if item1.is_runeword:
            self.assertIsNotNone(tp1.runeword_property_list, "Item1 should have runeword properties")
            self.assertIsNotNone(tp2.runeword_property_list, "Item2 should have runeword properties")
            
            rw_props1 = tp1.runeword_property_list.mProperty
            rw_props2 = tp2.runeword_property_list.mProperty
            
            self.assertEqual(len(rw_props1), len(rw_props2),
                           f"Runeword property count mismatch: {len(rw_props1)} vs {len(rw_props2)}")
            
            for i, (p1, p2) in enumerate(zip(rw_props1, rw_props2)):
                self.assertEqual(p1[0], p2[0], f"Runeword property {i}: ID mismatch")
                self.assertEqual(p1[1], p2[1], f"Runeword property {i}: Layer mismatch")
                self.assertEqual(p1[2], p2[2], f"Runeword property {i}: Value mismatch")
        
        if item1.is_set():
            self.assertEqual(len(tp1.has_set_prop_list), len(tp2.has_set_prop_list),
                           "Set property list count mismatch")
            
            for i, (has1, has2) in enumerate(zip(tp1.has_set_prop_list, tp2.has_set_prop_list)):
                self.assertEqual(has1, has2, f"Set property {i} existence mismatch")
                
                if has1 and has2:
                    set_props1 = tp1.set_properties[i].mProperty if tp1.set_properties[i] else []
                    set_props2 = tp2.set_properties[i].mProperty if tp2.set_properties[i] else []
                    
                    self.assertEqual(len(set_props1), len(set_props2),
                                   f"Set property {i} count mismatch: {len(set_props1)} vs {len(set_props2)}")
                    
                    for j, (p1, p2) in enumerate(zip(set_props1, set_props2)):
                        self.assertEqual(p1[0], p2[0], f"Set property {i}.{j}: ID mismatch")
                        self.assertEqual(p1[1], p2[1], f"Set property {i}.{j}: Layer mismatch")
                        self.assertEqual(p1[2], p2[2], f"Set property {i}.{j}: Value mismatch")
    
    def test_deserialize_unique_amulet_0x63(self):
        file_path = os.path.join(self.examples_dir, 'Rixots Keen.d2i')
        item = self._deserialize_item(file_path)
        
        self.assertEqual(item.type_name, b'amu ')
        self.assertEqual(item.quality(), 7)
        self.assertTrue(item.is_identified)
        self.assertFalse(item.is_simple)
        self.assertEqual(item.version, 0x63)
    
    def test_deserialize_runeword_spirit_0x69(self):
        file_path = os.path.join(self.items_dir, 'runeword', 'Spirit-crystal_sword.d2i')
        item = self._deserialize_item(file_path, version=0x69)
        
        self.assertEqual(item.type_name, b'crs ')
        self.assertTrue(item.is_runeword)
        self.assertTrue(item.is_socketed)
        self.assertTrue(item.is_identified)
        self.assertFalse(item.is_simple)

        if item.item_info and item.item_info.ext_info:
            ext = item.item_info.ext_info
            self.assertIsNotNone(ext.rune_id)
            self.assertEqual(ext.rune_id, 20635)
    
    def test_serialize_unique_amulet_0x63(self):
        file_path = os.path.join(self.examples_dir, 'Rixots Keen.d2i')
        if not os.path.exists(file_path):
            self.skipTest(f"Test file not found: {file_path}")
        
        with open(file_path, 'rb') as f:
            original_data = f.read()
        
        item = self._deserialize_item(file_path)
        
        serialized_data = self._serialize_item(item, 0x63)
        
        bs = IBitStream(serialized_data)
        item2 = D2Item()
        item2.deserialize(bs, 0x63, read_magic=False)
        
        self._compare_items(item, item2)
        self._compare_properties(item, item2)
    
    def test_serialize_runeword_spirit_0x69(self):
        file_path = os.path.join(self.items_dir, 'runeword', 'Spirit-crystal_sword.d2i')
        
        item = self._deserialize_item(file_path, version=0x69)
        
        serialized_data = self._serialize_item(item, 0x69)
        
        bs = IBitStream(serialized_data)
        item2 = D2Item()
        item2.deserialize(bs, 0x69, read_magic=False)
        
        self._compare_items(item, item2)
        self._compare_properties(item, item2)
    
    def test_serialize_magic_item_0x69(self):
        file_path = os.path.join(self.items_dir, 'magic', 'cm1_006.d2i')
        
        item = self._deserialize_item(file_path, version=0x69)
        
        self.assertEqual(item.quality(), 4, "Item should be magic quality")
        
        serialized_data = self._serialize_item(item, 0x69)
        
        bs = IBitStream(serialized_data)
        item2 = D2Item()
        item2.deserialize(bs, 0x69, read_magic=False)
        
        self._compare_items(item, item2)
        self._compare_properties(item, item2)
    
    def test_serialize_rare_item_0x69(self):
        file_path = os.path.join(self.items_dir, 'rare', 'wa4_012.d2i')
        
        item = self._deserialize_item(file_path, version=0x69)
        
        self.assertEqual(item.quality(), 6, "Item should be rare quality")
        
        serialized_data = self._serialize_item(item, 0x69)
        
        bs = IBitStream(serialized_data)
        item2 = D2Item()
        item2.deserialize(bs, 0x69, read_magic=False)
        
        self._compare_items(item, item2)
        self._compare_properties(item, item2)
    
    def test_serialize_set_item_0x69(self):
        file_path = os.path.join(self.items_dir, 'set', 'hbl_000.d2i')
        
        item = self._deserialize_item(file_path, version=0x69)
        
        self.assertEqual(item.quality(), 5, "Item should be set quality")
        
        serialized_data = self._serialize_item(item, 0x69)
        
        bs = IBitStream(serialized_data)
        item2 = D2Item()
        item2.deserialize(bs, 0x69, read_magic=False)
        
        self._compare_items(item, item2)
        self._compare_properties(item, item2)
    
    def test_serialize_normal_item_0x69(self):
        file_path = os.path.join(self.items_dir, 'normal', 'box_009.d2i')
        
        item = self._deserialize_item(file_path, version=0x69)
        
        self.assertEqual(item.quality(), 2, "Item should be normal quality")
        
        serialized_data = self._serialize_item(item, 0x69)
        
        bs = IBitStream(serialized_data)
        item2 = D2Item()
        item2.deserialize(bs, 0x69, read_magic=False)
        
        self._compare_items(item, item2)


if __name__ == '__main__':
    unittest.main()
