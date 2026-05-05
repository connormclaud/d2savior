import pickle
from dataclasses import dataclass, field
from typing import Optional
from PySide6.QtCore import QMimeData, QByteArray

MIME_TYPE_ITEM = "application/x-d2savior-item"


@dataclass
class ItemDragData:
    item: object
    source_doc_id: int
    source_location: int
    source_column: int
    source_row: int
    source_stored_in: int = -1
    source_position: int = -1
    is_copy: bool = False
    
    def to_mime_data(self) -> QMimeData:
        mime = QMimeData()
        data = pickle.dumps(self)
        mime.setData(MIME_TYPE_ITEM, QByteArray(data))
        return mime
    
    @staticmethod
    def from_mime_data(mime: QMimeData) -> Optional['ItemDragData']:
        if not mime.hasFormat(MIME_TYPE_ITEM):
            return None
        try:
            data = mime.data(MIME_TYPE_ITEM)
            return pickle.loads(data.data())
        except Exception:
            return None


@dataclass
class DropTargetInfo:
    target_doc_id: int
    target_location: int
    target_column: int
    target_row: int
    target_stored_in: int = -1
    target_position: int = -1
