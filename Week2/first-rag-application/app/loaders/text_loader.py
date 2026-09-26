"""Loader for plain-text (.txt) and Markdown (.md) files."""

from pathlib import Path
from typing import List

from app.core.utils import stable_id
from app.models.document import Document


def load_text_file(path: str | Path) -> List[Document]:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    return [
        Document(
            document_id=stable_id(p.name),        # file name -> re-uploading updates, not duplicates
            text=text,
            source=p.name,
            metadata={
                "filename": p.name,
                "source_type": p.suffix.lower().lstrip("."),   # "txt" or "md"
                "page": None,
                "size_bytes": p.stat().st_size,
            },
        )
    ]
