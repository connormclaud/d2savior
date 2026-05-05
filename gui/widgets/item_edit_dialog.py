import os

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout,
    QLabel, QCheckBox, QSpinBox, QGroupBox, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QDialogButtonBox, QScrollArea,
    QWidget, QComboBox, QMessageBox, QAbstractItemView, QLineEdit,
    QStyle, QProxyStyle
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QFont, QIcon, QPalette, QColor, QPainter, QPolygonF
from PySide6.QtCore import QPointF

from core.d2data import get_d2data_manager
from core.localized_data import get_localized_data
from core.property import format_property, get_property_name
from core.item import (
    D2Item, PropertyList, get_stat_cost, get_property_meta,
    PropertyList as CPropList
)
from gui.gui_translator import tr, tr_format
from gui.image_manager import get_image_manager
from gui.widgets.item_grid_widget import (
    build_item_tooltip, ITEM_QUALITY_COLORS, RUNEWORD_COLOR,
    TOOLTIP_WHITE, TOOLTIP_BLUE, TOOLTIP_GREEN, TOOLTIP_RARE,
    TOOLTIP_UNIQUE, TOOLTIP_CRAFT, TOOLTIP_GRAY, GRID_SIZE
)


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


def _ensure_arrow_pngs():
    icons_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             'resources', 'icons')
    os.makedirs(icons_dir, exist_ok=True)
    up_png = os.path.join(icons_dir, 'arrow-up.png')
    down_png = os.path.join(icons_dir, 'arrow-down.png')
    if os.path.isfile(up_png) and os.path.isfile(down_png):
        return up_png, down_png
    from PySide6.QtGui import QPixmap, QPainter, QColor, QPolygonF
    from PySide6.QtCore import QPointF
    for path, points in [
        (up_png, [QPointF(4, 1), QPointF(7, 7), QPointF(1, 7)]),
        (down_png, [QPointF(4, 7), QPointF(7, 1), QPointF(1, 1)]),
    ]:
        pm = QPixmap(8, 8)
        pm.fill(QColor(0, 0, 0, 0))
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor(160, 160, 192))
        p.setPen(Qt.NoPen)
        p.drawPolygon(QPolygonF(points))
        p.end()
        pm.save(path)
    return up_png, down_png


def _build_dark_style():
    up_png, down_png = _ensure_arrow_pngs()
    up_png = up_png.replace('\\', '/')
    down_png = down_png.replace('\\', '/')
    return DARK_STYLE_BASE + f"""
QSpinBox::up-button {{
    background-color: #1a1a3e;
    border: 1px solid #3d3d54;
    width: 16px;
}}
QSpinBox::down-button {{
    background-color: #1a1a3e;
    border: 1px solid #3d3d54;
    width: 16px;
}}
QSpinBox::up-arrow {{
    image: url({up_png});
    width: 8px;
    height: 8px;
}}
QSpinBox::down-arrow {{
    image: url({down_png});
    width: 8px;
    height: 8px;
}}
"""


DARK_STYLE_BASE = """
QDialog {
    background-color: #1a1a2e;
    color: #e0e0e0;
}
QGroupBox {
    background-color: #16213e;
    border: 1px solid #3d3d54;
    border-radius: 4px;
    margin-top: 12px;
    padding-top: 12px;
    color: #c0c0c0;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
}
QLabel {
    color: #c0c0c0;
}
QCheckBox {
    color: #c0c0c0;
    spacing: 6px;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
}
QSpinBox {
    background-color: #0f3460;
    border: 1px solid #3d3d54;
    border-radius: 3px;
    color: #e0e0e0;
    padding: 2px 6px;
    min-height: 22px;
}
QTableWidget {
    background-color: #0e0e1e;
    border: 1px solid #3d3d54;
    border-radius: 3px;
    gridline-color: #2d2d44;
    color: #e0e0e0;
    selection-background-color: #2a2a5e;
    selection-color: #ffffff;
}
QTableWidget::item {
    padding: 2px 4px;
}
QHeaderView::section {
    background-color: #1a1a3e;
    border: 1px solid #3d3d54;
    padding: 4px 8px;
    color: #a0a0c0;
    font-weight: bold;
}
QPushButton {
    background-color: #0f3460;
    border: 1px solid #3d3d54;
    border-radius: 4px;
    color: #e0e0e0;
    padding: 5px 16px;
    min-height: 24px;
}
QPushButton:hover {
    background-color: #1a4a80;
    border-color: #5a5a8e;
}
QPushButton:pressed {
    background-color: #0a2540;
}
QPushButton#addPropBtn {
    background-color: #1a4a2e;
    border-color: #2d6e3d;
}
QPushButton#addPropBtn:hover {
    background-color: #2a6a3e;
}
QPushButton#removePropBtn {
    background-color: #4a1a1a;
    border-color: #6e2d2d;
}
QPushButton#removePropBtn:hover {
    background-color: #6a2a2a;
}
QPushButton#removePropBtn:disabled {
    background-color: #1a1a2e;
    border-color: #3d3d54;
    color: #555566;
}
QDialogButtonBox QPushButton {
    min-width: 80px;
}
QScrollArea {
    border: none;
    background-color: transparent;
}
QComboBox {
    background-color: #0f3460;
    border: 1px solid #3d3d54;
    border-radius: 3px;
    color: #e0e0e0;
    padding: 2px 6px;
    min-height: 22px;
}
QComboBox QAbstractItemView {
    background-color: #0f3460;
    color: #e0e0e0;
    selection-background-color: #2a2a5e;
}
"""


class ItemEditDialog(QDialog):
    item_changed = Signal(object)

    def __init__(self, item: D2Item, version: int = 0x63, parent=None):
        super().__init__(parent)
        self._item = item
        self._version = version
        self._modified = False
        self._arrow_style = _DarkArrowStyle()
        self._init_ui()
        self._load_item_data()
        for cb in self.findChildren(QComboBox):
            cb.setStyle(self._arrow_style)

    def _init_ui(self):
        self.setWindowTitle(tr("Edit Item"))
        self.setMinimumSize(520, 680)
        self.resize(560, 720)
        self.setStyleSheet(_build_dark_style())
        pal = self.palette()
        pal.setColor(QPalette.ColorRole.ButtonText, QColor(200, 200, 220))
        pal.setColor(QPalette.ColorRole.WindowText, QColor(200, 200, 220))
        self.setPalette(pal)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content = QWidget()
        main_layout = QVBoxLayout(content)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(8)

        self._create_header(main_layout)
        self._create_basic_group(main_layout)
        self._create_type_specific_group(main_layout)
        self._create_properties_group(main_layout)
        self._create_gems_group(main_layout)

        scroll.setWidget(content)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(scroll)

        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.button(QDialogButtonBox.Ok).setText(tr("OK"))
        button_box.button(QDialogButtonBox.Cancel).setText(tr("Cancel"))
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self.reject)
        outer_layout.addWidget(button_box)

    def _create_header(self, layout):
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)

        self._item_image = QLabel()
        self._item_image.setFixedSize(80, 80)
        self._item_image.setAlignment(Qt.AlignCenter)
        self._item_image.setStyleSheet(
            "background-color: #0e0e1e; border: 1px solid #3d3d54; border-radius: 4px;"
        )
        header_layout.addWidget(self._item_image)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)

        self._item_name_label = QLabel()
        self._item_name_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
        self._item_name_label.setWordWrap(True)
        info_layout.addWidget(self._item_name_label)

        self._item_type_label = QLabel()
        self._item_type_label.setStyleSheet("color: #888;")
        info_layout.addWidget(self._item_type_label)

        self._item_quality_label = QLabel()
        info_layout.addWidget(self._item_quality_label)

        info_layout.addStretch()
        header_layout.addLayout(info_layout, 1)

        layout.addLayout(header_layout)

    def _create_basic_group(self, layout):
        group = QGroupBox(tr("Basic Information"))
        form = QGridLayout(group)
        form.setSpacing(4)
        form.setContentsMargins(8, 14, 8, 8)

        self._chk_identified = QCheckBox(tr("Identified"))
        self._chk_ethereal = QCheckBox(tr("Ethereal"))
        self._chk_socketed = QCheckBox(tr("Socketed"))
        self._chk_socketed.setEnabled(False)
        self._chk_newbie = QCheckBox(tr("Newbie"))
        self._chk_simple = QCheckBox(tr("Simple"))
        self._chk_simple.setEnabled(False)
        self._chk_personalized = QCheckBox(tr("Personalized"))
        self._chk_personalized.setEnabled(False)
        self._chk_runeword = QCheckBox(tr("Rune Word"))
        self._chk_runeword.setEnabled(False)
        self._chk_indestructible = QCheckBox(tr("Indestructible"))

        form.addWidget(self._chk_identified, 0, 0)
        form.addWidget(self._chk_ethereal, 0, 1)
        form.addWidget(self._chk_socketed, 0, 2)
        form.addWidget(self._chk_newbie, 0, 3)
        form.addWidget(self._chk_simple, 1, 0)
        form.addWidget(self._chk_personalized, 1, 1)
        form.addWidget(self._chk_runeword, 1, 2)
        form.addWidget(self._chk_indestructible, 1, 3)

        sep = QLabel()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: #3d3d54;")
        form.addWidget(sep, 2, 0, 1, 4)

        lbl_guid = QLabel(tr("GUID:"))
        self._edit_guid = QLineEdit()
        self._edit_guid.setMaxLength(10)
        self._edit_guid.setPlaceholderText("0x00000000")
        self._edit_guid.setStyleSheet(
            "QLineEdit { background-color: #0f3460; border: 1px solid #3d3d54; "
            "border-radius: 3px; color: #e0e0e0; padding: 2px 6px; min-height: 22px; }"
        )
        form.addWidget(lbl_guid, 3, 0)
        form.addWidget(self._edit_guid, 3, 1, 1, 3)

        lbl_drop = QLabel(tr("Drop Level:"))
        self._spin_droplevel = QSpinBox()
        self._spin_droplevel.setRange(0, 127)
        form.addWidget(lbl_drop, 4, 0)
        form.addWidget(self._spin_droplevel, 4, 1, 1, 3)

        layout.addWidget(group)

    def _create_type_specific_group(self, layout):
        group = QGroupBox(tr("Type Specific"))
        form = QGridLayout(group)
        form.setSpacing(4)
        form.setContentsMargins(8, 14, 8, 8)

        self._group_type_specific = group

        self._lbl_defence = QLabel(tr("Defense:"))
        self._spin_defence = QSpinBox()
        self._spin_defence.setRange(0, 2047)
        self._spin_defence.setFixedWidth(70)

        self._lbl_max_dur = QLabel(tr("Max Dur:"))
        self._spin_max_dur = QSpinBox()
        self._spin_max_dur.setRange(0, 255)
        self._spin_max_dur.setFixedWidth(70)
        self._spin_max_dur.valueChanged.connect(self._on_max_dur_changed)
        self._chk_indestructible.toggled.connect(self._on_indestructible_changed)

        self._lbl_cur_dur = QLabel(tr("Cur Dur:"))
        self._spin_cur_dur = QSpinBox()
        self._spin_cur_dur.setRange(0, 511)
        self._spin_cur_dur.setFixedWidth(70)

        self._lbl_socket = QLabel(tr("Sockets:"))
        self._spin_socket = QSpinBox()
        self._spin_socket.setRange(0, 7)
        self._spin_socket.setFixedWidth(70)

        self._lbl_quantity = QLabel(tr("Quantity:"))
        self._spin_quantity = QSpinBox()
        self._spin_quantity.setRange(0, 511)
        self._spin_quantity.setFixedWidth(70)

        row0 = QHBoxLayout()
        row0.setSpacing(4)
        row0.addWidget(self._lbl_defence)
        row0.addWidget(self._spin_defence)
        row0.addSpacing(12)
        row0.addWidget(self._lbl_socket)
        row0.addWidget(self._spin_socket)
        row0.addStretch()
        form.addLayout(row0, 0, 0, 1, 1)

        row1 = QHBoxLayout()
        row1.setSpacing(4)
        row1.addWidget(self._lbl_cur_dur)
        row1.addWidget(self._spin_cur_dur)
        row1.addSpacing(12)
        row1.addWidget(self._lbl_max_dur)
        row1.addWidget(self._spin_max_dur)
        row1.addStretch()
        form.addLayout(row1, 1, 0, 1, 1)

        row2 = QHBoxLayout()
        row2.setSpacing(4)
        row2.addWidget(self._lbl_quantity)
        row2.addWidget(self._spin_quantity)
        row2.addStretch()
        form.addLayout(row2, 2, 0, 1, 1)

        layout.addWidget(group)

    def _create_properties_group(self, layout):
        group = QGroupBox(tr("Properties"))
        group_layout = QVBoxLayout(group)
        group_layout.setContentsMargins(10, 16, 10, 10)
        group_layout.setSpacing(6)

        self._prop_table = QTableWidget(0, 4)
        self._prop_table.setHorizontalHeaderLabels([
            tr("ID"), tr("Property"), tr("Value"), tr("Layer")
        ])
        self._prop_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._prop_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._prop_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._prop_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._prop_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._prop_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._prop_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._prop_table.cellDoubleClicked.connect(self._on_prop_double_clicked)
        self._prop_table.itemSelectionChanged.connect(self._on_prop_selection_changed)
        self._prop_table.verticalHeader().setVisible(False)
        self._prop_table.setMinimumHeight(150)

        group_layout.addWidget(self._prop_table)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self._btn_add_prop = QPushButton(tr("Add Property"))
        self._btn_add_prop.setObjectName("addPropBtn")
        self._btn_add_prop.clicked.connect(self._on_add_property)
        btn_layout.addWidget(self._btn_add_prop)

        self._btn_remove_prop = QPushButton(tr("Remove Property"))
        self._btn_remove_prop.setObjectName("removePropBtn")
        self._btn_remove_prop.setEnabled(False)
        self._btn_remove_prop.clicked.connect(self._on_remove_property)
        btn_layout.addWidget(self._btn_remove_prop)

        btn_layout.addStretch()

        self._btn_move_up = QPushButton()
        self._btn_move_up.setIcon(self.style().standardIcon(QStyle.SP_ArrowUp))
        self._btn_move_up.setFixedSize(30, 26)
        self._btn_move_up.setToolTip(tr("Move Up"))
        self._btn_move_up.clicked.connect(self._on_move_prop_up)
        btn_layout.addWidget(self._btn_move_up)

        self._btn_move_down = QPushButton()
        self._btn_move_down.setIcon(self.style().standardIcon(QStyle.SP_ArrowDown))
        self._btn_move_down.setFixedSize(30, 26)
        self._btn_move_down.setToolTip(tr("Move Down"))
        self._btn_move_down.clicked.connect(self._on_move_prop_down)
        btn_layout.addWidget(self._btn_move_down)
        group_layout.addLayout(btn_layout)

        layout.addWidget(group)

    def _create_gems_group(self, layout):
        self._gems_group = QGroupBox(tr("Socketed Gems / Runes"))
        group_layout = QVBoxLayout(self._gems_group)
        group_layout.setContentsMargins(10, 16, 10, 10)
        group_layout.setSpacing(4)

        self._gems_list = QTableWidget(0, 3)
        self._gems_list.setHorizontalHeaderLabels([
            tr("Type"), tr("Name"), tr("Action")
        ])
        self._gems_list.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._gems_list.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._gems_list.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._gems_list.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._gems_list.setSelectionMode(QAbstractItemView.NoSelection)
        self._gems_list.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._gems_list.verticalHeader().setVisible(False)
        self._gems_list.setMinimumHeight(60)
        self._gems_list.setMaximumHeight(180)

        group_layout.addWidget(self._gems_list)

        layout.addWidget(self._gems_group)

    def _load_item_data(self):
        item = self._item
        version = self._version

        self._load_header(item, version)
        self._load_basic_info(item)
        self._load_type_specific(item)
        self._load_properties(item, version)
        self._load_gems(item, version)

        if item.bEar:
            self._group_type_specific.setVisible(False)

    def _load_header(self, item, version):
        image_manager = get_image_manager()
        d2data_manager = get_d2data_manager()
        loc = get_localized_data()

        type_name = item.sTypeName.decode('ascii', errors='replace') if item.sTypeName else ''
        type_name = type_name.strip()

        if item.bEar and item.pEar:
            display_name = f"{item.pEar.sEarName}'s {tr('Ear')}"
            self._item_name_label.setText(display_name)
            self._item_name_label.setStyleSheet(f"color: {TOOLTIP_WHITE};")
            self._item_type_label.setText("Type: ear")
            self._item_quality_label.setText(f"{tr('Quality')}: {tr('Ear')}")
            self._item_quality_label.setStyleSheet(f"color: {TOOLTIP_WHITE};")
            return

        if item.pItemInfo and item.pItemInfo.is_gold() and item.pItemInfo.pGold:
            display_name = tr("Gold")
            self._item_name_label.setText(display_name)
            self._item_name_label.setStyleSheet(f"color: {TOOLTIP_WHITE};")
            self._item_type_label.setText("Type: gld ")
            self._item_quality_label.setText(f"{tr('Quantity')}: {item.pItemInfo.pGold.wQuantity}")
            self._item_quality_label.setStyleSheet(f"color: #ffcc00;")
            return

        if image_manager and type_name:
            inv_w, inv_h = 2, 3
            if d2data_manager:
                type_info = d2data_manager.get_item(type_name, version)
                if type_info:
                    inv_w = max(1, getattr(type_info, 'invwidth', 2))
                    inv_h = max(1, getattr(type_info, 'invheight', 3))
            pixmap = image_manager.get_image_by_code(type_name, (inv_w * 28, inv_h * 28))
            if pixmap:
                scaled = pixmap.scaled(72, 72, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self._item_image.setPixmap(scaled)

        base_name = type_name
        loc_name = loc.get_item_name(type_name)
        if loc_name and loc_name != type_name:
            base_name = loc_name
        elif d2data_manager:
            type_info = d2data_manager.get_item(type_name, version)
            if type_info:
                base_name = type_info.name

        quality = item.quality() if hasattr(item, 'quality') else 2
        is_runeword = hasattr(item, 'bRuneWord') and item.bRuneWord
        is_ethereal = hasattr(item, 'bEthereal') and item.bEthereal

        if is_runeword:
            name_color = RUNEWORD_COLOR
        elif quality <= 3:
            name_color = TOOLTIP_GRAY if is_ethereal else TOOLTIP_WHITE
        elif quality == 4:
            name_color = TOOLTIP_BLUE
        elif quality == 5:
            name_color = TOOLTIP_GREEN
        elif quality == 6:
            name_color = TOOLTIP_RARE
        elif quality == 7:
            name_color = TOOLTIP_UNIQUE
        elif quality == 8:
            name_color = TOOLTIP_CRAFT
        else:
            name_color = TOOLTIP_WHITE

        display_name = base_name
        if not item.bSimple and item.pItemInfo and item.pItemInfo.pExtItemInfo:
            ext = item.pItemInfo.pExtItemInfo
            if quality == 4:
                prefix_name = ''
                suffix_name = ''
                if ext.wPrefix.exist() and d2data_manager:
                    pi = d2data_manager.get_magic_prefix(ext.wPrefix.value, version)
                    if pi:
                        loc_prefix = loc.get_item_nameaffix(pi.name)
                        prefix_name = loc_prefix if loc_prefix != pi.name else pi.name
                if ext.wSuffix.exist() and d2data_manager:
                    si = d2data_manager.get_magic_suffix(ext.wSuffix.value, version)
                    if si:
                        loc_suffix = loc.get_item_nameaffix(si.name)
                        suffix_name = loc_suffix if loc_suffix != si.name else si.name
                display_name = f'{prefix_name} {base_name} {suffix_name}'.strip()
            elif quality == 5:
                if ext.wSetID.exist() and d2data_manager:
                    set_item = d2data_manager.get_set_item(ext.wSetID.value, version)
                    if set_item:
                        loc_set_name = loc.get_item_name(set_item.name)
                        display_name = loc_set_name if loc_set_name != set_item.name else set_item.name
            elif quality == 6:
                if ext.pRareName:
                    from core.property import get_language
                    lang = get_language()
                    n1 = lang.get_section_string('rare_crafted_name', ext.pRareName.iName1) if lang else f'Name#{ext.pRareName.iName1}'
                    n2 = lang.get_section_string('rare_crafted_name', ext.pRareName.iName2) if lang else f'Name#{ext.pRareName.iName2}'
                    display_name = f'{n1} {n2}'.strip()
            elif quality == 7:
                if ext.wUniID.exist() and d2data_manager:
                    ui = d2data_manager.get_unique_item(ext.wUniID.value, version)
                    if ui:
                        ui_name = ui.index if hasattr(ui, 'index') else f'Unique #{ext.wUniID.value}'
                        loc_ui_name = loc.get_item_name(ui_name)
                        display_name = loc_ui_name if loc_ui_name != ui_name else ui_name
            elif quality == 8:
                if ext.pCraftName:
                    from core.property import get_language
                    lang = get_language()
                    n1 = lang.get_section_string('rare_crafted_name', ext.pCraftName.iName1) if lang else f'Name#{ext.pCraftName.iName1}'
                    n2 = lang.get_section_string('rare_crafted_name', ext.pCraftName.iName2) if lang else f'Name#{ext.pCraftName.iName2}'
                    display_name = f'{n1} {n2}'.strip()

        self._item_name_label.setText(display_name)
        self._item_name_label.setStyleSheet(f"color: {name_color};")

        self._item_type_label.setText(f"Type: {type_name}")

        quality_names = {1: "Low", 2: "Normal", 3: "High", 4: "Magic", 5: "Set", 6: "Rare", 7: "Unique", 8: "Crafted"}
        q_name = tr(quality_names.get(quality, f"Q{quality}"))
        self._item_quality_label.setText(f"{tr('Quality')}: {q_name}")
        self._item_quality_label.setStyleSheet(f"color: {name_color};")

    def _load_basic_info(self, item):
        self._chk_identified.setChecked(item.bIdentified)
        self._chk_ethereal.setChecked(item.bEthereal)
        self._chk_socketed.setChecked(item.bSocketed)
        self._chk_newbie.setChecked(item.bNewbie)
        self._chk_simple.setChecked(item.bSimple)
        self._chk_personalized.setChecked(item.bPersonalized)
        self._chk_runeword.setChecked(item.bRuneWord)

        if item.pItemInfo and item.pItemInfo.pExtItemInfo:
            ext = item.pItemInfo.pExtItemInfo
            self._edit_guid.setText(f"0x{ext.dwGUID:08X}")
            self._spin_droplevel.setValue(ext.iDropLevel)
        else:
            self._edit_guid.setText("0x00000000")
            self._spin_droplevel.setValue(0)

    def _load_type_specific(self, item):
        has_type_specific = bool(item.pItemInfo and item.pItemInfo.pTpSpInfo)
        self._group_type_specific.setVisible(has_type_specific)

        if not has_type_specific:
            return

        tsi = item.pItemInfo.pTpSpInfo

        has_def = tsi.iDefence.exist()
        self._set_row_visible(self._lbl_defence, self._spin_defence, has_def)
        if has_def:
            self._spin_defence.setValue(tsi.get_defence())

        has_max_dur = tsi.iMaxDurability.exist()
        self._chk_indestructible.setVisible(has_max_dur)
        if has_max_dur:
            is_indestructible = tsi.is_indestructible()
            self._chk_indestructible.blockSignals(True)
            self._chk_indestructible.setChecked(is_indestructible)
            self._chk_indestructible.blockSignals(False)
            dur_visible = has_max_dur and not is_indestructible
            self._set_row_visible(self._lbl_max_dur, self._spin_max_dur, dur_visible)
            self._set_row_visible(self._lbl_cur_dur, self._spin_cur_dur, dur_visible)
            if dur_visible:
                self._spin_max_dur.setValue(tsi.iMaxDurability.value)
                self._spin_cur_dur.setValue(tsi.iCurDur.value if tsi.iCurDur.exist() else 0)
        else:
            self._set_row_visible(self._lbl_max_dur, self._spin_max_dur, False)
            self._set_row_visible(self._lbl_cur_dur, self._spin_cur_dur, False)

        has_socket = tsi.iSocket.exist()
        self._set_row_visible(self._lbl_socket, self._spin_socket, has_socket)
        if has_socket:
            self._spin_socket.setValue(tsi.iSocket.value)

        has_quantity = tsi.iQuantity.exist()
        self._set_row_visible(self._lbl_quantity, self._spin_quantity, has_quantity)
        if has_quantity:
            self._spin_quantity.setValue(tsi.iQuantity.value)

    def _set_row_visible(self, label, field, visible):
        label.setVisible(visible)
        field.setVisible(visible)

    def _load_properties(self, item, version):
        self._prop_table.setRowCount(0)

        if not item.pItemInfo or not item.pItemInfo.pTpSpInfo:
            return

        tsi = item.pItemInfo.pTpSpInfo
        if not tsi.stPropertyList or not tsi.stPropertyList.mProperty:
            return

        self._add_property_rows(tsi.stPropertyList.mProperty, version, TOOLTIP_BLUE)

        if item.is_set() and tsi.apSetProperty:
            for i, set_prop in enumerate(tsi.apSetProperty):
                if set_prop and set_prop.mProperty:
                    self._add_property_rows(set_prop.mProperty, version, TOOLTIP_GREEN, prefix=f"[Set {i + 1}] ")

        if item.bRuneWord and tsi.stRuneWordPropertyList and tsi.stRuneWordPropertyList.mProperty:
            self._add_property_rows(tsi.stRuneWordPropertyList.mProperty, version, RUNEWORD_COLOR, prefix="[RW] ")

    def _add_property_rows(self, properties, version, color, prefix=""):
        for prop_id, layer, value in properties:
            if prop_id in CPropList.IMPLICIT_STATS:
                continue

            row = self._prop_table.rowCount()
            self._prop_table.insertRow(row)

            id_item = QTableWidgetItem(str(prop_id))
            id_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            id_item.setTextAlignment(Qt.AlignCenter)
            self._prop_table.setItem(row, 0, id_item)

            from gui.widgets.property_edit_dialog import _decode_prop_params
            decoded = _decode_prop_params(prop_id, value, layer, version)
            display = format_property(prop_id, decoded, version)
            if not display:
                display = get_property_name(prop_id) or f"Property #{prop_id}"
            if prefix:
                display = f"{prefix}{display}"
            name_item = QTableWidgetItem(display)
            name_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            name_item.setForeground(self._color_to_qcolor(color))
            self._prop_table.setItem(row, 1, name_item)

            value_item = QTableWidgetItem(str(value))
            value_item.setTextAlignment(Qt.AlignCenter)
            self._prop_table.setItem(row, 2, value_item)

            layer_item = QTableWidgetItem(str(layer))
            layer_item.setTextAlignment(Qt.AlignCenter)
            self._prop_table.setItem(row, 3, layer_item)

    def _color_to_qcolor(self, hex_color):
        from PySide6.QtGui import QColor
        c = QColor(hex_color)
        if not c.isValid():
            c = QColor("#e0e0e0")
        return c

    def _load_gems(self, item, version):
        self._gems_list.setRowCount(0)
        gem_items = item.aGemItems if hasattr(item, 'aGemItems') else []
        has_gems = len(gem_items) > 0
        self._gems_group.setVisible(has_gems)

        if not has_gems:
            return

        is_runeword = getattr(item, 'bRuneWord', False)
        d2data_manager = get_d2data_manager()
        loc = get_localized_data()

        for i, gem in enumerate(gem_items):
            row = self._gems_list.rowCount()
            self._gems_list.insertRow(row)

            code = gem.sTypeName.decode('ascii', errors='replace').strip() if gem.sTypeName else ''
            type_info = d2data_manager.get_item(code, version) if d2data_manager else None
            item_type2 = getattr(type_info, 'item_type2', '') or ''

            type_text = tr("Gem") if item_type2 in ('gem', 'gem2') else tr("Rune")
            type_item = QTableWidgetItem(type_text)
            type_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            type_item.setTextAlignment(Qt.AlignCenter)
            self._gems_list.setItem(row, 0, type_item)

            loc_name = loc.get_item_name(code) if loc else ''
            if not loc_name or loc_name == code:
                loc_name = type_info.name if type_info else code
            name_item = QTableWidgetItem(loc_name)
            name_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self._gems_list.setItem(row, 1, name_item)

            remove_btn = QPushButton(tr("Remove"))
            remove_btn.setFixedHeight(22)
            if is_runeword:
                remove_btn.setEnabled(False)
                remove_btn.setToolTip(tr("Cannot remove runes from runeword"))
                remove_btn.setStyleSheet(
                    "QPushButton { background-color: #2a2a2a; color: #555566; border: 1px solid #3a3a3a; "
                    "border-radius: 3px; padding: 1px 8px; font-size: 11px; }"
                )
            else:
                remove_btn.setStyleSheet(
                    "QPushButton { background-color: #5a1a1a; color: #ff8888; border: 1px solid #8a3a3a; "
                    "border-radius: 3px; padding: 1px 8px; font-size: 11px; }"
                    "QPushButton:hover { background-color: #7a2a2a; }"
                )
                remove_btn.clicked.connect(lambda checked, idx=i: self._on_remove_gem(idx))
            self._gems_list.setCellWidget(row, 2, remove_btn)

    def _on_remove_gem(self, index):
        item = self._item
        if not hasattr(item, 'aGemItems') or index >= len(item.aGemItems):
            return

        item.aGemItems.pop(index)

        if item.pItemInfo and item.pItemInfo.pExtItemInfo:
            item.pItemInfo.pExtItemInfo.nGems = max(0, item.pItemInfo.pExtItemInfo.nGems - 1)

        if item.pItemInfo and item.pItemInfo.pTpSpInfo and item.pItemInfo.pTpSpInfo.iSocket.exist():
            socket_val = item.pItemInfo.pTpSpInfo.iSocket.value
            used = len(item.aGemItems)
            if used < socket_val:
                pass

        self._load_gems(item, self._version)
        self._modified = True

    def _on_max_dur_changed(self, value):
        if self._chk_indestructible.isChecked():
            return
        self._spin_cur_dur.setEnabled(value > 0)
        if value == 0:
            self._spin_cur_dur.setValue(0)

    def _on_indestructible_changed(self, checked):
        visible = not checked
        self._lbl_max_dur.setVisible(visible)
        self._spin_max_dur.setVisible(visible)
        self._lbl_cur_dur.setVisible(visible)
        self._spin_cur_dur.setVisible(visible)
        if not checked:
            self._spin_max_dur.setValue(1)
            self._spin_cur_dur.setValue(1)

    def _on_prop_selection_changed(self):
        selected = self._prop_table.selectedItems()
        if not selected:
            self._btn_remove_prop.setEnabled(False)
            return
        row = selected[0].row()
        prefix = self._get_row_prefix(row)
        self._btn_remove_prop.setEnabled(prefix == "base")

    def _on_prop_double_clicked(self, row, col):
        id_item = self._prop_table.item(row, 0)
        value_item = self._prop_table.item(row, 2)
        layer_item = self._prop_table.item(row, 3)
        if not id_item or not value_item:
            return

        try:
            prop_id = int(id_item.text())
            value = int(value_item.text())
            layer = int(layer_item.text()) if layer_item else 0
        except ValueError:
            return

        from gui.widgets.property_edit_dialog import PropertyEditDialog, _decode_prop_params
        dlg = PropertyEditDialog(prop_id, value, layer, self._version, self)
        if dlg.exec() != QDialog.Accepted:
            return

        value_item.setText(str(dlg.result_value))
        layer_item.setText(str(dlg.result_layer))

        name_item = self._prop_table.item(row, 1)
        name_text = name_item.text() if name_item else ""
        prefix = ""
        if name_text.startswith("[RW]"):
            prefix = "[RW] "
        elif name_text.startswith("[Set"):
            space_idx = name_text.index(" ")
            prefix = name_text[:space_idx + 1]

        decoded = _decode_prop_params(prop_id, dlg.result_value, dlg.result_layer, self._version)
        display = format_property(prop_id, decoded, self._version)
        if display:
            if prefix:
                display = f"{prefix}{display}"
            name_item.setText(display)

        self._modified = True

    def _on_add_property(self):
        from gui.widgets.property_select_dialog import PropertySelectDialog

        dlg = PropertySelectDialog(self._version, self)
        if dlg.exec() != QDialog.Accepted:
            return

        prop_id = dlg.selected_stat_id
        if prop_id is None:
            return

        from gui.widgets.property_edit_dialog import PropertyEditDialog, _decode_prop_params
        edit_dlg = PropertyEditDialog(prop_id, 0, 0, self._version, self)
        if edit_dlg.exec() != QDialog.Accepted:
            return

        row = self._prop_table.rowCount()
        self._prop_table.insertRow(row)

        id_item = QTableWidgetItem(str(prop_id))
        id_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        id_item.setTextAlignment(Qt.AlignCenter)
        self._prop_table.setItem(row, 0, id_item)

        decoded = _decode_prop_params(prop_id, edit_dlg.result_value, edit_dlg.result_layer, self._version)
        display = format_property(prop_id, decoded, self._version)
        if not display:
            display = get_property_name(prop_id) or f"Property #{prop_id}"
        name_item = QTableWidgetItem(display)
        name_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        name_item.setForeground(self._color_to_qcolor(TOOLTIP_BLUE))
        self._prop_table.setItem(row, 1, name_item)

        value_item = QTableWidgetItem(str(edit_dlg.result_value))
        value_item.setTextAlignment(Qt.AlignCenter)
        self._prop_table.setItem(row, 2, value_item)

        layer_item = QTableWidgetItem(str(edit_dlg.result_layer))
        layer_item.setTextAlignment(Qt.AlignCenter)
        self._prop_table.setItem(row, 3, layer_item)

        self._prop_table.scrollToItem(id_item)
        self._prop_table.selectRow(row)
        self._modified = True

    def _on_remove_property(self):
        rows = set()
        for item in self._prop_table.selectedItems():
            row = item.row()
            if self._get_row_prefix(row) != "base":
                continue
            rows.add(row)

        if not rows:
            return

        for row in sorted(rows, reverse=True):
            self._prop_table.removeRow(row)

    def _is_readonly_row(self, row):
        return False

    def _get_row_prefix(self, row):
        name_item = self._prop_table.item(row, 1)
        if name_item:
            text = name_item.text()
            if text.startswith("[RW]"):
                return "rw"
            elif text.startswith("[Set"):
                return "set"
        return "base"

    def _swap_rows(self, row1, row2):
        items1 = [self._prop_table.takeItem(row1, c) for c in range(self._prop_table.columnCount())]
        items2 = [self._prop_table.takeItem(row2, c) for c in range(self._prop_table.columnCount())]
        for c, item in enumerate(items2):
            if item:
                self._prop_table.setItem(row1, c, item)
        for c, item in enumerate(items1):
            if item:
                self._prop_table.setItem(row2, c, item)

    def _on_move_prop_up(self):
        rows = set()
        for item in self._prop_table.selectedItems():
            rows.add(item.row())
        if not rows:
            return
        row = min(rows)
        if row <= 0:
            return
        if self._get_row_prefix(row) != self._get_row_prefix(row - 1):
            return
        self._swap_rows(row, row - 1)
        self._prop_table.selectRow(row - 1)
        self._modified = True

    def _on_move_prop_down(self):
        rows = set()
        for item in self._prop_table.selectedItems():
            rows.add(item.row())
        if not rows:
            return
        row = max(rows)
        if row >= self._prop_table.rowCount() - 1:
            return
        if self._get_row_prefix(row) != self._get_row_prefix(row + 1):
            return
        self._swap_rows(row, row + 1)
        self._prop_table.selectRow(row + 1)
        self._modified = True

    def _on_accept(self):
        self._apply_changes()
        self._modified = True
        self.item_changed.emit(self._item)
        self.accept()

    def _apply_changes(self):
        item = self._item

        item.bIdentified = self._chk_identified.isChecked()
        item.bEthereal = self._chk_ethereal.isChecked()
        item.bNewbie = self._chk_newbie.isChecked()

        if item.pItemInfo and item.pItemInfo.pExtItemInfo:
            ext = item.pItemInfo.pExtItemInfo
            guid_text = self._edit_guid.text().strip()
            try:
                if guid_text.startswith("0x") or guid_text.startswith("0X"):
                    ext.dwGUID = int(guid_text, 16)
                else:
                    ext.dwGUID = int(guid_text)
            except ValueError:
                pass
            ext.iDropLevel = self._spin_droplevel.value()

        if item.pItemInfo and item.pItemInfo.pTpSpInfo:
            tsi = item.pItemInfo.pTpSpInfo

            if tsi.iDefence.exist():
                from core.item import get_stat_cost
                ac_stat = get_stat_cost(31)
                save_add = ac_stat.save_add if ac_stat else 10
                tsi.iDefence.value = self._spin_defence.value() + save_add

            if tsi.iMaxDurability.exist():
                if self._chk_indestructible.isChecked() and self._chk_indestructible.isVisible():
                    tsi.iMaxDurability.value = 0
                    if tsi.iCurDur.exist():
                        tsi.iCurDur.value = 0
                else:
                    tsi.iMaxDurability.value = self._spin_max_dur.value()
                    if tsi.iMaxDurability.value > 0:
                        tsi.iCurDur.ensure(self._spin_cur_dur.value())

            if tsi.iSocket.exist():
                tsi.iSocket.value = self._spin_socket.value()

            if tsi.iQuantity.exist():
                tsi.iQuantity.value = self._spin_quantity.value()

        self._apply_property_changes(item)

    def _apply_property_changes(self, item):
        if not item.pItemInfo or not item.pItemInfo.pTpSpInfo:
            return

        tsi = item.pItemInfo.pTpSpInfo
        if not tsi.stPropertyList:
            return

        base_props = []
        rw_props = []
        set_props = {}

        for row in range(self._prop_table.rowCount()):
            id_item = self._prop_table.item(row, 0)
            value_item = self._prop_table.item(row, 2)
            layer_item = self._prop_table.item(row, 3)

            if not id_item or not value_item:
                continue

            try:
                prop_id = int(id_item.text())
                value = int(value_item.text())
                layer = int(layer_item.text()) if layer_item else 0
            except ValueError:
                continue

            name_item = self._prop_table.item(row, 1)
            name_text = name_item.text() if name_item else ""
            if name_text.startswith("[RW]"):
                rw_props.append((prop_id, layer, value))
            elif name_text.startswith("[Set"):
                space_idx = name_text.index(" ")
                prefix = name_text[:space_idx]
                set_num = int(prefix.replace("[Set ", "").replace("]", ""))
                set_idx = set_num - 1
                if set_idx not in set_props:
                    set_props[set_idx] = []
                set_props[set_idx].append((prop_id, layer, value))
            else:
                base_props.append((prop_id, layer, value))

        tsi.stPropertyList.mProperty = base_props

        if rw_props:
            if not tsi.stRuneWordPropertyList:
                tsi.stRuneWordPropertyList = PropertyList()
            tsi.stRuneWordPropertyList.mProperty = rw_props
        elif tsi.stRuneWordPropertyList:
            tsi.stRuneWordPropertyList.mProperty = []

        if set_props or item.is_set():
            if not tsi.apSetProperty:
                tsi.apSetProperty = []
            max_set_idx = max(set_props.keys()) if set_props else -1
            while len(tsi.apSetProperty) <= max_set_idx:
                tsi.apSetProperty.append(PropertyList())
            for set_idx, props in set_props.items():
                if set_idx < len(tsi.apSetProperty):
                    tsi.apSetProperty[set_idx].mProperty = props
            for i in range(len(tsi.apSetProperty)):
                if i not in set_props:
                    tsi.apSetProperty[i].mProperty = []

    @property
    def is_modified(self):
        return self._modified
