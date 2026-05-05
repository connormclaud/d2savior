import os
import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QApplication, QFrame, QTabWidget, QTreeWidget,
    QTreeWidgetItem, QHeaderView, QMessageBox, QMenu, QFileDialog
)
from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtGui import QPixmap, QPainter, QColor, QPen, QAction

from core.stash import (SharedStash, STASH_TAB_TYPE_NORMAL, STASH_TAB_TYPE_ADVANCED, STASH_TAB_TYPE_CHRONICLE,
                         ADVANCED_SUBTYPE_GEM, ADVANCED_SUBTYPE_RUNE, ADVANCED_SUBTYPE_MATERIAL, ADVANCED_SUBTYPE_UNKNOWN,
                         classify_advanced_tab, compute_advanced_grid,
                         NORMAL_LAYOUT, GEM_LAYOUT, RUNE_LAYOUT, MATERIAL_LAYOUT,
                         GEM_SLOT_ORDER, RUNE_SLOT_ORDER, MATERIAL_SLOT_ORDER,
                         RUNE_CODES, GEM_CODES, MATERIAL_CODES)
from core.ibitstream import IBitStream
from core.d2data import get_d2data_manager
from core.localized_data import get_localized_data
from gui.gui_translator import tr, tr_format
from gui.image_manager import get_image_manager


CELL_SIZE = 28

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


class StashTooltip(QLabel):
    _instance = None

    def __init__(self, parent=None):
        super().__init__(parent, Qt.ToolTip | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setMargin(8)
        self.setStyleSheet("color: #e0e0e0; font-size: 12px;")

    @classmethod
    def show_tooltip(cls, global_pos: QPoint, html: str):
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


def _build_stash_tooltip(item, version=0x69):
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

    rune_number = 0
    if type_name.startswith('r') and len(type_name) >= 3 and type_name[1:].strip().isdigit():
        rune_number = int(type_name[1:].strip())
        if not is_runeword:
            base_name = f'#{rune_number} {base_name}'

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
        ear_name = loc.get_tooltip_ui('Ear')
        ear_name = ear_name if ear_name != 'Ear' else 'Ear'
        lines.append(f'<span style="color:{TOOLTIP_WHITE}; font-weight:bold">{item.pEar.sEarName}\'s {ear_name}</span>')
        return '<div style="text-align:center">' + '<br>'.join(lines) + '</div>'

    if item.pItemInfo and item.pItemInfo.is_gold() and item.pItemInfo.pGold:
        gold_name = loc.get_tooltip_ui('Gold')
        gold_name = gold_name if gold_name != 'Gold' else 'Gold'
        qty_name = loc.get_tooltip_ui('Quantity')
        qty_name = qty_name if qty_name != 'Quantity' else 'Quantity'
        lines.append(f'<span style="color:{TOOLTIP_WHITE}; font-weight:bold">{gold_name}</span>')
        lines.append(f'<span style="color:{TOOLTIP_WHITE}">{qty_name}: {item.pItemInfo.pGold.wQuantity}</span>')
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
            rw_id = item.rune_word_id()
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
            low_q = loc.get_item_nameaffix("Low Quality")
            lines.append(f'<span style="color:{name_color}; font-weight:bold">{low_q} {base_name}</span>')
        elif quality == 2:
            if ext.wMonsterID.exist():
                from core.property import get_monster_name
                mname = get_monster_name(ext.wMonsterID.value)
                lines.append(f'<span style="color:{name_color}; font-weight:bold">{mname} {base_name}</span>')
            else:
                lines.append(f'<span style="color:{name_color}; font-weight:bold">{base_name}</span>')
        elif quality == 3:
            hi_q = loc.get_item_nameaffix("Hiquality")
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

        if tsi.iDefence.exist():
            def_name = loc.get_tooltip_ui('Defense')
            def_name = def_name if def_name != 'Defense' else 'Defense'
            lines.append(f'<span style="color:{TOOLTIP_WHITE}">{def_name}: {tsi.get_defence()}</span>')
        if tsi.iMaxDurability.exist():
            if tsi.is_indestructible():
                indestr_name = loc.get_tooltip_ui('Indestructible')
                indestr_name = indestr_name if indestr_name != 'Indestructible' else 'Indestructible'
                lines.append(f'<span style="color:{TOOLTIP_BLUE}">{indestr_name}</span>')
            elif tsi.iCurDur.exist():
                dur_name = loc.get_tooltip_ui('Durability')
                dur_name = dur_name if dur_name != 'Durability' else 'Durability'
                lines.append(f'<span style="color:{TOOLTIP_WHITE}">{dur_name}: {tsi.iCurDur.value}/{tsi.iMaxDurability.value}</span>')
        if tsi.iQuantity.exist():
            qty_name = loc.get_tooltip_ui('Quantity')
            qty_name = qty_name if qty_name != 'Quantity' else 'Quantity'
            lines.append(f'<span style="color:{TOOLTIP_WHITE}">{qty_name}: {tsi.iQuantity.value}</span>')

    if not item.bSimple and item.pItemInfo and item.pItemInfo.pExtItemInfo:
        if hasattr(item.pItemInfo.pTpSpInfo, 'stPropertyList') and item.pItemInfo.pTpSpInfo.stPropertyList and item.pItemInfo.pTpSpInfo.stPropertyList.mProperty:
            from core.property import format_property
            try:
                parsed = item.pItemInfo.pTpSpInfo.stPropertyList.get_parsed_properties(version)
                for prop_id, value, params in parsed:
                    try:
                        prop_text = format_property(prop_id, params, version)
                        if prop_text:
                            lines.append(f'<span style="color:{TOOLTIP_BLUE}">{prop_text}</span>')
                    except Exception:
                        pass
            except Exception:
                pass

        if quality == 5 and hasattr(item.pItemInfo.pTpSpInfo, 'apSetProperty'):
            for set_prop in item.pItemInfo.pTpSpInfo.apSetProperty:
                if set_prop is not None and hasattr(set_prop, 'mProperty') and set_prop.mProperty:
                    from core.property import format_property
                    try:
                        parsed = set_prop.get_parsed_properties(version)
                        for prop_id, value, params in parsed:
                            try:
                                prop_text = format_property(prop_id, params, version)
                                if prop_text:
                                    lines.append(f'<span style="color:{TOOLTIP_GREEN}">{prop_text}</span>')
                            except Exception:
                                pass
                    except Exception:
                        pass

        if is_runeword and hasattr(item.pItemInfo.pTpSpInfo, 'stRuneWordPropertyList') and item.pItemInfo.pTpSpInfo.stRuneWordPropertyList and item.pItemInfo.pTpSpInfo.stRuneWordPropertyList.mProperty:
            from core.property import format_property
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
        eth_name = loc.get_tooltip_ui('Ethereal')
        eth_name = eth_name if eth_name != 'Ethereal' else 'Ethereal'
        lines.append(f'<span style="color:{TOOLTIP_BLUE}">{eth_name}</span>')

    if hasattr(item, 'bSocketed') and item.bSocketed:
        sockets = 0
        if hasattr(item.pItemInfo.pTpSpInfo, 'iSocket') and item.pItemInfo.pTpSpInfo.iSocket.exist():
            sockets = item.pItemInfo.pTpSpInfo.iSocket.value
        gem_items = item.aGemItems if hasattr(item, 'aGemItems') and item.aGemItems else []
        gem_count = len(gem_items)
        if sockets > 0:
            sock_name = loc.get_tooltip_ui('Socketed')
            sock_name = sock_name if sock_name != 'Socketed' else 'Socketed'
            lines.append(f'<span style="color:{TOOLTIP_BLUE}">{sock_name} ({gem_count}/{sockets})</span>')
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
        unid_name = loc.get_tooltip_ui('Unidentified')
        unid_name = unid_name if unid_name != 'Unidentified' else 'Unidentified'
        lines.append(f'<span style="color:{TOOLTIP_RED}">{unid_name}</span>')

    return '<div style="text-align:center">' + '<br>'.join(lines) + '</div>'


class StashCell(QLabel):
    clicked = Signal(object)

    def __init__(self, col, row, parent=None):
        super().__init__(parent)
        self._col = col
        self._row = row
        self._item = None
        self._version = 0x69
        self._is_main = True
        self._grid_width = 1
        self._grid_height = 1
        self._hovered = False
        self.setFixedSize(CELL_SIZE, CELL_SIZE)
        self.setAlignment(Qt.AlignCenter)
        self.setMouseTracking(True)
        self._update_empty_style()

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

    def _get_item_colors(self, item):
        is_rw = hasattr(item, 'bRuneWord') and item.bRuneWord
        quality = item.quality() if hasattr(item, 'quality') else 2
        if is_rw:
            border_color = RUNEWORD_COLOR
            bg_color = self._quality_bg_color(quality, is_runeword=True)
        else:
            border_color = ITEM_QUALITY_COLORS.get(quality, "#2d2d44")
            bg_color = self._quality_bg_color(quality)
        return border_color, bg_color

    def _update_empty_style(self):
        self.setStyleSheet(
            "QLabel { background-color: #1a1a2e; border: 1px solid #2a2a44; }"
        )

    def set_item(self, item, version=0x69, is_main=True, grid_width=1, grid_height=1, pixmap=None):
        self._item = item
        self._version = version
        self._is_main = is_main
        self._grid_width = grid_width
        self._grid_height = grid_height
        self._hovered = False

        if is_main:
            border_color, bg_color = self._get_item_colors(item)

            if grid_width > 1 or grid_height > 1:
                w = grid_width * CELL_SIZE
                h = grid_height * CELL_SIZE
                self.setFixedSize(w, h)
                if pixmap and not pixmap.isNull():
                    scaled = pixmap.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                    self.setPixmap(scaled)
                else:
                    type_name = item.sTypeName.decode('ascii', errors='replace').strip() if isinstance(item.sTypeName, bytes) else str(item.sTypeName)
                    self.setText(type_name[:6])
                    self.setStyleSheet(f"""
                        QLabel {{
                            background-color: {bg_color};
                            border: 1px solid {border_color};
                            color: {border_color};
                            font-size: 8px;
                            font-weight: bold;
                        }}
                    """)
                    return
            else:
                if pixmap and not pixmap.isNull():
                    self.setPixmap(pixmap)
                else:
                    type_name = item.sTypeName.decode('ascii', errors='replace').strip() if isinstance(item.sTypeName, bytes) else str(item.sTypeName)
                    self.setText(type_name[:3])
                    self.setStyleSheet(f"""
                        QLabel {{
                            background-color: {bg_color};
                            border: 1px solid {border_color};
                            color: {border_color};
                            font-size: 7px;
                            font-weight: bold;
                        }}
                    """)
                    return

            self.setStyleSheet(f"""
                QLabel {{
                    background-color: {bg_color};
                    border: 1px solid {border_color};
                }}
            """)
            self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        else:
            _, bg_color = self._get_item_colors(item)
            self.setStyleSheet(f"""
                QLabel {{
                    background-color: {bg_color};
                    border: none;
                }}
            """)
            self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

    def clear_item(self):
        self._item = None
        self._is_main = True
        self._grid_width = 1
        self._grid_height = 1
        self._hovered = False
        self.setFixedSize(CELL_SIZE, CELL_SIZE)
        self.setPixmap(QPixmap())
        self.setText("")
        self._update_empty_style()
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)

    def enterEvent(self, event):
        if self._item and self._is_main:
            self._hovered = True
            border_color, bg_color = self._get_item_colors(self._item)
            self.setStyleSheet(f"""
                QLabel {{
                    background-color: {bg_color};
                    border: 2px solid {border_color};
                }}
            """)
            try:
                tooltip = _build_stash_tooltip(self._item, self._version)
            except Exception:
                tooltip = ""
            if tooltip:
                pos = self.mapToGlobal(self.rect().bottomRight() + QPoint(1, 1))
                StashTooltip.show_tooltip(pos, tooltip)
        super().enterEvent(event)

    def leaveEvent(self, event):
        if self._item and self._is_main:
            self._hovered = False
            border_color, bg_color = self._get_item_colors(self._item)
            self.setStyleSheet(f"""
                QLabel {{
                    background-color: {bg_color};
                    border: 1px solid {border_color};
                }}
            """)
        StashTooltip.hide_tooltip()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self._item and self._is_main:
            self.clicked.emit(self._item)
        super().mousePressEvent(event)

    def contextMenuEvent(self, event):
        if not self._item or not self._is_main:
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

        type_name = self._item.sTypeName.decode('ascii', errors='replace').strip() if isinstance(self._item.sTypeName, bytes) else str(self._item.sTypeName)

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


class StashGridWidget(QWidget):
    item_clicked = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.items_data = []
        self._version = 0x69
        self._cols = NORMAL_LAYOUT[0]
        self._rows = NORMAL_LAYOUT[1]
        self._slot_order = None
        self._init_ui()

    def _init_ui(self):
        grid_w = self._cols * CELL_SIZE
        grid_h = self._rows * CELL_SIZE
        self.setFixedSize(grid_w, grid_h)
        self.setStyleSheet("background-color: #0e0e1e;")

        self.cells = {}
        for row in range(self._rows):
            for col in range(self._cols):
                cell = StashCell(col, row, self)
                cell.setGeometry(col * CELL_SIZE, row * CELL_SIZE, CELL_SIZE, CELL_SIZE)
                cell.clicked.connect(self.item_clicked.emit)
                self.cells[(col, row)] = cell

    def setup_grid(self, cols, rows, slot_order=None):
        self._cols = cols
        self._rows = rows
        self._slot_order = slot_order

        for cell in self.cells.values():
            cell.deleteLater()
        self.cells.clear()

        grid_w = cols * CELL_SIZE
        grid_h = rows * CELL_SIZE
        self.setFixedSize(grid_w, grid_h)

        for row in range(rows):
            for col in range(cols):
                cell = StashCell(col, row, self)
                cell.setGeometry(col * CELL_SIZE, row * CELL_SIZE, CELL_SIZE, CELL_SIZE)
                cell.clicked.connect(self.item_clicked.emit)
                self.cells[(col, row)] = cell

        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setPen(QPen(QColor("#4a4a6e"), 1))
        for col in range(self._cols + 1):
            x = col * CELL_SIZE
            painter.drawLine(x, 0, x, self.height())
        for row in range(self._rows + 1):
            y = row * CELL_SIZE
            painter.drawLine(0, y, self.width(), y)
        painter.end()

    def clear_items(self):
        for cell in self.cells.values():
            cell.clear_item()
            cell.show()

    def _get_item_grid_size(self, item, version=0x69):
        d2data = get_d2data_manager()
        type_name = item.sTypeName.decode('ascii', errors='replace').strip() if isinstance(item.sTypeName, bytes) else str(item.sTypeName)
        if d2data:
            type_info = d2data.get_item(type_name, version)
            if type_info:
                w = getattr(type_info, 'invwidth', 1)
                h = getattr(type_info, 'invheight', 1)
                return max(1, w), max(1, h)
        return 1, 1

    def set_items(self, items, version=0x69, is_advanced=False, slot_order=None):
        self.clear_items()
        self.items_data = items
        self._version = version

        img_mgr = get_image_manager()
        d2data = get_d2data_manager()

        if is_advanced and slot_order:
            self._set_items_advanced(items, version, slot_order, img_mgr, d2data)
        else:
            self._set_items_normal(items, version, img_mgr, d2data)

    def _set_items_normal(self, items, version, img_mgr, d2data):
        for item in items:
            if not hasattr(item, 'sTypeName'):
                continue

            col = item.iColumn if hasattr(item, 'iColumn') else 0
            row = item.iRow if hasattr(item, 'iRow') else 0

            if col < 0 or col >= self._cols or row < 0 or row >= self._rows:
                continue

            width, height = self._get_item_grid_size(item, version)

            type_name = item.sTypeName.decode('ascii', errors='replace').strip() if isinstance(item.sTypeName, bytes) else str(item.sTypeName)

            pixmap = None
            if img_mgr:
                pixmap = img_mgr.get_image_by_code(type_name, (width * CELL_SIZE - 2, height * CELL_SIZE - 2))

            main_cell = self.cells.get((col, row))
            if not main_cell:
                continue

            main_cell.set_item(item, version, is_main=True, grid_width=width, grid_height=height, pixmap=pixmap)
            w = width * CELL_SIZE
            h = height * CELL_SIZE
            main_cell.setGeometry(col * CELL_SIZE, row * CELL_SIZE, w, h)
            main_cell.setAlignment(Qt.AlignCenter)
            main_cell.raise_()

            for dy in range(height):
                for dx in range(width):
                    if dx == 0 and dy == 0:
                        continue
                    sub_pos = (col + dx, row + dy)
                    sub_cell = self.cells.get(sub_pos)
                    if sub_cell:
                        sub_cell.set_item(item, version, is_main=False, grid_width=1, grid_height=1, pixmap=None)
                        sub_cell.hide()

    def _set_items_advanced(self, items, version, slot_order, img_mgr, d2data):
        item_map = {}
        for item in items:
            if hasattr(item, 'sTypeName'):
                tn = item.sTypeName
                if tn:
                    item_map[tn] = item

        used_slots = set()
        for slot_idx, type_code in enumerate(slot_order):
            col = slot_idx % self._cols
            row = slot_idx // self._cols
            if col >= self._cols or row >= self._rows:
                break

            item = item_map.get(type_code)
            if not item:
                continue

            used_slots.add((col, row))
            type_name = item.sTypeName.decode('ascii', errors='replace').strip() if isinstance(item.sTypeName, bytes) else str(item.sTypeName)

            pixmap = None
            if img_mgr:
                pixmap = img_mgr.get_image_by_code(type_name, (CELL_SIZE - 2, CELL_SIZE - 2))

            cell = self.cells.get((col, row))
            if cell:
                cell.set_item(item, version, is_main=True, grid_width=1, grid_height=1, pixmap=pixmap)
                cell.setGeometry(col * CELL_SIZE, row * CELL_SIZE, CELL_SIZE, CELL_SIZE)
                cell.setAlignment(Qt.AlignCenter)
                cell.raise_()

        placed_codes = set(slot_order)
        for item in items:
            if not hasattr(item, 'sTypeName'):
                continue
            tn = item.sTypeName
            if tn and tn not in placed_codes:
                for row in range(self._rows):
                    for col in range(self._cols):
                        if (col, row) not in used_slots:
                            used_slots.add((col, row))
                            type_name = tn.decode('ascii', errors='replace').strip() if isinstance(tn, bytes) else str(tn)
                            pixmap = None
                            if img_mgr:
                                pixmap = img_mgr.get_image_by_code(type_name, (CELL_SIZE - 2, CELL_SIZE - 2))
                            cell = self.cells.get((col, row))
                            if cell:
                                cell.set_item(item, version, is_main=True, grid_width=1, grid_height=1, pixmap=pixmap)
                                cell.setGeometry(col * CELL_SIZE, row * CELL_SIZE, CELL_SIZE, CELL_SIZE)
                                cell.setAlignment(Qt.AlignCenter)
                                cell.raise_()
                            break
                    else:
                        continue
                    break


ADVANCED_CELL_SIZE = 32


class AdvancedStashCell(QWidget):
    clicked = Signal(object)
    quantity_changed = Signal()

    def __init__(self, type_code, col, row, parent=None):
        super().__init__(parent)
        self._type_code = type_code
        self._col = col
        self._row = row
        self._item = None
        self._version = 0x69
        self._quantity = 0
        self._hovered = False
        self.setFixedSize(ADVANCED_CELL_SIZE, ADVANCED_CELL_SIZE)
        self.setMouseTracking(True)
        self.setContextMenuPolicy(Qt.NoContextMenu)
        self._update_style()

    def _type_code_str(self):
        if isinstance(self._type_code, bytes):
            return self._type_code.decode('ascii', errors='replace').strip()
        return str(self._type_code).strip()

    def _update_style(self):
        if self._item:
            self.setStyleSheet(
                "QWidget { background-color: #1a1a2e; border: 1px solid #3a3a5e; }"
            )
        else:
            self.setStyleSheet(
                "QWidget { background-color: #12121e; border: 1px solid #222238; }"
            )

    def set_item(self, item, version=0x69):
        self._item = item
        self._version = version
        self._quantity = 0
        if item:
            info = getattr(item, 'pItemInfo', None)
            if info and getattr(info, '_bHasAdvancedStashSize', False):
                self._quantity = getattr(info, 'iAdvancedStashStackSize', 0)
            elif info:
                ext = getattr(info, 'pExtItemInfo', None)
                if ext:
                    q = getattr(ext, 'iQuantity', None)
                    if q and hasattr(q, 'exist') and q.exist():
                        self._quantity = q.value
                    elif isinstance(q, int) and q > 0:
                        self._quantity = q
        self._update_style()
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        type_str = self._type_code_str()
        img_mgr = get_image_manager()
        icon_size = ADVANCED_CELL_SIZE - 4

        if self._item:
            pixmap = None
            if img_mgr:
                pixmap = img_mgr.get_image_by_code(type_str, (icon_size, icon_size))
            if pixmap and not pixmap.isNull():
                painter.drawPixmap(2, 2, icon_size, icon_size, pixmap)
            else:
                painter.setPen(QColor("#888899"))
                painter.setFont(self.font())
                painter.drawText(self.rect(), Qt.AlignCenter, type_str[:3])

            if self._quantity > 0:
                painter.setPen(QColor("#ffffff"))
                font = painter.font()
                font.setPixelSize(10)
                font.setBold(True)
                painter.setFont(font)
                text = str(self._quantity)
                fm = painter.fontMetrics()
                tw = fm.horizontalAdvance(text)
                x = ADVANCED_CELL_SIZE - tw - 2
                y = ADVANCED_CELL_SIZE - 2
                painter.fillRect(x - 1, y - 10, tw + 2, 12, QColor(0, 0, 0, 160))
                painter.drawText(x, y, text)
        else:
            pixmap = None
            if img_mgr:
                pixmap = img_mgr.get_image_by_code(type_str, (icon_size, icon_size))
            if pixmap and not pixmap.isNull():
                painter.setOpacity(0.2)
                painter.drawPixmap(2, 2, icon_size, icon_size, pixmap)
                painter.setOpacity(1.0)
            else:
                painter.setPen(QColor("#333344"))
                font = painter.font()
                font.setPixelSize(8)
                painter.setFont(font)
                painter.drawText(self.rect(), Qt.AlignCenter, type_str[:3])

        painter.end()

    def enterEvent(self, event):
        self._hovered = True
        if self._item:
            self.setStyleSheet(
                "QWidget { background-color: #1a1a3e; border: 2px solid #5a5a8e; }"
            )
            try:
                tooltip = _build_stash_tooltip(self._item, self._version)
            except Exception:
                tooltip = ""
            if tooltip:
                pos = self.mapToGlobal(self.rect().bottomRight() + QPoint(1, 1))
                StashTooltip.show_tooltip(pos, tooltip)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self._update_style()
        StashTooltip.hide_tooltip()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._change_quantity(1)
        elif event.button() == Qt.RightButton:
            self._change_quantity(-1)
        super().mousePressEvent(event)

    def _change_quantity(self, delta):
        new_qty = max(0, self._quantity + delta)
        if new_qty == self._quantity:
            return
        self._quantity = new_qty
        if self._item:
            info = getattr(self._item, 'pItemInfo', None)
            if info:
                if new_qty > 0:
                    info.iAdvancedStashStackSize = new_qty
                    info._bHasAdvancedStashSize = True
                else:
                    info.iAdvancedStashStackSize = 0
                    info._bHasAdvancedStashSize = False
        elif new_qty > 0:
            self._create_placeholder_item()
        self._update_style()
        self.update()
        self.quantity_changed.emit()

    def _create_placeholder_item(self):
        from core.item import D2Item, ItemInfo
        item = D2Item()
        item.dwVersion = self._version
        item.bSimple = True
        item.bIdentified = True
        item._flags = 0x00200010
        item.iLocation = 0
        item.iStoredIn = 4
        info = ItemInfo()
        type_name = self._type_code if isinstance(self._type_code, bytes) else self._type_code.encode('ascii')
        info.sTypeName = type_name
        info.iAdvancedStashStackSize = self._quantity
        info._bHasAdvancedStashSize = True
        item.pItemInfo = info
        self._item = item


class AdvancedStashGridWidget(QWidget):
    item_clicked = Signal(object)
    data_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cells = {}
        self._cols = 0
        self._rows = 0
        self._subtype = ADVANCED_SUBTYPE_UNKNOWN
        self._advanced_tab = None
        self._version = 0x69

    def setup(self, subtype, items=None, version=0x69, advanced_tab=None):
        self._subtype = subtype
        self._advanced_tab = advanced_tab
        self._version = version
        for cell in self.cells.values():
            cell.deleteLater()
        self.cells.clear()

        if subtype == ADVANCED_SUBTYPE_GEM:
            slot_order = GEM_SLOT_ORDER
            cols, rows = GEM_LAYOUT
        elif subtype == ADVANCED_SUBTYPE_RUNE:
            slot_order = RUNE_SLOT_ORDER
            cols, rows = RUNE_LAYOUT
        elif subtype == ADVANCED_SUBTYPE_MATERIAL:
            slot_order = MATERIAL_SLOT_ORDER
            cols, rows = MATERIAL_LAYOUT
        else:
            return

        self._cols = cols
        self._rows = rows
        grid_w = cols * ADVANCED_CELL_SIZE
        grid_h = rows * ADVANCED_CELL_SIZE
        self.setFixedSize(grid_w, grid_h)
        self.setStyleSheet("background-color: #0e0e1e;")

        for slot_idx, type_code in enumerate(slot_order):
            col = slot_idx % cols
            row = slot_idx // cols
            if col >= cols or row >= rows:
                break
            cell = AdvancedStashCell(type_code, col, row, self)
            cell.setGeometry(col * ADVANCED_CELL_SIZE, row * ADVANCED_CELL_SIZE,
                             ADVANCED_CELL_SIZE, ADVANCED_CELL_SIZE)
            cell.clicked.connect(self.item_clicked.emit)
            cell.quantity_changed.connect(self._on_cell_quantity_changed)
            self.cells[(col, row)] = cell

        if items:
            self._fill_items(items, version, slot_order)

    def _fill_items(self, items, version, slot_order):
        item_map = {}
        for item in items:
            if hasattr(item, 'sTypeName'):
                tn = item.sTypeName
                if tn:
                    item_map[tn] = item

        for slot_idx, type_code in enumerate(slot_order):
            col = slot_idx % self._cols
            row = slot_idx // self._cols
            if col >= self._cols or row >= self._rows:
                break
            item = item_map.get(type_code)
            cell = self.cells.get((col, row))
            if cell and item:
                cell.set_item(item, version)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setPen(QPen(QColor("#3a3a5e"), 1))
        for col in range(self._cols + 1):
            x = col * ADVANCED_CELL_SIZE
            painter.drawLine(x, 0, x, self.height())
        for row in range(self._rows + 1):
            y = row * ADVANCED_CELL_SIZE
            painter.drawLine(0, y, self.width(), y)
        painter.end()

    def _on_cell_quantity_changed(self):
        if not self._advanced_tab or not self._advanced_tab.Items:
            self.data_changed.emit()
            return

        vitems = self._advanced_tab.Items.vItems
        for cell in self.cells.values():
            item = cell._item
            if item is None:
                continue
            in_list = item in vitems
            if cell._quantity > 0 and not in_list:
                vitems.append(item)
            elif cell._quantity == 0 and in_list:
                vitems.remove(item)

        self._advanced_tab.Items.nItems = len(vitems)
        self.data_changed.emit()

    def clear_items(self):
        for cell in self.cells.values():
            cell._item = None
            cell._quantity = 0
            cell._update_style()
            cell.update()


class _BackupListWidget(QWidget):
    restore_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._save_path = ""
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([tr("File"), tr("Time"), tr("Size")])
        self.tree.header().setStretchLastSection(False)
        self.tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.setStyleSheet(
            "QTreeWidget { background-color: #12121e; color: #aaaacc; border: 1px solid #3a3a5e; font-size: 11px; }"
            "QTreeWidget::item { padding: 2px; }"
            "QTreeWidget::item:selected { background-color: #3a3a5e; color: #ffffff; }"
            "QTreeWidget::item:alternate { background-color: #16162a; }"
            "QHeaderView::section { background-color: #2a2a44; color: #aaaacc; padding: 3px; border: 1px solid #3a3a5e; font-size: 10px; }"
        )
        layout.addWidget(self.tree)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.preview_btn = QPushButton(tr("Preview"))
        self.preview_btn.setFixedSize(60, 22)
        self.preview_btn.setEnabled(False)
        self.preview_btn.setStyleSheet(
            "QPushButton { border: 1px solid #3a3a5e; color: #aaaacc; background: #2a2a44; border-radius: 2px; font-size: 10px; }"
            "QPushButton:hover { color: #ffffff; background: #3a3a5e; }"
            "QPushButton:disabled { color: #555566; background: #1a1a2e; }"
        )
        self.preview_btn.clicked.connect(self._preview)
        btn_layout.addWidget(self.preview_btn)

        self.restore_btn = QPushButton(tr("Restore"))
        self.restore_btn.setFixedSize(60, 22)
        self.restore_btn.setEnabled(False)
        self.restore_btn.setStyleSheet(
            "QPushButton { border: 1px solid #3a3a5e; color: #ffaa44; background: #2a1a0e; border-radius: 2px; font-size: 10px; }"
            "QPushButton:hover { color: #ffffff; background: #3a2a1e; }"
            "QPushButton:disabled { color: #555566; background: #1a1a2e; }"
        )
        self.restore_btn.clicked.connect(self._restore)
        btn_layout.addWidget(self.restore_btn)

        layout.addLayout(btn_layout)

        self.tree.currentItemChanged.connect(self._on_selection_changed)

    def set_save_path(self, path: str):
        self._save_path = path
        self.refresh()

    def refresh(self):
        self.tree.clear()
        if not self._save_path or not os.path.isdir(self._save_path):
            return

        backups = []
        for f in os.listdir(self._save_path):
            if f.lower().endswith('.d2ib'):
                path = os.path.join(self._save_path, f)
                try:
                    stat = os.stat(path)
                    backups.append((f, path, stat.st_mtime, stat.st_size))
                except OSError:
                    continue

        backups.sort(key=lambda x: x[2], reverse=True)

        for name, path, mtime, size in backups:
            dt = datetime.datetime.fromtimestamp(mtime)
            time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
            if size >= 1024 * 1024:
                size_str = f"{size / 1024 / 1024:.1f} MB"
            elif size >= 1024:
                size_str = f"{size / 1024:.1f} KB"
            else:
                size_str = f"{size} B"

            item = QTreeWidgetItem([name, time_str, size_str])
            item.setData(0, Qt.UserRole, path)
            self.tree.addTopLevelItem(item)

    def _on_selection_changed(self, current, previous):
        has_selection = current is not None
        self.preview_btn.setEnabled(has_selection)
        self.restore_btn.setEnabled(has_selection)

    def _get_selected_path(self):
        current = self.tree.currentItem()
        if current:
            return current.data(0, Qt.UserRole)
        return None

    def _preview(self):
        path = self._get_selected_path()
        if not path or not os.path.isfile(path):
            return

        try:
            with open(path, 'rb') as f:
                data = f.read()
            bs = IBitStream(data)
            stash = SharedStash()
            stash.deserialize(bs)

            tab_count = len(stash.tabs)
            total_items = 0
            for tab in stash.tabs:
                if tab.Items:
                    total_items += len(tab.Items.vItems)

            info = tr_format("Backup Preview\n\nTabs: {}\nTotal Items: {}", tab_count, total_items)
            QMessageBox.information(self, tr("Backup Preview"), info)
        except Exception as e:
            QMessageBox.warning(self, tr("Preview Error"), tr_format("Failed to read backup:\n{}", str(e)))

    def _restore(self):
        path = self._get_selected_path()
        if not path or not os.path.isfile(path):
            return

        basename = os.path.basename(path)
        result = QMessageBox.warning(
            self, tr("Restore Backup"),
            tr_format("Replace current stash with backup?\n{}\n\nUnsaved changes will be lost.", basename),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if result != QMessageBox.Yes:
            return

        self.restore_requested.emit(path)


class _StashPageWidget(QWidget):
    item_clicked = Signal(object)
    data_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.stash = None
        self._normal_page = 0
        self._normal_tabs = []
        self._advanced_items = []
        self._advanced_version = 0x69
        self._has_advanced_tab = False
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(2)

        self.normal_nav = QWidget()
        normal_nav_layout = QHBoxLayout(self.normal_nav)
        normal_nav_layout.setContentsMargins(4, 0, 4, 0)
        normal_nav_layout.setSpacing(2)

        self.normal_prev_btn = QPushButton("◀")
        self.normal_prev_btn.setFixedSize(24, 20)
        self.normal_prev_btn.setStyleSheet(
            "QPushButton { border: 1px solid #4a4a6e; color: #aaaacc; background: #2a2a44; border-radius: 2px; }"
            "QPushButton:hover { background: #3a3a5e; color: #ffffff; }"
            "QPushButton:disabled { color: #555566; background: #1a1a2e; }"
        )
        self.normal_prev_btn.clicked.connect(self._prev_normal_page)
        normal_nav_layout.addWidget(self.normal_prev_btn)

        self.normal_page_label = QLabel("0/0")
        self.normal_page_label.setAlignment(Qt.AlignCenter)
        self.normal_page_label.setStyleSheet("color: #ccccdd; font-size: 11px; min-width: 40px;")
        normal_nav_layout.addWidget(self.normal_page_label)

        self.normal_next_btn = QPushButton("▶")
        self.normal_next_btn.setFixedSize(24, 20)
        self.normal_next_btn.setStyleSheet(
            "QPushButton { border: 1px solid #4a4a6e; color: #aaaacc; background: #2a2a44; border-radius: 2px; }"
            "QPushButton:hover { background: #3a3a5e; color: #ffffff; }"
            "QPushButton:disabled { color: #555566; background: #1a1a2e; }"
        )
        self.normal_next_btn.clicked.connect(self._next_normal_page)
        normal_nav_layout.addWidget(self.normal_next_btn)

        normal_nav_layout.addStretch()

        self.gold_label = QLabel(tr_format("Gold: {}", "0"))
        self.gold_label.setStyleSheet("color: #ffcc00; font-size: 10px;")
        normal_nav_layout.addWidget(self.gold_label)

        layout.addWidget(self.normal_nav)

        self.normal_grid = StashGridWidget()
        self.normal_grid.item_clicked.connect(self.item_clicked.emit)
        layout.addWidget(self.normal_grid)

        self._add_separator(layout)

        self.gem_label = QLabel(tr("Gem"))
        self.gem_label.setStyleSheet("color: #8888aa; font-size: 10px; font-weight: bold;")
        layout.addWidget(self.gem_label)

        self.gem_grid = AdvancedStashGridWidget()
        self.gem_grid.item_clicked.connect(self.item_clicked.emit)
        self.gem_grid.data_changed.connect(self.data_changed.emit)
        layout.addWidget(self.gem_grid)

        self.rune_label = QLabel(tr("Rune"))
        self.rune_label.setStyleSheet("color: #8888aa; font-size: 10px; font-weight: bold;")
        layout.addWidget(self.rune_label)

        self.rune_grid = AdvancedStashGridWidget()
        self.rune_grid.item_clicked.connect(self.item_clicked.emit)
        self.rune_grid.data_changed.connect(self.data_changed.emit)
        layout.addWidget(self.rune_grid)

        self.material_label = QLabel(tr("Material"))
        self.material_label.setStyleSheet("color: #8888aa; font-size: 10px; font-weight: bold;")
        layout.addWidget(self.material_label)

        self.material_grid = AdvancedStashGridWidget()
        self.material_grid.item_clicked.connect(self.item_clicked.emit)
        self.material_grid.data_changed.connect(self.data_changed.emit)
        layout.addWidget(self.material_grid)

    def _add_separator(self, layout):
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setStyleSheet("color: #3a3a5e;")
        layout.addWidget(line)

    def load_stash(self, stash):
        self.stash = stash
        self._normal_page = 0
        self._normal_tabs = []
        self._advanced_items = []
        self._advanced_version = 0x69
        self._has_advanced_tab = False

        if not stash:
            self.normal_nav.hide()
            self.normal_grid.hide()
            self.gem_label.hide()
            self.gem_grid.hide()
            self.rune_label.hide()
            self.rune_grid.hide()
            self.material_label.hide()
            self.material_grid.hide()
            self._update_nav()
            return

        self._classify_tabs()

        if self._normal_tabs:
            self.normal_nav.show()
            self.normal_grid.show()
            self._normal_page = 0
            self._show_normal_page(0)
        else:
            self.normal_nav.hide()
            self.normal_grid.hide()

        self._setup_advanced_grids()

    def _classify_tabs(self):
        self._normal_tabs = []
        self._advanced_items = []
        self._advanced_version = 0x69
        self._has_advanced_tab = False
        self._advanced_tab = None
        if not self.stash:
            return
        for i, tab in enumerate(self.stash.tabs):
            if tab.TabType == STASH_TAB_TYPE_ADVANCED:
                self._has_advanced_tab = True
                self._advanced_tab = tab
                items = tab.Items.vItems if tab.Items else []
                self._advanced_items.extend(items)
                self._advanced_version = tab.ItemFormat if tab.ItemFormat else 0x69
            elif tab.TabType == STASH_TAB_TYPE_CHRONICLE:
                pass
            else:
                self._normal_tabs.append(i)

    def _setup_advanced_grids(self):
        gem_items = []
        rune_items = []
        material_items = []
        for item in self._advanced_items:
            tn = getattr(item, 'sTypeName', b'')
            if tn in RUNE_CODES:
                rune_items.append(item)
            elif tn in GEM_CODES:
                gem_items.append(item)
            elif tn in MATERIAL_CODES:
                material_items.append(item)

        version = self._advanced_version

        if self._has_advanced_tab:
            adv_tab = self._advanced_tab
            self.gem_label.show()
            self.gem_grid.show()
            self.gem_grid.setup(ADVANCED_SUBTYPE_GEM, gem_items, version, adv_tab)

            self.rune_label.show()
            self.rune_grid.show()
            self.rune_grid.setup(ADVANCED_SUBTYPE_RUNE, rune_items, version, adv_tab)

            self.material_label.show()
            self.material_grid.show()
            self.material_grid.setup(ADVANCED_SUBTYPE_MATERIAL, material_items, version, adv_tab)
        else:
            self.gem_label.hide()
            self.gem_grid.hide()
            self.rune_label.hide()
            self.rune_grid.hide()
            self.material_label.hide()
            self.material_grid.hide()

    def _show_normal_page(self, page_idx):
        if page_idx < 0 or page_idx >= len(self._normal_tabs):
            self.normal_grid.clear_items()
            return

        tab_idx = self._normal_tabs[page_idx]
        tab = self.stash.get_tab(tab_idx)
        if not tab:
            return

        version = tab.ItemFormat if tab.ItemFormat else 0x69
        items = self.stash.get_tab_items(tab_idx)

        self.normal_grid.setup_grid(NORMAL_LAYOUT[0], NORMAL_LAYOUT[1])
        self.normal_grid.set_items(items, version)
        self.gold_label.setText(tr_format("Gold: {}", f"{tab.Gold:,}"))
        self._update_nav()

    def _prev_normal_page(self):
        if self._normal_page > 0:
            self._normal_page -= 1
            self._show_normal_page(self._normal_page)

    def _next_normal_page(self):
        if self._normal_page < len(self._normal_tabs) - 1:
            self._normal_page += 1
            self._show_normal_page(self._normal_page)

    def _update_nav(self):
        normal_total = len(self._normal_tabs)
        normal_current = self._normal_page + 1 if normal_total > 0 else 0
        self.normal_page_label.setText(f"{normal_current}/{normal_total}")
        self.normal_prev_btn.setEnabled(self._normal_page > 0)
        self.normal_next_btn.setEnabled(self._normal_page < normal_total - 1)


class SharedStashWidget(QWidget):
    stash_loaded = Signal()
    data_changed = Signal()
    item_clicked = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._modern_stash = None
        self._classic_stash = None
        self._save_path = ""
        self._modified = False
        self._load_errors = []
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(4, 2, 4, 2)
        header_layout.setSpacing(4)

        header_label = QLabel(tr("Shared Stash"))
        header_label.setStyleSheet("font-weight: bold; font-size: 12px; color: #ccccdd;")
        header_layout.addWidget(header_label)

        header_layout.addStretch()

        self.save_btn = QPushButton("S")
        self.save_btn.setFixedSize(20, 20)
        self.save_btn.setToolTip(tr("Save Stash"))
        self.save_btn.setEnabled(False)
        self.save_btn.setStyleSheet(
            "QPushButton { border: 1px solid #3d3d54; color: #555566; background: #1a1a2e; border-radius: 2px; font-size: 11px; font-weight: bold; }"
        )
        self.save_btn.clicked.connect(self._save_stash)
        header_layout.addWidget(self.save_btn)

        self.refresh_btn = QPushButton("↻")
        self.refresh_btn.setFixedSize(20, 20)
        self.refresh_btn.setToolTip(tr("Reload Stash"))
        self.refresh_btn.setStyleSheet(
            "QPushButton { border: none; color: #aaaacc; font-size: 14px; }"
            "QPushButton:hover { color: #ffffff; }"
        )
        self.refresh_btn.clicked.connect(self._reload_stash)
        header_layout.addWidget(self.refresh_btn)

        layout.addWidget(header)

        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet(
            "QTabWidget::pane { border: 1px solid #3a3a5e; background: #1a1a2e; }"
            "QTabBar::tab { background: #2a2a44; color: #aaaacc; padding: 3px 8px; border: 1px solid #3a3a5e; font-size: 10px; }"
            "QTabBar::tab:selected { background: #3a3a5e; color: #ffffff; }"
            "QTabBar::tab:hover { background: #3a3a5e; }"
        )

        self.modern_page = _StashPageWidget()
        self.modern_page.item_clicked.connect(self.item_clicked.emit)
        self.modern_page.data_changed.connect(self._on_data_changed)
        self.tab_widget.addTab(self.modern_page, tr("Modern"))

        self.classic_page = _StashPageWidget()
        self.classic_page.item_clicked.connect(self.item_clicked.emit)
        self.classic_page.data_changed.connect(self._on_data_changed)
        self.tab_widget.addTab(self.classic_page, tr("Classic"))

        self.backup_page = _BackupListWidget()
        self.backup_page.restore_requested.connect(self._restore_backup)
        self.tab_widget.addTab(self.backup_page, tr("Backups"))

        layout.addWidget(self.tab_widget)

        self.no_stash_label = QLabel(tr("No shared stash\nSet save folder to auto-load"))
        self.no_stash_label.setAlignment(Qt.AlignCenter)
        self.no_stash_label.setStyleSheet("color: #555566; font-size: 11px; padding: 20px;")
        layout.addWidget(self.no_stash_label)
        self.no_stash_label.hide()

        grid_width = CELL_SIZE * NORMAL_LAYOUT[0] + 4
        self.setMinimumWidth(grid_width + 8)
        self.setMaximumWidth(grid_width + 8)

    def _on_data_changed(self):
        self._modified = True
        self._update_save_btn_style()
        self.data_changed.emit()

    @property
    def stash(self):
        current = self.tab_widget.currentWidget()
        if current and isinstance(current, _StashPageWidget):
            return current.stash
        return self._modern_stash or self._classic_stash

    def set_save_path(self, path: str):
        self._save_path = path
        self._load_stash()

    def _load_stash(self):
        self._modern_stash = None
        self._classic_stash = None
        self._modified = False
        self._load_errors = []

        modern_file, classic_file = self._find_stash_files()

        if modern_file:
            try:
                self._modern_stash = self._load_stash_file(modern_file)
            except Exception as e:
                import logging
                logging.error(f"Failed to load modern stash: {e}", exc_info=True)
                self._load_errors.append(("Modern", modern_file, str(e)))

        if classic_file:
            try:
                self._classic_stash = self._load_stash_file(classic_file)
            except Exception as e:
                import logging
                logging.error(f"Failed to load classic stash: {e}", exc_info=True)
                self._load_errors.append(("Classic", classic_file, str(e)))

        has_any = self._modern_stash is not None or self._classic_stash is not None
        has_backups = False

        self.backup_page.set_save_path(self._save_path)
        has_backups = self.backup_page.tree.topLevelItemCount() > 0

        if has_any or has_backups:
            self.no_stash_label.hide()
            self.tab_widget.show()
        else:
            self.no_stash_label.show()
            self.tab_widget.hide()

        self.modern_page.load_stash(self._modern_stash)
        self.classic_page.load_stash(self._classic_stash)

        self.tab_widget.setTabVisible(0, self._modern_stash is not None)
        self.tab_widget.setTabVisible(1, self._classic_stash is not None)
        self.tab_widget.setTabVisible(2, has_backups or bool(self._load_errors))

        if self._load_errors:
            self.tab_widget.setCurrentIndex(2)
        elif self._modern_stash:
            self.tab_widget.setCurrentIndex(0)
        elif self._classic_stash:
            self.tab_widget.setCurrentIndex(0)
        elif has_backups:
            self.tab_widget.setCurrentIndex(2)

        self._update_save_btn_style()
        self.stash_loaded.emit()

    def _load_stash_file(self, file_path):
        with open(file_path, 'rb') as f:
            data = f.read()
        bs = IBitStream(data)
        stash = SharedStash()
        stash.deserialize(bs)
        stash.file_path = file_path
        return stash

    def _find_stash_files(self):
        if not self._save_path or not os.path.isdir(self._save_path):
            return None, None

        modern_candidates = [
            "ModernSharedStashSoftCoreV2.d2i",
            "ModernSharedStashHardCoreV2.d2i",
        ]
        classic_candidates = [
            "SharedStashSoftCoreV2.d2i",
            "SharedStashHardCoreV2.d2i",
        ]

        modern_file = None
        classic_file = None

        for name in modern_candidates:
            path = os.path.join(self._save_path, name)
            if os.path.isfile(path):
                modern_file = path
                break

        for name in classic_candidates:
            path = os.path.join(self._save_path, name)
            if os.path.isfile(path):
                classic_file = path
                break

        if not modern_file or not classic_file:
            for f in os.listdir(self._save_path):
                fl = f.lower()
                path = os.path.join(self._save_path, f)
                if not fl.endswith(".d2i"):
                    continue
                if fl.startswith("modernsharedstash") and not modern_file:
                    modern_file = path
                elif fl.startswith("sharedstash") and not classic_file:
                    classic_file = path

        return modern_file, classic_file

    def _reload_stash(self):
        self._load_stash()

    def _restore_backup(self, backup_path):
        if not backup_path or not os.path.isfile(backup_path):
            return

        basename = os.path.basename(backup_path).lower()
        is_modern = 'modern' in basename

        target_stash = self._modern_stash if is_modern else self._classic_stash
        if target_stash:
            target_path = getattr(target_stash, 'file_path', '')
        else:
            modern_file, classic_file = self._find_stash_files()
            target_path = modern_file if is_modern else classic_file

        if not target_path:
            QMessageBox.warning(self, tr("Error"), tr("Cannot determine target stash file"))
            return

        import shutil
        try:
            shutil.copy2(backup_path, target_path)
        except Exception as e:
            QMessageBox.critical(self, tr("Error"), tr_format("Failed to restore backup:\n{}", str(e)))
            return

        self._load_stash()

    def _save_stash(self):
        stashes = []
        if self._modern_stash:
            stashes.append(self._modern_stash)
        if self._classic_stash:
            stashes.append(self._classic_stash)

        if not stashes:
            return

        for stash in stashes:
            file_path = getattr(stash, 'file_path', '')
            if not file_path or not os.path.exists(file_path):
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(self, tr("Error"), tr("Stash file path not found"))
                return

            incomplete = self._check_parse_incomplete(stash)
            if incomplete:
                from PySide6.QtWidgets import QMessageBox
                msg = tr_format(
                    "Some items could not be parsed correctly ({} tabs affected in {}).\n"
                    "Saving now may lose those items.\n\nSave anyway?",
                    len(incomplete), os.path.basename(file_path)
                )
                result = QMessageBox.warning(
                    self, tr("Warning"), msg,
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No
                )
                if result != QMessageBox.Yes:
                    return

        for stash in stashes:
            file_path = getattr(stash, 'file_path', '')
            self._create_backup(file_path)

            try:
                from core.obitstream import OBitStream
                bs = OBitStream()
                stash.serialize(bs)
                data = bs.get_data()

                with open(file_path, 'wb') as f:
                    f.write(data)
            except Exception as e:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.critical(self, tr("Error"), tr_format("Failed to save stash:\n{}", str(e)))
                return

        self._modified = False
        self._update_save_btn_style()

        self.save_btn.setStyleSheet(
            "QPushButton { border: 1px solid #88cc88; color: #88cc88; background: #0e2a1a; border-radius: 2px; font-size: 11px; font-weight: bold; }"
            "QPushButton:hover { color: #ffffff; background: #1e3a2a; }"
        )
        from PySide6.QtCore import QTimer
        QTimer.singleShot(2000, lambda: self._update_save_btn_style())

    def _check_parse_incomplete(self, stash):
        incomplete = []
        if not stash:
            return incomplete
        for i, tab in enumerate(stash.tabs):
            if tab.Items and tab.Items.nItems != len(tab.Items.vItems):
                incomplete.append((i, tab.Items.nItems, len(tab.Items.vItems)))
        return incomplete

    def _create_backup(self, file_path):
        if not file_path or not os.path.exists(file_path):
            return
        import stat
        base, ext = os.path.splitext(file_path)
        for i in range(7, 0, -1):
            src = f"{base}.{i}.d2ib"
            dst = f"{base}.{i + 1}.d2ib"
            if os.path.exists(src):
                try:
                    if os.path.exists(dst):
                        os.chmod(dst, stat.S_IWRITE | stat.S_IREAD)
                    os.rename(src, dst)
                except OSError:
                    try:
                        if os.path.exists(src):
                            os.chmod(src, stat.S_IWRITE | stat.S_IREAD)
                            os.remove(src)
                    except OSError:
                        pass
        backup_path = f"{base}.1.d2ib"
        try:
            import shutil
            shutil.copy2(file_path, backup_path)
        except OSError:
            pass

    def mark_modified(self):
        self._modified = True
        self._update_save_btn_style()
        self.data_changed.emit()

    def _update_save_btn_style(self):
        if self._modified:
            self.save_btn.setEnabled(True)
            self.save_btn.setStyleSheet(
                "QPushButton { border: 1px solid #ffaa44; color: #ffaa44; background: #2a1a0e; border-radius: 2px; font-size: 11px; font-weight: bold; }"
                "QPushButton:hover { color: #ffffff; background: #3a2a1e; }"
            )
        else:
            self.save_btn.setEnabled(False)
            self.save_btn.setStyleSheet(
                "QPushButton { border: 1px solid #3d3d54; color: #555566; background: #1a1a2e; border-radius: 2px; font-size: 11px; font-weight: bold; }"
            )
