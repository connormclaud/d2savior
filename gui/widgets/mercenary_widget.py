import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QLabel
)
from PySide6.QtCore import Qt, Signal

from app_path import resource_path
from core.d2data import get_d2data_manager
from core.localized_data import get_localized_data
from gui.gui_translator import tr, tr_format
from gui.image_manager import get_image_manager, init_image_manager
from gui.widgets.item_grid_widget import EquipmentSlot, EquipmentGridWidget, GRID_SIZE


MERC_TYPE_NAMES = {
    271: "Rogue Scout (Act I)",
    272: "Desert Mercenary (Act II)",
    273: "Iron Wolf (Act III)",
    274: "Barbarian (Act V)",
}

def _tr_merc_type(merc_id):
    key = MERC_TYPE_NAMES.get(merc_id, f"Unknown ({merc_id})")
    return tr(key)


class MercenaryWidget(QWidget):
    item_clicked = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.char_data = None
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
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self._info_group = QGroupBox(tr("Mercenary Information"))
        info_layout = QGridLayout(self._info_group)
        info_layout.setColumnStretch(1, 1)

        self._info_labels = {}

        lbl = QLabel(tr("Status:"))
        lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        info_layout.addWidget(lbl, 0, 0)
        self._info_labels['status'] = lbl
        self.status_label = QLabel(tr("No Mercenary"))
        info_layout.addWidget(self.status_label, 0, 1)

        lbl = QLabel(tr("Type:"))
        lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        info_layout.addWidget(lbl, 1, 0)
        self._info_labels['type'] = lbl
        self.type_label = QLabel("-")
        info_layout.addWidget(self.type_label, 1, 1)

        lbl = QLabel(tr("Name ID:"))
        lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        info_layout.addWidget(lbl, 2, 0)
        self._info_labels['name_id'] = lbl
        self.name_id_label = QLabel("-")
        info_layout.addWidget(self.name_id_label, 2, 1)

        lbl = QLabel(tr("Experience:"))
        lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        info_layout.addWidget(lbl, 3, 0)
        self._info_labels['experience'] = lbl
        self.exp_label = QLabel("-")
        info_layout.addWidget(self.exp_label, 3, 1)

        layout.addWidget(self._info_group)

        self._items_group = QGroupBox(tr("Mercenary Items"))
        items_layout = QVBoxLayout(self._items_group)
        items_layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)

        MERC_EQUIP_COLS = 8
        MERC_EQUIP_ROWS = 8
        MERC_EQUIP_LAYOUT = {
            'helm':   (3, 0, 2, 2),
            'weapon': (0, 2, 2, 4),
            'armor':  (3, 3, 2, 4),
            'shield': (6, 2, 2, 4),
        }

        equipment_widget = EquipmentGridWidget(MERC_EQUIP_COLS, MERC_EQUIP_ROWS)
        equipment_widget.setObjectName("mercEquipPanel")
        equipment_widget.setStyleSheet("""
            #mercEquipPanel {
                background-color: #0e0e1e;
                border: 1px solid #2d2d44;
                border-radius: 3px;
            }
        """)
        equipment_layout = QGridLayout(equipment_widget)
        equipment_layout.setSpacing(0)
        equipment_layout.setContentsMargins(4, 4, 4, 4)

        for c in range(MERC_EQUIP_COLS):
            equipment_layout.setColumnMinimumWidth(c, GRID_SIZE)
            equipment_layout.setColumnStretch(c, 0)
        for r in range(MERC_EQUIP_ROWS):
            equipment_layout.setRowMinimumHeight(r, GRID_SIZE)
            equipment_layout.setRowStretch(r, 0)

        eq_w = MERC_EQUIP_COLS * GRID_SIZE + 8 + 1
        eq_h = MERC_EQUIP_ROWS * GRID_SIZE + 8 + 1
        equipment_widget.setFixedSize(eq_w, eq_h)

        self.helm_slot = EquipmentSlot(tr("Helm"), "helm")
        self.helm_slot.clicked.connect(self._on_slot_clicked)

        self.armor_slot = EquipmentSlot(tr("Armor"), "armor")
        self.armor_slot.clicked.connect(self._on_slot_clicked)

        self.weapon_slot = EquipmentSlot(tr("Weapon"), "weapon")
        self.weapon_slot.clicked.connect(self._on_slot_clicked)

        self.shield_slot = EquipmentSlot(tr("Shield"), "shield")
        self.shield_slot.clicked.connect(self._on_slot_clicked)

        slot_widgets = {
            'helm': self.helm_slot,
            'armor': self.armor_slot,
            'weapon': self.weapon_slot,
            'shield': self.shield_slot,
        }

        for name, (col, row, col_span, row_span) in MERC_EQUIP_LAYOUT.items():
            widget = slot_widgets[name]
            equipment_layout.addWidget(widget, row, col, row_span, col_span, Qt.AlignLeft | Qt.AlignTop)

        self._equip_slots = {
            1: self.helm_slot,
            3: self.armor_slot,
            4: self.weapon_slot,
            5: self.shield_slot,
        }

        items_layout.addWidget(equipment_widget, 0, Qt.AlignHCenter)
        layout.addWidget(self._items_group)

        self._golem_group = QGroupBox(tr("Golem"))
        golem_layout = QGridLayout(self._golem_group)
        golem_layout.setColumnStretch(1, 1)

        self._golem_labels = {}

        lbl = QLabel(tr("Has Golem:"))
        lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        golem_layout.addWidget(lbl, 0, 0)
        self._golem_labels['has_golem'] = lbl
        self.golem_label = QLabel(tr("No"))
        golem_layout.addWidget(self.golem_label, 0, 1)

        lbl = QLabel(tr("Golem Item:"))
        lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        golem_layout.addWidget(lbl, 1, 0)
        self._golem_labels['golem_item'] = lbl
        self.golem_item_label = QLabel("-")
        golem_layout.addWidget(self.golem_item_label, 1, 1)

        layout.addWidget(self._golem_group)

        layout.addStretch()

    def refresh_ui_texts(self):
        self._info_group.setTitle(tr("Mercenary Information"))
        self._info_labels['status'].setText(tr("Status:"))
        self._info_labels['type'].setText(tr("Type:"))
        self._info_labels['name_id'].setText(tr("Name ID:"))
        self._info_labels['experience'].setText(tr("Experience:"))
        self._items_group.setTitle(tr("Mercenary Items"))
        self._golem_group.setTitle(tr("Golem"))
        self._golem_labels['has_golem'].setText(tr("Has Golem:"))
        self._golem_labels['golem_item'].setText(tr("Golem Item:"))

    def update_data(self, char_data):
        self.char_data = char_data
        self._populate_mercenary()

    def _get_item_pixmap(self, type_name, width=1, height=1):
        if not self._image_manager:
            return None
        type_name = type_name.strip().lower()
        img_w = width * GRID_SIZE - 2
        img_h = height * GRID_SIZE - 2
        return self._image_manager.get_image_by_code(type_name, (img_w, img_h))

    def _get_item_grid_size(self, item, version):
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

    def _populate_mercenary(self):
        for slot in self._equip_slots.values():
            slot.clear_item()

        if not self.char_data:
            self.status_label.setText(tr("No data"))
            return

        has_merc = self.char_data.has_mercenary() if hasattr(self.char_data, 'has_mercenary') else False

        if not has_merc:
            self.status_label.setText(tr("No Mercenary"))
            self.type_label.setText("-")
            self.name_id_label.setText("-")
            self.exp_label.setText("-")
            return

        self.status_label.setText(tr("Hired"))

        if hasattr(self.char_data, 'mercHirelingId'):
            merc_type = _tr_merc_type(self.char_data.mercHirelingId)
            self.type_label.setText(merc_type)

        if hasattr(self.char_data, 'mercNameIndex'):
            self.name_id_label.setText(str(self.char_data.mercNameIndex))

        if hasattr(self.char_data, 'mercExperience'):
            self.exp_label.setText(str(self.char_data.mercExperience))

        if hasattr(self.char_data, 'stMercenary') and self.char_data.stMercenary:
            merc = self.char_data.stMercenary
            if merc.stItems and merc.stItems.vItems:
                version = self.char_data.dwVersion if self.char_data.dwVersion else 0x63

                for item in merc.stItems.vItems:
                    type_name = item.sTypeName.decode('ascii', errors='replace') if item.sTypeName else ''
                    type_name = type_name.strip()

                    width, height = self._get_item_grid_size(item, version)
                    pixmap = self._get_item_pixmap(type_name, width, height)

                    iPosition = item.iPosition if hasattr(item, 'iPosition') else -1
                    if iPosition in self._equip_slots:
                        self._equip_slots[iPosition].set_item(item, pixmap, version)

        if hasattr(self.char_data, 'stGolem') and self.char_data.stGolem:
            golem = self.char_data.stGolem
            has_golem = golem.bHasGolem if hasattr(golem, 'bHasGolem') else False
            self.golem_label.setText(tr("Yes") if has_golem else tr("No"))

            if has_golem and golem.pItem:
                type_name = golem.pItem.sTypeName.decode('ascii', errors='replace') if golem.pItem.sTypeName else 'Unknown'
                self.golem_item_label.setText(type_name.strip())
            else:
                self.golem_item_label.setText("-")
        else:
            self.golem_label.setText(tr("No"))
            self.golem_item_label.setText("-")

    def _on_slot_clicked(self, item):
        if item:
            self.item_clicked.emit(item)
