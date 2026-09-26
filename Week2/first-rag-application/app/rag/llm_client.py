"""
One shared OpenAI-compatible client for EURI, used for both embeddings and chat.
EURI speaks the OpenAI API, so we use the official `openai` package and only change base_url.
"""

from typing import Optional

from langsmith.wrappers import wrap_openai
from openai import OpenAI

from app.core.config import settings

_client: Optional[OpenAI] = None


def get_llm_client() -> OpenAI:
    global _client
    if _client is None:                       # created lazily on first use
        if not settings.euri_api_key:
            raise RuntimeError("EURI_API_KEY is missing. Add it to your .env file.")
        _client = OpenAI(api_key=settings.euri_api_key, base_url=settings.euri_base_url)
        if settings.tracing_enabled:
            _client = wrap_openai(_client)    # every chat call now shows up in LangSmith
    return _client
