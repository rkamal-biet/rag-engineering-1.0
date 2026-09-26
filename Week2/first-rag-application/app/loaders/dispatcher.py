"""
One entry point for every file type. The rest of the pipeline never cares about formats:
it calls load_document(path) and gets back a list of Documents.
"""

from pathlib import Path
from typing import List

from app.core.config import settings
from app.loaders.docx_loader import load_docx
from app.loaders.pdf_loader import load_pdf
from app.loaders.text_loader import load_text_file
from app.models.document import Document

LOADERS = {
    ".txt": load_text_file,
    ".md": load_text_file,
    ".pdf": load_pdf,
    ".docx": load_docx,
}


def validate_document_filename(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix not in settings.allowed_extensions:
        raise ValueError(f"Unsupported file type '{suffix}'. Allowed: {list(settings.allowed_extensions)}")
    return suffix


def load_document(path: str | Path) -> List[Document]:
    suffix = validate_document_filename(str(path))
    return LOADERS[suffix](path)


def list_supported_files(folder: str | Path) -> List[Path]:
    # Top-level files only: data/archive/ and data/uploads/ are NOT picked up
    return [f for f in sorted(Path(folder).iterdir())
            if f.is_file() and f.suffix.lower() in settings.allowed_extensions]


def load_directory(folder: str | Path) -> List[Document]:
    documents = []
    for f in list_supported_files(folder):
        documents.extend(load_document(f))
    return documents
