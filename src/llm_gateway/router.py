"""Rule-based model router (Phase 4, see ADR-005).

Classifies each request as ``simple`` or ``complex`` using cheap, transparent
heuristics (prompt length, keyword signals, requested output size). Simple tasks
on an expensive model are swapped to a configured cheaper sibling; complex tasks
are left untouched. Routing decisions are made at *request time*, before the
provider is called, adding negligible latency.

Rules live in ``config/routing.yaml`` and are hot-reloadable, consistent with the
platform's config-as-data philosophy (see ADR-003).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from .config import get_settings
from .schemas import CompletionRequest, Provider

logger = logging.getLogger(__name__)

DEFAULT_MAX_SIMPLE_CHARS = 2000
DEFAULT_MAX_SIMPLE_OUTPUT = 1024
DEFAULT_KEYWORDS = ["analyze", "reasoning", "step by step", "prove", "design", "evaluate", "compare", "debug"]


@dataclass(frozen=True)
class RoutingDecision:
    requested_model: str
    chosen_model: str
    routed: bool
    complexity: str  # "simple" | "complex" | "unknown"
    reason: str


class Router:
    def __init__(self, raw: dict):
        c = raw.get("complexity") or {}
        self.max_simple_chars = int(c.get("max_simple_chars", DEFAULT_MAX_SIMPLE_CHARS))
        self.max_simple_output = int(c.get("max_simple_output_tokens", DEFAULT_MAX_SIMPLE_OUTPUT))
        self.keywords = [k.lower() for k in (c.get("complex_keywords") or DEFAULT_KEYWORDS)]
        self.downgrades: dict[str, dict[str, str]] = raw.get("downgrades") or {}

    def classify(self, request: CompletionRequest) -> tuple[str, str]:
        """Return (complexity, human-readable reason)."""
        text = " ".join(m.content for m in request.messages)
        haystack = f"{text} {request.metadata.use_case}".lower()

        if len(text) > self.max_simple_chars:
            return "complex", f"long prompt ({len(text)} chars)"
        matched = next((k for k in self.keywords if k in haystack), None)
        if matched:
            return "complex", f"complex keyword '{matched}'"
        if request.max_tokens and request.max_tokens > self.max_simple_output:
            return "complex", f"large output requested ({request.max_tokens} tokens)"
        return "simple", "short prompt, no complex signals"

    def _downgrade_for(self, provider: Provider, model: str) -> str | None:
        return (self.downgrades.get(provider.value) or {}).get(model)

    def route(self, request: CompletionRequest) -> RoutingDecision:
        requested = request.model
        if not get_settings().router_enabled:
            return RoutingDecision(requested, requested, False, "unknown", "router disabled")

        complexity, why = self.classify(request)
        if complexity == "complex":
            return RoutingDecision(requested, requested, False, complexity, f"kept {requested}: {why}")

        cheaper = self._downgrade_for(request.provider, requested)
        if not cheaper:
            return RoutingDecision(
                requested, requested, False, complexity, f"no cheaper model configured for {requested}"
            )
        return RoutingDecision(requested, cheaper, True, complexity, f"{requested} -> {cheaper}: {why}")

    def as_dict(self) -> dict:
        return {
            "max_simple_chars": self.max_simple_chars,
            "max_simple_output_tokens": self.max_simple_output,
            "complex_keywords": self.keywords,
            "downgrades": self.downgrades,
            "enabled": get_settings().router_enabled,
        }


def _load_router() -> Router:
    path = Path(get_settings().routing_config_path)
    if not path.exists():
        logger.warning("Routing config not found at %s; routing rules empty", path)
        return Router({})
    with path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    return Router(raw)


@lru_cache
def get_router() -> Router:
    """Cached router singleton."""
    return _load_router()


def reload_router() -> Router:
    """Clear the cache and reload routing rules from disk."""
    get_router.cache_clear()
    return get_router()
