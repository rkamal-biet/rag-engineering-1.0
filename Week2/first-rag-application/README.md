# Task 1 — Build Your First RAG Application

An end-to-end **document question-answering RAG** built from scratch in plain Python (no LangChain),
so every step of the data flow is visible. Based on Chapter 2, *Building Your First RAG*.

Use case: **NovaCart**, a *fictional* e-commerce company. All documents are synthetic.

**Stack:** Euron EURI (embeddings + LLM) · Qdrant (in-memory or Cloud) · SQLite or Supabase · FastAPI · LangSmith

The project comes in two forms:

| Phase | What | Where |
|---|---|---|
| 1 | Teaching notebook: every step explained, one section per module | `first_rag_application.ipynb` |
| 2 | Modular application + API | `app/`, `scripts/`, `tests/` |

---

## Quick start (API + Swagger UI)

```bash
python -m venv venv && venv\Scripts\activate        # Windows  (macOS/Linux: source venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env                               # add your EURI_API_KEY

python run.py
```

Open **http://127.0.0.1:8000/docs**. At startup the server indexes everything in `data/`
(unchanged files are skipped), so you can query straight away:

1. `GET /health`: `points` should be > 0
2. `POST /rag/query` → **Try it out** → pick an example → **Execute**
3. `POST /documents/upload`: upload your own `.pdf/.docx/.md/.txt`, then ask about it

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | status, point count, document count, active backends |
| POST | `/documents/upload` | upload a file → validate → ingest |
| GET | `/documents` | list registered documents |
| GET | `/documents/{document_id}` | one document + chunk/point counts |
| POST | `/rag/query` | `{question, top_k, source_filter}` → answer + sources + metrics |

## Other commands

```bash
python -m pytest                      # 18 offline tests (fake EURI, in-memory Qdrant, temp SQLite)
python -m scripts.ingest [--force]    # index data/ from the command line (useful with Qdrant Cloud)
python -m scripts.evaluate            # 22 test questions -> Success@k, MRR, answer checks + CSV
python make_dataset.py                # rebuild the sample documents in data/
```

Always run commands from the project root. `python -m scripts.x` (not `python scripts/x.py`)
keeps the root on the import path, so `from app...` imports work.

## Backends: offline by default, cloud with one word

| Setting in `.env` | Default | Cloud value | Also needs |
|---|---|---|---|
| `VECTOR_STORE` | `memory` (in-memory Qdrant) | `cloud` (Qdrant Cloud) | `QDRANT_URL`, `QDRANT_API_KEY` |
| `REGISTRY_BACKEND` | `sqlite` (`rag_registry.db`) | `supabase` | `SUPABASE_URL`, `SUPABASE_KEY` |
| `LANGSMITH_TRACING` | `false` | `true` | `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT` |

- **Supabase one-time setup:** SQL Editor → run `sql/supabase_registry.sql`. Use the **secret** key
  (`sb_secret_…`); the publishable key is rejected by Row Level Security.
  `DATABASE_URL` / `DATABASE_KEY` are accepted as older names for `SUPABASE_URL` / `SUPABASE_KEY`.
- **In-memory Qdrant** is empty after every restart, so the server re-indexes `data/` at startup
  (`AUTO_INGEST_ON_STARTUP=true`). Uploaded files are not re-indexed; use Qdrant Cloud to keep them.
- **LangSmith:** each question is one `rag_pipeline` trace with `similarity_search`, `build_context`,
  `generate_answer` and the LLM call nested inside it.

## Project layout

```text
first-rag-application/
├── app/
│   ├── main.py                  FastAPI app, routers, startup ingestion
│   ├── api/
│   │   ├── health.py            GET  /health
│   │   ├── documents.py         POST /documents/upload · GET /documents · GET /documents/{id}
│   │   └── query.py             POST /rag/query
│   ├── core/
│   │   ├── config.py            Settings (pydantic-settings, reads .env)
│   │   ├── logging.py           get_logger
│   │   ├── tracing.py           LangSmith helpers + flush()
│   │   └── utils.py             stable_id, content_hash, batched, utc_now
│   ├── loaders/
│   │   ├── text_loader.py       .txt / .md
│   │   ├── pdf_loader.py        .pdf (one Document per page)
│   │   ├── docx_loader.py       .docx
│   │   ├── web_loader.py        web pages (bonus)
│   │   └── dispatcher.py        load_document(): picks the loader by extension
│   ├── rag/
│   │   ├── chunking.py          normalize + word-window chunking
│   │   ├── llm_client.py        shared EURI (OpenAI-compatible) client
│   │   ├── embeddings.py        batched, retried, cached embeddings
│   │   ├── indexing.py          ingest_file / ingest_directory → Qdrant + registry
│   │   ├── retrieval.py         similarity_search (+ source filter)
│   │   ├── context.py           build_context → [S1], [S2] …
│   │   ├── prompting.py         grounded system prompt
│   │   ├── generation.py        LLM call
│   │   └── pipeline.py          answer_question + citation checks
│   ├── db/
│   │   ├── qdrant.py            client (memory/cloud) + collection helpers
│   │   └── registry.py          SQLiteRegistry, SupabaseRegistry, get_registry()
│   └── models/
│       ├── document.py          Document, Chunk
│       └── api.py               request/response schemas (drive Swagger)
├── scripts/                     ingest.py, evaluate.py
├── tests/                       conftest.py (offline fakes), test_chunking/loaders/api.py
├── data/                        sample documents (archive/ = old version, not indexed)
├── sql/supabase_registry.sql    run once in Supabase
├── evaluation/                  evaluation_sheet.csv (written by scripts/evaluate.py)
├── first_rag_application.ipynb
├── make_dataset.py · run.py · pyproject.toml · requirements.txt
├── .env.example · .gitignore
├── README.md
└── Architecture.md
```

Imports are always absolute and point at the module that defines the thing
(`from app.rag.pipeline import answer_question`). Every `__init__.py` is empty; it only marks
the folder as a package.

Differences from the chapter's Section 17 layout: `db/postgres.py` became `db/registry.py`
(it holds both SQLite and Supabase), and `api/health.py`, `rag/pipeline.py`, `rag/llm_client.py`,
`loaders/dispatcher.py`, `core/tracing.py` and `core/utils.py` were added so each file has one job.

See **Architecture.md** for the request flows and design decisions.
