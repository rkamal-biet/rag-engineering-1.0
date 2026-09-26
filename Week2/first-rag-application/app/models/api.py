"""Request and response schemas for the HTTP API (these also drive the Swagger UI)."""

from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class RAGQueryRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [
        {"question": "How many days of annual leave do employees get?", "top_k": 5},
        {"question": "How long does a UPI refund take?", "top_k": 3, "source_filter": "refund_policy.md"},
    ]})

    question: str = Field(min_length=2, max_length=5000)
    top_k: int = Field(default=5, ge=1, le=20)
    source_filter: Optional[str] = Field(default=None, description="Only search inside this file name")


class SourceItem(BaseModel):
    source_id: str
    document_id: str
    chunk_id: str
    source: str
    page: Optional[int] = None
    score: float
    cited: bool = False


class RAGQueryResponse(BaseModel):
    question: str
    answer: str
    sources: List[SourceItem]
    invalid_citations: List[str] = []
    metrics: Dict[str, Optional[float]]


class DocumentRecord(BaseModel):
    document_id: str
    filename: str
    source_type: Optional[str] = None
    ingestion_status: str
    num_pages: Optional[int] = None
    num_chunks: Optional[int] = 0
    error_message: Optional[str] = None
    updated_at: Optional[str] = None


class DocumentDetail(DocumentRecord):
    chunks_in_registry: int
    points_in_qdrant: int


class IngestResponse(BaseModel):
    document_id: str
    filename: str
    status: str
    chunks: int
    seconds: float


class HealthResponse(BaseModel):
    status: str
    collection: str
    points: int
    documents: int
    vector_store: str
    registry_backend: str
    tracing: bool
