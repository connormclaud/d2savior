import pytest
import os
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.ibitstream import IBitStream
from core.obitstream import OBitStream
from core.d2s_struct import D2SStruct
from core.item import init_item_data
from core.d2data import init_d2data
from core.localized_data import init_localized_data


class TestCharSerialization:
    @classmethod
    def setup_class(cls):
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
        
        init_item_data(
            os.path.join(data_dir, 'itemdata.txt'),
            os.path.join(data_dir, 'property.txt'),
            os.path.join(data_dir, 'ItemStatCost.txt')
        )
        init_d2data(data_dir)
        init_localized_data(os.path.join(data_dir, 'local'), lang_key='enUS')
    
    def _test_char_roundtrip(self, save_file):
        with open(save_file, 'rb') as f:
            original_data = f.read()
        
        bs = IBitStream(original_data)
        d2s = D2SStruct()
        d2s.deserialize(bs)
        
        obs = OBitStream()
        d2s.serialize(obs)
        
        serialized_data = obs.get_data()
        
        print(f'\nOriginal size: {len(original_data)} bytes')
        print(f'Serialized size: {len(serialized_data)} bytes')
        
        if len(original_data) != len(serialized_data):
            print(f'\nSize mismatch: {len(original_data)} vs {len(serialized_data)}')
            
            for i in range(min(len(original_data), len(serialized_data))):
                if original_data[i] != serialized_data[i]:
                    print(f'First diff at offset 0x{i:04X}: 0x{original_data[i]:02X} vs 0x{serialized_data[i]:02X}')
                    print(f'Context (original): {original_data[max(0,i-10):i+10].hex()}')
                    print(f'Context (serialized): {serialized_data[max(0,i-10):i+10].hex()}')
                    break
        
        assert len(original_data) == len(serialized_data), f'Size mismatch: {len(original_data)} vs {len(serialized_data)}'
        
        if original_data != serialized_data:
            for i in range(len(original_data)):
                if original_data[i] != serialized_data[i]:
                    print(f'Diff at 0x{i:04X}: 0x{original_data[i]:02X} vs 0x{serialized_data[i]:02X}')
                    if i > 10:
                        break
        
        assert original_data == serialized_data, 'Data mismatch after round-trip'
    
    def test_serialize_warlock_0x69(self):
        save_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '..', 'examples', '0x69', 'warlock.d2s')
        if os.path.exists(save_file):
            self._test_char_roundtrip(save_file)
        else:
            pytest.skip(f'Save file not found: {save_file}')
    
    def test_serialize_amazon_0x63(self):
        save_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '..', 'examples', '0x63', 'Amazon.d2s')
        if os.path.exists(save_file):
            self._test_char_roundtrip(save_file)
        else:
            pytest.skip(f'Save file not found: {save_file}')
    
    def test_serialize_paladin_0x63(self):
        save_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '..', 'examples', '0x63', 'Paladin.d2s')
        if os.path.exists(save_file):
            self._test_char_roundtrip(save_file)
        else:
            pytest.skip(f'Save file not found: {save_file}')
    
    def test_serialize_0x63(self):
        save_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '..', 'examples', '0x63')
        if not os.path.exists(save_dir):
            pytest.skip(f'Save directory not found: {save_dir}')
        save_files = [f for f in os.listdir(save_dir) if f.endswith('.d2s')]
        if not save_files:
            pytest.skip(f'No .d2s files found in {save_dir}')
        self._test_char_roundtrip(os.path.join(save_dir, save_files[0]))
    
    def _test_checksum_update(self, save_file):
        with open(save_file, 'rb') as f:
            original_data = f.read()
        
        bs = IBitStream(original_data)
        d2s = D2SStruct()
        d2s.deserialize(bs)
        
        obs = OBitStream()
        d2s.serialize(obs)
        serialized_data = obs.get_data()
        
        d2s.size = len(serialized_data)
        final_data = d2s.update_checksum(serialized_data)
        
        checksum = int.from_bytes(final_data[0x0C:0x10], 'little')
        assert checksum != 0, 'Checksum should not be zero'
        
        verify_checksum = d2s.calculate_checksum(final_data)
        assert verify_checksum == checksum, f'Checksum verification failed: {verify_checksum} vs {checksum}'
    
    def test_checksum_warlock_0x69(self):
        save_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '..', 'examples', '0x69', 'warlock.d2s')
        if os.path.exists(save_file):
            self._test_checksum_update(save_file)
        else:
            pytest.skip(f'Save file not found: {save_file}')
    
    def test_checksum_0x63(self):
        save_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '..', 'examples', '0x63')
        if not os.path.exists(save_dir):
            pytest.skip(f'Save directory not found: {save_dir}')
        save_files = [f for f in os.listdir(save_dir) if f.endswith('.d2s')]
        if not save_files:
            pytest.skip(f'No .d2s files found in {save_dir}')
        self._test_checksum_update(os.path.join(save_dir, save_files[0]))


class TestBackupRotation:
    def test_backup_rotation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, 'test.d2s')
            with open(test_file, 'wb') as f:
                f.write(b'test_data_v0')
            
            MAX_BACKUPS = 7
            
            def create_backup(file_path):
                if not file_path or not os.path.exists(file_path):
                    return
                base, ext = os.path.splitext(file_path)
                oldest = f"{base}.{MAX_BACKUPS}{ext}"
                if os.path.exists(oldest):
                    os.remove(oldest)
                for i in range(MAX_BACKUPS - 1, 0, -1):
                    src = f"{base}.{i}{ext}"
                    dst = f"{base}.{i + 1}{ext}"
                    if os.path.exists(src):
                        os.rename(src, dst)
                backup_path = f"{base}.1{ext}"
                shutil.copy2(file_path, backup_path)
            
            for v in range(1, 10):
                with open(test_file, 'wb') as f:
                    f.write(f'test_data_v{v}'.encode())
                create_backup(test_file)
            
            assert os.path.exists(test_file)
            assert os.path.exists(os.path.join(tmpdir, 'test.1.d2s'))
            assert os.path.exists(os.path.join(tmpdir, 'test.7.d2s'))
            assert not os.path.exists(os.path.join(tmpdir, 'test.8.d2s'))
            
            with open(os.path.join(tmpdir, 'test.1.d2s'), 'rb') as f:
                assert f.read() == b'test_data_v9'
            with open(os.path.join(tmpdir, 'test.7.d2s'), 'rb') as f:
                assert f.read() == b'test_data_v3'
