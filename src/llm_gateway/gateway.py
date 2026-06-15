"""The unified LLM gateway — the one function every call flows through.

`complete()` is the choke point ADR-001/ADR-002 describe: it resolves the right
provider adapter, times the call, calculates cost, persists a canonical
`CallLog`, and returns a normalized `CompletionResponse`. Tagging, measurement,
and logging happen here exactly once, no matter the provider.
"""

from __future__ import annotations

import json
import time

from .cost import calculate_cost
from .db import session_scope
from .models import CallLog
from .providers import get_provider
from .schemas import CompletionRequest, CompletionResponse, Usage


def complete(request: CompletionRequest) -> CompletionResponse:
    provider = get_provider(request.provider)

    start = time.perf_counter()
    result = provider.complete(request)
    latency_ms = (time.perf_counter() - start) * 1000.0

    cost_usd = calculate_cost(request.provider, request.model, result)

    log = CallLog(
        team=request.metadata.team,
        project=request.metadata.project,
        agent_name=request.metadata.agent_name,
        use_case=request.metadata.use_case,
        provider=request.provider.value,
        model=request.model,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        total_tokens=result.total_tokens,
        cost_usd=cost_usd,
        latency_ms=latency_ms,
        request_messages=json.dumps([m.model_dump(mode="json") for m in request.messages]),
        response_text=result.content,
        requested_model=request.model,
        routed=False,
        estimated_savings_usd=0.0,
    )

    with session_scope() as session:
        session.add(log)
        session.flush()  # populate autoincrement id before the session closes
        log_id = log.id

    return CompletionResponse(
        id=log_id,
        provider=request.provider,
        model=request.model,
        content=result.content,
        usage=Usage(
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            total_tokens=result.total_tokens,
        ),
        cost_usd=cost_usd,
        latency_ms=latency_ms,
        metadata=request.metadata,
    )
