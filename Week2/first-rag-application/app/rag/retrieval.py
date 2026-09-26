"""
Similarity search: embed the question with the SAME model as the documents, then ask Qdrant
for the closest chunks. A high score means "close in vector space" — not true, fresh or allowed.
"""

from typing import Any, Dict, List, Optional

from langsmith import traceable
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue

from app.core.config import settings
from app.core.tracing import summarize_hits
from app.db.qdrant import get_qdrant_client
from app.rag.embeddings import embed_texts


@traceable(run_type="retriever", name="similarity_search", process_outputs=summarize_hits)
def similarity_search(question: str, client: Optional[QdrantClient] = None,
                      collection_name: Optional[str] = None, top_k: Optional[int] = None,
                      source_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    client = client or get_qdrant_client()
    collection_name = collection_name or settings.collection_name
    top_k = top_k or settings.top_k

    if not client.collection_exists(collection_name):
        return []

    query_vector = embed_texts([question])[0]

    query_filter = None                  # optional metadata filter, e.g. only search inside one file
    if source_filter:
        query_filter = Filter(must=[FieldCondition(key="source", match=MatchValue(value=source_filter))])

    response = client.query_points(collection_name=collection_name, query=query_vector,
                                   query_filter=query_filter, limit=top_k, with_payload=True)

    return [{"rank": rank, "score": float(p.score), "payload": p.payload}
            for rank, p in enumerate(response.points, start=1)]
