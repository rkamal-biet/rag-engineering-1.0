"""
The full RAG pipeline with source attribution.

    retrieval hit ─► payload (file, page, chunk_id) ─► label [S1] ─► context ─► answer cites [S1]
                                                              └────────► sources returned to the user

Citations come from OUR data, never from the model's memory, and every [S#] the model uses is checked.
"""

import re
import time
from typing import Any, Dict, List, Optional

from langsmith import traceable
from qdrant_client import QdrantClient

from app.rag.context import build_context
from app.rag.generation import generate_answer
from app.rag.prompting import ABSTAIN_MESSAGE, create_rag_prompt
from app.rag.retrieval import similarity_search


def extract_citations(answer: str) -> List[str]:
    return sorted(set(re.findall(r"\[(S\d+)\]", answer)), key=lambda s: int(s[1:]))


@traceable(run_type="chain", name="rag_pipeline")
def answer_question(question: str, top_k: Optional[int] = None, client: Optional[QdrantClient] = None,
                    collection_name: Optional[str] = None,
                    source_filter: Optional[str] = None) -> Dict[str, Any]:
    t0 = time.perf_counter()
    hits = similarity_search(question, client=client, collection_name=collection_name,
                             top_k=top_k, source_filter=source_filter)
    retrieval_ms = (time.perf_counter() - t0) * 1000

    context, sources = build_context(hits)

    t1 = time.perf_counter()
    if not sources:                                    # nothing retrieved -> don't even call the LLM
        generation = {"text": ABSTAIN_MESSAGE, "prompt_tokens": 0, "completion_tokens": 0}
    else:
        generation = generate_answer(create_rag_prompt(question, context))
    generation_ms = (time.perf_counter() - t1) * 1000

    cited = extract_citations(generation["text"])
    valid_ids = {s["source_id"] for s in sources}
    for s in sources:
        s["cited"] = s["source_id"] in cited

    return {
        "question": question,
        "answer": generation["text"],
        "sources": sources,
        "invalid_citations": [c for c in cited if c not in valid_ids],   # should always be []
        "metrics": {
            "retrieval_ms": round(retrieval_ms, 2),
            "generation_ms": round(generation_ms, 2),
            "total_ms": round((time.perf_counter() - t0) * 1000, 2),
            "prompt_tokens": generation["prompt_tokens"],
            "completion_tokens": generation["completion_tokens"],
        },
    }
