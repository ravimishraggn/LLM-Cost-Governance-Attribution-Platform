"""Anthropic adapter.

Two normalization quirks handled here:
- Anthropic takes the system prompt as a top-level `system` arg, not a message.
- Usage is reported as `input_tokens` / `output_tokens` (vs OpenAI's
  `prompt_tokens` / `completion_tokens`).
"""

from __future__ import annotations

from ..config import get_settings
from ..schemas import CompletionRequest, Role
from .base import LLMProvider, ProviderResult


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def complete(self, request: CompletionRequest) -> ProviderResult:
        from anthropic import Anthropic  # lazy import

        client = Anthropic(api_key=get_settings().anthropic_api_key)

        system_parts = [m.content for m in request.messages if m.role == Role.SYSTEM]
        chat = [
            {"role": m.role.value, "content": m.content}
            for m in request.messages
            if m.role != Role.SYSTEM
        ]

        resp = client.messages.create(
            model=request.model,
            system="\n".join(system_parts) or None,
            messages=chat,
            max_tokens=request.max_tokens or 512,
            temperature=request.temperature,
        )
        text = "".join(block.text for block in resp.content if block.type == "text")
        return ProviderResult(
            content=text,
            prompt_tokens=resp.usage.input_tokens,
            completion_tokens=resp.usage.output_tokens,
            model=resp.model,
        )
