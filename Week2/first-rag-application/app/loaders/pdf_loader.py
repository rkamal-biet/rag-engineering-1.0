"""
PDF loader: one Document per page, so every chunk remembers its page number
(that is what lets us cite "handbook, page 2"). All pages share the file's document_id.
"""

from pathlib import Path
from typing import List

import pymupdf

from app.core.logging import get_logger
from app.core.utils import stable_id
from app.models.document import Document

log = get_logger(__name__)


def load_pdf(path: str | Path) -> List[Document]:
    p = Path(path)
    document_id = stable_id(p.name)
    pages = []

    with pymupdf.open(p) as pdf:
        for page_number, page in enumerate(pdf, start=1):
            text = page.get_text("text")
            if not text.strip():
                # Empty page -> probably a scanned image. OCR is out of scope for a first RAG.
                log.warning("No text on %s page %s (scanned?)", p.name, page_number)
                continue
            pages.append(
                Document(
                    document_id=document_id,
                    text=text,
                    source=p.name,
                    metadata={"filename": p.name, "source_type": "pdf",
                              "page": page_number, "total_pages": len(pdf)},
                )
            )
    return pages
