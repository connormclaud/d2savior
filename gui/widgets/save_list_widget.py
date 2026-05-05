import os

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QLabel, QPushButton, QFileDialog, QToolBar
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon, QFont

from gui.gui_translator import tr


CLASS_ICONS = {
    0: "⚔",
    1: "✦",
    2: "☠",
    3: "✝",
    4: "🪓",
    5: "🌿",
    6: "🗡",
    7: "🔮",
}

CLASS_NAMES = {
    0: "Amazon",
    1: "Sorceress",
    2: "Necromancer",
    3: "Paladin",
    4: "Barbarian",
    5: "Druid",
    6: "Assassin",
    7: "Warlock",
}


def _tr_class(class_id):
    return tr(CLASS_NAMES.get(class_id, "???"))


class SaveListWidget(QWidget):
    character_double_clicked = Signal(str)
    save_path_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._save_path = ""
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(6, 4, 6, 4)
        header_layout.setSpacing(4)

        header_label = QLabel(tr("Characters"))
        header_label.setStyleSheet("font-weight: bold; font-size: 13px; color: #ccccdd;")
        header_layout.addWidget(header_label)

        header_layout.addStretch()

        refresh_btn = QPushButton("↻")
        refresh_btn.setFixedSize(24, 24)
        refresh_btn.setToolTip(tr("Refresh"))
        refresh_btn.setStyleSheet(
            "QPushButton { border: none; color: #aaaacc; font-size: 16px; }"
            "QPushButton:hover { color: #ffffff; }"
        )
        refresh_btn.clicked.connect(self.refresh)
        header_layout.addWidget(refresh_btn)

        folder_btn = QPushButton("📁")
        folder_btn.setFixedSize(24, 24)
        folder_btn.setToolTip(tr("Set Save Folder"))
        folder_btn.setStyleSheet(
            "QPushButton { border: none; color: #aaaacc; font-size: 14px; }"
            "QPushButton:hover { color: #ffffff; }"
        )
        folder_btn.clicked.connect(self._choose_save_path)
        header_layout.addWidget(folder_btn)

        layout.addWidget(header)

        self.path_label = QLabel(tr("No save folder set"))
        self.path_label.setWordWrap(True)
        self.path_label.setStyleSheet(
            "color: #888899; font-size: 11px; padding: 2px 6px 4px 6px;"
        )
        layout.addWidget(self.path_label)

        self.char_list = QListWidget()
        self.char_list.setStyleSheet(
            "QListWidget { background-color: #1e1e32; border: none; color: #ccccdd; font-size: 12px; }"
            "QListWidget::item { padding: 5px 8px; border-bottom: 1px solid #2a2a44; }"
            "QListWidget::item:selected { background-color: #3a3a5e; }"
            "QListWidget::item:hover { background-color: #2e2e4a; }"
        )
        self.char_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.char_list)

        self.setFixedWidth(200)

    @property
    def save_path(self):
        return self._save_path

    def set_save_path(self, path: str):
        self._save_path = path
        if path and os.path.isdir(path):
            display = path
            if len(display) > 35:
                display = "..." + display[-32:]
            self.path_label.setText(display)
            self.path_label.setToolTip(path)
        else:
            self.path_label.setText(tr("No save folder set"))
            self.path_label.setToolTip("")
        self.refresh()

    def refresh(self):
        self.char_list.clear()

        if not self._save_path or not os.path.isdir(self._save_path):
            item = QListWidgetItem(tr("(No save folder)"))
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
            item.setForeground(Qt.gray)
            self.char_list.addItem(item)
            return

        d2s_files = []
        for f in sorted(os.listdir(self._save_path)):
            if f.lower().endswith('.d2s'):
                d2s_files.append(f)

        if not d2s_files:
            item = QListWidgetItem(tr("(No characters found)"))
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
            item.setForeground(Qt.gray)
            self.char_list.addItem(item)
            return

        for f in d2s_files:
            full_path = os.path.join(self._save_path, f)
            char_name = os.path.splitext(f)[0]

            info = self._read_char_basic(full_path)

            if info:
                icon_char = CLASS_ICONS.get(info['class'], "·")
                class_name = _tr_class(info['class'])
                level = info['level']
                display = f"{icon_char} {char_name}"
                item = QListWidgetItem(display)
                item.setData(Qt.UserRole, full_path)
                item.setToolTip(f"{class_name} Lv.{level}\n{full_path}")
            else:
                display = f"· {char_name}"
                item = QListWidgetItem(display)
                item.setData(Qt.UserRole, full_path)
                item.setToolTip(full_path)

            self.char_list.addItem(item)

    def _read_char_basic(self, file_path: str) -> dict:
        try:
            with open(file_path, 'rb') as f:
                data = f.read()
            if len(data) < 40:
                return None

            magic = data[0:4]
            if magic != b'\x55\xaa\x55\xaa':
                return None

            version = int.from_bytes(data[4:8], 'little')

            name_bytes = data[8:24]
            try:
                name = name_bytes.split(b'\x00')[0].decode('ascii', errors='replace')
            except Exception:
                name = ""

            char_class = 0xFF
            char_level = 0

            if version == 0x63:
                if len(data) > 40:
                    char_class = data[40]
                if len(data) > 43:
                    char_level = data[43]
            elif version == 0x69:
                if len(data) > 40:
                    char_class = data[40]
                if len(data) > 43:
                    char_level = data[43]

            return {
                'name': name,
                'class': char_class,
                'level': char_level,
                'version': version,
            }
        except Exception:
            return None

    def _on_item_double_clicked(self, item: QListWidgetItem):
        file_path = item.data(Qt.UserRole)
        if file_path and os.path.isfile(file_path):
            self.character_double_clicked.emit(file_path)

    def _choose_save_path(self):
        current = self._save_path if self._save_path and os.path.isdir(self._save_path) else ""
        path = QFileDialog.getExistingDirectory(
            self,
            tr("Select Diablo II Save Folder"),
            current,
        )
        if path:
            self.set_save_path(path)
            self.save_path_changed.emit(path)
