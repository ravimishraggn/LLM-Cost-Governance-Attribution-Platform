"""OpenAI adapter. SDK is imported lazily so the gateway runs (and tests/mocks
work) without the `openai` package or an API key installed."""

from __future__ import annotations

from ..config import get_settings
from ..schemas import CompletionRequest
from .base import LLMProvider, ProviderResult


class OpenAIProvider(LLMProvider):
    name = "openai"

    def complete(self, request: CompletionRequest) -> ProviderResult:
        from openai import OpenAI  # lazy import

        client = OpenAI(api_key=get_settings().openai_api_key)
        resp = client.chat.completions.create(
            model=request.model,
            messages=[{"role": m.role.value, "content": m.content} for m in request.messages],
            max_tokens=request.max_tokens,
            temperature=request.temperature,
        )
        choice = resp.choices[0]
        usage = resp.usage
        return ProviderResult(
            content=choice.message.content or "",
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            model=resp.model,
        )
