import os
from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtCore import Signal

from app_path import resource_path
from core.d2data import get_d2data_manager
from gui.image_manager import get_image_manager, init_image_manager
from gui.widgets.item_grid_widget import ItemPanelWidget, GRID_SIZE


class ItemsWidget(QWidget):
    item_clicked = Signal(object)
    item_dropped = Signal(object, int, int, int, int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.char_data = None
        self._doc_id = -1
        self._image_manager = None
        self._init_image_manager()
        self._init_ui()
    
    def _init_image_manager(self):
        image_dir = resource_path(os.path.join('gui', 'resources', 'images', 'Pictcures'))
        if os.path.exists(image_dir):
            self._image_manager = init_image_manager(image_dir)
        else:
            self._image_manager = get_image_manager()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.item_panel = ItemPanelWidget()
        self.item_panel.item_clicked.connect(self._on_grid_item_clicked)
        self.item_panel.weapon_set_changed.connect(self._on_weapon_set_changed)
        self.item_panel.item_dropped.connect(self._on_item_dropped)
        
        layout.addWidget(self.item_panel)
    
    def set_document_id(self, doc_id: int):
        self._doc_id = doc_id
        self.item_panel.set_document_id(doc_id)
    
    def update_data(self, char_data):
        self.char_data = char_data
        self._populate_grid()
    
    def _on_item_dropped(self, drag_data, target_stored_in, target_col, target_row, target_position):
        self.item_dropped.emit(drag_data, target_stored_in, target_col, target_row, target_position)
    
    def _get_item_pixmap(self, type_name, width=1, height=1):
        if not self._image_manager:
            return None
        
        type_name = type_name.strip().lower()
        img_w = width * GRID_SIZE - 2
        img_h = height * GRID_SIZE - 2
        return self._image_manager.get_image_by_code(type_name, (img_w, img_h))
    
    def _get_item_grid_size(self, item):
        version = self.char_data.dwVersion if self.char_data else 0x63
        d2data_manager = get_d2data_manager()
        
        type_name = item.sTypeName.decode('ascii', errors='replace') if item.sTypeName else ''
        type_name = type_name.strip()
        
        if d2data_manager:
            type_info = d2data_manager.get_item(type_name, version)
            if type_info:
                w = getattr(type_info, 'invwidth', 1)
                h = getattr(type_info, 'invheight', 1)
                return max(1, w), max(1, h)
        
        return 1, 1
    
    def _populate_grid(self):
        self.item_panel.clear_all()
        self.item_panel.belt_view.set_active_rows(1)
        
        if not self.char_data or not self.char_data.ItemList:
            return
        
        items = self.char_data.ItemList.vItems
        if not items:
            return
        
        current_set = self.item_panel.current_weapon_set()
        version = self.char_data.dwVersion if self.char_data.dwVersion else 0x63
        
        for item in items:
            type_name = item.sTypeName.decode('ascii', errors='replace') if item.sTypeName else ''
            type_name = type_name.strip()
            
            width, height = self._get_item_grid_size(item)
            pixmap = self._get_item_pixmap(type_name, width, height)
            
            iLocation = item.iLocation if hasattr(item, 'iLocation') else 0
            iPosition = item.iPosition if hasattr(item, 'iPosition') else -1
            iColumn = item.iColumn if hasattr(item, 'iColumn') else -1
            iRow = item.iRow if hasattr(item, 'iRow') else -1
            iStoredIn = item.iStoredIn if hasattr(item, 'iStoredIn') else -1
            
            if iLocation == 1:
                self._place_equipment(item, iPosition, pixmap, current_set, version)
            elif iLocation == 0:
                self._place_storage(item, iStoredIn, iColumn, iRow, pixmap, width, height, version)
            elif iLocation == 2:
                self._place_belt(item, iColumn, pixmap, version)
    
    def _place_equipment(self, item, position, pixmap, weapon_set=0, version=0x63):
        shared_slots = {
            1: self.item_panel.helm_slot,
            2: self.item_panel.amulet_slot,
            3: self.item_panel.armor_slot,
            6: self.item_panel.right_ring_slot,
            7: self.item_panel.left_ring_slot,
            8: self.item_panel.belt_slot,
            9: self.item_panel.boots_slot,
            10: self.item_panel.gloves_slot,
        }

        set1_slots = {
            4: self.item_panel.weapon_slot,
            5: self.item_panel.shield_slot,
        }

        set2_slots = {
            11: self.item_panel.weapon_slot,
            12: self.item_panel.shield_slot,
        }

        if position in shared_slots:
            shared_slots[position].set_item(item, pixmap, version)
            if position == 8:
                belt_rows = self._get_belt_rows_from_item(item, version)
                self.item_panel.belt_view.set_active_rows(belt_rows)
        elif weapon_set == 0 and position in set1_slots:
            set1_slots[position].set_item(item, pixmap, version)
        elif weapon_set == 1 and position in set2_slots:
            set2_slots[position].set_item(item, pixmap, version)
    
    def _place_storage(self, item, stored_in, col, row, pixmap, width, height, version=0x63):
        if stored_in == 0:
            if 0 <= col < 10 and 0 <= row < 4:
                self.item_panel.inventory_view.set_item(col, row, item, pixmap, width, height, False, version)
        elif stored_in == 3:
            if 0 <= col < 3 and 0 <= row < 4:
                self.item_panel.cube_view.set_item(col, row, item, pixmap, width, height, False, version)
        elif stored_in == 4:
            stash_cols = 10 if version >= 0x69 else 6
            stash_rows = 10 if version >= 0x69 else 8
            if 0 <= col < stash_cols and 0 <= row < stash_rows:
                self.item_panel.stash_view.set_item(col, row, item, pixmap, width, height, False, version)
    
    def _place_belt(self, item, column, pixmap, version=0x63):
        if 0 <= column < 16:
            col = column % 4
            row = column // 4
            self.item_panel.belt_view.set_item(col, row, item, pixmap, 1, 1, False, version)

    def _get_belt_rows_from_item(self, item, version=0x63) -> int:
        if item.pItemInfo and item.pItemInfo.pTpSpInfo:
            tsi = item.pItemInfo.pTpSpInfo
            if tsi.stPropertyList and tsi.stPropertyList.mProperty:
                for prop_id, layer, value in tsi.stPropertyList.mProperty:
                    if prop_id == 68:
                        return max(1, min(4, value))
        type_name = item.sTypeName.decode('ascii', errors='replace').strip() if item.sTypeName else ''
        if type_name:
            d2data_manager = get_d2data_manager()
            if d2data_manager:
                rows = d2data_manager.get_belt_rows(type_name, version)
                if rows > 0:
                    return rows
        return 1
    
    def _on_weapon_set_changed(self, set_id):
        self._populate_grid()
    
    def _on_grid_item_clicked(self, item):
        self.item_clicked.emit(item)
