"""Config-driven pricing engine (Phase 2).

Loads the pricing book from a YAML file (see ADR-003) and turns token counts
into dollars. Pricing is keyed by ``(provider, model)`` because the same model
family is priced differently across providers (e.g. Anthropic direct vs. the
same model on Bedrock).

The book is cached after first load; call :func:`reload_pricing_book` to pick up
edits to the YAML without restarting the service.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from .config import get_settings
from .schemas import Provider

logger = logging.getLogger(__name__)

# Pricing is published per 1,000,000 tokens.
_TOKENS_PER_UNIT = 1_000_000


@dataclass(frozen=True)
class ModelPrice:
    input_per_1m: float
    output_per_1m: float

    def cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        return (
            prompt_tokens / _TOKENS_PER_UNIT * self.input_per_1m
            + completion_tokens / _TOKENS_PER_UNIT * self.output_per_1m
        )


class PricingBook:
    """In-memory view of the pricing YAML with model-name resolution."""

    def __init__(self, raw: dict):
        self.version: str = str(raw.get("version", "unknown"))
        self.currency: str = str(raw.get("currency", "USD"))
        self._prices: dict[str, dict[str, ModelPrice]] = {}
        for provider, models in (raw.get("providers") or {}).items():
            self._prices[provider] = {
                model: ModelPrice(float(p["input"]), float(p["output"]))
                for model, p in (models or {}).items()
            }

    @property
    def model_count(self) -> int:
        return sum(len(m) for m in self._prices.values())

    def price_for(self, provider: Provider, model: str) -> ModelPrice | None:
        """Resolve a price. Exact match first, then a prefix fallback so that a
        dated snapshot id (e.g. ``gpt-4o-mini-2024-07-18``) still matches the
        ``gpt-4o-mini`` entry. The longest matching key wins."""
        models = self._prices.get(provider.value, {})
        if model in models:
            return models[model]
        candidates = [key for key in models if model.startswith(key)]
        if candidates:
            return models[max(candidates, key=len)]
        return None

    def cost(self, provider: Provider, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        price = self.price_for(provider, model)
        if price is None:
            # Unpriced model: don't guess. Record $0 and flag it loudly so the
            # gap is visible rather than silently mis-attributed.
            logger.warning("No pricing for provider=%s model=%s; recording $0.00", provider.value, model)
            return 0.0
        return price.cost(prompt_tokens, completion_tokens)

    def as_dict(self) -> dict:
        return {
            "version": self.version,
            "currency": self.currency,
            "unit": "per_1m_tokens",
            "model_count": self.model_count,
            "providers": {
                provider: {
                    model: {"input": p.input_per_1m, "output": p.output_per_1m}
                    for model, p in models.items()
                }
                for provider, models in self._prices.items()
            },
        }


def _load_book() -> PricingBook:
    path = Path(get_settings().pricing_config_path)
    if not path.exists():
        logger.warning("Pricing config not found at %s; all costs will be $0.00", path)
        return PricingBook({})
    with path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    book = PricingBook(raw)
    logger.info("Loaded pricing book version=%s (%d models)", book.version, book.model_count)
    return book


@lru_cache
def get_pricing_book() -> PricingBook:
    """Cached pricing book singleton."""
    return _load_book()


def reload_pricing_book() -> PricingBook:
    """Clear the cache and reload from disk — lets ops update prices live."""
    get_pricing_book.cache_clear()
    return get_pricing_book()
