"""Phase 4 tests — rule-based routing and savings tracking."""

from __future__ import annotations

import os

os.environ["GATEWAY_MOCK_MODE"] = "true"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from llm_gateway.router import Router  # noqa: E402
from llm_gateway.schemas import (  # noqa: E402
    CallMetadata,
    CompletionRequest,
    Message,
    Provider,
    Role,
)

CONFIG = {
    "complexity": {
        "max_simple_chars": 200,
        "max_simple_output_tokens": 1024,
        "complex_keywords": ["analyze", "reasoning", "design"],
    },
    "downgrades": {
        "anthropic": {"claude-opus-4-8": "claude-haiku-4-5"},
        "openai": {"gpt-4o": "gpt-4o-mini"},
    },
}


def _req(model, content, use_case="task", provider=Provider.ANTHROPIC, max_tokens=512):
    return CompletionRequest(
        provider=provider,
        model=model,
        messages=[Message(role=Role.USER, content=content)],
        metadata=CallMetadata(team="t", project="p", agent_name="a", use_case=use_case),
        max_tokens=max_tokens,
    )


def test_simple_task_downgrades_expensive_model():
    r = Router(CONFIG)
    d = r.route(_req("claude-opus-4-8", "Say hello."))
    assert d.routed is True
    assert d.chosen_model == "claude-haiku-4-5"
    assert d.complexity == "simple"


def test_complex_keyword_keeps_expensive_model():
    r = Router(CONFIG)
    d = r.route(_req("claude-opus-4-8", "Analyze the macroeconomic impact in detail."))
    assert d.routed is False
    assert d.chosen_model == "claude-opus-4-8"
    assert d.complexity == "complex"


def test_long_prompt_is_complex():
    r = Router(CONFIG)
    d = r.route(_req("claude-opus-4-8", "word " * 100))  # > 200 chars
    assert d.routed is False
    assert "long prompt" in d.reason


def test_use_case_keyword_triggers_complex():
    r = Router(CONFIG)
    d = r.route(_req("claude-opus-4-8", "Do it.", use_case="reasoning-heavy"))
    assert d.complexity == "complex"


def test_already_cheap_model_is_not_downgraded():
    r = Router(CONFIG)
    d = r.route(_req("claude-haiku-4-5", "Say hello."))
    assert d.routed is False
    assert "no cheaper model" in d.reason


def test_gateway_logs_estimated_savings(monkeypatch):
    """End-to-end: a simple Opus call should route to Haiku, log routed=True and
    a positive estimated saving (Opus output costs more than Haiku output)."""
    from llm_gateway import gateway
    from llm_gateway.db import init_db, session_scope
    from llm_gateway.models import CallLog
    from llm_gateway.pricing import PricingBook
    from llm_gateway import pricing as pricing_mod
    from llm_gateway import router as router_mod

    init_db()

    book = PricingBook(
        {
            "providers": {
                "anthropic": {
                    "claude-opus-4-8": {"input": 15.0, "output": 75.0},
                    "claude-haiku-4-5": {"input": 1.0, "output": 5.0},
                }
            }
        }
    )
    monkeypatch.setattr(pricing_mod, "get_pricing_book", lambda: book)
    monkeypatch.setattr(gateway, "get_pricing_book", lambda: book)
    monkeypatch.setattr(gateway, "calculate_cost", lambda p, m, res: book.cost(p, m, res.prompt_tokens, res.completion_tokens))
    monkeypatch.setattr(gateway, "get_router", lambda: Router(CONFIG))

    resp = gateway.complete(_req("claude-opus-4-8", "Say hello."))

    assert resp.routed is True
    assert resp.model == "claude-haiku-4-5"
    assert resp.requested_model == "claude-opus-4-8"
    assert resp.estimated_savings_usd > 0

    with session_scope() as session:
        row = session.get(CallLog, resp.id)
        assert row.routed is True
        assert row.model == "claude-haiku-4-5"
        assert row.estimated_savings_usd > 0
