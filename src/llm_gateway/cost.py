"""Cost calculation hook.

Thin wrapper over the Phase 2 pricing engine. The gateway calls
``calculate_cost()`` for every completion; the actual rate-card logic and
model-name resolution live in :mod:`llm_gateway.pricing` (see ADR-003).
"""

from __future__ import annotations

from .pricing import get_pricing_book
from .providers import ProviderResult
from .schemas import Provider


def calculate_cost(provider: Provider, model: str, result: ProviderResult) -> float:
    """Return cost in USD for a completed call, from the config-driven book."""
    return get_pricing_book().cost(
        provider, model, result.prompt_tokens, result.completion_tokens
    )
