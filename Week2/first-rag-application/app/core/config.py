"""
Application settings, read once from environment variables / the .env file.

Every other module does:
    from app.core.config import settings
and reads e.g. settings.chunk_size. One source of truth means the embedding model,
vector size and collection name can never drift apart between files.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

from dotenv import load_dotenv
from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Put .env values into os.environ too. The LangSmith SDK reads its LANGSMITH_* variables
# straight from os.environ, so pydantic-settings alone is not enough.
load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    # --- EURI (OpenAI-compatible gateway) ---
    euri_api_key: Optional[str] = None
    euri_base_url: str = "https://api.euron.one/api/v1"
    chat_model: str = Field("gpt-4.1-mini", validation_alias="EURI_CHAT_MODEL")
    embedding_model: str = Field("text-embedding-3-small", validation_alias="EURI_EMBEDDING_MODEL")

    # --- Vector store: "memory" (default) or "cloud" (Qdrant Cloud / any Qdrant server) ---
    vector_store: Literal["memory", "cloud"] = "memory"
    qdrant_url: Optional[str] = None
    qdrant_api_key: Optional[str] = None
    collection_name: str = Field("novacart_first_rag", validation_alias="QDRANT_COLLECTION")

    # --- Document registry: "sqlite" (default) or "supabase" ---
    registry_backend: Literal["sqlite", "supabase"] = "sqlite"
    sqlite_path: str = "rag_registry.db"
    # DATABASE_URL / DATABASE_KEY are accepted as older names for the same two values
    supabase_url: Optional[str] = Field(None, validation_alias=AliasChoices("SUPABASE_URL", "DATABASE_URL"))
    supabase_key: Optional[str] = Field(None, validation_alias=AliasChoices("SUPABASE_KEY", "DATABASE_KEY"))

    # --- LangSmith tracing (the SDK itself reads LANGSMITH_API_KEY etc. from the environment) ---
    tracing_enabled: bool = Field(False, validation_alias="LANGSMITH_TRACING")
    langsmith_project: str = "default"

    # --- RAG knobs ---
    chunk_size: int = 120            # words per chunk
    chunk_overlap: int = 20          # words repeated between neighbouring chunks
    embed_batch_size: int = 64
    top_k: int = 5
    max_context_chars: int = 12000
    temperature: float = Field(0.1, validation_alias="LLM_TEMPERATURE")

    # --- Files ---
    data_dir: Path = Path("data")
    upload_dir: Path = Path("data/uploads")
    allowed_extensions: tuple[str, ...] = (".txt", ".md", ".pdf", ".docx")

    # --- API ---
    # Index everything in data/ when the server starts, so Swagger works immediately
    # (essential with in-memory Qdrant, which is empty after every restart).
    auto_ingest_on_startup: bool = True

    @model_validator(mode="after")
    def check_backend_credentials(self) -> "Settings":
        # Fail at startup with a clear message instead of a confusing error on the first request
        if self.vector_store == "cloud" and not self.qdrant_url:
            raise ValueError("VECTOR_STORE=cloud needs QDRANT_URL (and QDRANT_API_KEY for Qdrant Cloud)")
        if self.registry_backend == "supabase" and not (self.supabase_url and self.supabase_key):
            raise ValueError("REGISTRY_BACKEND=supabase needs SUPABASE_URL and SUPABASE_KEY")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
