"""
FastAPI application: creates the app, wires the routers, and (optionally) indexes data/ at startup.

Run:   python run.py            (or: uvicorn app.main:app --reload)
Open:  http://127.0.0.1:8000/docs
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from app.api import documents, health, query
from app.core.config import settings
from app.core.logging import get_logger
from app.core.tracing import flush
from app.rag.indexing import ingest_directory

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- startup ---
    log.info("Vector store: %s | registry: %s | tracing: %s",
             settings.vector_store, settings.registry_backend, settings.tracing_enabled)
    if settings.auto_ingest_on_startup and settings.data_dir.exists():
        # Unchanged files are skipped, so this is cheap with Qdrant Cloud and
        # essential with in-memory Qdrant (empty after every restart).
        for result in ingest_directory(settings.data_dir):
            log.info("Startup ingest: %-32s %s (%s chunks)", result["filename"], result["status"], result["chunks"])
    yield
    # --- shutdown ---
    flush()                                    # upload any pending LangSmith traces


app = FastAPI(
    title="NovaCart — First RAG API",
    version="1.0.0",
    description="Document question answering over NovaCart's (fictional) policies. "
                "EURI embeddings + LLM · Qdrant · SQLite/Supabase registry · LangSmith tracing.",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(documents.router)
app.include_router(query.router)


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")       # opening the base URL lands on Swagger UI
