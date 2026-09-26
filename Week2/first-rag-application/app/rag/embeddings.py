"""
Text -> vectors through EURI, with the three habits every pipeline needs:
batching (fewer calls), retries (networks fail) and caching (don't pay twice for the same text).
"""

import time
from typing import Dict, List, Optional

from langsmith import traceable

from app.core.config import settings
from app.core.logging import get_logger
from app.core.tracing import summarize_vectors
from app.core.utils import batched, content_hash
from app.rag.llm_client import get_llm_client

log = get_logger(__name__)

_embedding_cache: Dict[str, List[float]] = {}   # content hash -> vector (lives in memory)


def embed_batch_with_retry(texts: List[str], max_retries: int = 3) -> List[List[float]]:
    for attempt in range(max_retries):
        try:
            response = get_llm_client().embeddings.create(model=settings.embedding_model, input=texts)
            return [item.embedding for item in response.data]
        except Exception as exc:
            if attempt == max_retries - 1:
                raise
            wait = 2 ** attempt                   # exponential backoff: 1s, 2s, 4s ...
            log.warning("Embedding call failed (%s). Retrying in %ss...", exc, wait)
            time.sleep(wait)


@traceable(run_type="embedding", name="embed_texts", process_outputs=summarize_vectors)
def embed_texts(texts: List[str], batch_size: Optional[int] = None) -> List[List[float]]:
    batch_size = batch_size or settings.embed_batch_size
    keys = [content_hash(f"{settings.embedding_model}::{t}") for t in texts]

    # Only send texts we have never embedded before (and each unique text only once)
    missing = [(k, t) for k, t in zip(keys, texts) if k not in _embedding_cache]
    unique_missing = list(dict(missing).items())

    for batch in batched(unique_missing, batch_size):
        vectors = embed_batch_with_retry([t for _, t in batch])
        for (k, _), v in zip(batch, vectors):
            _embedding_cache[k] = v

    return [_embedding_cache[k] for k in keys]
