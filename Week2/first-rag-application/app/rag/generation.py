"""LLM generation through EURI. Low temperature -> stable, factual answers."""

from typing import Any, Dict, List, Optional

from langsmith import traceable

from app.core.config import settings
from app.rag.llm_client import get_llm_client


@traceable(run_type="chain", name="generate_answer")
def generate_answer(messages: List[Dict[str, str]], temperature: Optional[float] = None) -> Dict[str, Any]:
    temperature = settings.temperature if temperature is None else temperature
    response = get_llm_client().chat.completions.create(
        model=settings.chat_model, temperature=temperature, messages=messages)

    usage = getattr(response, "usage", None)          # token usage -> cost tracking later
    return {
        "text": response.choices[0].message.content.strip(),
        "prompt_tokens": getattr(usage, "prompt_tokens", None),
        "completion_tokens": getattr(usage, "completion_tokens", None),
    }
