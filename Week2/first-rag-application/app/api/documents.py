"""
Document endpoints: upload (+ ingest), list, get one.

Note: ingestion runs inside the upload request. Fine for small files; production systems return
202 Accepted immediately and ingest in a background job/queue.
"""

from pathlib import Path
from typing import List

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.core.config import settings
from app.core.logging import get_logger
from app.db.qdrant import count_document_points, get_qdrant_client
from app.db.registry import get_registry
from app.loaders.dispatcher import validate_document_filename
from app.models.api import DocumentDetail, DocumentRecord, IngestResponse
from app.rag.indexing import ingest_file

router = APIRouter(prefix="/documents", tags=["documents"])
log = get_logger(__name__)


@router.post("/upload", response_model=IngestResponse)
def upload_document(file: UploadFile = File(..., description="A .pdf, .docx, .md or .txt file")):
    # A plain `def` endpoint: FastAPI runs it in a worker thread, so slow ingestion
    # does not block other requests.
    try:
        validate_document_filename(file.filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    destination = settings.upload_dir / Path(file.filename).name     # .name blocks "../../" tricks
    destination.write_bytes(file.file.read())

    try:
        return ingest_file(destination)
    except Exception as exc:
        log.exception("Ingestion failed for %s", file.filename)
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {exc}")


@router.get("", response_model=List[DocumentRecord])
def list_documents():
    return get_registry().list_documents()


@router.get("/{document_id}", response_model=DocumentDetail)
def get_document(document_id: str):
    registry = get_registry()
    doc = registry.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return {
        **doc,
        "chunks_in_registry": registry.count_chunks(document_id),
        "points_in_qdrant": count_document_points(get_qdrant_client(), settings.collection_name, document_id),
    }
