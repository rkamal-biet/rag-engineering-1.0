"""
Context construction: decide what the LLM actually reads.
Every chunk gets a stable label [S1], [S2]... with its source and page, duplicates are dropped,
and we stop at a character budget (a simple stand-in for a token budget).
"""

from typing import Any, Dict, List, Optional, Tuple

from langsmith import traceable

from app.core.config import settings


@traceable(run_type="chain", name="build_context",
           process_inputs=lambda i: {"num_hits": len(i["hits"]), "max_chars": i.get("max_chars")})
def build_context(hits: List[Dict[str, Any]],
                  max_chars: Optional[int] = None) -> Tuple[str, List[Dict[str, Any]]]:
    max_chars = max_chars or settings.max_context_chars
    blocks, sources, seen_texts, used = [], [], set(), 0

    for hit in hits:
        p = hit["payload"]
        if p["text"] in seen_texts:                  # skip exact duplicates
            continue

        source_id = f"S{len(sources) + 1}"
        page = f", page {p['page']}" if p.get("page") else ""
        block = f"[{source_id}] (source: {p['source']}{page})\n{p['text']}\n"

        if used + len(block) > max_chars:            # context budget reached
            break

        blocks.append(block)
        seen_texts.add(p["text"])
        used += len(block)
        sources.append({
            "source_id": source_id, "document_id": p["document_id"], "chunk_id": p["chunk_id"],
            "source": p["source"], "page": p.get("page"), "score": round(hit["score"], 4),
        })

    return "\n".join(blocks), sources
