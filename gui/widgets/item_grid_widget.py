from PySide6.QtWidgets import (
    QWidget, QGridLayout, QLabel, QScrollArea, QVBoxLayout,
    QHBoxLayout, QPushButton, QButtonGroup, QApplication, QMenu, QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt, QSize, Signal, QRect, QPoint, QTimer, QMimeData
from PySide6.QtGui import QPixmap, QPainter, QColor, QPen, QFont, QDrag, QAction

from core.d2data import get_d2data_manager
from core.localized_data import get_localized_data
from core.property import format_property
from gui.gui_translator import tr, tr_format
from gui.drag_drop import ItemDragData, MIME_TYPE_ITEM


GRID_SIZE = 28

TOOLTIP_WHITE = "#ffffff"
TOOLTIP_BLUE = "#4444ff"
TOOLTIP_GREEN = "#00ff00"
TOOLTIP_RARE = "#ffff00"
TOOLTIP_UNIQUE = "#948064"
TOOLTIP_CRAFT = "#ff8000"
TOOLTIP_RED = "#ff0000"
TOOLTIP_GRAY = "#646464"

ITEM_QUALITY_COLORS = {
    1: TOOLTIP_WHITE,
    2: TOOLTIP_WHITE,
    3: TOOLTIP_WHITE,
    4: TOOLTIP_BLUE,
    5: TOOLTIP_GREEN,
    6: TOOLTIP_RARE,
    7: TOOLTIP_UNIQUE,
    8: TOOLTIP_CRAFT,
}
RUNEWORD_COLOR = TOOLTIP_RED

ITEM_QUALITY_NAMES = {
    1: "Low",
    2: "Normal",
    3: "High",
    4: "Magic",
    5: "Set",
    6: "Rare",
    7: "Unique",
    8: "Crafted",
}

EQUIP_SLOT_NAMES = {
    1: "Helmet",
    2: "Amulet",
    3: "Armor",
    4: "Weapon I",
    5: "Shield I",
    6: "Ring (Right)",
    7: "Ring (Left)",
    8: "Belt",
    9: "Boots",
    10: "Gloves",
    11: "Weapon II",
    12: "Shield II",
}


def _tr_quality(quality):
    return tr(ITEM_QUALITY_NAMES.get(quality, f"Q{quality}"))


def _tr_equip_slot(slot_id):
    return tr(EQUIP_SLOT_NAMES.get(slot_id, f"Slot {slot_id}"))


class TranslucentTooltip(QLabel):
    _instance = None

    def __init__(self, parent=None):
        super().__init__(parent, Qt.ToolTip | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setMargin(8)
        self.setStyleSheet("color: #e0e0e0; font-size: 12px;")

    @classmethod
    def show_tooltip(cls, global_pos: QPoint, html: str, widget=None):
        if cls._instance is None:
            cls._instance = cls()
        tip = cls._instance
        tip.setText(html)
        tip.adjustSize()
        screen = QApplication.screenAt(global_pos)
        if screen:
            geo = screen.availableGeometry()
            x = global_pos.x()
            y = global_pos.y()
            if x + tip.width() > geo.right():
                x = geo.right() - tip.width()
            if y + tip.height() > geo.bottom():
                y = global_pos.y() - tip.height()
            tip.move(x, y)
        else:
            tip.move(global_pos)
        tip.show()
        tip.raise_()

    @classmethod
    def hide_tooltip(cls):
        if cls._instance:
            cls._instance.hide()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor(26, 26, 46, 210))
        p.setPen(QPen(QColor(74, 74, 110), 1))
        p.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 4, 4)
        p.end()
        super().paintEvent(event)


def _tr(key: str, default: str = '') -> str:
    loc = get_localized_data()
    val = loc.get_tooltip_ui(key)
    if val and val != key:
        return val
    return default if default else key


def _tr_affix(key: str) -> str:
    loc = get_localized_data()
    val = loc.get_item_nameaffix(key)
    if val and val != key:
        return val
    return key


def build_item_tooltip(item, version=0x63):
    if not item:
        return ""

    d2data_manager = get_d2data_manager()
    loc = get_localized_data()
    type_name = item.sTypeName.decode('ascii', errors='replace') if item.sTypeName else 'Unknown'
    type_name = type_name.strip()

    base_name = type_name
    loc_name = loc.get_item_name(type_name)
    if loc_name and loc_name != type_name:
        base_name = loc_name
    elif d2data_manager:
        type_info = d2data_manager.get_item(type_name, version)
        if type_info:
            base_name = type_info.name

    is_runeword = hasattr(item, 'bRuneWord') and item.bRuneWord
    is_ethereal = hasattr(item, 'bEthereal') and item.bEthereal
    quality = item.quality() if hasattr(item, 'quality') else 2

    if is_runeword:
        name_color = TOOLTIP_UNIQUE
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

    lines = []

    if item.bEar and item.pEar:
        lines.append(f'<span style="color:{TOOLTIP_WHITE}; font-weight:bold">{item.pEar.sEarName}\'s {_tr("Ear", "Ear")}</span>')
        from core.property import get_class_name
        lines.append(f'<span style="color:{TOOLTIP_WHITE}">{get_class_name(item.pEar.iEarClass)}</span>')
        lines.append(f'<span style="color:{TOOLTIP_WHITE}">{_tr("Level", "Level")}: {item.pEar.iEarLevel}</span>')
        return '<div style="text-align:center">' + '<br>'.join(lines) + '</div>'

    if item.pItemInfo and item.pItemInfo.is_gold() and item.pItemInfo.pGold:
        lines.append(f'<span style="color:{TOOLTIP_WHITE}; font-weight:bold">{_tr("Gold", "Gold")}</span>')
        lines.append(f'<span style="color:{TOOLTIP_WHITE}">{_tr("Quantity", "Quantity")}: {item.pItemInfo.pGold.wQuantity}</span>')
        return '<div style="text-align:center">' + '<br>'.join(lines) + '</div>'

    if not item.bSimple and item.pItemInfo and item.pItemInfo.pExtItemInfo:
        ext = item.pItemInfo.pExtItemInfo
        if ext.sPersonName:
            try:
                pname = bytes(ext.sPersonName).decode('utf-8', errors='replace').rstrip('\x00')
                if pname:
                    lines.append(f'<span style="color:{name_color}">{pname}\'s</span>')
            except Exception:
                pass

        if is_runeword:
            rw_id = item.rune_word_id() if hasattr(item, 'rune_word_id') else 0
            rw_name = f'Runeword #{rw_id}'
            rw_info = None
            if d2data_manager:
                rw_info = d2data_manager.get_runeword(rw_id)
                if rw_info:
                    if rw_info.key:
                        loc_rw_name = loc.get_string('item-runes.json', rw_info.key)
                        rw_name = loc_rw_name if loc_rw_name != rw_info.key else rw_info.name
                    else:
                        rw_name = rw_info.name
            lines.append(f'<span style="color:{RUNEWORD_COLOR}; font-weight:bold">{rw_name}</span>')
            if rw_info and rw_info.rune_codes:
                rune_parts = []
                for code in rw_info.rune_codes:
                    num = int(code[1:])
                    rune_name = code
                    loc_rune_name = loc.get_string('item-runes.json', code)
                    if loc_rune_name and loc_rune_name != code:
                        rune_name = loc_rune_name.replace(' Rune', '').replace('符文', '')
                    elif d2data_manager:
                        ti = d2data_manager.get_item(code, version)
                        if ti and ti.name:
                            short = ti.name.replace(' Rune', '')
                            rune_name = short
                    rune_parts.append(f'#{num} {rune_name}')
                lines.append(f'<span style="color:{RUNEWORD_COLOR}">{" + ".join(rune_parts)}</span>')
            lines.append(f'<span style="color:{TOOLTIP_GRAY}; font-weight:bold">{base_name}</span>')
        elif quality == 1:
            low_q = _tr_affix("Low Quality")
            lines.append(f'<span style="color:{name_color}; font-weight:bold">{low_q} {base_name}</span>')
        elif quality == 2:
            if ext.wMonsterID.exist():
                from core.property import get_monster_name
                mname = get_monster_name(ext.wMonsterID.value)
                lines.append(f'<span style="color:{name_color}; font-weight:bold">{mname} {base_name}</span>')
            else:
                lines.append(f'<span style="color:{name_color}; font-weight:bold">{base_name}</span>')
        elif quality == 3:
            hi_q = _tr_affix("Hiquality")
            lines.append(f'<span style="color:{name_color}; font-weight:bold">{hi_q} {base_name}</span>')
        elif quality == 4:
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
            full_name = f'{prefix_name} {base_name} {suffix_name}'.strip()
            lines.append(f'<span style="color:{name_color}; font-weight:bold">{full_name}</span>')
        elif quality == 5:
            if ext.wSetID.exist() and d2data_manager:
                set_item = d2data_manager.get_set_item(ext.wSetID.value, version)
                if set_item:
                    loc_set_name = loc.get_item_name(set_item.name)
                    set_display_name = loc_set_name if loc_set_name != set_item.name else set_item.name
                    lines.append(f'<span style="color:{name_color}; font-weight:bold">{set_display_name}</span>')
                else:
                    lines.append(f'<span style="color:{name_color}; font-weight:bold">{base_name}</span>')
            else:
                lines.append(f'<span style="color:{name_color}; font-weight:bold">{base_name}</span>')
        elif quality == 6:
            if ext.pRareName:
                from core.property import get_language
                lang = get_language()
                n1 = lang.get_section_string('rare_crafted_name', ext.pRareName.iName1) if lang else f'Name#{ext.pRareName.iName1}'
                n2 = lang.get_section_string('rare_crafted_name', ext.pRareName.iName2) if lang else f'Name#{ext.pRareName.iName2}'
                title = f'{n1} {n2}'.strip()
                lines.append(f'<span style="color:{name_color}; font-weight:bold">{title}</span>')
            lines.append(f'<span style="color:{name_color}; font-weight:bold">{base_name}</span>')
        elif quality == 7:
            if ext.wUniID.exist() and d2data_manager:
                ui = d2data_manager.get_unique_item(ext.wUniID.value, version)
                if ui:
                    ui_name = ui.index if hasattr(ui, 'index') else f'Unique #{ext.wUniID.value}'
                    loc_ui_name = loc.get_item_name(ui_name)
                    ui_display_name = loc_ui_name if loc_ui_name != ui_name else ui_name
                    lines.append(f'<span style="color:{name_color}; font-weight:bold">{ui_display_name}</span>')
                else:
                    lines.append(f'<span style="color:{name_color}; font-weight:bold">{base_name}</span>')
            else:
                lines.append(f'<span style="color:{name_color}; font-weight:bold">{base_name}</span>')
        elif quality == 8:
            if ext.pCraftName:
                from core.property import get_language
                lang = get_language()
                n1 = lang.get_section_string('rare_crafted_name', ext.pCraftName.iName1) if lang else f'Name#{ext.pCraftName.iName1}'
                n2 = lang.get_section_string('rare_crafted_name', ext.pCraftName.iName2) if lang else f'Name#{ext.pCraftName.iName2}'
                title = f'{n1} {n2}'.strip()
                lines.append(f'<span style="color:{name_color}; font-weight:bold">{title}</span>')
            lines.append(f'<span style="color:{name_color}; font-weight:bold">{base_name}</span>')
        else:
            lines.append(f'<span style="color:{name_color}; font-weight:bold">{base_name}</span>')
    else:
        lines.append(f'<span style="color:{name_color}; font-weight:bold">{base_name}</span>')

    if hasattr(item, 'pItemInfo') and item.pItemInfo and hasattr(item.pItemInfo, 'pTpSpInfo') and item.pItemInfo.pTpSpInfo:
        tsi = item.pItemInfo.pTpSpInfo

        if hasattr(tsi, 'iDefence') and tsi.iDefence.exist():
            lines.append(f'<span style="color:{TOOLTIP_WHITE}">{_tr("Defense", "Defense")}: {tsi.get_defence()}</span>')
        if hasattr(tsi, 'iMaxDurability') and tsi.iMaxDurability.exist():
            if tsi.iMaxDurability.value == 0:
                lines.append(f'<span style="color:{TOOLTIP_BLUE}">{_tr("Indestructible", "Indestructible")}</span>')
            elif hasattr(tsi, 'iCurDur') and tsi.iCurDur.exist():
                lines.append(f'<span style="color:{TOOLTIP_WHITE}">{_tr("Durability", "Durability")}: {tsi.iCurDur.value}/{tsi.iMaxDurability.value}</span>')
        if hasattr(tsi, 'iQuantity') and tsi.iQuantity.exist():
            lines.append(f'<span style="color:{TOOLTIP_WHITE}">{_tr("Quantity", "Quantity")}: {tsi.iQuantity.value}</span>')

    if not item.bSimple and item.pItemInfo and item.pItemInfo.pExtItemInfo:
        if hasattr(item.pItemInfo.pTpSpInfo, 'stPropertyList') and item.pItemInfo.pTpSpInfo.stPropertyList:
            for prop_id, value, params in item.pItemInfo.pTpSpInfo.stPropertyList.get_parsed_properties(version):
                try:
                    prop_text = format_property(prop_id, params, version)
                    if prop_text:
                        lines.append(f'<span style="color:{TOOLTIP_BLUE}">{prop_text}</span>')
                except Exception:
                    pass

        if quality == 5 and hasattr(item.pItemInfo.pTpSpInfo, 'apSetProperty'):
            for set_prop in item.pItemInfo.pTpSpInfo.apSetProperty:
                if set_prop is not None and hasattr(set_prop, 'mProperty') and set_prop.mProperty:
                    try:
                        for prop_id, value, params in set_prop.get_parsed_properties(version):
                            try:
                                prop_text = format_property(prop_id, params, version)
                                if prop_text:
                                    lines.append(f'<span style="color:{TOOLTIP_GREEN}">{prop_text}</span>')
                            except Exception:
                                pass
                    except Exception:
                        pass

        if is_runeword and hasattr(item.pItemInfo.pTpSpInfo, 'stRuneWordPropertyList') and item.pItemInfo.pTpSpInfo.stRuneWordPropertyList and item.pItemInfo.pTpSpInfo.stRuneWordPropertyList.mProperty:
            try:
                parsed = item.pItemInfo.pTpSpInfo.stRuneWordPropertyList.get_parsed_properties(version)
                for prop_id, value, params in parsed:
                    try:
                        prop_text = format_property(prop_id, params, version)
                        if prop_text:
                            lines.append(f'<span style="color:{TOOLTIP_BLUE}">{prop_text}</span>')
                    except Exception:
                        pass
            except Exception:
                pass

    if is_ethereal:
        lines.append(f'<span style="color:{TOOLTIP_BLUE}">{_tr("Ethereal", "Ethereal")}</span>')

    if hasattr(item, 'bSocketed') and item.bSocketed:
        sockets = 0
        if hasattr(item.pItemInfo.pTpSpInfo, 'iSocket') and item.pItemInfo.pTpSpInfo.iSocket.exist():
            sockets = item.pItemInfo.pTpSpInfo.iSocket.value
        gem_items = item.aGemItems if hasattr(item, 'aGemItems') and item.aGemItems else []
        gem_count = len(gem_items)
        if sockets > 0:
            lines.append(f'<span style="color:{TOOLTIP_BLUE}">{_tr("Socketed", "Socketed")} ({gem_count}/{sockets})</span>')
            socket_parts = []
            for i in range(sockets):
                if i < gem_count:
                    sock = gem_items[i]
                    try:
                        sock_type = sock.sTypeName.decode('ascii', errors='replace').strip() if sock.sTypeName else ''
                        sock_name = sock_type
                        loc_sock_name = loc.get_item_name(sock_type)
                        if loc_sock_name and loc_sock_name != sock_type:
                            sock_name = loc_sock_name.replace(' Rune', '').replace(' Gem', '').replace('符文', '').replace('宝石', '')
                        elif d2data_manager:
                            ti = d2data_manager.get_item(sock_type, version)
                            if ti and ti.name:
                                short = ti.name.replace(' Rune', '').replace(' Gem', '')
                                sock_name = short
                        socket_parts.append(f'<span style="color:{RUNEWORD_COLOR}">●</span> <span style="color:{TOOLTIP_WHITE}">{sock_name}</span>')
                    except Exception:
                        socket_parts.append(f'<span style="color:{RUNEWORD_COLOR}">●</span>')
                else:
                    socket_parts.append(f'<span style="color:{TOOLTIP_GRAY}">○</span>')
            lines.append('  '.join(socket_parts))

    if hasattr(item, 'bIdentified') and not item.bIdentified:
        lines.append(f'<span style="color:{TOOLTIP_RED}">{_tr("Unidentified", "Unidentified")}</span>')

    return '<div style="text-align:center">' + '<br>'.join(lines) + '</div>'


class ItemGridCell(QLabel):
    clicked = Signal(object)
    item_dragged = Signal(object)
    
    def __init__(self, parent=None, cell_size=None):
        super().__init__(parent)
        self.item = None
        self._grid_width = 1
        self._grid_height = 1
        self._pixmap = None
        self._is_main_cell = True
        self._version = 0x63
        self._drag_start_pos = None
        self._doc_id = -1
        self._location = 0
        self._column = 0
        self._row = 0
        self._stored_in = -1
        self._cell_size = cell_size if cell_size else GRID_SIZE
        self.setAcceptDrops(True)
    
    def set_item(self, item, pixmap=None, grid_width=1, grid_height=1, is_main_cell=True, version=0x63):
        self.item = item
        self._pixmap = pixmap
        self._grid_width = grid_width
        self._grid_height = grid_height
        self._is_main_cell = is_main_cell
        self._version = version
        
        if is_main_cell and pixmap and not pixmap.isNull():
            w = grid_width * self._cell_size
            h = grid_height * self._cell_size
            scaled_pixmap = pixmap.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            self.setFixedSize(w, h)
            self.setPixmap(scaled_pixmap)
            
            quality = item.quality() if hasattr(item, 'quality') else 2
            is_rw = hasattr(item, 'bRuneWord') and item.bRuneWord
            if is_rw:
                border_color = RUNEWORD_COLOR
                bg_color = self._quality_bg_color(quality, is_runeword=True)
            else:
                border_color = ITEM_QUALITY_COLORS.get(quality, "#2d2d44")
                bg_color = self._quality_bg_color(quality)
            self.setStyleSheet(f"""
                QLabel {{
                    background-color: {bg_color};
                    border: 1px solid {border_color};
                }}
            """)
            self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        elif not is_main_cell:
            self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
    
    def set_source_info(self, doc_id: int, location: int, column: int, row: int, stored_in: int = -1):
        self._doc_id = doc_id
        self._location = location
        self._column = column
        self._row = row
        self._stored_in = stored_in
    
    def clear_item(self):
        self.item = None
        self._pixmap = None
        self._is_main_cell = True
        self._grid_width = 1
        self._grid_height = 1
        self.clear()
        self.setMinimumSize(GRID_SIZE, GRID_SIZE)
        self.setMaximumSize(GRID_SIZE, GRID_SIZE)
        self.setStyleSheet("background-color: transparent;")
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
    
    def paintEvent(self, event):
        super().paintEvent(event)
    
    def _quality_bg_color(self, quality, is_runeword=False):
        if is_runeword:
            return "#1a150e"
        bg_map = {
            1: "#1a1a1a",
            2: "#0e0e1e",
            3: "#1a1a1a",
            4: "#0e0e2a",
            5: "#0e1a0e",
            6: "#1a1a0e",
            7: "#1a150e",
            8: "#1a0e0e",
        }
        return bg_map.get(quality, "#0e0e1e")
    
    def enterEvent(self, event):
        if self.item and self._is_main_cell:
            try:
                tooltip = build_item_tooltip(self.item, self._version)
            except Exception:
                tooltip = ""
            if tooltip:
                pos = self.mapToGlobal(self.rect().bottomRight() + QPoint(1, 1))
                TranslucentTooltip.show_tooltip(pos, tooltip)
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        TranslucentTooltip.hide_tooltip()
        super().leaveEvent(event)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.item and self._is_main_cell:
            self._drag_start_pos = event.pos()
        super().mousePressEvent(event)
    
    def contextMenuEvent(self, event):
        if not self.item or not self._is_main_cell:
            return
        
        menu = QMenu(self)
        
        save_action = QAction(tr("Save Item As..."), self)
        save_action.triggered.connect(lambda: self._save_item_as())
        menu.addAction(save_action)
        
        menu.exec(event.globalPos())
    
    def _save_item_as(self):
        if not self.item:
            return
        
        from core.obitstream import OBitStream
        
        type_name = self.item.sTypeName.decode('ascii', errors='replace').strip() if self.item.sTypeName else 'item'
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            tr("Save Item"),
            f"{type_name}.d2i",
            tr("D2I Files (*.d2i);;All Files (*)")
        )
        
        if not file_path:
            return
        
        try:
            bs = OBitStream()
            self.item.serialize(bs, self._version, write_magic=False)
            data = bs.get_data()
            
            with open(file_path, 'wb') as f:
                f.write(data)
            
            QMessageBox.information(self, tr("Success"), tr_format("Item saved to:\n{}", file_path))
        except Exception as e:
            QMessageBox.critical(self, tr("Error"), tr_format("Failed to save item:\n{}", str(e)))
    
    def mouseMoveEvent(self, event):
        if not self._drag_start_pos:
            return
        
        if not self.item or not self._is_main_cell:
            return
        
        distance = (event.pos() - self._drag_start_pos).manhattanLength()
        if distance < QApplication.startDragDistance():
            return
        
        is_copy = bool(event.modifiers() & Qt.ControlModifier)
        
        drag = QDrag(self)
        mime_data = QMimeData()
        
        drag_data = ItemDragData(
            item=self.item,
            source_doc_id=self._doc_id,
            source_location=self.item.iLocation if hasattr(self.item, 'iLocation') else self._location,
            source_column=self.item.iColumn if hasattr(self.item, 'iColumn') else self._column,
            source_row=self.item.iRow if hasattr(self.item, 'iRow') else self._row,
            source_stored_in=self.item.iStoredIn if hasattr(self.item, 'iStoredIn') else self._stored_in,
            is_copy=is_copy
        )
        mime_data.setData(MIME_TYPE_ITEM, drag_data.to_mime_data().data(MIME_TYPE_ITEM))
        drag.setMimeData(mime_data)
        
        if self._pixmap and not self._pixmap.isNull():
            drag.setPixmap(self._pixmap.scaled(56, 56, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            drag.setHotSpot(event.pos())
        
        default_action = Qt.CopyAction if is_copy else Qt.MoveAction
        drag.exec_(Qt.CopyAction | Qt.MoveAction, default_action)
        self._drag_start_pos = None
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._drag_start_pos and self.item and self._is_main_cell:
            distance = (event.pos() - self._drag_start_pos).manhattanLength()
            if distance < QApplication.startDragDistance():
                self.clicked.emit(self.item)
        self._drag_start_pos = None
        super().mouseReleaseEvent(event)
    
    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(MIME_TYPE_ITEM):
            if self._stored_in == 5:
                drag_data = ItemDragData.from_mime_data(event.mimeData())
                if drag_data and drag_data.item:
                    type_name = drag_data.item.sTypeName.decode('ascii', errors='replace').strip() if drag_data.item.sTypeName else ''
                    from core.d2data import get_d2data_manager
                    d2mgr = get_d2data_manager()
                    if d2mgr and not d2mgr.is_beltable(type_name):
                        event.ignore()
                        return
            event.setDropAction(Qt.MoveAction)
            event.accept()
        else:
            event.ignore()
    
    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat(MIME_TYPE_ITEM):
            if self._stored_in == 5:
                drag_data = ItemDragData.from_mime_data(event.mimeData())
                if drag_data and drag_data.item:
                    type_name = drag_data.item.sTypeName.decode('ascii', errors='replace').strip() if drag_data.item.sTypeName else ''
                    from core.d2data import get_d2data_manager
                    d2mgr = get_d2data_manager()
                    if d2mgr and not d2mgr.is_beltable(type_name):
                        event.ignore()
                        return
                    if self._location == 0 and self._row >= 0:
                        parent = self.parent()
                        while parent and not isinstance(parent, ItemGridView):
                            parent = parent.parent()
                        if parent and hasattr(parent, '_active_rows') and self._row >= parent._active_rows:
                            event.ignore()
                            return
            if event.modifiers() & Qt.ControlModifier:
                event.setDropAction(Qt.CopyAction)
            else:
                event.setDropAction(Qt.MoveAction)
            event.accept()
        else:
            event.ignore()
    
    def dropEvent(self, event):
        if not event.mimeData().hasFormat(MIME_TYPE_ITEM):
            event.ignore()
            return
        
        drag_data = ItemDragData.from_mime_data(event.mimeData())
        if drag_data:
            drag_data.is_copy = bool(QApplication.keyboardModifiers() & Qt.ControlModifier)
            self.item_dragged.emit(drag_data)
            event.acceptProposedAction()
        else:
            event.ignore()


class GridWidget(QWidget):
    def __init__(self, cols, rows, cell_size=None, parent=None):
        super().__init__(parent)
        self._cols = cols
        self._rows = rows
        self._cell_size = cell_size if cell_size else GRID_SIZE
        grid_w = cols * self._cell_size + 1
        grid_h = rows * self._cell_size + 1
        self.setFixedSize(grid_w, grid_h)
        self.setStyleSheet("background-color: #0e0e1e;")
    
    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setPen(QPen(QColor("#4a4a6e"), 1))
        cs = self._cell_size
        for col in range(self._cols + 1):
            x = col * cs + 0.5
            painter.drawLine(x, 0.5, x, self.height() - 0.5)
        for row in range(self._rows + 1):
            y = row * cs + 0.5
            painter.drawLine(0.5, y, self.width() - 0.5, y)
        painter.end()


class EquipmentGridWidget(QWidget):
    def __init__(self, cols, rows, parent=None):
        super().__init__(parent)
        self._cols = cols
        self._rows = rows
        self._padding = 4
    
    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        p = self._padding
        h = self.height() - p - 0.5
        w = self.width() - p - 0.5
        
        painter.setPen(QPen(QColor("#1a1a2e"), 1))
        for col in range(self._cols + 1):
            x = p + col * GRID_SIZE + 0.5
            painter.drawLine(x, p + 0.5, x, h)
        for row in range(self._rows + 1):
            y = p + row * GRID_SIZE + 0.5
            painter.drawLine(p + 0.5, y, w, y)
        
        painter.setPen(QPen(QColor("#2d2d44"), 1))
        for col in range(self._cols + 1):
            x = p + col * GRID_SIZE + 0.5
            painter.drawLine(x, p + 0.5, x, h)
        for row in range(self._rows + 1):
            y = p + row * GRID_SIZE + 0.5
            painter.drawLine(p + 0.5, y, w, y)
        painter.end()


class ItemGridView(QWidget):
    item_clicked = Signal(object)
    item_dropped = Signal(object, int, int)
    
    def __init__(self, title="", cols=10, rows=4, cell_size=None, border_color=None, parent=None):
        super().__init__(parent)
        self._cols = cols
        self._rows = rows
        self._title = title
        self._cell_size = cell_size if cell_size else GRID_SIZE
        self._border_color = border_color if border_color else "#2d2d44"
        self._cells = {}
        self._version = 0x63
        self._doc_id = -1
        self._stored_in = -1
        self._active_rows = rows
        self._init_ui()
    
    def set_document_info(self, doc_id: int, stored_in: int):
        self._doc_id = doc_id
        self._stored_in = stored_in
        for (col, row), cell in self._cells.items():
            cell.set_source_info(doc_id, 0, col, row, stored_in)
    
    def set_active_rows(self, rows: int):
        self._active_rows = max(1, min(self._rows, rows))
        for (col, row), cell in self._cells.items():
            if row >= self._active_rows and not cell.item:
                cell.setStyleSheet("background-color: #0a0a0a;")
                cell.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            elif row >= self._active_rows and cell.item:
                pass
            else:
                if not cell.item:
                    cell.setStyleSheet("background-color: transparent;")
                    cell.setAttribute(Qt.WA_TransparentForMouseEvents, False)
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)
        
        if self._title:
            title_label = QLabel(self._title)
            title_label.setStyleSheet("color: #aaa; font-weight: bold; font-size: 11px;")
            layout.addWidget(title_label)
        
        cs = self._cell_size
        grid_w = self._cols * cs + 1
        grid_h = self._rows * cs + 1
        
        self._grid_widget = GridWidget(self._cols, self._rows, cs)
        self._grid_widget.setFixedSize(grid_w, grid_h)
        
        for row in range(self._rows):
            for col in range(self._cols):
                cell = ItemGridCell(self._grid_widget, self._cell_size)
                cell.setGeometry(col * cs, row * cs, cs, cs)
                cell.clicked.connect(self._on_cell_clicked)
                cell.item_dragged.connect(self._on_cell_dragged)
                if self._doc_id >= 0:
                    cell.set_source_info(self._doc_id, 0, col, row, self._stored_in)
                self._cells[(col, row)] = cell
        
        layout.addWidget(self._grid_widget, 0, Qt.AlignLeft)
        
        self.setObjectName("itemGridView")
        self.setStyleSheet(f"""
            #itemGridView {{
                background-color: #0d0d1a;
                border: 1px solid {self._border_color};
                border-radius: 3px;
            }}
        """)
    
    def _on_cell_clicked(self, item):
        self.item_clicked.emit(item)
    
    def _on_cell_dragged(self, drag_data):
        cell = self.sender()
        for (col, row), c in self._cells.items():
            if c is cell:
                self.item_dropped.emit(drag_data, col, row)
                break
    
    def clear_items(self):
        for cell in self._cells.values():
            cell.clear_item()
            cell.show()
    
    def resize_grid(self, cols, rows):
        if cols == self._cols and rows == self._rows:
            return
        
        cs = self._cell_size
        
        for (col, row), cell in self._cells.items():
            if col >= cols or row >= rows:
                cell.setParent(None)
                cell.deleteLater()
        
        new_cells = {}
        for (col, row), cell in self._cells.items():
            if col < cols and row < rows:
                new_cells[(col, row)] = cell
        
        for row in range(rows):
            for col in range(cols):
                if (col, row) not in new_cells:
                    cell = ItemGridCell(self._grid_widget, self._cell_size)
                    cell.setGeometry(col * cs, row * cs, cs, cs)
                    cell.clicked.connect(self._on_cell_clicked)
                    cell.item_dragged.connect(self._on_cell_dragged)
                    if self._doc_id >= 0:
                        cell.set_source_info(self._doc_id, 0, col, row, self._stored_in)
                    new_cells[(col, row)] = cell
        
        self._cells = new_cells
        self._cols = cols
        self._rows = rows
        
        grid_w = cols * cs + 1
        grid_h = rows * cs + 1
        self._grid_widget._cols = cols
        self._grid_widget._rows = rows
        self._grid_widget.setFixedSize(grid_w, grid_h)
        self._grid_widget.update()
    
    def set_item(self, col, row, item, pixmap=None, width=1, height=1, is_equipment=False, version=0x63):
        self._version = version
        if (col, row) not in self._cells:
            return
        
        cs = self._cell_size
        main_cell = self._cells[(col, row)]
        main_cell.setMinimumSize(0, 0)
        main_cell.setMaximumSize(16777215, 16777215)
        main_cell.set_item(item, pixmap, width, height, True, version)
        main_cell.set_source_info(self._doc_id, 0, col, row, self._stored_in)
        w = width * cs
        h = height * cs
        main_cell.setGeometry(col * cs, row * cs, w, h)
        main_cell.setAlignment(Qt.AlignCenter)
        main_cell.raise_()
        
        for dx in range(width):
            for dy in range(height):
                if dx == 0 and dy == 0:
                    continue
                other_col, other_row = col + dx, row + dy
                if (other_col, other_row) in self._cells:
                    other = self._cells[(other_col, other_row)]
                    other.set_item(item, None, 1, 1, False, version)
                    other.hide()


class EquipmentSlot(QLabel):
    clicked = Signal(object)
    item_dropped = Signal(object, int)
    
    SLOT_SIZES = {
        'helm': (2, 2),
        'amulet': (1, 1),
        'armor': (2, 3),
        'weapon': (2, 4),
        'shield': (2, 4),
        'ring': (1, 1),
        'belt': (2, 1),
        'gloves': (2, 2),
        'boots': (2, 2),
    }
    
    def __init__(self, name="", slot_type="", parent=None):
        super().__init__(parent)
        self._name = name
        self._slot_type = slot_type
        self._item = None
        self._version = 0x63
        self._doc_id = -1
        self._position = -1
        self._pixmap = None
        self._drag_start_pos = None
        
        size = self.SLOT_SIZES.get(slot_type, (2, 2))
        self._grid_width = size[0]
        self._grid_height = size[1]
        
        self._set_style()
        self.setAcceptDrops(True)
    
    def set_document_info(self, doc_id: int, position: int):
        self._doc_id = doc_id
        self._position = position
    
    def _set_style(self):
        width = self._grid_width * GRID_SIZE
        height = self._grid_height * GRID_SIZE
        self.setFixedSize(width, height)
        self.setAlignment(Qt.AlignCenter)
        
        if self._name:
            self.setText(self._name)
            self.setStyleSheet("""
                QLabel {
                    background-color: #1a1a2e;
                    border: 1px solid #3d3d54;
                    border-radius: 2px;
                    color: #666;
                    font-size: 9px;
                }
            """)
        else:
            self.setStyleSheet("""
                QLabel {
                    background-color: #1a1a2e;
                    border: 1px solid #3d3d54;
                    border-radius: 2px;
                }
            """)
    
    def set_item(self, item, pixmap=None, version=0x63):
        self._item = item
        self._version = version
        self._pixmap = pixmap
        
        if pixmap and not pixmap.isNull():
            d2data_manager = get_d2data_manager()
            type_name = item.sTypeName.decode('ascii', errors='replace') if item.sTypeName else ''
            type_name = type_name.strip()
            inv_w, inv_h = self._grid_width, self._grid_height
            if d2data_manager and type_name:
                type_info = d2data_manager.get_item(type_name, version)
                if type_info:
                    inv_w = max(1, getattr(type_info, 'invwidth', inv_w))
                    inv_h = max(1, getattr(type_info, 'invheight', inv_h))
            
            width = self._grid_width * GRID_SIZE - 2
            height = self._grid_height * GRID_SIZE - 2
            scaled = pixmap.scaled(width, height, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            self.setPixmap(scaled)
            
            quality = item.quality() if hasattr(item, 'quality') else 2
            is_rw = hasattr(item, 'bRuneWord') and item.bRuneWord
            if is_rw:
                border_color = RUNEWORD_COLOR
                bg_color = self._quality_bg_color(quality, is_runeword=True)
            else:
                border_color = ITEM_QUALITY_COLORS.get(quality, "#5a5a7e")
                bg_color = self._quality_bg_color(quality)
            self.setStyleSheet(f"""
                QLabel {{
                    background-color: {bg_color};
                    border: 2px solid {border_color};
                    border-radius: 3px;
                }}
            """)
        else:
            self._set_style()
    
    def _quality_bg_color(self, quality, is_runeword=False):
        if is_runeword:
            return "#1a150e"
        bg_map = {
            1: "#1a1a1a",
            2: "#1a1a2e",
            3: "#1a1a1a",
            4: "#0e0e2a",
            5: "#0e1a0e",
            6: "#1a1a0e",
            7: "#1a150e",
            8: "#1a0e0e",
        }
        return bg_map.get(quality, "#1a1a2e")
    
    def clear_item(self):
        self._item = None
        self._pixmap = None
        self._set_style()
    
    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._item:
            painter = QPainter(self)
            painter.setPen(QPen(QColor("#2d2d44"), 1))
            for col in range(self._grid_width + 1):
                x = col * GRID_SIZE
                painter.drawLine(x, 0, x, self.height())
            for row in range(self._grid_height + 1):
                y = row * GRID_SIZE
                painter.drawLine(0, y, self.width(), y)
            painter.end()
    
    def enterEvent(self, event):
        if self._item:
            try:
                tooltip = build_item_tooltip(self._item, self._version)
            except Exception:
                tooltip = ""
            if tooltip:
                pos = self.mapToGlobal(self.rect().bottomRight() + QPoint(1, 1))
                TranslucentTooltip.show_tooltip(pos, tooltip)
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        TranslucentTooltip.hide_tooltip()
        super().leaveEvent(event)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self._item:
            self._drag_start_pos = event.pos()
        super().mousePressEvent(event)
    
    def contextMenuEvent(self, event):
        if not self._item:
            return
        
        menu = QMenu(self)
        
        save_action = QAction(tr("Save Item As..."), self)
        save_action.triggered.connect(lambda: self._save_item_as())
        menu.addAction(save_action)
        
        menu.exec(event.globalPos())
    
    def _save_item_as(self):
        if not self._item:
            return
        
        from core.obitstream import OBitStream
        
        type_name = self._item.sTypeName.decode('ascii', errors='replace').strip() if self._item.sTypeName else 'item'
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            tr("Save Item"),
            f"{type_name}.d2i",
            tr("D2I Files (*.d2i);;All Files (*)")
        )
        
        if not file_path:
            return
        
        try:
            bs = OBitStream()
            self._item.serialize(bs, self._version, write_magic=False)
            data = bs.get_data()
            
            with open(file_path, 'wb') as f:
                f.write(data)
            
            QMessageBox.information(self, tr("Success"), tr_format("Item saved to:\n{}", file_path))
        except Exception as e:
            QMessageBox.critical(self, tr("Error"), tr_format("Failed to save item:\n{}", str(e)))
    
    def mouseMoveEvent(self, event):
        if not self._drag_start_pos or not self._item:
            return
        
        distance = (event.pos() - self._drag_start_pos).manhattanLength()
        if distance < QApplication.startDragDistance():
            return
        
        is_copy = bool(event.modifiers() & Qt.ControlModifier)
        
        drag = QDrag(self)
        mime_data = QMimeData()
        
        drag_data = ItemDragData(
            item=self._item,
            source_doc_id=self._doc_id,
            source_location=1,
            source_column=0,
            source_row=0,
            source_position=self._position,
            is_copy=is_copy
        )
        mime_data.setData(MIME_TYPE_ITEM, drag_data.to_mime_data().data(MIME_TYPE_ITEM))
        drag.setMimeData(mime_data)
        
        if self._pixmap and not self._pixmap.isNull():
            drag.setPixmap(self._pixmap.scaled(56, 56, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            drag.setHotSpot(event.pos())
        
        default_action = Qt.CopyAction if is_copy else Qt.MoveAction
        drag.exec_(Qt.CopyAction | Qt.MoveAction, default_action)
        self._drag_start_pos = None
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._drag_start_pos and self._item:
            distance = (event.pos() - self._drag_start_pos).manhattanLength()
            if distance < QApplication.startDragDistance():
                self.clicked.emit(self._item)
        self._drag_start_pos = None
        super().mouseReleaseEvent(event)
    
    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(MIME_TYPE_ITEM):
            event.setDropAction(Qt.MoveAction)
            event.accept()
        else:
            event.ignore()
    
    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat(MIME_TYPE_ITEM):
            if event.modifiers() & Qt.ControlModifier:
                event.setDropAction(Qt.CopyAction)
            else:
                event.setDropAction(Qt.MoveAction)
            event.accept()
        else:
            event.ignore()
    
    def dropEvent(self, event):
        if not event.mimeData().hasFormat(MIME_TYPE_ITEM):
            event.ignore()
            return
        
        drag_data = ItemDragData.from_mime_data(event.mimeData())
        if drag_data:
            drag_data.is_copy = bool(QApplication.keyboardModifiers() & Qt.ControlModifier)
            self.item_dropped.emit(drag_data, self._position)
            event.acceptProposedAction()
        else:
            event.ignore()


class WeaponSetSwitcher(QWidget):
    set_changed = Signal(int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_set = 0
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        self._btn_group = QButtonGroup(self)
        
        btn_w = GRID_SIZE * 2 // 2
        self._btn_set1 = QPushButton("I")
        self._btn_set1.setFixedSize(btn_w, 18)
        self._btn_set1.setCheckable(True)
        self._btn_set1.setChecked(True)
        self._btn_set1.setStyleSheet("""
            QPushButton {
                background-color: #2a2a3e;
                border: 1px solid #4a4a6e;
                border-radius: 2px;
                color: #ccc;
                font-weight: bold;
                font-size: 10px;
            }
            QPushButton:checked {
                background-color: #4a4a6e;
                border: 1px solid #6a6a9e;
                color: #fff;
            }
            QPushButton:hover {
                background-color: #3a3a5e;
            }
        """)
        self._btn_group.addButton(self._btn_set1, 0)
        layout.addWidget(self._btn_set1)
        
        self._btn_set2 = QPushButton("II")
        self._btn_set2.setFixedSize(btn_w, 18)
        self._btn_set2.setCheckable(True)
        self._btn_set2.setStyleSheet("""
            QPushButton {
                background-color: #2a2a3e;
                border: 1px solid #4a4a6e;
                border-radius: 2px;
                color: #ccc;
                font-weight: bold;
                font-size: 10px;
            }
            QPushButton:checked {
                background-color: #4a4a6e;
                border: 1px solid #6a6a9e;
                color: #fff;
            }
            QPushButton:hover {
                background-color: #3a3a5e;
            }
        """)
        self._btn_group.addButton(self._btn_set2, 1)
        layout.addWidget(self._btn_set2)
        
        layout.addStretch()
        
        self._btn_group.idClicked.connect(self._on_set_clicked)
    
    def _on_set_clicked(self, set_id):
        self._current_set = set_id
        self.set_changed.emit(set_id)
    
    def current_set(self):
        return self._current_set


class ItemPanelWidget(QWidget):
    item_clicked = Signal(object)
    weapon_set_changed = Signal(int)
    item_dropped = Signal(object, int, int, int, int)
    
    EQUIPMENT_LAYOUT = {
        'helm':     (4, 0, 2, 2),
        'amulet':   (7, 1, 1, 1),
        'weapon':   (0, 1, 2, 4),
        'shield':   (8, 1, 2, 4),
        'armor':    (4, 2, 2, 4),
        'gloves':   (0, 6, 2, 2),
        'boots':    (8, 6, 2, 2),
        'ring_l':   (3, 7, 1, 1),
        'belt':     (4, 7, 2, 1),
        'ring_r':   (6, 7, 1, 1),
    }
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._doc_id = -1
        self._version = 0x63
        self._init_ui()
    
    def set_document_id(self, doc_id: int):
        self._doc_id = doc_id
        self.inventory_view.set_document_info(doc_id, 0)
        self.stash_view.set_document_info(doc_id, 4)
        self.cube_view.set_document_info(doc_id, 3)
        self.belt_view.set_document_info(doc_id, 5)
        
        equip_positions = {
            1: self.helm_slot,
            2: self.amulet_slot,
            3: self.armor_slot,
            4: self.weapon_slot,
            5: self.shield_slot,
            6: self.right_ring_slot,
            7: self.left_ring_slot,
            8: self.belt_slot,
            9: self.boots_slot,
            10: self.gloves_slot,
        }
        for pos, slot in equip_positions.items():
            slot.set_document_info(doc_id, pos)
    
    def set_version(self, version: int):
        self._version = version
        if version >= 0x69:
            self.stash_view.resize_grid(10, 10)
        else:
            self.stash_view.resize_grid(6, 8)
    
    def _init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(10)
        
        # === Column 1: Equipment + Inventory ===
        col1 = QVBoxLayout()
        col1.setSpacing(3)
        
        equipment_widget = EquipmentGridWidget(10, 8)
        equipment_widget.setObjectName("equipmentPanel")
        equipment_widget.setStyleSheet("""
            #equipmentPanel {
                background-color: #0e0e1e;
                border: 1px solid #2d2d44;
                border-radius: 3px;
            }
        """)
        equipment_layout = QGridLayout(equipment_widget)
        equipment_layout.setSpacing(0)
        equipment_layout.setContentsMargins(4, 4, 4, 4)
        
        for c in range(10):
            equipment_layout.setColumnMinimumWidth(c, GRID_SIZE)
            equipment_layout.setColumnStretch(c, 0)
        for r in range(8):
            equipment_layout.setRowMinimumHeight(r, GRID_SIZE)
            equipment_layout.setRowStretch(r, 0)
        
        eq_w = 10 * GRID_SIZE + 8 + 1
        eq_h = 8 * GRID_SIZE + 8 + 1
        equipment_widget.setFixedSize(eq_w, eq_h)
        
        self.weapon_set_switcher = WeaponSetSwitcher()
        self.weapon_set_switcher.set_changed.connect(self._on_weapon_set_changed)
        equipment_layout.addWidget(self.weapon_set_switcher, 0, 0, 1, 2, Qt.AlignCenter)
        
        self.helm_slot = EquipmentSlot(tr("Helm"), "helm")
        self.helm_slot.clicked.connect(self._on_slot_clicked)
        self.helm_slot.item_dropped.connect(self._on_slot_item_dropped)
        
        self.amulet_slot = EquipmentSlot(tr("Amu"), "amulet")
        self.amulet_slot.clicked.connect(self._on_slot_clicked)
        self.amulet_slot.item_dropped.connect(self._on_slot_item_dropped)
        
        self.armor_slot = EquipmentSlot(tr("Armor"), "armor")
        self.armor_slot.clicked.connect(self._on_slot_clicked)
        self.armor_slot.item_dropped.connect(self._on_slot_item_dropped)
        
        self.weapon_slot = EquipmentSlot(tr("Weapon"), "weapon")
        self.weapon_slot.clicked.connect(self._on_slot_clicked)
        self.weapon_slot.item_dropped.connect(self._on_slot_item_dropped)
        
        self.shield_slot = EquipmentSlot(tr("Shield"), "shield")
        self.shield_slot.clicked.connect(self._on_slot_clicked)
        self.shield_slot.item_dropped.connect(self._on_slot_item_dropped)
        
        self.left_ring_slot = EquipmentSlot(tr("Ring"), "ring")
        self.left_ring_slot.clicked.connect(self._on_slot_clicked)
        self.left_ring_slot.item_dropped.connect(self._on_slot_item_dropped)
        
        self.right_ring_slot = EquipmentSlot(tr("Ring"), "ring")
        self.right_ring_slot.clicked.connect(self._on_slot_clicked)
        self.right_ring_slot.item_dropped.connect(self._on_slot_item_dropped)
        
        self.belt_slot = EquipmentSlot(tr("Belt"), "belt")
        self.belt_slot.clicked.connect(self._on_slot_clicked)
        self.belt_slot.item_dropped.connect(self._on_slot_item_dropped)
        
        self.gloves_slot = EquipmentSlot(tr("Gloves"), "gloves")
        self.gloves_slot.clicked.connect(self._on_slot_clicked)
        self.gloves_slot.item_dropped.connect(self._on_slot_item_dropped)
        
        self.boots_slot = EquipmentSlot(tr("Boots"), "boots")
        self.boots_slot.clicked.connect(self._on_slot_clicked)
        self.boots_slot.item_dropped.connect(self._on_slot_item_dropped)
        
        slot_widgets = {
            'helm': self.helm_slot,
            'amulet': self.amulet_slot,
            'armor': self.armor_slot,
            'weapon': self.weapon_slot,
            'shield': self.shield_slot,
            'belt': self.belt_slot,
            'ring_l': self.left_ring_slot,
            'ring_r': self.right_ring_slot,
            'gloves': self.gloves_slot,
            'boots': self.boots_slot,
        }
        
        for name, (col, row, col_span, row_span) in self.EQUIPMENT_LAYOUT.items():
            widget = slot_widgets[name]
            equipment_layout.addWidget(widget, row, col, row_span, col_span, Qt.AlignLeft | Qt.AlignTop)
        
        col1.addWidget(equipment_widget, 0, Qt.AlignHCenter | Qt.AlignTop)
        
        self.inventory_view = ItemGridView(tr("Inventory"), 10, 4)
        self.inventory_view.item_clicked.connect(self._on_item_clicked)
        self.inventory_view.item_dropped.connect(self._on_grid_item_dropped)
        col1.addWidget(self.inventory_view, 0, Qt.AlignHCenter)
        
        col1.addStretch(1)
        main_layout.addLayout(col1, 1)
        
        # === Column 2: Belt + Cube ===
        col2 = QVBoxLayout()
        col2.setSpacing(3)
        
        self.belt_view = ItemGridView(tr("Belt"), 4, 4, cell_size=21)
        self.belt_view.item_clicked.connect(self._on_item_clicked)
        self.belt_view.item_dropped.connect(self._on_grid_item_dropped)
        col2.addWidget(self.belt_view, 0, Qt.AlignHCenter)
        
        self.cube_view = ItemGridView(tr("Cube"), 3, 4, border_color="#8B7355")
        self.cube_view.item_clicked.connect(self._on_item_clicked)
        self.cube_view.item_dropped.connect(self._on_grid_item_dropped)
        col2.addWidget(self.cube_view, 0, Qt.AlignHCenter)
        
        col2.addStretch(1)
        main_layout.addLayout(col2, 1)
        
        # === Column 3: Stash ===
        col3 = QVBoxLayout()
        col3.setSpacing(3)
        
        self.stash_view = ItemGridView(tr("Stash"), 10, 10)
        self.stash_view.item_clicked.connect(self._on_item_clicked)
        self.stash_view.item_dropped.connect(self._on_grid_item_dropped)
        col3.addWidget(self.stash_view, 0, Qt.AlignHCenter)
        
        col3.addStretch(1)
        main_layout.addLayout(col3, 1)
    
    def _on_weapon_set_changed(self, set_id):
        self.weapon_set_changed.emit(set_id)
    
    def _on_slot_clicked(self, item):
        self.item_clicked.emit(item)
    
    def _on_item_clicked(self, item):
        self.item_clicked.emit(item)
    
    def _on_slot_item_dropped(self, drag_data, position):
        self.item_dropped.emit(drag_data, -1, -1, -1, position)
    
    def _on_grid_item_dropped(self, drag_data, col, row):
        sender = self.sender()
        stored_in = 0
        if sender == self.inventory_view:
            stored_in = 0
        elif sender == self.stash_view:
            stored_in = 4
        elif sender == self.cube_view:
            stored_in = 3
        elif sender == self.belt_view:
            stored_in = 5
            if row >= self.belt_view._active_rows:
                return
        
        self.item_dropped.emit(drag_data, stored_in, col, row, -1)
    
    def current_weapon_set(self):
        return self.weapon_set_switcher.current_set()
    
    def clear_all(self):
        self.helm_slot.clear_item()
        self.amulet_slot.clear_item()
        self.armor_slot.clear_item()
        self.weapon_slot.clear_item()
        self.shield_slot.clear_item()
        self.left_ring_slot.clear_item()
        self.right_ring_slot.clear_item()
        self.belt_slot.clear_item()
        self.gloves_slot.clear_item()
        self.boots_slot.clear_item()
        self.belt_view.clear_items()
        self.inventory_view.clear_items()
        self.stash_view.clear_items()
        self.cube_view.clear_items()
    
    def set_items(self, items_by_location, version=0x63):
        self.clear_all()
        self.belt_view.set_active_rows(1)
        
        for loc_id, items in items_by_location.items():
            for item in items:
                if not item or not item.pItemInfo:
                    continue
                
                pixmap = None
                if hasattr(item, '_pixmap') and item._pixmap:
                    pixmap = item._pixmap
                
                if loc_id == 1:
                    slot = self._get_equipment_slot(item)
                    if slot:
                        slot.set_item(item, pixmap, version)
                        if slot == self.belt_slot:
                            belt_rows = self._get_belt_rows_from_item(item)
                            self.belt_view.set_active_rows(belt_rows)
                elif loc_id == 2:
                    self._add_to_inventory(item, pixmap, version)
                elif loc_id == 3:
                    self._add_to_belt(item, pixmap, version)
                elif loc_id == 4:
                    self._add_to_stash(item, pixmap, version)
                elif loc_id == 5:
                    self._add_to_cube(item, pixmap, version)
    
    def _get_equipment_slot(self, item):
        if not item.pItemInfo:
            return None
        
        equip_loc = item.pItemInfo.equip_location
        if equip_loc is None:
            return None
        
        loc_map = {
            1: self.helm_slot,
            2: self.amulet_slot,
            3: self.armor_slot,
            4: self.weapon_slot,
            5: self.shield_slot,
            6: self.right_ring_slot,
            7: self.left_ring_slot,
            8: self.belt_slot,
            9: self.boots_slot,
            10: self.gloves_slot,
        }
        
        return loc_map.get(equip_loc)
    
    def _add_to_inventory(self, item, pixmap, version):
        if hasattr(item, '_meta') and item._meta:
            meta = item._meta
            col = getattr(meta, 'col', None)
            row = getattr(meta, 'row', None)
            width = getattr(meta, 'width', 1)
            height = getattr(meta, 'height', 1)
            if col is not None and row is not None:
                self.inventory_view.set_item(col, row, item, pixmap, width, height, version=version)
    
    def _get_belt_rows_from_item(self, item) -> int:
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
                rows = d2data_manager.get_belt_rows(type_name, self._version)
                if rows > 0:
                    return rows
        return 1
    
    def _add_to_belt(self, item, pixmap, version):
        if hasattr(item, '_meta') and item._meta:
            meta = item._meta
            col = getattr(meta, 'col', None)
            row = getattr(meta, 'row', None)
            if col is not None and row is not None:
                self.belt_view.set_item(col, row, item, pixmap, version=version)
    
    def _add_to_stash(self, item, pixmap, version):
        if hasattr(item, '_meta') and item._meta:
            meta = item._meta
            col = getattr(meta, 'col', None)
            row = getattr(meta, 'row', None)
            width = getattr(meta, 'width', 1)
            height = getattr(meta, 'height', 1)
            if col is not None and row is not None:
                self.stash_view.set_item(col, row, item, pixmap, width, height, version=version)
    
    def _add_to_cube(self, item, pixmap, version):
        if hasattr(item, '_meta') and item._meta:
            meta = item._meta
            col = getattr(meta, 'col', None)
            row = getattr(meta, 'row', None)
            width = getattr(meta, 'width', 1)
            height = getattr(meta, 'height', 1)
            if col is not None and row is not None:
                self.cube_view.set_item(col, row, item, pixmap, width, height, version=version)