"""
Document registry: which files we have, their status, content hash and chunks.

Two interchangeable backends with the same methods, picked by REGISTRY_BACKEND:
    sqlite   (default) -> local file, Python's built-in sqlite3
    supabase           -> Supabase Postgres over HTTPS (run sql/supabase_registry.sql once first)
"""

import sqlite3
from functools import lru_cache
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.core.logging import get_logger
from app.core.utils import batched, content_hash, utc_now
from app.db.qdrant import point_id_for
from app.models.document import Chunk

log = get_logger(__name__)

SQLITE_SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS rag_documents (
        document_id       TEXT PRIMARY KEY,
        filename          TEXT NOT NULL,
        source_uri        TEXT,
        source_type       TEXT,
        content_hash      TEXT NOT NULL,
        ingestion_status  TEXT NOT NULL DEFAULT 'pending',   -- pending | completed | failed
        error_message     TEXT,
        num_pages         INTEGER,
        num_chunks        INTEGER DEFAULT 0,
        qdrant_collection TEXT,
        created_at        TEXT NOT NULL,
        updated_at        TEXT NOT NULL
    )""",
    """
    CREATE TABLE IF NOT EXISTS rag_chunks (
        chunk_id        TEXT PRIMARY KEY,
        document_id     TEXT NOT NULL REFERENCES rag_documents(document_id) ON DELETE CASCADE,
        chunk_index     INTEGER NOT NULL,
        page_number     INTEGER,
        qdrant_point_id TEXT NOT NULL,
        content_hash    TEXT NOT NULL,
        created_at      TEXT NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS idx_rag_chunks_document ON rag_chunks(document_id)",
]


def chunk_rows(document_id: str, chunks: List[Chunk]) -> List[Dict[str, Any]]:
    # One registry row per chunk — shared by both backends
    now = utc_now()
    return [{"chunk_id": c.chunk_id, "document_id": document_id, "chunk_index": c.metadata["chunk_index"],
             "page_number": c.metadata.get("page"), "qdrant_point_id": point_id_for(c.chunk_id),
             "content_hash": content_hash(c.text), "created_at": now} for c in chunks]


class SQLiteRegistry:
    backend = "sqlite"

    def __init__(self, path: str):
        self.conn = sqlite3.connect(path, check_same_thread=False)   # FastAPI runs handlers in threads
        self.conn.row_factory = sqlite3.Row
        for statement in SQLITE_SCHEMA:
            self.conn.execute(statement)
        self.conn.commit()

    def _run(self, sql: str, params: Any = ()) -> List[Dict[str, Any]]:
        rows = [dict(r) for r in self.conn.execute(sql, params).fetchall()]
        self.conn.commit()
        return rows

    def get_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        rows = self._run("SELECT * FROM rag_documents WHERE document_id = ?", (document_id,))
        return rows[0] if rows else None

    def list_documents(self) -> List[Dict[str, Any]]:
        return self._run("SELECT * FROM rag_documents ORDER BY filename")

    def upsert_document(self, record: Dict[str, Any]) -> None:
        self._run("""
            INSERT INTO rag_documents (document_id, filename, source_uri, source_type, content_hash,
                                       ingestion_status, num_pages, qdrant_collection, created_at, updated_at)
            VALUES (:document_id, :filename, :source_uri, :source_type, :content_hash,
                    'pending', :num_pages, :qdrant_collection, :now, :now)
            ON CONFLICT (document_id) DO UPDATE SET
                source_uri = excluded.source_uri, content_hash = excluded.content_hash,
                ingestion_status = 'pending', error_message = NULL, num_pages = excluded.num_pages,
                qdrant_collection = excluded.qdrant_collection, updated_at = excluded.updated_at
        """, {**record, "now": utc_now()})

    def mark_completed(self, document_id: str, num_chunks: int) -> None:
        self._run("UPDATE rag_documents SET ingestion_status = 'completed', num_chunks = ?, updated_at = ? "
                  "WHERE document_id = ?", (num_chunks, utc_now(), document_id))

    def mark_failed(self, document_id: str, error: str) -> None:
        self._run("UPDATE rag_documents SET ingestion_status = 'failed', error_message = ?, updated_at = ? "
                  "WHERE document_id = ?", (error[:1000], utc_now(), document_id))

    def replace_chunks(self, document_id: str, chunks: List[Chunk]) -> None:
        self.conn.execute("DELETE FROM rag_chunks WHERE document_id = ?", (document_id,))
        self.conn.executemany("""
            INSERT INTO rag_chunks (chunk_id, document_id, chunk_index, page_number, qdrant_point_id,
                                    content_hash, created_at)
            VALUES (:chunk_id, :document_id, :chunk_index, :page_number, :qdrant_point_id,
                    :content_hash, :created_at)""", chunk_rows(document_id, chunks))
        self.conn.commit()

    def count_chunks(self, document_id: str) -> int:
        return self._run("SELECT COUNT(*) AS n FROM rag_chunks WHERE document_id = ?", (document_id,))[0]["n"]


class SupabaseRegistry:
    backend = "supabase"

    def __init__(self, url: str, key: str):
        from supabase import create_client          # imported here: only needed for this backend
        if key.startswith("sb_publishable_"):
            log.warning("SUPABASE_KEY is a PUBLISHABLE key. With RLS on and no anon policies, writes fail. "
                        "Use the secret key (sb_secret_...) for server-side code.")
        self.db = create_client(url, key)
        try:                                        # fail fast with a helpful message
            self.db.table("rag_documents").select("document_id").limit(1).execute()
        except Exception as exc:
            raise RuntimeError(
                "Cannot read table 'rag_documents' in Supabase. Run sql/supabase_registry.sql in the "
                f"Supabase SQL Editor and check SUPABASE_KEY. Original error: {exc}"
            ) from exc

    def get_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        rows = self.db.table("rag_documents").select("*").eq("document_id", document_id).limit(1).execute().data
        return rows[0] if rows else None

    def list_documents(self) -> List[Dict[str, Any]]:
        return self.db.table("rag_documents").select("*").order("filename").execute().data

    def upsert_document(self, record: Dict[str, Any]) -> None:
        now = utc_now()
        existing = self.get_document(record["document_id"])
        self.db.table("rag_documents").upsert({
            **record, "ingestion_status": "pending", "error_message": None,
            "created_at": existing["created_at"] if existing else now, "updated_at": now,
        }, on_conflict="document_id").execute()

    def mark_completed(self, document_id: str, num_chunks: int) -> None:
        self.db.table("rag_documents").update({"ingestion_status": "completed", "num_chunks": num_chunks,
                                               "updated_at": utc_now()}).eq("document_id", document_id).execute()

    def mark_failed(self, document_id: str, error: str) -> None:
        self.db.table("rag_documents").update({"ingestion_status": "failed", "error_message": error[:1000],
                                               "updated_at": utc_now()}).eq("document_id", document_id).execute()

    def replace_chunks(self, document_id: str, chunks: List[Chunk]) -> None:
        self.db.table("rag_chunks").delete().eq("document_id", document_id).execute()
        for batch in batched(chunk_rows(document_id, chunks), 500):   # one HTTP call per 500 rows
            self.db.table("rag_chunks").insert(batch).execute()

    def count_chunks(self, document_id: str) -> int:
        return self.db.table("rag_chunks").select("chunk_id", count="exact") \
                      .eq("document_id", document_id).execute().count


@lru_cache
def get_registry() -> SQLiteRegistry | SupabaseRegistry:
    # One registry object per process, chosen by REGISTRY_BACKEND
    if settings.registry_backend == "supabase":
        return SupabaseRegistry(settings.supabase_url, settings.supabase_key)
    return SQLiteRegistry(settings.sqlite_path)
