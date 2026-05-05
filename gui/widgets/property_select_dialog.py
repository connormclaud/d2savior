from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QLineEdit, QAbstractItemView, QDialogButtonBox, QGroupBox,
    QStyle, QProxyStyle
)
from PySide6.QtCore import Qt, QSortFilterProxyModel, QPointF
from PySide6.QtGui import QStandardItemModel, QStandardItem, QPainter, QPolygonF, QColor

from core.item import get_stat_cost
from core.property import get_property_name, get_item_modifier
from core.d2data import get_d2data_manager, get_d2data
from core.localized_data import get_localized_data
from gui.gui_translator import tr


STAT_DESC_OVERRIDES = {
    56: "X seconds cold duration",
    59: "X seconds poison duration",
    67: "+X% Faster Run/Walk",
    68: "+X% Faster Attack Rate",
    73: "+X to Maximum Durability",
    88: "Double Potion Duration",
    92: "Required Level: X",
    112: "+X% Howl",
    126: "+X to Skill (Class Only)",
    155: "X% Reanimate as: Monster",
    159: "+X to Minimum Throw Damage",
    160: "+X to Maximum Throw Damage",
    179: "+X% to Attack Rating versus Monster",
    180: "+X% to Damage versus Monster",
    252: "Replenish Durability",
    253: "Replenish Quantity",
}


def _get_stat_description(sid: int) -> str:
    if sid in STAT_DESC_OVERRIDES:
        return tr(STAT_DESC_OVERRIDES[sid])

    d2data = get_d2data()
    stat = d2data.get_stat(sid) if d2data else None
    if stat and stat.descstrpos:
        template = get_item_modifier(stat.descstrpos)
        if template and template != stat.descstrpos:
            return template

    return ""


class _DarkArrowStyle(QProxyStyle):
    def subControlRect(self, cc, opt, sc, widget):
        r = super().subControlRect(cc, opt, sc, widget)
        if cc == QStyle.ComplexControl.CC_ComboBox and sc == QStyle.SubControl.SC_ComboBoxArrow:
            r.setLeft(r.left() - 14)
        return r

    def drawPrimitive(self, element, option, painter, widget):
        if element == QStyle.PrimitiveElement.PE_IndicatorArrowDown:
            r = option.rect
            cx = r.center().x()
            cy = r.center().y()
            hw = r.width() * 0.4
            hh = r.height() * 0.3
            painter.save()
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setBrush(QColor(192, 192, 220))
            painter.setPen(Qt.NoPen)
            painter.drawPolygon(QPolygonF([
                QPointF(cx - hw, cy - hh),
                QPointF(cx + hw, cy - hh),
                QPointF(cx, cy + hh),
            ]))
            painter.restore()
            return
        super().drawPrimitive(element, option, painter, widget)


STAT_CATEGORIES = [
    ("attributes", "Attributes", [0, 1, 2, 3, 4, 5]),
    ("life_mana", "Life / Mana / Stamina", [6, 7, 8, 9, 10, 11, 74, 76, 77, 26, 27, 28]),
    ("combat", "Combat", [12, 13, 14, 15, 19, 21, 22, 23, 24, 25, 119, 137, 159, 160, 185, 186]),
    ("defense", "Defense", [16, 31, 32, 33, 34, 35, 36, 72, 73, 75, 111]),
    ("damage_percent", "Damage %", [17, 18, 121, 122, 123, 124, 180]),
    ("fire_damage", "Fire Damage", [48, 49, 227]),
    ("lightning_damage", "Lightning Damage", [50, 51, 228]),
    ("cold_damage", "Cold Damage", [54, 55, 56, 226]),
    ("poison_damage", "Poison Damage", [57, 58, 59, 229]),
    ("magic_damage", "Magic Damage", [52, 53, 365]),
    ("drain", "Life / Mana Drain", [60, 61, 62, 63]),
    ("fire_resist", "Fire Resist", [39, 40, 231, 285, 306]),
    ("lightning_resist", "Lightning Resist", [41, 42, 232, 286, 307]),
    ("cold_resist", "Cold Resist", [43, 44, 230, 284, 305]),
    ("poison_resist", "Poison Resist", [45, 46, 233, 287, 308]),
    ("other_resist", "Other Resist", [37, 38, 109, 110]),
    ("fire_absorb", "Fire Absorb", [142, 143, 235, 289]),
    ("lightning_absorb", "Lightning Absorb", [144, 145, 236, 290]),
    ("cold_absorb", "Cold Absorb", [148, 149, 234, 288]),
    ("magic_absorb", "Magic Absorb", [146, 147, 237, 291]),
    ("speed", "Speed", [67, 68, 93, 96, 99, 102, 105, 154]),
    ("skills", "Skills", [83, 97, 107, 126, 127, 188]),
    ("aura", "Aura", [151]),
    ("trigger", "Chance to Cast", [195, 196, 197, 198, 199, 201]),
    ("charges", "Charges", [204, 200, 205]),
    ("special", "Special Effects", [78, 81, 108, 115, 116, 117, 118, 120, 125, 128, 134, 135, 136, 141, 150, 151, 152, 153, 156, 157, 158]),
    ("gold_mf", "Gold / Magic Find", [79, 80, 85, 87]),
    ("per_level", "Per Level", [214, 215, 216, 217, 218, 219, 220, 221, 222, 223, 224, 225, 243, 244, 245, 246, 247, 248, 249, 250]),
    ("sunder", "Sunder", [187, 189, 190, 191, 192, 193]),
    ("replenish", "Replenish", [252, 253, 254]),
    ("other", "Other", [20, 47, 66, 69, 70, 71, 82, 86, 88, 89, 90, 91, 92, 94, 98, 100, 101, 103, 104, 106, 112, 113, 114, 129, 130, 131, 132, 133, 139, 140, 155, 161, 162, 163, 164, 165, 166, 167, 168, 169, 170, 171, 172, 194, 203, 206, 207, 208, 209, 256, 257, 258, 259, 260, 261, 262, 263, 264, 265, 266, 267, 309, 310, 311, 312, 313, 314, 315, 333, 334, 335, 336, 348, 349, 357, 358, 366]),
]


def _build_all_stats():
    all_ids = set()
    for _, _, ids in STAT_CATEGORIES:
        all_ids.update(ids)

    d2data = get_d2data_manager()
    if d2data:
        for ver in (0x63, 0x69):
            data = d2data.get_version_data(ver)
            if data and data.stat_cost:
                for stat_id in data.stat_cost:
                    if stat_id not in all_ids:
                        STAT_CATEGORIES[-1][2].append(stat_id)
                        all_ids.add(stat_id)
                break

    return all_ids


_g_all_stats_built = False


def _ensure_all_stats():
    global _g_all_stats_built
    if not _g_all_stats_built:
        _build_all_stats()
        _g_all_stats_built = True


DIALOG_STYLE = """
QDialog {
    background-color: #1a1a2e;
    color: #e0e0e0;
}
QGroupBox {
    border: 1px solid #3d3d54;
    border-radius: 4px;
    margin-top: 8px;
    padding-top: 16px;
    font-weight: bold;
    color: #aaaacc;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
}
QComboBox {
    background-color: #0f3460;
    border: 1px solid #3d3d54;
    border-radius: 3px;
    color: #e0e0e0;
    padding: 4px 8px;
    min-height: 22px;
}
QComboBox QAbstractItemView {
    background-color: #16213e;
    color: #e0e0e0;
    selection-background-color: #0f3460;
    selection-color: #ffffff;
    border: 1px solid #3d3d54;
    outline: none;
}
QLineEdit {
    background-color: #0f3460;
    border: 1px solid #3d3d54;
    border-radius: 3px;
    color: #e0e0e0;
    padding: 4px 8px;
    min-height: 22px;
}
QTableWidget {
    background-color: #16213e;
    alternate-background-color: #1a1a3e;
    border: 1px solid #3d3d54;
    gridline-color: #2a2a44;
    color: #e0e0e0;
    selection-background-color: #0f3460;
    selection-color: #ffffff;
    outline: none;
}
QTableWidget::item {
    padding: 3px 6px;
}
QHeaderView::section {
    background-color: #16213e;
    color: #aaaacc;
    border: 1px solid #2a2a44;
    padding: 4px 6px;
    font-weight: bold;
}
QPushButton {
    background-color: #0f3460;
    border: 1px solid #3d3d54;
    border-radius: 3px;
    color: #e0e0e0;
    padding: 5px 15px;
    min-height: 22px;
}
QPushButton:hover {
    background-color: #1a4a80;
    border-color: #5a5a7e;
}
QPushButton:pressed {
    background-color: #0a2a50;
}
QPushButton#selectBtn {
    background-color: #1b5e20;
    border-color: #2e7d32;
}
QPushButton#selectBtn:hover {
    background-color: #2e7d32;
}
QLabel {
    color: #e0e0e0;
}
"""


class PropertySelectDialog(QDialog):
    def __init__(self, version: int = 0x63, parent=None):
        super().__init__(parent)
        self._version = version
        self._selected_stat_id = None
        self._stat_items = []
        self._arrow_style = _DarkArrowStyle()
        self._init_ui()
        self._load_categories()
        for cb in self.findChildren(QComboBox):
            cb.setStyle(self._arrow_style)

    def _init_ui(self):
        self.setWindowTitle(tr("Select Property"))
        self.setMinimumSize(480, 520)
        self.resize(520, 580)
        self.setStyleSheet(DIALOG_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        filter_group = QGroupBox(tr("Filter"))
        filter_layout = QVBoxLayout(filter_group)
        filter_layout.setSpacing(6)

        row1 = QHBoxLayout()
        row1.setSpacing(8)

        cat_label = QLabel(tr("Category:"))
        cat_label.setFixedWidth(60)
        row1.addWidget(cat_label)

        self._combo_category = QComboBox()
        self._combo_category.currentIndexChanged.connect(self._on_category_changed)
        row1.addWidget(self._combo_category, 1)

        filter_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(8)

        search_label = QLabel(tr("Search:"))
        search_label.setFixedWidth(60)
        row2.addWidget(search_label)

        self._edit_search = QLineEdit()
        self._edit_search.setPlaceholderText(tr("Type to filter by name or ID..."))
        self._edit_search.textChanged.connect(self._on_search_changed)
        row2.addWidget(self._edit_search, 1)

        filter_layout.addLayout(row2)
        layout.addWidget(filter_group)

        self._table = QTableWidget()
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels([tr("ID"), tr("Description"), tr("Property")])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(True)
        self._table.cellDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self._table, 1)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        select_btn = QPushButton(tr("Select"))
        select_btn.setObjectName("selectBtn")
        select_btn.clicked.connect(self._on_select)
        btn_layout.addWidget(select_btn)

        cancel_btn = QPushButton(tr("Cancel"))
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

    def _load_categories(self):
        _ensure_all_stats()

        self._combo_category.blockSignals(True)
        self._combo_category.addItem(tr("All"), "all")

        for cat_key, cat_name, _ in STAT_CATEGORIES:
            display_name = tr(cat_name)
            if display_name == cat_name:
                display_name = tr(cat_key)
            self._combo_category.addItem(display_name, cat_key)

        self._combo_category.blockSignals(False)
        self._combo_category.setCurrentIndex(0)
        self._on_category_changed(0)

    def _get_stats_for_category(self, cat_key: str):
        if cat_key == "all":
            all_ids = set()
            for _, _, ids in STAT_CATEGORIES:
                all_ids.update(ids)
            return sorted(all_ids)

        for ck, _, ids in STAT_CATEGORIES:
            if ck == cat_key:
                return list(ids)
        return []

    def _on_category_changed(self, index):
        if index < 0:
            return

        cat_key = self._combo_category.itemData(index)
        stat_ids = self._get_stats_for_category(cat_key)
        self._edit_search.clear()
        self._populate_table(stat_ids)

    def _on_search_changed(self, text):
        cat_index = self._combo_category.currentIndex()
        cat_key = self._combo_category.itemData(cat_index) if cat_index >= 0 else "all"
        stat_ids = self._get_stats_for_category(cat_key)

        if not text.strip():
            self._populate_table(stat_ids)
            return

        search = text.strip().lower()
        filtered = []
        for sid in stat_ids:
            prop_name = get_property_name(sid)
            if not prop_name:
                prop_name = f"Stat #{sid}"
            if search in prop_name.lower() or search in str(sid):
                filtered.append(sid)
                continue
            desc = _get_stat_description(sid)
            if desc and search in desc.lower():
                filtered.append(sid)

        self._populate_table(filtered)

    def _populate_table(self, stat_ids: list):
        self._table.setRowCount(0)
        self._stat_items = []

        for sid in sorted(stat_ids):
            prop_name = get_property_name(sid)
            if not prop_name:
                prop_name = f"Stat #{sid}"

            desc = _get_stat_description(sid)

            row = self._table.rowCount()
            self._table.insertRow(row)
            self._stat_items.append(sid)

            id_item = QTableWidgetItem(str(sid))
            id_item.setTextAlignment(Qt.AlignCenter)
            id_item.setData(Qt.UserRole, sid)
            self._table.setItem(row, 0, id_item)

            desc_item = QTableWidgetItem(desc)
            self._table.setItem(row, 1, desc_item)

            name_item = QTableWidgetItem(prop_name)
            name_item.setForeground(Qt.gray)
            self._table.setItem(row, 2, name_item)

        if self._table.rowCount() > 0:
            self._table.selectRow(0)

    def _on_double_click(self, row, col):
        if 0 <= row < len(self._stat_items):
            self._selected_stat_id = self._stat_items[row]
            self.accept()

    def _on_select(self):
        rows = self._table.selectionModel().selectedRows()
        if rows:
            row = rows[0].row()
            if 0 <= row < len(self._stat_items):
                self._selected_stat_id = self._stat_items[row]
                self.accept()
                return

        if self._table.currentRow() >= 0 and self._table.currentRow() < len(self._stat_items):
            self._selected_stat_id = self._stat_items[self._table.currentRow()]
            self.accept()

    @property
    def selected_stat_id(self):
        return self._selected_stat_id
