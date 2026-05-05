from typing import Optional, List, Dict, Callable
from pathlib import Path
import os

from .document import Document, CharDocument, ItemDocument, StashDocument, DocumentType


class DocumentManager:
    _instance: Optional['DocumentManager'] = None
    
    def __init__(self):
        self._documents: Dict[int, Document] = {}
        self._next_id: int = 1
        self._active_document: Optional[Document] = None
        self._on_document_added: Optional[Callable[[Document], None]] = None
        self._on_document_removed: Optional[Callable[[Document], None]] = None
        self._on_document_changed: Optional[Callable[[Document], None]] = None
        self._on_active_changed: Optional[Callable[[Optional[Document]], None]] = None
    
    @classmethod
    def instance(cls) -> 'DocumentManager':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def create_document(self, doc_type: DocumentType, file_path: Optional[str] = None, data: Optional[object] = None) -> Document:
        doc_id = self._next_id
        self._next_id += 1
        
        if doc_type == DocumentType.CHARACTER:
            doc = CharDocument(file_path=file_path, data=data)
        elif doc_type == DocumentType.SINGLE_ITEM:
            doc = ItemDocument(file_path=file_path, data=data)
        elif doc_type == DocumentType.STASH:
            doc = StashDocument(file_path=file_path, data=data)
        else:
            doc = Document(file_path=file_path, doc_type=doc_type, data=data)
        
        doc.window_id = doc_id
        self._documents[doc_id] = doc
        
        if self._on_document_added:
            self._on_document_added(doc)
        
        return doc
    
    def get_document(self, doc_id: int) -> Optional[Document]:
        return self._documents.get(doc_id)
    
    def remove_document(self, doc_id: int) -> Optional[Document]:
        doc = self._documents.pop(doc_id, None)
        if doc:
            if self._on_document_removed:
                self._on_document_removed(doc)
            if self._active_document and self._active_document.window_id == doc_id:
                self._active_document = None
                if self._on_active_changed:
                    self._on_active_changed(None)
        return doc
    
    def get_all_documents(self) -> List[Document]:
        return list(self._documents.values())
    
    def get_documents_by_type(self, doc_type: DocumentType) -> List[Document]:
        return [doc for doc in self._documents.values() if doc.doc_type == doc_type]
    
    def get_modified_documents(self) -> List[Document]:
        return [doc for doc in self._documents.values() if doc.modified]
    
    def set_active_document(self, doc_id: int):
        doc = self._documents.get(doc_id)
        if doc:
            self._active_document = doc
            if self._on_active_changed:
                self._on_active_changed(doc)
    
    def get_active_document(self) -> Optional[Document]:
        return self._active_document
    
    def notify_document_changed(self, doc_id: int):
        doc = self._documents.get(doc_id)
        if doc and self._on_document_changed:
            self._on_document_changed(doc)
    
    def has_unsaved_changes(self) -> bool:
        return any(doc.modified for doc in self._documents.values())
    
    def find_document_by_path(self, file_path: str) -> Optional[Document]:
        abs_path = os.path.abspath(file_path)
        for doc in self._documents.values():
            if doc.file_path and os.path.abspath(doc.file_path) == abs_path:
                return doc
        return None
    
    def close_all(self) -> List[Document]:
        modified = self.get_modified_documents()
        self._documents.clear()
        self._active_document = None
        if self._on_active_changed:
            self._on_active_changed(None)
        return modified
    
    def set_callbacks(self, 
                      on_document_added: Optional[Callable[[Document], None]] = None,
                      on_document_removed: Optional[Callable[[Document], None]] = None,
                      on_document_changed: Optional[Callable[[Document], None]] = None,
                      on_active_changed: Optional[Callable[[Optional[Document]], None]] = None):
        if on_document_added:
            self._on_document_added = on_document_added
        if on_document_removed:
            self._on_document_removed = on_document_removed
        if on_document_changed:
            self._on_document_changed = on_document_changed
        if on_active_changed:
            self._on_active_changed = on_active_changed
