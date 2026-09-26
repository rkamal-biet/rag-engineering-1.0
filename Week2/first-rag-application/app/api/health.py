"""GET /health — service, vector store and registry status."""

from fastapi import APIRouter

from app.core.config import settings
from app.db.qdrant import count_points, get_qdrant_client
from app.db.registry import get_registry
from app.models.api import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    registry = get_registry()
    return HealthResponse(
        status="ok",
        collection=settings.collection_name,
        points=count_points(get_qdrant_client(), settings.collection_name),
        documents=len(registry.list_documents()),
        vector_store=settings.vector_store,
        registry_backend=registry.backend,
        tracing=settings.tracing_enabled,
    )
