"""Observability — Langfuse tracing for every gateway call (Phase 3, ADR-004).

Design principles:
- **Observability must never break the primary path.** Every Langfuse call is
  wrapped in try/except; any failure degrades to a logged warning, never a 500.
- **Off by default, opt-in.** A no-op tracer is used unless Langfuse is enabled
  *and* credentials are present — so local/mock runs and tests need nothing.
- **No per-call flush.** Flushing on every request would add network latency to
  the hot path; instead we rely on the SDK's background batching and flush once
  at shutdown (see `main.py` lifespan).

The same attribution tags that go into the cost database (team / project /
agent / use_case) are attached to each trace, so cost and traces line up.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Protocol

from .config import get_settings
from .schemas import CompletionRequest

logger = logging.getLogger(__name__)


class Tracer(Protocol):
    """Minimal tracing interface the gateway depends on."""

    enabled: bool

    def trace_call(
        self,
        *,
        request: CompletionRequest,
        content: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        cost_usd: float,
        latency_ms: float,
        call_id: int | None,
        requested_model: str | None = None,
        routed: bool = False,
        estimated_savings_usd: float = 0.0,
    ) -> None: ...

    def flush(self) -> None: ...


def _tags(request: CompletionRequest) -> list[str]:
    m = request.metadata
    return [
        f"team:{m.team}",
        f"project:{m.project}",
        f"agent:{m.agent_name}",
        f"use_case:{m.use_case}",
        f"provider:{request.provider.value}",
        f"model:{request.model}",
    ]


class NoOpTracer:
    """Used when Langfuse is disabled or unconfigured — does nothing, safely."""

    enabled = False

    def trace_call(self, **_: object) -> None:  # noqa: D401
        return None

    def flush(self) -> None:
        return None


class LangfuseTracer:
    """Wraps the Langfuse client. Constructed only when enabled + configured."""

    enabled = True

    def __init__(self, public_key: str, secret_key: str, host: str):
        from langfuse import Langfuse  # lazy import

        self._client = Langfuse(public_key=public_key, secret_key=secret_key, host=host)

    def trace_call(
        self,
        *,
        request: CompletionRequest,
        content: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        cost_usd: float,
        latency_ms: float,
        call_id: int | None,
        requested_model: str | None = None,
        routed: bool = False,
        estimated_savings_usd: float = 0.0,
    ) -> None:
        m = request.metadata
        try:
            # Langfuse v3+ is OpenTelemetry-based: create a generation observation
            # via start_observation(as_type="generation"). Attribution tags and
            # routing/cost details are carried in metadata so they reconcile with
            # the cost database. (Validate the exact attribute mapping against a
            # live Langfuse instance before relying on it for dashboards.)
            gen = self._client.start_observation(
                as_type="generation",
                name=f"{request.provider.value}:{request.model}",
                model=request.model,
                input=[msg.model_dump(mode="json") for msg in request.messages],
                output=content,
                usage_details={
                    "input": prompt_tokens,
                    "output": completion_tokens,
                    "total": total_tokens,
                },
                # Surface our own cost calc into Langfuse so the two agree.
                cost_details={"total": cost_usd},
                metadata={
                    "tags": _tags(request),
                    "team": m.team,
                    "project": m.project,
                    "agent_name": m.agent_name,
                    "use_case": m.use_case,
                    "call_log_id": call_id,
                    "provider": request.provider.value,
                    "latency_ms": latency_ms,
                    "requested_model": requested_model or request.model,
                    "routed": routed,
                    "estimated_savings_usd": estimated_savings_usd,
                },
            )
            gen.end()
        except Exception:  # never let tracing break a real call
            logger.warning("Langfuse trace failed; continuing without it", exc_info=True)

    def flush(self) -> None:
        try:
            self._client.flush()
        except Exception:
            logger.warning("Langfuse flush failed", exc_info=True)


@lru_cache
def get_tracer() -> Tracer:
    """Cached tracer singleton. Returns a no-op unless Langfuse is enabled and
    both keys are present."""
    s = get_settings()
    if s.langfuse_enabled and s.langfuse_public_key and s.langfuse_secret_key:
        try:
            tracer = LangfuseTracer(s.langfuse_public_key, s.langfuse_secret_key, s.langfuse_host)
            logger.info("Langfuse tracing enabled (host=%s)", s.langfuse_host)
            return tracer
        except Exception:
            logger.warning("Langfuse init failed; tracing disabled", exc_info=True)
    return NoOpTracer()
