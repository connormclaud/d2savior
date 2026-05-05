from PySide6.QtWidgets import (
    QMdiSubWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QStatusBar, QMessageBox, QSizeGrip, QTreeWidget,
    QTreeWidgetItem, QHeaderView, QPushButton
)
from PySide6.QtCore import Signal, Qt

import os
import datetime

from core.d2s_struct import D2SStruct
from core.ibitstream import IBitStream
from gui.gui_translator import tr, tr_format
from gui.widgets.char_info_widget import CharInfoWidget
from gui.widgets.items_widget import ItemsWidget
from gui.widgets.quests_widget import QuestsWidget
from gui.widgets.waypoints_widget import WaypointsWidget
from gui.widgets.mercenary_widget import MercenaryWidget
from gui.models import CharDocument


class CharDocumentWindow(QMdiSubWindow):
    item_clicked = Signal(object)
    document_modified = Signal(int)
    item_dropped = Signal(object, int, int, int, int, int)
    
    def __init__(self, document: CharDocument, parent=None):
        super().__init__(parent)
        self._document = document
        self._init_ui()
        self._update_title()
    
    def _init_ui(self):
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        
        self.setFixedSize(780, 525)
        
        central_widget = QWidget()
        self.setWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(5, 5, 5, 5)
        
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        self.char_info_widget = CharInfoWidget()
        self.char_info_widget.data_changed.connect(self._on_data_changed)
        self.tab_widget.addTab(self.char_info_widget, tr("Character Info"))
        
        self.items_widget = ItemsWidget()
        self.items_widget.item_clicked.connect(self._on_item_clicked)
        self.items_widget.item_dropped.connect(self._on_item_dropped)
        self.tab_widget.addTab(self.items_widget, tr("Items"))
        
        self.quests_widget = QuestsWidget()
        self.tab_widget.addTab(self.quests_widget, tr("Quests"))
        
        self.waypoints_widget = WaypointsWidget()
        self.waypoints_widget.data_changed.connect(self._on_data_changed)
        self.tab_widget.addTab(self.waypoints_widget, tr("Waypoints"))
        
        self.mercenary_widget = MercenaryWidget()
        self.mercenary_widget.item_clicked.connect(self._on_item_clicked)
        self.tab_widget.addTab(self.mercenary_widget, tr("Mercenary"))

        self.backup_widget = _CharBackupWidget()
        self.backup_widget.restore_requested.connect(self._restore_char_backup)
        self.tab_widget.addTab(self.backup_widget, tr("Backups"))
        self.tab_widget.setTabVisible(5, False)

        if self._document.data:
            self.items_widget.set_document_id(self._document.window_id)
            self._update_ui()
            self._refresh_backups()
    
    @property
    def document(self) -> CharDocument:
        return self._document
    
    @property
    def doc_id(self) -> int:
        return self._document.window_id
    
    def _update_title(self):
        self.setWindowTitle(self._document.display_name)
    
    def _update_ui(self):
        if self._document.data:
            self.tab_widget.setTabText(0, tr("Character Info"))
            self.tab_widget.setTabText(1, tr("Items"))
            self.tab_widget.setTabText(2, tr("Quests"))
            self.tab_widget.setTabText(3, tr("Waypoints"))
            self.tab_widget.setTabText(4, tr("Mercenary"))
            self.char_info_widget.refresh_ui_texts()
            self.char_info_widget.update_data(self._document.data)
            self.items_widget.update_data(self._document.data)
            self.quests_widget.update_data(self._document.data)
            self.waypoints_widget.update_data(self._document.data)
            self.mercenary_widget.refresh_ui_texts()
            self.mercenary_widget.update_data(self._document.data)
    
    def _on_item_clicked(self, item):
        self.item_clicked.emit(item)
    
    def _on_item_dropped(self, drag_data, target_stored_in, target_col, target_row, target_position):
        self.item_dropped.emit(drag_data, target_stored_in, target_col, target_row, target_position, self._document.window_id)
    
    def _on_data_changed(self):
        self.mark_modified()
    
    def mark_modified(self):
        if not self._document.modified:
            self._document.mark_modified()
            self._update_title()
            self.document_modified.emit(self.doc_id)
    
    def mark_saved(self):
        self._document.mark_saved()
        self._update_title()
    
    def can_close(self) -> bool:
        if self._document.modified:
            reply = QMessageBox.question(
                self,
                tr("Unsaved Changes"),
                tr_format("Character '{}' has unsaved changes.\nDo you want to save?", self._document.char_name),
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel
            )
            
            if reply == QMessageBox.Cancel:
                return False
            elif reply == QMessageBox.Save:
                return self._request_save()
        
        return True
    
    def _request_save(self) -> bool:
        from gui.main_window import MainWindow
        widget = self
        while widget:
            widget = widget.parent()
            if isinstance(widget, MainWindow):
                return widget.save_document(self._document)
        return False
    
    def closeEvent(self, event):
        if self.can_close():
            self._cleanup()
            event.accept()
        else:
            event.ignore()

    def _cleanup(self):
        from gui.main_window import MainWindow
        widget = self
        while widget:
            widget = widget.parent()
            if isinstance(widget, MainWindow):
                widget.on_char_window_closed(self)
                break

    def _refresh_backups(self):
        file_path = self._document.file_path
        if not file_path:
            return
        self.backup_widget.refresh(file_path)
        has_backups = self.backup_widget.tree.topLevelItemCount() > 0
        self.tab_widget.setTabVisible(5, has_backups)

    def _restore_char_backup(self, backup_path):
        if not backup_path or not os.path.isfile(backup_path):
            return

        file_path = self._document.file_path
        if not file_path:
            return

        result = QMessageBox.warning(
            self, tr("Restore Backup"),
            tr_format("Replace current character with backup?\n{}\n\nUnsaved changes will be lost.", os.path.basename(backup_path)),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if result != QMessageBox.Yes:
            return

        import shutil
        try:
            shutil.copy2(backup_path, file_path)
        except Exception as e:
            QMessageBox.critical(self, tr("Error"), tr_format("Failed to restore backup:\n{}", str(e)))
            return

        with open(file_path, 'rb') as f:
            data = f.read()

        try:
            bs = IBitStream(data)
            char_data = D2SStruct()
            char_data.deserialize(bs)
            self._document.data = char_data
            self._update_ui()
            self._refresh_backups()
            self.mark_modified()
            self.statusBar().showMessage(tr_format("Restored from: {}", os.path.basename(backup_path)), 3000)
        except Exception as e:
            QMessageBox.critical(self, tr("Error"), tr_format("Failed to load restored file:\n{}", str(e)))


class _CharBackupWidget(QWidget):
    restore_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._file_path = ""
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

    def refresh(self, file_path):
        self._file_path = file_path
        self.tree.clear()
        if not file_path:
            return

        base, ext = os.path.splitext(file_path)
        backups = []
        for i in range(1, 8):
            backup_path = f"{base}.{i}.d2sb"
            if os.path.isfile(backup_path):
                try:
                    stat = os.stat(backup_path)
                    backups.append((i, backup_path, stat.st_mtime, stat.st_size))
                except OSError:
                    continue

        backups.sort(key=lambda x: x[2], reverse=True)

        for idx, path, mtime, size in backups:
            dt = datetime.datetime.fromtimestamp(mtime)
            time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
            if size >= 1024 * 1024:
                size_str = f"{size / 1024 / 1024:.1f} MB"
            elif size >= 1024:
                size_str = f"{size / 1024:.1f} KB"
            else:
                size_str = f"{size} B"

            item = QTreeWidgetItem([os.path.basename(path), time_str, size_str])
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
            char_data = D2SStruct()
            char_data.deserialize(bs)

            name = char_data.charTitle if hasattr(char_data, 'charTitle') else '?'
            level = char_data.nLevel if hasattr(char_data, 'nLevel') else '?'
            cls = char_data.cClass if hasattr(char_data, 'cClass') else '?'

            info = tr_format("Backup Preview\n\nName: {}\nClass: {}\nLevel: {}", name, cls, level)
            QMessageBox.information(self, tr("Backup Preview"), info)
        except Exception as e:
            QMessageBox.warning(self, tr("Preview Error"), tr_format("Failed to read backup:\n{}", str(e)))

    def _restore(self):
        path = self._get_selected_path()
        if not path or not os.path.isfile(path):
            return

        self.restore_requested.emit(path)
