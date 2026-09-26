"""
Qdrant connection + collection helpers.

VECTOR_STORE=memory -> QdrantClient(":memory:"): lives inside this Python process, empty after restart
VECTOR_STORE=cloud  -> Qdrant Cloud (or any Qdrant server): persistent and shared
The rest of the code never checks which one it is; QdrantClient has the same methods either way.
"""

import uuid
from functools import lru_cache

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, FieldCondition, Filter, FilterSelector, MatchValue, VectorParams

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)

FILTER_FIELDS = ("document_id", "source")     # payload fields we filter on


@lru_cache
def get_qdrant_client() -> QdrantClient:
    # lru_cache -> one client for the whole process (critical for ":memory:", or every call
    # would get its own empty database)
    if settings.vector_store == "cloud":
        # timeout=60: the first calls to a cloud cluster can be slow while it wakes up
        return QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key, timeout=60)
    return QdrantClient(":memory:")


def point_id_for(chunk_id: str) -> str:
    # Qdrant IDs must be an integer or a UUID -> turn our chunk_id into a stable UUID
    return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))


def document_filter(document_id: str) -> Filter:
    return Filter(must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))])


def ensure_collection(client: QdrantClient, collection_name: str, vector_size: int) -> None:
    if client.collection_exists(collection_name):
        existing_size = client.get_collection(collection_name).config.params.vectors.size
        if existing_size != vector_size:
            raise ValueError(
                f"Collection '{collection_name}' has vectors of size {existing_size}, but the embedding "
                f"model returns {vector_size}. Use a new collection name or delete the old one."
            )
    else:
        client.create_collection(collection_name=collection_name,
                                 vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE))
        log.info("Created collection '%s' (dim=%s, cosine)", collection_name, vector_size)

    # Payload indexes make metadata filters fast. Qdrant Cloud can REFUSE to filter on a field
    # without one ("Index required but not found"). Re-creating an existing index is harmless.
    if settings.vector_store == "cloud":
        for key in FILTER_FIELDS:
            client.create_payload_index(collection_name, field_name=key, field_schema="keyword")


def delete_document_points(client: QdrantClient, collection_name: str, document_id: str) -> None:
    # Remove old chunks before re-indexing a changed document (otherwise stale chunks linger)
    if client.collection_exists(collection_name):
        client.delete(collection_name=collection_name,
                      points_selector=FilterSelector(filter=document_filter(document_id)))


def count_points(client: QdrantClient, collection_name: str) -> int:
    if not client.collection_exists(collection_name):
        return 0
    return client.count(collection_name, exact=True).count


def count_document_points(client: QdrantClient, collection_name: str, document_id: str) -> int:
    if not client.collection_exists(collection_name):
        return 0
    return client.count(collection_name, exact=True, count_filter=document_filter(document_id)).count
