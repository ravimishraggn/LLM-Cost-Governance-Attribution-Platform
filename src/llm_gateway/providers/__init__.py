"""Provider adapter registry.

`get_provider()` returns the right adapter for a request, transparently
substituting the mock adapter when the gateway runs in mock mode.
"""

from __future__ import annotations

from ..config import get_settings
from ..schemas import Provider
from .anthropic_provider import AnthropicProvider
from .base import LLMProvider, ProviderResult
from .bedrock_provider import BedrockProvider
from .mock_provider import MockProvider
from .openai_provider import OpenAIProvider

_REGISTRY: dict[Provider, type[LLMProvider]] = {
    Provider.OPENAI: OpenAIProvider,
    Provider.ANTHROPIC: AnthropicProvider,
    Provider.BEDROCK: BedrockProvider,
}


def get_provider(provider: Provider) -> LLMProvider:
    """Resolve a provider adapter, honouring mock mode."""
    if get_settings().gateway_mock_mode:
        return MockProvider(wrapped_provider=provider.value)
    return _REGISTRY[provider]()


__all__ = ["LLMProvider", "ProviderResult", "get_provider"]
