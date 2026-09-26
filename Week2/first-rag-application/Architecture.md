# Architecture — NovaCart First RAG

## 1. The two flows

```text
INGESTION  (startup, POST /documents/upload, scripts/ingest.py)

 file ─► loaders/dispatcher ─► Document(s) ─► rag/chunking ─► Chunk(s) ─► rag/embeddings (EURI)
                                                                              │
                         db/registry  ◄── status, hash, chunk rows ──  rag/indexing ─► db/qdrant (upsert)

QUERY  (POST /rag/query)

 question ─► rag/retrieval ─► embed question (EURI) ─► Qdrant top-k ─► rag/context  [S1] [S2] …
                                                                          │
          answer + sources + metrics ◄── rag/pipeline (citation check) ◄── rag/generation (EURI LLM)
                                                                          ▲
                                                                  rag/prompting (grounded prompt)
```

## 2. Layers

| Layer | Package | Knows about | Never knows about |
|---|---|---|---|
| HTTP | `app/api`, `app/main.py` | request/response schemas, status codes | Qdrant, SQL, EURI |
| Pipeline | `app/rag` | chunks, vectors, prompts | HTTP |
| Storage | `app/db` | Qdrant, SQLite/Supabase | prompts, HTTP |
| Input | `app/loaders` | file formats | storage, LLM |
| Cross-cutting | `app/core` | settings, logging, tracing, ids | everything else |

Dependencies point downward only (api → rag → db/loaders → core), so there are no import cycles.

## 3. Key design decisions

| Decision | Why |
|---|---|
| **Deterministic IDs** (`document_id` from the file name, `chunk_id` from document + page + position, Qdrant id = uuid5(chunk_id)) | Re-ingesting overwrites points instead of duplicating them. The chapter's `id = 1, 2, 3…` overwrote earlier files. |
| **Delete-then-reindex per document** | A shorter new version of a file leaves no stale chunks behind. |
| **Content-hash skip** | Unchanged files are never re-embedded, so restarts with Qdrant Cloud cost nothing. |
| **Registry separate from Qdrant** | Qdrant answers "what is similar?"; the registry answers "what do we have, is it complete, did it fail?". |
| **Backend switches** (`VECTOR_STORE`, `REGISTRY_BACKEND`) | Offline by default (tests, class), cloud with one word; credentials can stay in `.env` either way. |
| **One cached client per process** (`lru_cache` on `get_qdrant_client`, `get_registry`) | Essential for `:memory:` Qdrant (a new client would be a new, empty database) and avoids reconnecting on every request. |
| **Citations built from payload metadata** | The model only chooses *which* `[S#]` to cite; file names and pages always come from our data. Unknown labels are reported in `invalid_citations`. |
| **Abstention sentence + no-LLM shortcut** | An empty retrieval never reaches the model; out-of-scope questions get a fixed, testable answer. |
| **Plain `def` endpoints** | FastAPI runs them in a thread pool, so a slow ingestion does not block other requests. |
| **Tracing via `@traceable` + `wrap_openai`** | Zero cost when disabled; vectors are summarized, not uploaded. |

## 4. Configuration

All settings live in `app/core/config.py` (pydantic-settings). They are read from environment
variables and `.env`, validated at startup (e.g. `VECTOR_STORE=cloud` without `QDRANT_URL`
fails immediately with a clear message), and imported everywhere as
`from app.core.config import settings`.

## 5. Testing strategy

`tests/conftest.py` sets environment variables **before** the app is imported: in-memory Qdrant,
a temporary SQLite file, tracing off. It also injects a fake EURI client (hash-based embeddings,
echo answers). The suite therefore runs offline, needs no API key and never touches cloud
resources, while still going through the real FastAPI app, lifespan, Qdrant and SQL code.

## 6. Known limits (next chapters)

Word-window chunking only · no hybrid search or reranking · synchronous ingestion inside the upload
request · no auth / multi-tenancy / ACLs · uploads are not re-indexed after a restart with in-memory
Qdrant · evaluation uses string checks rather than an LLM judge.
