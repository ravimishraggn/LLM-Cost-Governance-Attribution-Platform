"""The unified LLM gateway — the one function every call flows through.

`complete()` is the choke point ADR-001/ADR-002 describe: it routes (ADR-005),
resolves the right provider adapter, times the call, calculates cost, persists a
canonical `CallLog`, and returns a normalized `CompletionResponse`. Tagging,
measurement, routing, and logging happen here exactly once, no matter the
provider.
"""

from __future__ import annotations

import json
import logging
import time

from .cost import calculate_cost
from .db import session_scope
from .models import CallLog
from .observability import get_tracer
from .pricing import get_pricing_book
from .providers import get_provider
from .router import get_router
from .schemas import CompletionRequest, CompletionResponse, Usage


def complete(request: CompletionRequest) -> CompletionResponse:
    # 1. Route at request time: maybe swap an expensive model for a cheaper one.
    decision = get_router().route(request)
    served_request = (
        request.model_copy(update={"model": decision.chosen_model})
        if decision.routed
        else request
    )

    # 2. Forward to the provider (using the possibly-downgraded model).
    provider = get_provider(request.provider)
    start = time.perf_counter()
    result = provider.complete(served_request)
    latency_ms = (time.perf_counter() - start) * 1000.0

    # 3. Cost the call on the model that actually served it.
    cost_usd = calculate_cost(request.provider, decision.chosen_model, result)

    # 4. If we downgraded, estimate the savings vs. what the requested model
    #    would have cost for the same token usage.
    estimated_savings = 0.0
    if decision.routed:
        original_cost = get_pricing_book().cost(
            request.provider, decision.requested_model, result.prompt_tokens, result.completion_tokens
        )
        estimated_savings = max(original_cost - cost_usd, 0.0)

    log = CallLog(
        team=request.metadata.team,
        project=request.metadata.project,
        agent_name=request.metadata.agent_name,
        use_case=request.metadata.use_case,
        provider=request.provider.value,
        model=decision.chosen_model,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        total_tokens=result.total_tokens,
        cost_usd=cost_usd,
        latency_ms=latency_ms,
        request_messages=json.dumps([m.model_dump(mode="json") for m in request.messages]),
        response_text=result.content,
        requested_model=decision.requested_model,
        routed=decision.routed,
        estimated_savings_usd=estimated_savings,
    )

    with session_scope() as session:
        session.add(log)
        session.flush()  # populate autoincrement id before the session closes
        log_id = log.id

    # 5. Mirror the call into the tracing backend with the same attribution tags.
    #    No-op unless Langfuse is enabled. Guarded here as defense-in-depth so
    #    that even a misbehaving tracer can never break the primary path (ADR-004).
    try:
        get_tracer().trace_call(
            request=request,
            content=result.content,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            total_tokens=result.total_tokens,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            call_id=log_id,
            requested_model=decision.requested_model,
            routed=decision.routed,
            estimated_savings_usd=estimated_savings,
        )
    except Exception:  # pragma: no cover - belt-and-suspenders
        logging.getLogger(__name__).warning("Tracing failed; call unaffected", exc_info=True)

    return CompletionResponse(
        id=log_id,
        provider=request.provider,
        model=decision.chosen_model,
        content=result.content,
        usage=Usage(
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            total_tokens=result.total_tokens,
        ),
        cost_usd=cost_usd,
        latency_ms=latency_ms,
        metadata=request.metadata,
        requested_model=decision.requested_model,
        routed=decision.routed,
        estimated_savings_usd=estimated_savings,
    )
