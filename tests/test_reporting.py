"""Phase 5 tests — the reporting/aggregation layer (pure pandas, no UI)."""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest

from llm_gateway import reporting
from llm_gateway.budgets import BudgetBook

NOW = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)


def _df() -> pd.DataFrame:
    rows = [
        # team, use_case, model, requested, cost, savings, routed, day
        ("research", "deep-reasoning", "claude-opus-4-8", "claude-opus-4-8", 0.50, 0.0, False, 14),
        ("research", "deep-reasoning", "claude-opus-4-8", "claude-opus-4-8", 0.30, 0.0, False, 15),
        ("marketing", "tagline", "claude-haiku-4-5", "claude-opus-4-8", 0.001, 0.018, True, 15),
        ("support", "categorize", "claude-haiku-4-5", "claude-haiku-4-5", 0.002, 0.0, False, 15),
        ("support", "categorize", "claude-haiku-4-5", "claude-haiku-4-5", 0.003, 0.0, False, 10),
    ]
    df = pd.DataFrame(
        [
            {
                "created_at": datetime(2026, 6, day, 10, 0, tzinfo=timezone.utc),
                "team": team,
                "project": "p",
                "agent_name": "a",
                "use_case": uc,
                "provider": "anthropic",
                "model": model,
                "requested_model": requested,
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150,
                "cost_usd": cost,
                "latency_ms": 200.0,
                "routed": routed,
                "estimated_savings_usd": savings,
            }
            for (team, uc, model, requested, cost, savings, routed, day) in rows
        ]
    )
    return df


def test_cost_by_model_sorted_desc():
    g = reporting.cost_by_model(_df())
    assert list(g["model"])[0] == "claude-opus-4-8"
    assert g["cost_usd"].iloc[0] == pytest.approx(0.80)


def test_top_use_cases_orders_by_cost():
    g = reporting.top_use_cases(_df(), n=10)
    assert g.iloc[0]["use_case"] == "deep-reasoning"  # 0.80 total


def test_routing_savings_totals():
    s = reporting.routing_savings(_df())
    assert s["routed_calls"] == 1
    assert s["total_calls"] == 5
    assert s["total_savings_usd"] == pytest.approx(0.018)
    assert s["routed_pct"] == pytest.approx(20.0)


def test_budget_vs_actual_status_flags():
    budgets = BudgetBook(
        {
            "default": {"monthly_budget_usd": 100, "alert_threshold_pct": 80},
            "teams": {
                "research": {"monthly_budget_usd": 1.0, "alert_threshold_pct": 80},   # 0.80 -> WARN
                "marketing": {"monthly_budget_usd": 0.0005, "alert_threshold_pct": 80},  # over -> OVER
                "support": {"monthly_budget_usd": 100, "alert_threshold_pct": 80},     # tiny -> OK
            },
        }
    )
    bva = reporting.budget_vs_actual(_df(), budgets, when=NOW).set_index("team")
    # research: only June (14+15) counts = 0.80 of 1.00 = 80% -> WARN
    assert bva.loc["research", "status"] == "WARN"
    assert bva.loc["marketing", "status"] == "OVER"
    assert bva.loc["support", "status"] == "OK"


def test_budget_only_counts_current_month():
    budgets = BudgetBook({"teams": {"support": {"monthly_budget_usd": 100, "alert_threshold_pct": 80}}})
    # support has one row in June (0.002) and one in June too (day 10) — both June here.
    bva = reporting.budget_vs_actual(_df(), budgets, when=NOW).set_index("team")
    assert bva.loc["support", "actual_usd"] == pytest.approx(0.005)


def test_empty_df_returns_empty_frames():
    empty = pd.DataFrame(columns=reporting.CALL_COLUMNS)
    assert reporting.cost_by_model(empty).empty
    assert reporting.top_use_cases(empty).empty
    assert reporting.routing_savings(empty)["total_calls"] == 0
