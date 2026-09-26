"""
LangSmith tracing helpers.

The pipeline functions are decorated with `@traceable` (from the langsmith SDK) directly in
their own modules. This file only holds the small helpers those decorators use, plus `flush()`.
When LANGSMITH_TRACING is not "true", `@traceable` does nothing and these helpers are never called.
"""

from typing import Any, Dict

from app.core.config import settings


def summarize_vectors(output: Any) -> Dict[str, Any]:
    # Don't upload thousands of floats to LangSmith; log the shape instead
    vectors = output.get("output", output) if isinstance(output, dict) else output
    return {"num_vectors": len(vectors), "dim": len(vectors[0]) if vectors else 0}


def summarize_hits(output: Any) -> Dict[str, Any]:
    # Keep retriever traces readable: source, page, score and a text preview per hit
    hits = output.get("output", output) if isinstance(output, dict) else output
    return {"hits": [{"rank": h["rank"], "score": round(h["score"], 4), "source": h["payload"]["source"],
                      "page": h["payload"].get("page"), "text": h["payload"]["text"][:300]} for h in hits]}


def flush(timeout: float = 30) -> None:
    # Traces are uploaded in a background thread; call this before a script exits
    if settings.tracing_enabled:
        from langsmith.run_trees import get_cached_client
        get_cached_client().flush(timeout=timeout)
