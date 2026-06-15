"""Deterministic mock adapter used when GATEWAY_MOCK_MODE=true.

Lets the entire pipeline — tagging, cost calc, logging, dashboards — be
exercised end-to-end with zero real spend and no API keys. Token counts are a
crude word-count estimate so cost numbers are non-trivial and demos look real.
"""

from __future__ import annotations

from ..schemas import CompletionRequest
from .base import LLMProvider, ProviderResult


def _estimate_tokens(text: str) -> int:
    # ~0.75 words per token is a common rule of thumb; good enough for mock data.
    words = max(len(text.split()), 1)
    return int(words / 0.75) + 1


class MockProvider(LLMProvider):
    name = "mock"

    def __init__(self, wrapped_provider: str):
        # Remember which real provider we're standing in for, so logs still show
        # the intended provider/model attribution.
        self.wrapped_provider = wrapped_provider

    def complete(self, request: CompletionRequest) -> ProviderResult:
        prompt_text = "\n".join(m.content for m in request.messages)
        prompt_tokens = _estimate_tokens(prompt_text)
        reply = (
            f"[mock:{self.wrapped_provider}] Response from {request.model} for "
            f"use_case={request.metadata.use_case!r}."
        )
        completion_tokens = _estimate_tokens(reply)
        return ProviderResult(
            content=reply,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            model=request.model,
        )
