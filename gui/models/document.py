from dataclasses import dataclass, field
from typing import Optional, List, Callable
from enum import Enum
from pathlib import Path


class DocumentType(Enum):
    CHARACTER = "character"
    STASH = "stash"
    SINGLE_ITEM = "single_item"


@dataclass
class Document:
    file_path: Optional[str] = None
    doc_type: DocumentType = DocumentType.CHARACTER
    data: Optional[object] = None
    modified: bool = False
    window_id: Optional[int] = None
    
    @property
    def file_name(self) -> str:
        if self.file_path:
            return Path(self.file_path).name
        return "Untitled"
    
    @property
    def display_name(self) -> str:
        name = self.file_name
        if self.modified:
            name = f"*{name}"
        return name
    
    def mark_modified(self):
        self.modified = True
    
    def mark_saved(self):
        self.modified = False


@dataclass
class CharDocument(Document):
    doc_type: DocumentType = field(default=DocumentType.CHARACTER, init=False)
    
    @property
    def char_name(self) -> str:
        if self.data and hasattr(self.data, 'get_char_name'):
            return self.data.get_char_name()
        return "Unknown"
    
    @property
    def display_name(self) -> str:
        name = self.char_name
        if self.modified:
            name = f"*{name}"
        return name


@dataclass
class ItemDocument(Document):
    doc_type: DocumentType = field(default=DocumentType.SINGLE_ITEM, init=False)
    
    @property
    def item_name(self) -> str:
        if self.data:
            from core.d2data import get_d2data_manager
            from core.localized_data import get_localized_data
            d2data = get_d2data_manager()
            loc = get_localized_data()
            if d2data and hasattr(self.data, 'sTypeName'):
                type_name = self.data.sTypeName.decode('ascii', errors='replace').strip()
                loc_name = loc.get_item_name(type_name)
                if loc_name and loc_name != type_name:
                    return loc_name
                type_info = d2data.get_item(type_name, 0x63)
                if type_info:
                    return type_info.name
                return type_name
        return "Item"
    
    @property
    def display_name(self) -> str:
        name = self.item_name
        if self.modified:
            name = f"*{name}"
        return name


@dataclass
class StashDocument(Document):
    doc_type: DocumentType = field(default=DocumentType.STASH, init=False)
    
    @property
    def display_name(self) -> str:
        name = self.file_name
        if self.modified:
            name = f"*{name}"
        return name
