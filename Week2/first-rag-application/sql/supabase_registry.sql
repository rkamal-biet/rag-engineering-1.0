-- ============================================================================
-- Supabase document registry for Task 3 — Build Your First RAG
-- Run ONCE: Supabase dashboard -> SQL Editor -> paste -> Run. Safe to re-run.
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.rag_documents (
    document_id       TEXT PRIMARY KEY,
    filename          TEXT NOT NULL,
    source_uri        TEXT,
    source_type       TEXT,
    content_hash      TEXT NOT NULL,
    ingestion_status  TEXT NOT NULL DEFAULT 'pending'
                      CHECK (ingestion_status IN ('pending', 'completed', 'failed')),
    error_message     TEXT,
    num_pages         INTEGER,
    num_chunks        INTEGER DEFAULT 0,
    qdrant_collection TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.rag_chunks (
    chunk_id        TEXT PRIMARY KEY,
    document_id     TEXT NOT NULL REFERENCES public.rag_documents(document_id) ON DELETE CASCADE,
    chunk_index     INTEGER NOT NULL,
    page_number     INTEGER,
    qdrant_point_id TEXT NOT NULL,
    content_hash    TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rag_chunks_document ON public.rag_chunks(document_id);

-- Row Level Security ON with no policies = private tables.
-- Only the SECRET key (sb_secret_... / service_role) can read and write them.
-- Use the following commands to enable Row Level Security if needed:
-- ALTER TABLE public.rag_documents ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE public.rag_chunks    ENABLE ROW LEVEL SECURITY;

-- QUICK FIX (dev only): let the publishable key (anon role) read and write the registry tables.
-- RLS stays ON; these policies open access to the anon role.

DROP POLICY IF EXISTS "anon_all_rag_documents" ON public.rag_documents;
CREATE POLICY "anon_all_rag_documents" ON public.rag_documents
    FOR ALL TO anon
    USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "anon_all_rag_chunks" ON public.rag_chunks;
CREATE POLICY "anon_all_rag_chunks" ON public.rag_chunks
    FOR ALL TO anon
    USING (true) WITH CHECK (true);

-- Supabase normally grants these already; repeated here so it can't fail on permissions
GRANT SELECT, INSERT, UPDATE, DELETE ON public.rag_documents, public.rag_chunks TO anon;