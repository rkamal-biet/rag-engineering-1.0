"""Small helpers shared across the application."""

import hashlib
from datetime import datetime, timezone
from typing import Any, Iterable, List


def stable_id(value: str, prefix: str = "doc") -> str:
    # Same input -> same ID, every time, on every machine
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def content_hash(text: str) -> str:
    # Fingerprint of the content: tells us whether a file actually changed
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def batched(items: List[Any], batch_size: int) -> Iterable[List[Any]]:
    for i in range(0, len(items), batch_size):
        yield items[i:i + batch_size]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
