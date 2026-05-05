from PySide6.QtWidgets import (
    QMdiSubWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QFrame, QScrollArea, QApplication
)
from PySide6.QtCore import Signal, Qt, QMimeData, QPoint
from PySide6.QtGui import QPixmap, QFont, QDrag

from core.item import D2Item
from gui.models import ItemDocument
from gui.drag_drop import ItemDragData, MIME_TYPE_ITEM
from gui.widgets.item_grid_widget import build_item_tooltip


class DraggableItemLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._item = None
        self._version = 0x69
        self._doc_id = -1
        self._drag_start_pos = None
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(100, 100)

    def set_item(self, item, version=0x69, doc_id=-1):
        self._item = item
        self._version = version
        self._doc_id = doc_id

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self._item:
            self._drag_start_pos = event.pos()
        super().mousePressEvent(event)

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
            source_location=-1,
            source_column=0,
            source_row=0,
            source_stored_in=-1,
            source_position=-1,
            is_copy=is_copy
        )
        mime_data.setData(MIME_TYPE_ITEM, drag_data.to_mime_data().data(MIME_TYPE_ITEM))
        drag.setMimeData(mime_data)

        pixmap = self.pixmap()
        if pixmap and not pixmap.isNull():
            drag.setPixmap(pixmap.scaled(56, 56, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            drag.setHotSpot(QPoint(28, 28))

        default_action = Qt.CopyAction if is_copy else Qt.MoveAction
        drag.exec_(Qt.CopyAction | Qt.MoveAction, default_action)
        self._drag_start_pos = None

    def mouseReleaseEvent(self, event):
        self._drag_start_pos = None
        super().mouseReleaseEvent(event)


class ItemDocumentWindow(QMdiSubWindow):
    item_dropped = Signal(object, int, int, int)
    
    def __init__(self, document: ItemDocument, parent=None):
        super().__init__(parent)
        self._document = document
        self._init_ui()
        self._update_title()
    
    def _init_ui(self):
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        
        self.setFixedSize(400, 500)
        
        central_widget = QWidget()
        self.setWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        
        self._create_item_display(layout)
        
        if self._document.data:
            self._update_ui()
    
    def _create_item_display(self, layout):
        item_frame = QFrame()
        item_frame.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        item_frame.setStyleSheet("""
            QFrame {
                background-color: #1a1a1a;
                border: 2px solid #4a4a4a;
                border-radius: 5px;
            }
        """)
        
        frame_layout = QVBoxLayout(item_frame)
        frame_layout.setContentsMargins(10, 10, 10, 10)
        
        self.item_image_label = DraggableItemLabel()
        frame_layout.addWidget(self.item_image_label)
        
        self.item_info_label = QLabel()
        self.item_info_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.item_info_label.setWordWrap(True)
        self.item_info_label.setStyleSheet("""
            QLabel {
                color: #c0c0c0;
                font-size: 12px;
            }
        """)
        self.item_info_label.setFont(QFont("Consolas", 10))
        frame_layout.addWidget(self.item_info_label)
        
        layout.addWidget(item_frame)
    
    @property
    def document(self) -> ItemDocument:
        return self._document
    
    @property
    def doc_id(self) -> int:
        return self._document.window_id
    
    def _update_title(self):
        self.setWindowTitle(self._document.display_name)
    
    def _update_ui(self):
        if self._document.data:
            item = self._document.data
            self._display_item(item)
    
    def _display_item(self, item: D2Item):
        from gui.image_manager import get_image_manager
        
        image_manager = get_image_manager()
        
        type_name = item.sTypeName.decode('latin-1') if item.sTypeName else ''
        type_name = type_name.strip()
        
        self.item_image_label.set_item(item, item.dwVersion, self._document.window_id)
        
        if image_manager and type_name:
            from core.d2data import get_d2data_manager
            d2data = get_d2data_manager()
            item_info = d2data.get_item(type_name, item.dwVersion) if d2data else None
            
            inv_width = item_info.invwidth if item_info else 1
            inv_height = item_info.invheight if item_info else 1
            
            pixmap = image_manager.get_image_by_code(type_name, (inv_width * 56, inv_height * 56))
            if pixmap:
                self.item_image_label.setPixmap(pixmap)
        
        tooltip_text = build_item_tooltip(item, item.dwVersion)
        self.item_info_label.setText(tooltip_text)
    
    def mark_modified(self):
        if not self._document.modified:
            self._document.mark_modified()
            self._update_title()
    
    def mark_saved(self):
        self._document.mark_saved()
        self._update_title()
    
    def can_close(self) -> bool:
        return True
    
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
                widget.on_item_window_closed(self)
                break
