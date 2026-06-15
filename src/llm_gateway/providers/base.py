"""Provider adapter interface and the normalized result shape.

Each provider SDK has a different request/response format and a different way of
reporting token usage. Adapters hide those differences so the gateway only ever
deals with `ProviderResult`. This is the "adapter layer" that makes token counts
and content comparable across OpenAI, Anthropic, and Bedrock.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from ..schemas import CompletionRequest


@dataclass
class ProviderResult:
    """What every adapter returns, regardless of upstream provider."""

    content: str
    prompt_tokens: int
    completion_tokens: int
    model: str  # the model the provider actually reports having used

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class LLMProvider(ABC):
    """One adapter per provider SDK."""

    name: str

    @abstractmethod
    def complete(self, request: CompletionRequest) -> ProviderResult:
        """Forward the request to the underlying SDK and normalize the response."""
        raise NotImplementedError
