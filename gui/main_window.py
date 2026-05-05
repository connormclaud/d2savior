#!/usr/bin/env python3
import sys
import os
import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app_path import resource_path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QMenuBar, QMenu, QFileDialog, QMessageBox, QStatusBar, QMdiArea,
    QMdiSubWindow, QSplitter, QToolBar
)
from PySide6.QtCore import Qt, QSettings, Signal, QSize
from PySide6.QtGui import QAction, QIcon

from core.d2s_struct import D2SStruct
from core.ibitstream import IBitStream
from core.d2data import init_d2data, get_d2data_manager
from core.localized_data import init_localized_data, get_localized_data, set_language
from core.property import init_item_modifiers

from gui.gui_translator import tr, tr_format, init_gui_translator, get_gui_translator, GuiTranslator
from gui.models import DocumentManager, CharDocument, DocumentType, ItemDocument
from gui.widgets.char_document_window import CharDocumentWindow
from gui.widgets.save_list_widget import SaveListWidget
from gui.widgets.shared_stash_widget import SharedStashWidget


class MainWindow(QMainWindow):
    MAX_RECENT_FILES = 10

    def __init__(self):
        super().__init__()
        
        self._doc_manager = DocumentManager.instance()
        self._doc_windows = {}
        self._recent_files = []
        self._recent_actions = []
        self._menu_actions = {}
        
        self._init_gui_language()
        self._init_data()
        self._load_recent_files()
        self._init_ui()
        self._init_toolbar()
        self._init_menu()
        self._setup_callbacks()
        self._update_ui_state()
    
    def _init_gui_language(self):
        settings = QSettings("D2Savior", "D2Savior")
        saved_lang = settings.value("gui_language", "")
        if saved_lang:
            lang = saved_lang
        else:
            lang = GuiTranslator.detect_system_language()
        init_gui_translator(lang)
    
    def _init_data(self):
        data_dir = resource_path("data")
        
        gui_lang = get_gui_translator().current_lang
        data_lang = gui_lang if gui_lang in ('enUS', 'zhCN') else 'enUS'
        
        if os.path.exists(data_dir):
            init_d2data(data_dir)
            
            local_data_dir = os.path.join(data_dir, "local")
            if os.path.exists(local_data_dir):
                init_localized_data(local_data_dir, lang_key=data_lang)
                
                item_modifiers_file = os.path.join(local_data_dir, "item-modifiers.json")
                if os.path.exists(item_modifiers_file):
                    init_item_modifiers(item_modifiers_file, lang_key=data_lang)
                
                string_file = os.path.join(local_data_dir, "string.txt")
                if os.path.exists(string_file):
                    from core.property import init_language
                    lang_index = 1 if data_lang == 'enUS' else 0
                    init_language(string_file, lang_index=lang_index)
        
        image_dir = resource_path(os.path.join('gui', 'resources', 'images', 'Pictcures'))
        if os.path.exists(image_dir):
            from gui.image_manager import init_image_manager
            init_image_manager(image_dir)
    
    def _init_ui(self):
        self.setWindowTitle(tr("D2Savior - Diablo II Character Editor"))
        self.setGeometry(100, 100, 1400, 900)
        
        self.mdi_area = QMdiArea()
        self.mdi_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.mdi_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.mdi_area.setBackground(Qt.darkGray)
        self.mdi_area.subWindowActivated.connect(self._on_sub_window_activated)
        
        self.save_list = SaveListWidget()
        self.save_list.character_double_clicked.connect(self._on_save_list_double_clicked)
        self.save_list.save_path_changed.connect(self._on_save_path_changed)
        
        self.shared_stash = SharedStashWidget()
        self.shared_stash.item_clicked.connect(self._on_item_clicked)
        
        self._splitter = QSplitter(Qt.Horizontal)
        self._splitter.addWidget(self.save_list)
        self._splitter.addWidget(self.mdi_area)
        self._splitter.addWidget(self.shared_stash)
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setStretchFactor(2, 0)
        self._splitter.setSizes([200, 800, 300])
        
        self.setCentralWidget(self._splitter)
        
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage(tr("Ready"))
        
        self._load_save_path()
    
    def _init_toolbar(self):
        self._toolbar = QToolBar(tr("Toolbar"))
        self._toolbar.setMovable(False)
        self._toolbar.setIconSize(QSize(20, 20))
        self._toolbar.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self.addToolBar(self._toolbar)
        
        icons_dir = resource_path(os.path.join('gui', 'resources', 'icons'))
        
        def _icon(name):
            path = os.path.join(icons_dir, name)
            if os.path.exists(path):
                return QIcon(path)
            return QIcon()
        
        open_char_action = QAction(_icon("open-character.svg"), tr("Open Character..."), self)
        open_char_action.setToolTip(tr("Open Character...") + " (Ctrl+O)")
        open_char_action.triggered.connect(self.open_character_file)
        self._toolbar.addAction(open_char_action)
        self._toolbar_actions = {'open_char': open_char_action}
        
        open_item_action = QAction(_icon("open-item.svg"), tr("Open Item..."), self)
        open_item_action.setToolTip(tr("Open Item...") + " (Ctrl+Shift+O)")
        open_item_action.triggered.connect(self.open_item_file)
        open_item_action.setEnabled(False)
        self._toolbar.addAction(open_item_action)
        self._toolbar_actions['open_item'] = open_item_action
        
        self._toolbar.addSeparator()
        
        save_action = QAction(_icon("save.svg"), tr("Save"), self)
        save_action.setToolTip(tr("Save") + " (Ctrl+S)")
        save_action.triggered.connect(self.save_current_document)
        save_action.setEnabled(False)
        self._toolbar.addAction(save_action)
        self._toolbar_actions['save'] = save_action
        
        self._toolbar.addSeparator()
        
        toggle_list_action = QAction(_icon("save-list.svg"), tr("Character List"), self)
        toggle_list_action.setToolTip(tr("Toggle Character List"))
        toggle_list_action.setCheckable(True)
        toggle_list_action.setChecked(True)
        toggle_list_action.triggered.connect(self._toggle_char_list)
        self._toolbar.addAction(toggle_list_action)
        self._toolbar_actions['char_list'] = toggle_list_action
        
        toggle_stash_action = QAction(_icon("shared-stash.svg"), tr("Shared Stash"), self)
        toggle_stash_action.setToolTip(tr("Toggle Shared Stash"))
        toggle_stash_action.setCheckable(True)
        toggle_stash_action.setChecked(True)
        toggle_stash_action.triggered.connect(self._toggle_shared_stash)
        self._toolbar.addAction(toggle_stash_action)
        self._toolbar_actions['shared_stash'] = toggle_stash_action
    
    def _setup_callbacks(self):
        self._doc_manager.set_callbacks(
            on_document_added=self._on_document_added,
            on_document_removed=self._on_document_removed,
            on_active_changed=self._on_active_changed
        )
    
    def _init_menu(self):
        menubar = self.menuBar()
        
        file_menu = menubar.addMenu(tr("File"))
        
        open_action = QAction(tr("Open Character..."), self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_character_file)
        file_menu.addAction(open_action)
        self._menu_actions['open_char'] = open_action
        
        open_item_action = QAction(tr("Open Item..."), self)
        open_item_action.setShortcut("Ctrl+Shift+O")
        open_item_action.triggered.connect(self.open_item_file)
        open_item_action.setEnabled(False)
        self.open_item_action = open_item_action
        file_menu.addAction(open_item_action)
        self._menu_actions['open_item'] = open_item_action
        
        file_menu.addSeparator()
        
        save_action = QAction(tr("Save"), self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_current_document)
        save_action.setEnabled(False)
        self.save_action = save_action
        file_menu.addAction(save_action)
        self._menu_actions['save'] = save_action
        
        save_as_action = QAction(tr("Save As..."), self)
        save_as_action.setShortcut("Ctrl+Shift+S")
        save_as_action.triggered.connect(self.save_current_document_as)
        save_as_action.setEnabled(False)
        self.save_as_action = save_as_action
        file_menu.addAction(save_as_action)
        self._menu_actions['save_as'] = save_as_action
        
        save_all_action = QAction(tr("Save All"), self)
        save_all_action.setShortcut("Ctrl+Alt+S")
        save_all_action.triggered.connect(self.save_all_documents)
        save_all_action.setEnabled(False)
        self.save_all_action = save_all_action
        file_menu.addAction(save_all_action)
        self._menu_actions['save_all'] = save_all_action
        
        file_menu.addSeparator()
        
        self._recent_menu = file_menu.addMenu(tr("Recent Files"))
        self._menu_actions['recent_menu'] = self._recent_menu
        self._update_recent_menu()
        
        file_menu.addSeparator()
        
        close_action = QAction(tr("Close"), self)
        close_action.setShortcut("Ctrl+W")
        close_action.triggered.connect(self.close_current_document)
        close_action.setEnabled(False)
        self.close_action = close_action
        file_menu.addAction(close_action)
        self._menu_actions['close'] = close_action
        
        exit_action = QAction(tr("Exit"), self)
        exit_action.setShortcut("Alt+F4")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        self._menu_actions['exit'] = exit_action
        
        self._menu_actions['file_menu'] = file_menu
        
        view_menu = menubar.addMenu(tr("View"))
        
        lang_menu = view_menu.addMenu(tr("Language"))
        self._lang_actions = {}
        self._menu_actions['lang_menu'] = lang_menu
        
        lang_map = {"enUS": tr("English"), "zhCN": tr("Simplified Chinese")}
        current_lang = get_gui_translator().current_lang
        for lang_key, lang_name in lang_map.items():
            action = QAction(lang_name, self)
            action.setCheckable(True)
            action.setChecked(lang_key == current_lang)
            action.triggered.connect(lambda checked, k=lang_key: self._change_language(k))
            lang_menu.addAction(action)
            self._lang_actions[lang_key] = action
        
        view_menu.addSeparator()
        
        toggle_toolbar_action = QAction(tr("Toolbar"), self)
        toggle_toolbar_action.setCheckable(True)
        toggle_toolbar_action.setChecked(True)
        toggle_toolbar_action.triggered.connect(self._toggle_toolbar)
        view_menu.addAction(toggle_toolbar_action)
        self.toggle_toolbar_action = toggle_toolbar_action
        self._menu_actions['toolbar'] = toggle_toolbar_action
        
        toggle_char_list_action = QAction(tr("Character List"), self)
        toggle_char_list_action.setCheckable(True)
        toggle_char_list_action.setChecked(True)
        toggle_char_list_action.triggered.connect(self._toggle_char_list)
        view_menu.addAction(toggle_char_list_action)
        self.toggle_char_list_action = toggle_char_list_action
        self._menu_actions['char_list'] = toggle_char_list_action
        
        toggle_stash_action = QAction(tr("Shared Stash"), self)
        toggle_stash_action.setCheckable(True)
        toggle_stash_action.setChecked(True)
        toggle_stash_action.triggered.connect(self._toggle_shared_stash)
        view_menu.addAction(toggle_stash_action)
        self.toggle_stash_action = toggle_stash_action
        self._menu_actions['shared_stash'] = toggle_stash_action
        
        view_menu.addSeparator()
        
        cascade_action = QAction(tr("Cascade Windows"), self)
        cascade_action.triggered.connect(self.mdi_area.cascadeSubWindows)
        view_menu.addAction(cascade_action)
        self._menu_actions['cascade'] = cascade_action
        
        tile_action = QAction(tr("Tile Windows"), self)
        tile_action.triggered.connect(self.mdi_area.tileSubWindows)
        view_menu.addAction(tile_action)
        self._menu_actions['tile'] = tile_action
        
        self._menu_actions['view_menu'] = view_menu
        
        window_menu = menubar.addMenu(tr("Window"))
        self._window_menu = window_menu
        self._window_actions = []
        self._menu_actions['window_menu'] = window_menu
        
        settings_menu = menubar.addMenu(tr("Settings"))
        self._menu_actions['settings_menu'] = settings_menu
        
        set_save_path_action = QAction(tr("Set Save Folder..."), self)
        set_save_path_action.triggered.connect(self._set_save_folder)
        settings_menu.addAction(set_save_path_action)
        self._menu_actions['set_save_path'] = set_save_path_action
    
    def open_character_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            tr("Open Diablo II Character Save File"),
            "",
            tr("D2S Files (*.d2s);;All Files (*)")
        )
        
        if file_path:
            self._try_load_character(file_path)
    
    def _try_load_character(self, file_path, retries=1):
        try:
            self.load_character(file_path)
        except Exception as e:
            error_msg = str(e)
            if self._offer_char_backup_restore(file_path, error_msg) and retries > 0:
                self._try_load_character(file_path, retries - 1)
            else:
                QMessageBox.critical(self, tr("Error"), tr_format("Failed to load file:\n{}", error_msg))
    
    def open_item_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            tr("Open Diablo II Item File"),
            "",
            tr("D2I Files (*.d2i);;All Files (*)")
        )
        
        if file_path:
            try:
                self.load_item(file_path)
            except Exception as e:
                QMessageBox.critical(self, tr("Error"), tr_format("Failed to load file:\n{}", str(e)))
    
    def load_character(self, file_path: str):
        existing = self._doc_manager.find_document_by_path(file_path)
        if existing:
            self._activate_document(existing)
            return
        
        with open(file_path, 'rb') as f:
            data = f.read()
        
        bs = IBitStream(data)
        char_data = D2SStruct()
        char_data.deserialize(bs)
        
        doc = self._doc_manager.create_document(
            doc_type=DocumentType.CHARACTER,
            file_path=file_path,
            data=char_data
        )
        
        self._add_recent_file(file_path)
        self.statusBar.showMessage(tr_format("Loaded: {}", os.path.basename(file_path)))
    
    def _find_char_backups(self, file_path):
        if not file_path:
            return []
        base, ext = os.path.splitext(file_path)
        backups = []
        for i in range(1, self.MAX_BACKUPS + 1):
            backup_path = f"{base}.{i}.d2sb"
            if os.path.isfile(backup_path):
                try:
                    stat = os.stat(backup_path)
                    backups.append((i, backup_path, stat.st_mtime, stat.st_size))
                except OSError:
                    continue
        backups.sort(key=lambda x: x[2], reverse=True)
        return backups
    
    def _offer_char_backup_restore(self, file_path, error_msg):
        backups = self._find_char_backups(file_path)
        if not backups:
            return False
        
        backup_list = "\n".join(
            f"  {os.path.basename(b[1])}  ({datetime.datetime.fromtimestamp(b[2]).strftime('%Y-%m-%d %H:%M:%S')})"
            for b in backups
        )
        
        msg = tr_format(
            "Failed to load character:\n{}\n\nAvailable backups:\n{}\n\nRestore the most recent backup?",
            error_msg, backup_list
        )
        result = QMessageBox.warning(
            self, tr("Load Failed - Backups Available"), msg,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
        )
        
        if result == QMessageBox.Yes:
            import shutil
            backup_path = backups[0][1]
            try:
                shutil.copy2(backup_path, file_path)
                return True
            except Exception as e:
                QMessageBox.critical(self, tr("Error"), tr_format("Failed to restore backup:\n{}", str(e)))
        return False
    
    def load_item(self, file_path: str):
        existing = self._doc_manager.find_document_by_path(file_path)
        if existing:
            self._activate_document(existing)
            return
        
        from core.item import D2Item, init_item_data
        
        data_dir = resource_path("data")
        init_item_data(
            os.path.join(data_dir, 'itemdata.txt'),
            os.path.join(data_dir, 'property.txt'),
            os.path.join(data_dir, 'ItemStatCost.txt')
        )
        
        with open(file_path, 'rb') as f:
            data = f.read()
        
        has_magic = (len(data) >= 2 and data[:2] == b'JM')
        
        bs = IBitStream(data)
        item = D2Item()
        item.deserialize(bs, 0x69, read_magic=has_magic)
        
        item._has_magic = has_magic
        
        doc = self._doc_manager.create_document(
            doc_type=DocumentType.SINGLE_ITEM,
            file_path=file_path,
            data=item
        )
        
        self._add_recent_file(file_path)
        self.statusBar.showMessage(tr_format("Loaded: {}", os.path.basename(file_path)))
    
    def save_current_document(self):
        doc = self._doc_manager.get_active_document()
        if doc:
            self.save_document(doc)
    
    def save_current_document_as(self):
        doc = self._doc_manager.get_active_document()
        if doc:
            self.save_document_as(doc)
    
    def save_all_documents(self):
        modified_docs = self._doc_manager.get_modified_documents()
        for doc in modified_docs:
            if not self.save_document(doc):
                return False
        return True
    
    def save_document(self, doc) -> bool:
        if not doc.file_path:
            return self.save_document_as(doc)
        
        try:
            if doc.doc_type == DocumentType.SINGLE_ITEM:
                return self._save_item_document(doc)
            elif doc.doc_type == DocumentType.CHARACTER:
                return self._save_char_document(doc)
            else:
                QMessageBox.warning(self, tr("Error"), tr_format("Unknown document type: {}", doc.doc_type))
                return False
        except Exception as e:
            QMessageBox.critical(self, tr("Error"), tr_format("Failed to save file:\n{}", str(e)))
            return False
    
    def _save_item_document(self, doc) -> bool:
        from core.obitstream import OBitStream
        
        item = doc.data
        if not item:
            QMessageBox.warning(self, tr("Error"), tr("No item data to save"))
            return False
        
        self._create_backup(doc.file_path)
        
        has_magic = getattr(item, '_has_magic', False)
        
        bs = OBitStream()
        item.serialize(bs, item.dwVersion, write_magic=has_magic)
        data = bs.get_data()
        
        with open(doc.file_path, 'wb') as f:
            f.write(data)
        
        doc.mark_saved()
        self._update_window_title(doc)
        self._update_ui_state()
        self.statusBar.showMessage(tr_format("Saved: {}", os.path.basename(doc.file_path)))
        return True

    def _save_char_document(self, doc) -> bool:
        from core.obitstream import OBitStream
        
        char_data = doc.data
        if not char_data:
            QMessageBox.warning(self, tr("Error"), tr("No character data to save"))
            return False
        
        self._create_backup(doc.file_path)
        
        obs = OBitStream()
        char_data.serialize(obs)
        data = obs.get_data()
        
        import struct
        char_data.dwSize = len(data)
        data = bytearray(data)
        struct.pack_into('<I', data, 8, char_data.dwSize)
        data = char_data.update_checksum(bytes(data))
        
        with open(doc.file_path, 'wb') as f:
            f.write(data)
        
        doc.mark_saved()
        self._update_window_title(doc)
        self._update_ui_state()
        self.statusBar.showMessage(tr_format("Saved: {}", os.path.basename(doc.file_path)))
        return True
    
    MAX_BACKUPS = 7
    
    def _create_backup(self, file_path: str):
        if not file_path or not os.path.exists(file_path):
            return
        
        import stat
        
        def _remove_readonly(path):
            if os.path.exists(path):
                try:
                    os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
                except OSError:
                    pass
        
        def _safe_remove(path):
            if os.path.exists(path):
                try:
                    _remove_readonly(path)
                    os.remove(path)
                except OSError:
                    pass
        
        base, ext = os.path.splitext(file_path)
        
        oldest = f"{base}.{self.MAX_BACKUPS}.d2sb"
        _safe_remove(oldest)
        
        for i in range(self.MAX_BACKUPS - 1, 0, -1):
            src = f"{base}.{i}.d2sb"
            dst = f"{base}.{i + 1}.d2sb"
            if os.path.exists(src):
                try:
                    _remove_readonly(dst)
                    os.rename(src, dst)
                except OSError:
                    _safe_remove(src)
        
        backup_path = f"{base}.1.d2sb"
        import shutil
        try:
            shutil.copy2(file_path, backup_path)
        except OSError:
            try:
                _remove_readonly(backup_path)
                shutil.copy2(file_path, backup_path)
            except OSError:
                pass
    
    def save_document_as(self, doc) -> bool:
        if doc.doc_type == DocumentType.SINGLE_ITEM:
            file_filter = tr("D2I Files (*.d2i);;All Files (*)")
        else:
            file_filter = tr("D2S Files (*.d2s);;All Files (*)")
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            tr("Save Diablo II Save File"),
            doc.file_path or "",
            file_filter
        )
        
        if file_path:
            doc.file_path = file_path
            return self.save_document(doc)
        
        return False
    
    def close_current_document(self):
        active = self.mdi_area.activeSubWindow()
        if active:
            active.close()
    
    def _on_document_added(self, doc):
        if doc.doc_type == DocumentType.CHARACTER:
            window = CharDocumentWindow(doc)
            window.item_clicked.connect(self._on_item_clicked)
            window.document_modified.connect(self._on_document_modified)
            window.item_dropped.connect(self._on_item_dropped)
            self.mdi_area.addSubWindow(window)
            self._doc_windows[doc.window_id] = window
            
            doc_count = len(self._doc_manager.get_all_documents())
            offset = (doc_count - 1) * 30
            window.move(offset, offset)
            
            window.show()
        elif doc.doc_type == DocumentType.SINGLE_ITEM:
            from gui.widgets.item_document_window import ItemDocumentWindow
            window = ItemDocumentWindow(doc)
            self.mdi_area.addSubWindow(window)
            self._doc_windows[doc.window_id] = window
            
            doc_count = len(self._doc_manager.get_all_documents())
            offset = (doc_count - 1) * 30
            window.move(offset, offset)
            
            window.show()
        
        self._update_ui_state()
        self._update_window_menu()
    
    def _on_document_removed(self, doc):
        if doc.window_id in self._doc_windows:
            del self._doc_windows[doc.window_id]
        
        self._update_ui_state()
        self._update_window_menu()
    
    def on_char_window_closed(self, window):
        doc = window.document
        self.mdi_area.removeSubWindow(window)
        self._doc_manager.remove_document(doc.window_id)
    
    def on_item_window_closed(self, window):
        doc = window.document
        self.mdi_area.removeSubWindow(window)
        self._doc_manager.remove_document(doc.window_id)
    
    def _on_active_changed(self, doc):
        self._update_ui_state()
    
    def _on_document_modified(self, doc_id: int):
        self._update_ui_state()
    
    def _on_sub_window_activated(self, sub_window):
        from gui.widgets.item_document_window import ItemDocumentWindow
        if sub_window and isinstance(sub_window, CharDocumentWindow):
            self._doc_manager.set_active_document(sub_window.doc_id)
        elif sub_window and isinstance(sub_window, ItemDocumentWindow):
            self._doc_manager.set_active_document(sub_window.doc_id)
        elif sub_window is None and self._doc_windows:
            self._doc_manager._active_document = None
        self._update_ui_state()
    
    def _on_item_clicked(self, item):
        if not item:
            return
        
        version = 0x63
        active_doc = self._doc_manager.get_active_document()
        if active_doc and active_doc.data and hasattr(active_doc.data, 'dwVersion'):
            version = active_doc.data.dwVersion
        
        from gui.widgets.item_edit_dialog import ItemEditDialog
        dialog = ItemEditDialog(item, version, self)
        dialog.item_changed.connect(self._on_item_edited)
        dialog.exec()
    
    def _on_item_edited(self, item):
        stash_modified = self._check_stash_item(item)

        active_doc = self._doc_manager.get_active_document()
        if active_doc:
            if not active_doc.modified:
                active_doc.mark_modified()
                if active_doc.window_id in self._doc_windows:
                    self._doc_windows[active_doc.window_id]._update_title()
            
            if active_doc.window_id in self._doc_windows:
                win = self._doc_windows[active_doc.window_id]
                if hasattr(win, 'items_widget') and hasattr(win.items_widget, 'update_data'):
                    win.items_widget.update_data(active_doc.data)
            
            self._update_ui_state()

        if stash_modified:
            self.shared_stash.mark_modified()

    def _check_stash_item(self, item) -> bool:
        for stash in [self.shared_stash._modern_stash, self.shared_stash._classic_stash]:
            if not stash:
                continue
            for tab in stash.tabs:
                if tab.Items and tab.Items.vItems:
                    for stash_item in tab.Items.vItems:
                        if stash_item is item:
                            return True
        return False
    
    def _on_item_dropped(self, drag_data, target_stored_in, target_col, target_row, target_position, target_doc_id=-1):
        from gui.drag_drop import ItemDragData
        
        if not drag_data or not drag_data.item:
            return
        
        source_item_data = drag_data.item
        source_doc_id = drag_data.source_doc_id
        source_stored_in = drag_data.source_stored_in
        source_col = drag_data.source_column
        source_row = drag_data.source_row
        is_copy = drag_data.is_copy
        
        source_doc = self._doc_manager.get_document(source_doc_id)
        is_from_item_doc = isinstance(source_doc, ItemDocument)
        
        if not source_doc or not source_doc.data:
            return
        
        if not is_from_item_doc and not source_doc.data.ItemList:
            return
        
        source_items = source_doc.data.ItemList.vItems if not is_from_item_doc else None
        
        if target_doc_id >= 0:
            target_doc = self._doc_manager.get_document(target_doc_id)
        else:
            target_doc = self._doc_manager.get_active_document()
        if not target_doc or not target_doc.data or not target_doc.data.ItemList:
            return
        
        target_items = target_doc.data.ItemList.vItems
        version = target_doc.data.dwVersion if hasattr(target_doc.data, 'dwVersion') else 0x63
        
        is_equipment = (target_stored_in == -1 and target_position > 0)
        is_belt = (target_stored_in == 5)
        
        if is_equipment:
            item_width, item_height = self._get_item_grid_size(source_item_data, version)
            if not self._can_equip_item(source_item_data, target_position, version):
                return
        elif is_belt:
            item_width, item_height = 1, 1
            type_name = source_item_data.sTypeName.decode('ascii', errors='replace').strip() if source_item_data.sTypeName else ''
            from core.d2data import get_d2data_manager
            d2mgr = get_d2data_manager()
            if d2mgr and not d2mgr.is_beltable(type_name, version):
                return
            belt_rows = self._get_belt_rows(target_doc.data)
            belt_col = target_col if target_col >= 0 else 0
            belt_row = target_row if target_row >= 0 else 0
            if belt_row >= belt_rows:
                return
        else:
            if target_stored_in == -1:
                return
            item_width, item_height = self._get_item_grid_size(source_item_data, version)
        
        source_item = self._find_item(source_items, source_stored_in, source_col, source_row, drag_data.source_location, drag_data.source_position) if not is_from_item_doc else None
        
        is_same_place = False
        if source_doc == target_doc and not is_copy and source_item is not None:
            if is_equipment and drag_data.source_location == 1 and drag_data.source_position == target_position:
                is_same_place = True
            elif not is_equipment and not is_belt and drag_data.source_location == 0 and drag_data.source_stored_in == target_stored_in and source_col == target_col and source_row == target_row:
                is_same_place = True
        
        if is_same_place:
            return
        
        swap_item = None
        if is_equipment:
            swap_item = self._find_item(target_items, -1, 0, 0, location=1, position=target_position)
        elif not is_belt:
            swap_item = self._find_item_at_grid(target_items, target_stored_in, target_col, target_row, version)
        
        if swap_item is source_item:
            swap_item = None
        
        if swap_item and is_copy:
            swap_item = None
        
        if swap_item and is_from_item_doc:
            swap_item = None
        
        if swap_item and source_doc != target_doc:
            swap_item = None
        
        if swap_item:
            if is_equipment:
                if not self._can_equip_item(swap_item, drag_data.source_position if drag_data.source_location == 1 else -1, version):
                    if drag_data.source_location != 1:
                        swap_item = None
                    else:
                        return
            elif not is_belt and drag_data.source_location == 0:
                swap_w, swap_h = self._get_item_grid_size(swap_item, version)
                if drag_data.source_stored_in >= 0:
                    if not self._can_place_item(target_doc.data, drag_data.source_stored_in, source_col, source_row, swap_w, swap_h):
                        swap_item = None
                else:
                    swap_item = None
        
        if not is_from_item_doc and source_doc == target_doc and not is_copy:
            if source_item is not None:
                source_items.remove(source_item)
        
        if swap_item and source_doc == target_doc and not is_copy:
            target_items.remove(swap_item)
        
        if not is_equipment:
            if not self._can_place_item(target_doc.data, target_stored_in, target_col, target_row, item_width, item_height):
                if not is_from_item_doc and source_doc == target_doc and not is_copy and source_item is not None:
                    source_items.append(source_item)
                if swap_item and source_doc == target_doc and not is_copy:
                    target_items.append(swap_item)
                return
        
        new_item = self._copy_item(source_item_data, version)
        if not new_item:
            if not is_from_item_doc and source_doc == target_doc and not is_copy and source_item is not None:
                source_items.append(source_item)
            if swap_item and source_doc == target_doc and not is_copy:
                target_items.append(swap_item)
            return
        
        if not is_from_item_doc and not is_copy and source_item is not None:
            if source_doc != target_doc:
                source_items.remove(source_item)
                self._refresh_items_widget(source_doc)
                if not source_doc.modified:
                    source_doc.mark_modified()
                    self._doc_windows[source_doc.window_id]._update_title()
        
        if is_equipment:
            new_item.iLocation = 1
            new_item.iPosition = target_position
            new_item.iStoredIn = 0
            new_item.iColumn = 0
            new_item.iRow = 0
        elif is_belt:
            new_item.iLocation = 2
            new_item.iPosition = 0
            new_item.iStoredIn = -1
            new_item.iColumn = target_col + target_row * 4
            new_item.iRow = 0
        else:
            new_item.iLocation = 0
            new_item.iStoredIn = target_stored_in
            new_item.iColumn = target_col
            new_item.iRow = target_row
            new_item.iPosition = 0
        
        target_items.append(new_item)
        
        if swap_item and not is_copy:
            if drag_data.source_location == 1:
                swap_item.iLocation = 1
                swap_item.iPosition = drag_data.source_position
                swap_item.iStoredIn = 0
                swap_item.iColumn = 0
                swap_item.iRow = 0
            elif drag_data.source_location == 2:
                swap_item.iLocation = 2
                swap_item.iPosition = 0
                swap_item.iStoredIn = 0
                swap_item.iColumn = source_col
                swap_item.iRow = 0
            else:
                swap_item.iLocation = 0
                swap_item.iStoredIn = drag_data.source_stored_in
                swap_item.iColumn = source_col
                swap_item.iRow = source_row
                swap_item.iPosition = 0
            target_items.append(swap_item)
        
        self._refresh_items_widget(target_doc)
        if not target_doc.modified:
            target_doc.mark_modified()
            if target_doc.window_id in self._doc_windows:
                self._doc_windows[target_doc.window_id]._update_title()
        
        self._update_ui_state()
    
    def _find_item(self, items, stored_in, col, row, location=0, position=-1):
        for item in items:
            if location == 1:
                if (hasattr(item, 'iLocation') and hasattr(item, 'iPosition') and
                        item.iLocation == 1 and item.iPosition == position):
                    return item
            elif location == 2:
                if (hasattr(item, 'iLocation') and hasattr(item, 'iColumn') and
                        item.iLocation == 2 and item.iColumn == col):
                    return item
            else:
                if (hasattr(item, 'iStoredIn') and hasattr(item, 'iColumn') and hasattr(item, 'iRow') and
                        item.iStoredIn == stored_in and item.iColumn == col and item.iRow == row):
                    return item
        return None
    
    def _find_item_at_grid(self, items, stored_in, col, row, version=0x63):
        for item in items:
            if not hasattr(item, 'iLocation') or item.iLocation != 0:
                continue
            if not hasattr(item, 'iStoredIn') or item.iStoredIn != stored_in:
                continue
            iw, ih = self._get_item_grid_size(item, version)
            ic = item.iColumn if hasattr(item, 'iColumn') else 0
            ir = item.iRow if hasattr(item, 'iRow') else 0
            if ic <= col < ic + iw and ir <= row < ir + ih:
                return item
        return None
    
    def _get_belt_rows(self, char_data) -> int:
        if not char_data or not char_data.ItemList:
            return 1
        for item in char_data.ItemList.vItems:
            if hasattr(item, 'iLocation') and item.iLocation == 1 and hasattr(item, 'iPosition') and item.iPosition == 8:
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
                        version = getattr(char_data, 'dwVersion', 0x63)
                        rows = d2data_manager.get_belt_rows(type_name, version)
                        if rows > 0:
                            return rows
                break
        return 1
    
    def _can_equip_item(self, item_data, position, version=0x63):
        d2data_manager = get_d2data_manager()
        type_name = item_data.sTypeName.decode('ascii', errors='replace') if item_data.sTypeName else ''
        type_name = type_name.strip()
        if not type_name or not d2data_manager:
            return False
        version_data = d2data_manager.get_version_data(version)
        if not version_data:
            return False
        item_info = version_data.items.get(type_name)
        if not item_info:
            return False
        item_type = getattr(item_info, 'type', '')
        item_type2 = getattr(item_info, 'type2', '')
        valid_positions = set()
        for t in [type_name.lower(), item_type.lower(), item_type2.lower()]:
            if t:
                bodyloc = version_data.type_bodyloc.get(t)
                if bodyloc:
                    valid_positions.add(bodyloc[0])
                    if bodyloc[1]:
                        valid_positions.add(bodyloc[1])
        valid_positions.discard(0)
        return position in valid_positions
    
    def _get_item_grid_size(self, item, version=0x63):
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
    
    def _copy_item(self, item, version):
        from core.obitstream import OBitStream
        from core.ibitstream import IBitStream
        try:
            bs = OBitStream()
            item.serialize(bs, version, write_magic=False)
            data = bs.get_data()
            ibs = IBitStream(data)
            new_item = type(item)()
            new_item.deserialize(ibs, version, False)
            return new_item
        except Exception:
            return None
    
    def _can_place_item(self, char_data, stored_in, col, row, width, height):
        occupied = set()
        version = char_data.dwVersion if hasattr(char_data, 'dwVersion') else 0x63
        for item in char_data.ItemList.vItems:
            if not hasattr(item, 'iLocation'):
                continue
            if stored_in == 5:
                if item.iLocation != 2:
                    continue
                ic = item.iColumn if hasattr(item, 'iColumn') else 0
                belt_col = ic % 4
                belt_row = ic // 4
                occupied.add((belt_col, belt_row))
            else:
                if item.iLocation != 0 or not hasattr(item, 'iStoredIn') or item.iStoredIn != stored_in:
                    continue
                iw, ih = self._get_item_grid_size(item, version)
                ic = item.iColumn if hasattr(item, 'iColumn') else 0
                ir = item.iRow if hasattr(item, 'iRow') else 0
                for dx in range(iw):
                    for dy in range(ih):
                        occupied.add((ic + dx, ir + dy))
        
        if stored_in == 4:
            max_cols = 10 if version >= 0x69 else 6
            max_rows = 10 if version >= 0x69 else 8
        elif stored_in == 5:
            max_cols = 4
            max_rows = self._get_belt_rows(char_data)
        else:
            grid_limits = {0: (10, 4), 3: (3, 4)}
            max_cols, max_rows = grid_limits.get(stored_in, (0, 0))
        
        for dx in range(width):
            for dy in range(height):
                c, r = col + dx, row + dy
                if c < 0 or c >= max_cols or r < 0 or r >= max_rows:
                    return False
                if (c, r) in occupied:
                    return False
        
        return True
    
    def _refresh_items_widget(self, doc):
        if doc.window_id in self._doc_windows:
            win = self._doc_windows[doc.window_id]
            if hasattr(win, 'items_widget') and hasattr(win.items_widget, 'update_data'):
                win.items_widget.update_data(doc.data)
    
    def _on_save_list_double_clicked(self, file_path: str):
        try:
            self.load_character(file_path)
        except Exception as e:
            QMessageBox.critical(self, tr("Error"), tr_format("Failed to load file:\n{}", str(e)))
    
    def _on_save_path_changed(self, path: str):
        settings = QSettings("D2Savior", "D2Savior")
        settings.setValue("save_path", path)
    
    def _load_save_path(self):
        settings = QSettings("D2Savior", "D2Savior")
        save_path = settings.value("save_path", "")
        
        if not save_path or not os.path.isdir(save_path):
            default_path = os.path.join(
                os.environ.get('USERPROFILE', os.path.expanduser('~')),
                'Saved Games',
                'Diablo II Resurrected (CN)'
            )
            if os.path.isdir(default_path):
                save_path = default_path
            else:
                default_path_en = os.path.join(
                    os.environ.get('USERPROFILE', os.path.expanduser('~')),
                    'Saved Games',
                    'Diablo II Resurrected'
                )
                if os.path.isdir(default_path_en):
                    save_path = default_path_en
                else:
                    save_path = ""
        
        self.save_list.set_save_path(save_path)
        self.shared_stash.set_save_path(save_path)
    
    def _set_save_folder(self):
        current = self.save_list.save_path
        if not current or not os.path.isdir(current):
            current = ""
        path = QFileDialog.getExistingDirectory(
            self,
            tr("Select Diablo II Save Folder"),
            current,
        )
        if path:
            self.save_list.set_save_path(path)
            self.shared_stash.set_save_path(path)
            settings = QSettings("D2Savior", "D2Savior")
            settings.setValue("save_path", path)
    
    def _toggle_toolbar(self, checked):
        self._toolbar.setVisible(checked)
    
    def _toggle_char_list(self, checked):
        self.save_list.setVisible(checked)
        if hasattr(self, '_toolbar_actions') and 'char_list' in self._toolbar_actions:
            self._toolbar_actions['char_list'].setChecked(checked)
        if hasattr(self, 'toggle_char_list_action'):
            self.toggle_char_list_action.setChecked(checked)
    
    def _toggle_shared_stash(self, checked):
        self.shared_stash.setVisible(checked)
        if hasattr(self, '_toolbar_actions') and 'shared_stash' in self._toolbar_actions:
            self._toolbar_actions['shared_stash'].setChecked(checked)
        if hasattr(self, 'toggle_stash_action'):
            self.toggle_stash_action.setChecked(checked)
    
    def _activate_document(self, doc):
        if doc.window_id in self._doc_windows:
            window = self._doc_windows[doc.window_id]
            if not window.isVisible():
                window.show()
            self.mdi_area.setActiveSubWindow(window)
            window.setFocus()
            window.raise_()
    
    def _update_window_title(self, doc):
        if doc.window_id in self._doc_windows:
            window = self._doc_windows[doc.window_id]
            window.setWindowTitle(doc.display_name)
    
    def _update_ui_state(self):
        has_docs = len(self._doc_manager.get_all_documents()) > 0
        has_modified = len(self._doc_manager.get_modified_documents()) > 0
        active_doc = self._doc_manager.get_active_document()
        active_modified = active_doc is not None and active_doc.modified
        
        self.save_action.setEnabled(active_modified)
        self.save_as_action.setEnabled(active_doc is not None)
        self.save_all_action.setEnabled(has_modified)
        self.close_action.setEnabled(has_docs)
        self.open_item_action.setEnabled(True)
        
        if hasattr(self, '_toolbar_actions'):
            self._toolbar_actions['save'].setEnabled(active_modified)
            self._toolbar_actions['open_item'].setEnabled(True)
    
    def _update_window_menu(self):
        self._window_menu.clear()
        self._window_actions.clear()
        
        docs = self._doc_manager.get_all_documents()
        if not docs:
            empty = QAction("No open documents", self)
            empty.setEnabled(False)
            self._window_menu.addAction(empty)
            return
        
        for doc in docs:
            action = QAction(doc.display_name, self)
            action.triggered.connect(lambda checked, d=doc: self._activate_document(d))
            self._window_menu.addAction(action)
            self._window_actions.append(action)
    
    def _change_language(self, lang_key: str):
        get_gui_translator().set_language(lang_key)
        set_language(lang_key)
        
        settings = QSettings("D2Savior", "D2Savior")
        settings.setValue("gui_language", lang_key)
        
        for k, action in self._lang_actions.items():
            action.setChecked(k == lang_key)
        
        self._refresh_menu_texts()
        self.setWindowTitle(tr("D2Savior - Diablo II Character Editor"))
        self.statusBar.showMessage(tr("Ready"))
        
        for doc in self._doc_manager.get_all_documents():
            if doc.doc_type == DocumentType.CHARACTER and doc.window_id in self._doc_windows:
                window = self._doc_windows[doc.window_id]
                window._update_ui()
    
    def _refresh_menu_texts(self):
        ma = self._menu_actions
        if not ma:
            return
        
        menu_titles = {
            'file_menu': "File",
            'view_menu': "View",
            'window_menu': "Window",
            'settings_menu': "Settings",
            'lang_menu': "Language",
            'recent_menu': "Recent Files",
        }
        for key, text in menu_titles.items():
            if key in ma:
                ma[key].setTitle(tr(text))
        
        action_texts = {
            'open_char': "Open Character...",
            'open_item': "Open Item...",
            'save': "Save",
            'save_as': "Save As...",
            'save_all': "Save All",
            'close': "Close",
            'exit': "Exit",
            'toolbar': "Toolbar",
            'char_list': "Character List",
            'shared_stash': "Shared Stash",
            'cascade': "Cascade Windows",
            'tile': "Tile Windows",
            'set_save_path': "Set Save Folder...",
        }
        for key, text in action_texts.items():
            if key in ma:
                ma[key].setText(tr(text))
        
        if hasattr(self, '_toolbar_actions'):
            toolbar_tooltip_texts = {
                'open_char': ("Open Character...", "Ctrl+O"),
                'open_item': ("Open Item...", "Ctrl+Shift+O"),
                'save': ("Save", "Ctrl+S"),
                'char_list': ("Toggle Character List", None),
                'shared_stash': ("Toggle Shared Stash", None),
            }
            for key, (text, shortcut) in toolbar_tooltip_texts.items():
                if key in self._toolbar_actions:
                    action = self._toolbar_actions[key]
                    tooltip = tr(text)
                    if shortcut:
                        tooltip += f" ({shortcut})"
                    action.setToolTip(tooltip)
                    if key in ('char_list', 'shared_stash'):
                        action.setText(tr(text.replace("Toggle ", "")))
                    else:
                        action.setText(tr(text))
        
        lang_map = {"enUS": "English", "zhCN": "Simplified Chinese"}
        for lang_key, lang_name in lang_map.items():
            if lang_key in self._lang_actions:
                self._lang_actions[lang_key].setText(tr(lang_name))
        
        self._update_recent_menu()
    
    def _load_recent_files(self):
        settings = QSettings("D2Savior", "D2Savior")
        self._recent_files = settings.value("recent_files", []) or []
    
    def _save_recent_files(self):
        settings = QSettings("D2Savior", "D2Savior")
        settings.setValue("recent_files", self._recent_files)
    
    def _add_recent_file(self, file_path: str):
        file_path = os.path.abspath(file_path)
        if file_path in self._recent_files:
            self._recent_files.remove(file_path)
        self._recent_files.insert(0, file_path)
        self._recent_files = self._recent_files[:self.MAX_RECENT_FILES]
        self._save_recent_files()
        self._update_recent_menu()
    
    def _update_recent_menu(self):
        self._recent_menu.clear()
        self._recent_actions.clear()
        if not self._recent_files:
            empty = QAction(tr("No recent files"), self)
            empty.setEnabled(False)
            self._recent_menu.addAction(empty)
            return
        for i, fpath in enumerate(self._recent_files):
            if not os.path.exists(fpath):
                continue
            text = f"&{i + 1} {os.path.basename(fpath)}"
            action = QAction(text, self)
            action.triggered.connect(lambda checked, p=fpath: self._open_recent(p))
            self._recent_menu.addAction(action)
            self._recent_actions.append(action)
    
    def _open_recent(self, file_path: str):
        try:
            if file_path.endswith('.d2s'):
                self.load_character(file_path)
            elif file_path.endswith('.d2i'):
                self.load_item(file_path)
        except Exception as e:
            QMessageBox.critical(self, tr("Error"), tr_format("Failed to load file:\n{}", str(e)))
    
    def closeEvent(self, event):
        modified_docs = self._doc_manager.get_modified_documents()
        
        if modified_docs:
            reply = QMessageBox.question(
                self,
                tr("Unsaved Changes"),
                tr("You have {} document(s) with unsaved changes.\nDo you want to save all changes?").format(len(modified_docs)),
                QMessageBox.SaveAll | QMessageBox.Discard | QMessageBox.Cancel
            )
            
            if reply == QMessageBox.Cancel:
                event.ignore()
                return
            elif reply == QMessageBox.SaveAll:
                if not self.save_all_documents():
                    event.ignore()
                    return
        
        self._doc_manager.close_all()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    from PySide6.QtGui import QPalette, QColor
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor(26, 26, 46))
    pal.setColor(QPalette.ColorRole.WindowText, QColor(224, 224, 224))
    pal.setColor(QPalette.ColorRole.Base, QColor(15, 52, 96))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor(26, 26, 46))
    pal.setColor(QPalette.ColorRole.Text, QColor(224, 224, 224))
    pal.setColor(QPalette.ColorRole.Button, QColor(30, 30, 60))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor(200, 200, 220))
    pal.setColor(QPalette.ColorRole.Light, QColor(60, 60, 90))
    pal.setColor(QPalette.ColorRole.Midlight, QColor(45, 45, 75))
    pal.setColor(QPalette.ColorRole.Dark, QColor(15, 15, 40))
    pal.setColor(QPalette.ColorRole.Mid, QColor(30, 30, 55))
    pal.setColor(QPalette.ColorRole.Shadow, QColor(10, 10, 30))
    pal.setColor(QPalette.ColorRole.Highlight, QColor(42, 42, 94))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor(90, 90, 110))
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(90, 90, 110))
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(90, 90, 110))
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Highlight, QColor(30, 30, 60))
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.HighlightedText, QColor(90, 90, 110))
    
    app.setPalette(pal)
    
    app.setStyleSheet("""
        QToolTip {
            background-color: rgba(26, 26, 46, 210);
            color: #e0e0e0;
            border: 1px solid #4a4a6e;
            border-radius: 3px;
            padding: 6px;
            font-size: 12px;
        }
        QMdiArea {
            background-color: #1a1a2e;
        }
        QToolBar {
            background-color: #16213e;
            border: none;
            spacing: 3px;
            padding: 3px;
        }
        QToolBar QToolButton {
            background-color: transparent;
            border: 1px solid transparent;
            border-radius: 3px;
            padding: 3px;
            margin: 1px;
        }
        QToolBar QToolButton:hover {
            background-color: #1a1a4e;
            border: 1px solid #4a4a6e;
        }
        QToolBar QToolButton:pressed {
            background-color: #2a2a5e;
        }
        QToolBar QToolButton:checked {
            background-color: #2a2a5e;
            border: 1px solid #6a6a9e;
        }
        QToolBar QToolButton:disabled {
            background-color: transparent;
            border: 1px solid transparent;
            color: #555566;
        }
        QToolBar::separator {
            width: 1px;
            background-color: #4a4a6e;
            margin: 4px 2px;
        }
    """)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
