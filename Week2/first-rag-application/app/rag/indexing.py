"""
Ingestion: file -> chunks -> vectors -> Qdrant, with the registry tracking every step.

    file ─► registry: pending ─► load ─► changed? ──no──► skip
                                            │yes
                                            ▼
                         delete old points ─► chunk ─► embed ─► upsert ─► registry: completed
"""

import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from langsmith import traceable
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

from app.core.config import settings
from app.core.utils import batched, content_hash
from app.db.qdrant import (count_document_points, delete_document_points, ensure_collection,
                           get_qdrant_client, point_id_for)
from app.db.registry import get_registry
from app.loaders.dispatcher import list_supported_files, load_document
from app.models.document import Chunk, Document
from app.rag.chunking import chunk_documents
from app.rag.embeddings import embed_texts


def index_chunks(client: QdrantClient, collection_name: str,
                 chunks: List[Chunk], embeddings: List[List[float]]) -> int:
    if len(chunks) != len(embeddings):
        raise ValueError("Chunks and embeddings must have equal length.")
    if not chunks:
        return 0

    ensure_collection(client, collection_name, vector_size=len(embeddings[0]))

    points = [
        PointStruct(
            id=point_id_for(chunk.chunk_id),          # deterministic -> re-ingesting overwrites
            vector=vector,
            payload={"chunk_id": chunk.chunk_id, "document_id": chunk.document_id,
                     "source": chunk.source, "text": chunk.text, **chunk.metadata},
        )
        for chunk, vector in zip(chunks, embeddings)
    ]
    for batch in batched(points, 256):
        client.upsert(collection_name=collection_name, points=batch)
    return len(points)


@traceable(run_type="chain", name="ingest_documents",
           process_inputs=lambda i: {"num_documents": len(i["documents"]), "collection": i["collection_name"],
                                     "chunk_size": i.get("chunk_size"), "overlap": i.get("overlap")})
def ingest_documents(documents: List[Document], client: QdrantClient, collection_name: str,
                     chunk_size: Optional[int] = None, overlap: Optional[int] = None) -> List[Chunk]:
    # The pure "vector side": normalize + chunk -> batch embed -> index
    chunk_size = chunk_size or settings.chunk_size
    overlap = settings.chunk_overlap if overlap is None else overlap

    chunks = chunk_documents(documents, chunk_size, overlap)
    embeddings = embed_texts([c.text for c in chunks])
    index_chunks(client, collection_name, chunks, embeddings)
    return chunks


@traceable(run_type="chain", name="ingest_file",
           process_inputs=lambda i: {"path": str(i["path"]), "force": i.get("force")})
def ingest_file(path: str | Path, client: Optional[QdrantClient] = None,
                collection_name: Optional[str] = None, force: bool = False) -> Dict[str, Any]:
    # The "product side": register, skip unchanged files, clean old points, ingest, mark status
    client = client or get_qdrant_client()
    collection_name = collection_name or settings.collection_name
    registry = get_registry()
    p = Path(path)
    start = time.perf_counter()

    documents = load_document(p)                                   # 1. load + extract
    if not documents:
        raise ValueError(f"No extractable text in {p.name}")
    document_id = documents[0].document_id
    file_hash = content_hash("".join(d.text for d in documents))

    existing = registry.get_document(document_id)                  # 2. unchanged? skip it
    if (not force and existing and existing["content_hash"] == file_hash
            and existing["ingestion_status"] == "completed"
            and existing["qdrant_collection"] == collection_name
            # the vectors must really be there (in-memory Qdrant is empty after a restart)
            and count_document_points(client, collection_name, document_id) == existing["num_chunks"]):
        return {"document_id": document_id, "filename": p.name, "status": "skipped (unchanged)",
                "chunks": existing["num_chunks"], "seconds": 0.0}

    registry.upsert_document({
        "document_id": document_id, "filename": p.name, "source_uri": str(p),
        "source_type": documents[0].metadata["source_type"], "content_hash": file_hash,
        "num_pages": len(documents) if p.suffix.lower() == ".pdf" else None,
        "qdrant_collection": collection_name,
    })
    try:
        delete_document_points(client, collection_name, document_id)   # 3. remove stale chunks
        chunks = ingest_documents(documents, client, collection_name)   # 4. chunk + embed + index
        registry.replace_chunks(document_id, chunks)
        registry.mark_completed(document_id, len(chunks))               # 5. done
    except Exception as exc:
        registry.mark_failed(document_id, str(exc))
        raise

    return {"document_id": document_id, "filename": p.name, "status": "completed",
            "chunks": len(chunks), "seconds": round(time.perf_counter() - start, 2)}


def ingest_directory(folder: str | Path, force: bool = False) -> List[Dict[str, Any]]:
    return [ingest_file(f, force=force) for f in list_supported_files(folder)]
