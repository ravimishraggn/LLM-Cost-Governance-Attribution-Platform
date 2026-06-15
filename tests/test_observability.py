"""Phase 3 tests — tracer selection and the safety guarantees around it."""

from __future__ import annotations

import os

os.environ["GATEWAY_MOCK_MODE"] = "true"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from llm_gateway import gateway, observability  # noqa: E402
from llm_gateway.db import init_db  # noqa: E402
from llm_gateway.observability import NoOpTracer, _tags, get_tracer  # noqa: E402
from llm_gateway.schemas import (  # noqa: E402
    CallMetadata,
    CompletionRequest,
    Message,
    Provider,
    Role,
)


def _request() -> CompletionRequest:
    return CompletionRequest(
        provider=Provider.ANTHROPIC,
        model="claude-haiku-4-5",
        messages=[Message(role=Role.USER, content="hi")],
        metadata=CallMetadata(
            team="support", project="triage", agent_name="bot", use_case="categorize"
        ),
    )


def test_defaults_to_noop_when_disabled():
    get_tracer.cache_clear()
    assert isinstance(get_tracer(), NoOpTracer)
    assert get_tracer().enabled is False


def test_tags_carry_attribution_metadata():
    tags = _tags(_request())
    assert "team:support" in tags
    assert "use_case:categorize" in tags
    assert "provider:anthropic" in tags


def test_a_failing_tracer_never_breaks_a_call(monkeypatch):
    """Observability must never take down the primary path (ADR-004)."""
    init_db()

    class ExplodingTracer:
        enabled = True

        def trace_call(self, **_):
            raise RuntimeError("tracing backend down")

        def flush(self):
            pass

    monkeypatch.setattr(observability, "get_tracer", lambda: ExplodingTracer())
    monkeypatch.setattr(gateway, "get_tracer", lambda: ExplodingTracer())

    # The call should still succeed and be logged despite the tracer raising.
    resp = gateway.complete(_request())
    assert resp.content
    assert resp.usage.total_tokens > 0
