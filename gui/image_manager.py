import csv
import os
import re
import struct
from typing import Dict, Optional, Tuple
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtCore import QSize

from app_path import resource_path


def _load_palette(pal_path: str):
    if not os.path.exists(pal_path):
        return None
    with open(pal_path, 'rb') as f:
        data = f.read()
    if len(data) < 768:
        return None
    palette = []
    for i in range(256):
        r = data[i * 3]
        g = data[i * 3 + 1]
        b = data[i * 3 + 2]
        palette.append((r, g, b))
    return palette


def _decode_dc6_to_image(data: bytes, palette: list):
    if len(data) < 24:
        return None
    
    version, unk1, unk2, term, num_dir, frames_per_dir = struct.unpack_from('<6I', data, 0)
    
    total_frames = num_dir * frames_per_dir
    if total_frames < 1:
        return None
    
    frame_offset_pos = 24
    if len(data) < frame_offset_pos + 4:
        return None
    
    frame_offset = struct.unpack_from('<I', data, frame_offset_pos)[0]
    
    if frame_offset >= len(data) or frame_offset + 32 > len(data):
        return None
    
    flip, width, height, offset_x, offset_y, alloc_size, next_block, length = struct.unpack_from(
        '<I3iIIII', data, frame_offset
    )
    
    if width <= 0 or height <= 0:
        return None
    
    img_data = bytearray(width * height * 4)
    
    pos = frame_offset + 32
    
    for row_idx in range(height):
        x = 0
        y = height - 1 - row_idx
        
        while pos < len(data):
            b = data[pos]
            pos += 1
            if b == 0x80:
                break
            elif b & 0x80:
                x += b & 0x7F
            else:
                for _ in range(b):
                    if x >= width or pos >= len(data):
                        break
                    idx = data[pos]
                    pos += 1
                    if idx < len(palette):
                        r, g, b_val = palette[idx]
                        pixel_offset = (y * width + x) * 4
                        img_data[pixel_offset] = b_val
                        img_data[pixel_offset + 1] = g
                        img_data[pixel_offset + 2] = r
                        img_data[pixel_offset + 3] = 255
                    x += 1
    
    image = QImage(img_data, width, height, width * 4, QImage.Format_ARGB32)
    return QPixmap.fromImage(image)


def _load_code_mappings():
    code_to_invfile = {}
    code_to_normcode = {}
    code_to_name = {}
    data_dir = resource_path(os.path.join('data', '0x69'))
    if not os.path.isdir(data_dir):
        return code_to_invfile, code_to_normcode, code_to_name
    for txt_name in ('Armor.txt', 'Weapons.txt', 'Misc.txt'):
        txt_path = os.path.join(data_dir, txt_name)
        if not os.path.isfile(txt_path):
            continue
        try:
            with open(txt_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f, delimiter='\t')
                for row in reader:
                    invfile = row.get('invfile', '').strip().lower()
                    normcode = row.get('normcode', '').strip().lower()
                    item_name = row.get('name', '').strip().lower()
                    for col in ('code', 'normcode', 'ubercode', 'ultracode'):
                        code = row.get(col, '').strip().lower()
                        if code and code != 'xxx':
                            if code not in code_to_invfile and invfile:
                                code_to_invfile[code] = invfile
                            if code not in code_to_normcode and normcode and normcode != 'xxx':
                                code_to_normcode[code] = normcode
                            if code not in code_to_name and item_name:
                                code_to_name[code] = item_name
        except Exception:
            pass
    return code_to_invfile, code_to_normcode, code_to_name


class ItemImageManager:
    _instance = None
    
    def __init__(self):
        self._images: Dict[str, QPixmap] = {}
        self._image_dir = None
        self._loaded = False
        self._code_to_invfile, self._code_to_normcode, self._code_to_item_name = _load_code_mappings()
    
    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def set_image_dir(self, image_dir: str):
        self._image_dir = image_dir
        self._loaded = False
        self._images.clear()
    
    def load_images(self):
        if self._loaded or not self._image_dir:
            return
        
        if not os.path.exists(self._image_dir):
            return
        
        palette = None
        pal_path = os.path.join(os.path.dirname(self._image_dir), 'palette', 'pal.dat')
        if not os.path.exists(pal_path):
            pal_path = os.path.join(self._image_dir, '..', 'palette', 'pal.dat')
        if not os.path.exists(pal_path):
            pal_path = os.path.join(os.path.dirname(self._image_dir), 'palette.dat')
        if os.path.exists(pal_path):
            palette = _load_palette(pal_path)
        
        for root, dirs, files in os.walk(self._image_dir):
            if os.path.basename(root).lower() == 'inv':
                continue
            for file in files:
                file_lower = file.lower()
                if file_lower.endswith(('.bmp', '.png')):
                    file_path = os.path.join(root, file)
                    name = os.path.splitext(file)[0].lower()
                    try:
                        pixmap = QPixmap(file_path)
                        if not pixmap.isNull():
                            self._images[name] = pixmap
                            stripped = re.sub(r'^\d+\s+', '', name)
                            if stripped != name and stripped not in self._images:
                                self._images[stripped] = pixmap
                    except Exception:
                        pass
                elif file_lower.endswith('.dc6') and palette:
                    file_path = os.path.join(root, file)
                    name = os.path.splitext(file)[0].lower()
                    try:
                        with open(file_path, 'rb') as f:
                            data = f.read()
                        pixmap = _decode_dc6_to_image(data, palette)
                        if pixmap and not pixmap.isNull():
                            self._images[name] = pixmap
                            stripped = re.sub(r'^\d+\s+', '', name)
                            if stripped != name and stripped not in self._images:
                                self._images[stripped] = pixmap
                    except Exception:
                        pass
        
        self._loaded = True
    
    def get_image(self, type_name: str, size: Optional[Tuple[int, int]] = None) -> Optional[QPixmap]:
        if not self._loaded:
            self.load_images()
        
        type_name = type_name.strip().lower()
        
        if type_name in self._images:
            pixmap = self._images[type_name]
            if size:
                return pixmap.scaled(QSize(size[0], size[1]))
            return pixmap
        
        return None
    
    def get_image_by_code(self, code: str, size: Optional[Tuple[int, int]] = None) -> Optional[QPixmap]:
        code_lower = code.strip().lower()

        code_to_name = {
            'cap': '01 cap', 'skp': '02 skull cap', 'hlm': '03 helm', 'fhl': '04 full helm',
            'ghm': '05 great helm', 'crn': '06 crown', 'msk': '07 mask', 'bhm': '08 grim helm',
            'xap': '01 cap', 'xkp': '02 skull cap', 'xlm': '03 helm', 'xhl': '04 full helm',
            'xhm': '05 great helm', 'xrn': '06 crown', 'xsk': '07 mask', 'xh9': '08 grim helm',
            'ci0': '09 circlet', 'ci1': '10 coronet', 'ci2': '11 tiara', 'ci3': '12 diadem',
            
            'lgl': '01 leather gloves', 'vgl': '02 heavy gloves', 'mgl': '03 chain gloves',
            'tgl': '04 light gauntlets', 'hgl': '05 gauntlets',
            
            'lbt': '01 boots', 'vbt': '02 heavy boots', 'mbt': '03 chain boots',
            'tbt': '04 light plated boots', 'hbt': '05 greaves',
            
            'lbl': '01 sash', 'vbl': '02 light belt', 'mbl': '03 belt',
            'tbl': '04 heavy belt', 'hbl': '05 plated belt',
            
            'ssd': '01 short sword', 'scm': '02 scimitar', 'sbr': '03 sabre', 'flc': '04 falchion',
            'crs': '05 crystal sword', 'bsd': '06 broad sword', 'lsd': '07 long sword',
            'wsd': '08 war sword', 'dgr': '15 dagger', 'dir': '16 dirk', 'kri': '17 kris', 'bld': '18 blade',
            
            'sbw': '01 short bow', 'hbw': "02 hunter's bow", 'lbw': '03 long bow',
            'cbw': '04 composite bow', 'lxb': '09 light crossbow', 'mxb': '10 crossbow',
            
            'hax': '01 hand axe', 'axe': '02 axe', '2ax': '03 double axe', 'mpi': '04 military pick',
            'wax': '05 war axe', 'lax': '06 large axe', 'bax': '07 broad axe', 'btx': '08 battle axe',
            'gax': '09 great axe', 'gix': '10 gaint axe',
            
            'clb': '01 club', 'spc': '02 spiked club', 'mac': '03 mace', 'mst': '04 morning star',
            'fla': '05 flail', 'whm': '06 war hammer', 'mau': '07 maul', 'gma': '08 great maul',
            
            'jav': '1 javelin', 'pil': '2 pilum', 'ssp': '3 short spear', 'glv': '4 glaive',
            'tsp': '5 throwing spear',
            
            'spr': '01 spear', 'tri': '02 trident', 'brn': '03 brandistock', 'spt': '04 spetum',
            'pik': '05 pike', 'bar': '06 bardiche', 'vou': '07 voulge', 'scy': '08 scythe',
            'pax': '09 poleaxe', 'hal': '10 halberd', 'wsc': '11 war scythe',
            
            'wnd': '01 wand', 'ywn': '02 yew wand', 'bwn': '03 bone wand', 'gwn': '04 grim wand',
            
            'scp': '01 scepter', 'gsc': '02 grand scepter', 'wsp': '03 war scepter',
            
            'sst': '01 jo staff', 'lst': '02 long staff', 'cst': '03 ganrled staff',
            'bst': '04 battle staff', 'wst': '05 war staff',
            
            'ob1': '1 eagle orb', 'ob2': '2 sacred globe', 'ob3': '3 smoked sphere',
            'ob4': '4 clasped orb', 'ob5': "5 jared's stone",
            
            'amulet': 'amulet', 'amu': 'amulet',
            'ring': 'ring', 'rin': 'ring',
            
            'gcv': 'chipped amethyst', 'gfv': 'flawed amethyst', 'gsv': 'amethyst',
            'gzv': 'flawless amethyst', 'gpv': 'perfect amethyst',
            'gcy': 'chipped diamond', 'gfy': 'flawed diamond', 'gsy': 'diamond',
            'gly': 'flawless diamond', 'gpy': 'perfect diamond',
            'gcb': 'chipped emerald', 'gfb': 'flawed emerald', 'gsb': 'emerald',
            'glb': 'flawless emerald', 'gpb': 'perfect emerald',
            'gcr': 'chipped ruby', 'gfr': 'flawled ruby', 'gsr': 'ruby',
            'glr': 'flawless ruby', 'gpr': 'perfect ruby',
            'gcw': 'chipped sapphire', 'gfw': 'flawed saphire', 'gsw': 'sapphire',
            'glw': 'flawless sapphire', 'gpw': 'perfect sapphire',
            'skc': 'chipped skull', 'skf': 'flawed skull', 'sku': 'skull',
            'skl': 'flawless skull', 'skz': 'perfect skull',
            'gcg': 'chipped topaz', 'gfg': 'flawed topaz', 'gsg': 'topaz',
            'glg': 'flawless topaz', 'gpg': 'perfect topaz',
            
            'jew': 'jewel',
            
            'r01': 'el rune', 'r02': 'eld rune', 'r03': 'tir rune', 'r04': 'nef rune',
            'r05': 'eth rune', 'r06': 'ith rune', 'r07': 'tal rune', 'r08': 'ral rune',
            'r09': 'ort rune', 'r10': 'thul rune', 'r11': 'amn rune', 'r12': 'sol rune',
            'r13': 'shael rune', 'r14': 'dol rune', 'r15': 'hel rune', 'r16': 'io rune',
            'r17': 'lum rune', 'r18': 'ko rune', 'r19': 'fal rune', 'r20': 'lem rune',
            'r21': 'pul rune', 'r22': 'um rune', 'r23': 'mal rune', 'r24': 'ist rune',
            'r25': 'gul rune', 'r26': 'vex rune', 'r27': 'ohm rune', 'r28': 'lo rune',
            'r29': 'sur rune', 'r30': 'ber rune', 'r31': 'jah rune', 'r32': 'cham rune',
            'r33': 'zod rune',
            
            'hp1': 'light healing potion', 'hp2': 'healing potion', 'hp3': 'greater healing potion',
            'hp4': 'super healing potion', 'hp5': 'full reiuvenation potion',
            'mp1': 'light mana potion', 'mp2': 'mana potion', 'mp3': 'greater mana potion',
            'mp4': 'super mana potion', 'mp5': 'full reiuvenation potion',
            'rvs': 'reiuvenation potion', 'rvl': 'full reiuvenation potion',
            
            'tbk': 'tome of town portal', 'ibk': 'tome of identify',
            'tsc': 'scroll of town portal', 'isc': 'scroll of identify',
            
            'box': 'horadric cube',
            'key': 'key',
            
            'cm1': 'small charm', 'cm2': 'grand charm', 'cm3': 'large charm',
            
            'gld': 'gold',
            
            'ear': 'ear',
        }
        
        name = code_to_name.get(code_lower, code_lower)
        pixmap = self.get_image(name, size)
        if pixmap:
            return pixmap

        item_name = self._code_to_item_name.get(code_lower)
        if item_name:
            pixmap = self.get_image(item_name, size)
            if pixmap:
                return pixmap

        invfile = self._code_to_invfile.get(code_lower)
        if invfile:
            pixmap = self.get_image(invfile, size)
            if pixmap:
                return pixmap

        normcode = self._code_to_normcode.get(code_lower)
        if normcode and normcode != code_lower:
            name2 = code_to_name.get(normcode, normcode)
            pixmap = self.get_image(name2, size)
            if pixmap:
                return pixmap
            item_name2 = self._code_to_item_name.get(normcode)
            if item_name2:
                pixmap = self.get_image(item_name2, size)
                if pixmap:
                    return pixmap
            invfile2 = self._code_to_invfile.get(normcode)
            if invfile2:
                pixmap = self.get_image(invfile2, size)
                if pixmap:
                    return pixmap

        return self.get_image('inv' + code_lower, size)


def get_image_manager():
    return ItemImageManager.instance()


def init_image_manager(image_dir: str):
    manager = get_image_manager()
    manager.set_image_dir(image_dir)
    manager.load_images()
    return manager
