"""Phase 1 smoke tests — run against an isolated in-memory SQLite DB in mock mode."""

from __future__ import annotations

import os

# Force mock mode + ephemeral DB before any app module imports settings.
os.environ["GATEWAY_MOCK_MODE"] = "true"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from llm_gateway import gateway  # noqa: E402
from llm_gateway.db import init_db, session_scope  # noqa: E402
from llm_gateway.models import CallLog  # noqa: E402
from llm_gateway.schemas import (  # noqa: E402
    CallMetadata,
    CompletionRequest,
    Message,
    Provider,
    Role,
)


def _request(provider: Provider, model: str) -> CompletionRequest:
    return CompletionRequest(
        provider=provider,
        model=model,
        messages=[Message(role=Role.USER, content="Summarize Q3 earnings in one line.")],
        metadata=CallMetadata(
            team="finance-ai",
            project="earnings-digest",
            agent_name="summarizer",
            use_case="one-line-summary",
        ),
    )


def test_completion_is_logged_with_attribution():
    init_db()
    resp = gateway.complete(_request(Provider.OPENAI, "gpt-4o-mini"))

    assert resp.content
    assert resp.usage.total_tokens > 0
    assert resp.metadata.team == "finance-ai"

    with session_scope() as session:
        row = session.get(CallLog, resp.id)
        assert row is not None
        assert row.team == "finance-ai"
        assert row.use_case == "one-line-summary"
        assert row.total_tokens == resp.usage.total_tokens


def test_all_providers_normalize_to_same_shape():
    init_db()
    for provider, model in [
        (Provider.OPENAI, "gpt-4o-mini"),
        (Provider.ANTHROPIC, "claude-haiku-4-5"),
        (Provider.BEDROCK, "anthropic.claude-haiku-4-5-v1:0"),
    ]:
        resp = gateway.complete(_request(provider, model))
        assert resp.provider == provider
        assert resp.usage.prompt_tokens > 0
        assert resp.usage.completion_tokens > 0
