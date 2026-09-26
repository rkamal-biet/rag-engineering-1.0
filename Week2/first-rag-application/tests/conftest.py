"""
Shared test setup. Tests run fully OFFLINE:
- in-memory Qdrant + a temporary SQLite file (never your cloud resources)
- a fake EURI client (deterministic hash embeddings, echo-style answers), so no API key or credits
"""

import hashlib
import os
import re
import tempfile
from types import SimpleNamespace

import pytest

# Must be set BEFORE anything imports app.core.config (settings are read once, at import time).
# Real environment variables win over .env, so your .env is ignored for these keys.
_tmp = tempfile.mkdtemp(prefix="first_rag_tests_")
os.environ.update({
    "VECTOR_STORE": "memory",
    "REGISTRY_BACKEND": "sqlite",
    "SQLITE_PATH": os.path.join(_tmp, "registry.db"),
    "UPLOAD_DIR": os.path.join(_tmp, "uploads"),
    "LANGSMITH_TRACING": "false",
    "EURI_API_KEY": "test-key",
    "AUTO_INGEST_ON_STARTUP": "true",
})

from app.rag import llm_client  # noqa: E402  (import after the env vars above)


def fake_embedding(text: str, dim: int = 256) -> list[float]:
    # Bag-of-words hashed into a fixed-size vector: same words -> similar vectors
    vector = [0.0] * dim
    for word in re.findall(r"[a-z0-9]+", text.lower()):
        vector[int(hashlib.md5(word.encode()).hexdigest(), 16) % dim] += 1.0
    norm = sum(v * v for v in vector) ** 0.5 or 1.0
    return [v / norm for v in vector]


class FakeEuriClient:
    def __init__(self):
        self.embeddings = SimpleNamespace(create=self._embed)
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._chat))

    @staticmethod
    def _embed(model, input):
        return SimpleNamespace(data=[SimpleNamespace(embedding=fake_embedding(t)) for t in input])

    @staticmethod
    def _chat(model, messages, **kwargs):
        # Answer with the first line of source [S1] and cite it
        match = re.search(r"\[S1\] \(source: [^)]*\)\n(.*)", messages[-1]["content"])
        text = f"{match.group(1)[:150]} [S1]" if match else "No context."
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))],
                               usage=SimpleNamespace(prompt_tokens=100, completion_tokens=20))


@pytest.fixture(autouse=True, scope="session")
def fake_llm():
    llm_client._client = FakeEuriClient()     # get_llm_client() returns this cached client
    yield
    llm_client._client = None
