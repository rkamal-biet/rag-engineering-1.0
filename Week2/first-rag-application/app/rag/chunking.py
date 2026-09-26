"""
Normalization + word-window chunking with overlap.

    words:   w1 ........ w120
                      w101 ........ w220        <- 20 words overlap
                                   w201 ........ w320
"""

import re
from typing import List

from app.core.utils import stable_id
from app.models.document import Chunk, Document


def normalize_text(text: str) -> str:
    # Light, non-destructive cleanup: punctuation and headings carry meaning, so keep them
    text = text.replace("\r\n", "\n").replace("\r", "\n")   # Windows/Mac line endings -> \n
    text = re.sub(r"[ \t]+", " ", text)                       # many spaces/tabs -> one space
    text = re.sub(r"\n{3,}", "\n\n", text)                    # 3+ blank lines -> 1 blank line
    return text.strip()


def chunk_document(document: Document, chunk_size: int = 120, overlap: int = 20) -> List[Chunk]:
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    words = normalize_text(document.text).split()
    page = document.metadata.get("page")
    chunks: List[Chunk] = []
    start, chunk_index = 0, 0

    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunks.append(
            Chunk(
                # document + page + position -> stable and unique
                chunk_id=stable_id(f"{document.document_id}::p{page}::c{chunk_index}", prefix="chunk"),
                document_id=document.document_id,
                text=" ".join(words[start:end]),
                source=document.source,
                metadata={**document.metadata, "chunk_index": chunk_index,
                          "word_start": start, "word_end": end},
            )
        )
        if end == len(words):
            break
        start = end - overlap          # step back by `overlap` words
        chunk_index += 1

    return chunks


def chunk_documents(documents: List[Document], chunk_size: int, overlap: int) -> List[Chunk]:
    all_chunks: List[Chunk] = []
    for d in documents:
        all_chunks.extend(chunk_document(d, chunk_size, overlap))
    return all_chunks
