"""Cost calculation hook.

Phase 1 ships a stub that returns 0.0 so the call record has a `cost_usd`
column wired end-to-end. Phase 2 replaces the body with a config-driven pricing
engine (see ADR-003) — the gateway calls `calculate_cost()` either way, so that
change is local to this module.
"""

from __future__ import annotations

from .providers import ProviderResult
from .schemas import Provider


def calculate_cost(provider: Provider, model: str, result: ProviderResult) -> float:
    """Return cost in USD for a completed call. Stubbed until Phase 2."""
    return 0.0
