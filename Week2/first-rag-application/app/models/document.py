"""
Internal data models passed between pipeline stages.

Document -> normalized text of one file (or one PDF page) + metadata
Chunk    -> the smallest unit the retriever can return
"""

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class Document:
    document_id: str
    text: str
    source: str                      # file name or URL
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Chunk:
    chunk_id: str
    document_id: str
    text: str
    source: str
    metadata: Dict[str, Any] = field(default_factory=dict)
