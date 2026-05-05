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
        self.assertEqual(item1.sTypeName, item2.sTypeName)
        self.assertEqual(item1.quality(), item2.quality())
        self.assertEqual(item1.bIdentified, item2.bIdentified)
        self.assertEqual(item1.bSimple, item2.bSimple)
        self.assertEqual(item1.bSocketed, item2.bSocketed)
        self.assertEqual(item1.bRuneWord, item2.bRuneWord)
        self.assertEqual(item1.bEthereal, item2.bEthereal)
        self.assertEqual(item1.bPersonalized, item2.bPersonalized)
        
        if item1.pItemInfo and item1.pItemInfo.pExtItemInfo and \
           item2.pItemInfo and item2.pItemInfo.pExtItemInfo:
            ext1 = item1.pItemInfo.pExtItemInfo
            ext2 = item2.pItemInfo.pExtItemInfo
            self.assertEqual(ext1.iQuality, ext2.iQuality)
            self.assertEqual(ext1.dwGUID, ext2.dwGUID)
            self.assertEqual(ext1.nGems, ext2.nGems)
    
    def _compare_properties(self, item1: D2Item, item2: D2Item):
        if not item1.pItemInfo or not item2.pItemInfo:
            return
        
        tp1 = item1.pItemInfo.pTpSpInfo
        tp2 = item2.pItemInfo.pTpSpInfo
        
        if not tp1 or not tp2:
            return
        
        props1 = tp1.stPropertyList.mProperty
        props2 = tp2.stPropertyList.mProperty
        
        self.assertEqual(len(props1), len(props2), 
                        f"Property count mismatch: {len(props1)} vs {len(props2)}")
        
        for i, (p1, p2) in enumerate(zip(props1, props2)):
            self.assertEqual(p1[0], p2[0], f"Property {i}: ID mismatch")
            self.assertEqual(p1[1], p2[1], f"Property {i}: Layer mismatch")
            self.assertEqual(p1[2], p2[2], f"Property {i}: Value mismatch")
        
        if item1.bRuneWord:
            self.assertIsNotNone(tp1.stRuneWordPropertyList, "Item1 should have runeword properties")
            self.assertIsNotNone(tp2.stRuneWordPropertyList, "Item2 should have runeword properties")
            
            rw_props1 = tp1.stRuneWordPropertyList.mProperty
            rw_props2 = tp2.stRuneWordPropertyList.mProperty
            
            self.assertEqual(len(rw_props1), len(rw_props2),
                           f"Runeword property count mismatch: {len(rw_props1)} vs {len(rw_props2)}")
            
            for i, (p1, p2) in enumerate(zip(rw_props1, rw_props2)):
                self.assertEqual(p1[0], p2[0], f"Runeword property {i}: ID mismatch")
                self.assertEqual(p1[1], p2[1], f"Runeword property {i}: Layer mismatch")
                self.assertEqual(p1[2], p2[2], f"Runeword property {i}: Value mismatch")
        
        if item1.is_set():
            self.assertEqual(len(tp1.aHasSetPropList), len(tp2.aHasSetPropList),
                           "Set property list count mismatch")
            
            for i, (has1, has2) in enumerate(zip(tp1.aHasSetPropList, tp2.aHasSetPropList)):
                self.assertEqual(has1, has2, f"Set property {i} existence mismatch")
                
                if has1 and has2:
                    set_props1 = tp1.apSetProperty[i].mProperty if tp1.apSetProperty[i] else []
                    set_props2 = tp2.apSetProperty[i].mProperty if tp2.apSetProperty[i] else []
                    
                    self.assertEqual(len(set_props1), len(set_props2),
                                   f"Set property {i} count mismatch: {len(set_props1)} vs {len(set_props2)}")
                    
                    for j, (p1, p2) in enumerate(zip(set_props1, set_props2)):
                        self.assertEqual(p1[0], p2[0], f"Set property {i}.{j}: ID mismatch")
                        self.assertEqual(p1[1], p2[1], f"Set property {i}.{j}: Layer mismatch")
                        self.assertEqual(p1[2], p2[2], f"Set property {i}.{j}: Value mismatch")
    
    def test_deserialize_unique_amulet_0x63(self):
        file_path = os.path.join(self.examples_dir, 'Rixots Keen.d2i')
        item = self._deserialize_item(file_path)
        
        self.assertEqual(item.sTypeName, b'amu ')
        self.assertEqual(item.quality(), 7)
        self.assertTrue(item.bIdentified)
        self.assertFalse(item.bSimple)
        self.assertEqual(item.dwVersion, 0x63)
    
    def test_deserialize_runeword_spirit_0x69(self):
        file_path = os.path.join(self.items_dir, 'runeword', 'Spirit-crystal_sword.d2i')
        item = self._deserialize_item(file_path, version=0x69)
        
        self.assertEqual(item.sTypeName, b'crs ')
        self.assertTrue(item.bRuneWord)
        self.assertTrue(item.bSocketed)
        self.assertTrue(item.bIdentified)
        self.assertFalse(item.bSimple)
        
        if item.pItemInfo and item.pItemInfo.pExtItemInfo:
            ext = item.pItemInfo.pExtItemInfo
            self.assertTrue(ext.wRune.exist())
            self.assertEqual(ext.wRune.value, 20635)
    
    def test_serialize_unique_amulet_0x63(self):
        file_path = os.path.join(self.examples_dir, 'Rixots Keen.d2i')
        
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
