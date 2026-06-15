"""Phase 6 tests — budget policy-violation events and de-duplication."""

from __future__ import annotations

import os
from datetime import datetime, timezone

os.environ["GATEWAY_MOCK_MODE"] = "true"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from sqlalchemy import select  # noqa: E402

from llm_gateway import governance  # noqa: E402
from llm_gateway.budgets import BudgetBook  # noqa: E402
from llm_gateway.db import init_db, session_scope  # noqa: E402
from llm_gateway.models import CallLog, PolicyViolation  # noqa: E402

WHEN = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)
BUDGETS = BudgetBook(
    {
        "teams": {
            "research": {"monthly_budget_usd": 1.0, "alert_threshold_pct": 80},
            "support": {"monthly_budget_usd": 1000.0, "alert_threshold_pct": 80},
        }
    }
)


def _add_call(session, team, cost, when=WHEN):
    session.add(
        CallLog(
            created_at=when,
            team=team,
            project="p",
            agent_name="a",
            use_case="u",
            provider="anthropic",
            model="claude-opus-4-8",
            prompt_tokens=1,
            completion_tokens=1,
            total_tokens=2,
            cost_usd=cost,
            latency_ms=1.0,
            requested_model="claude-opus-4-8",
        )
    )


def test_warn_event_recorded_at_threshold():
    init_db()
    with session_scope() as session:
        session.query(PolicyViolation).delete()
        session.query(CallLog).delete()
        _add_call(session, "research", 0.85)  # 85% of $1 budget -> WARN
        session.flush()
        v = governance.record_violation_if_needed(session, "research", WHEN, BUDGETS)
        assert v is not None
        assert v.severity == "WARN"


def test_over_event_recorded_above_budget():
    init_db()
    with session_scope() as session:
        session.query(PolicyViolation).delete()
        session.query(CallLog).delete()
        _add_call(session, "research", 1.50)  # 150% -> OVER
        session.flush()
        v = governance.record_violation_if_needed(session, "research", WHEN, BUDGETS)
        assert v is not None and v.severity == "OVER"


def test_no_event_under_threshold():
    init_db()
    with session_scope() as session:
        session.query(PolicyViolation).delete()
        session.query(CallLog).delete()
        _add_call(session, "support", 10.0)  # 1% of $1000 -> OK
        session.flush()
        assert governance.record_violation_if_needed(session, "support", WHEN, BUDGETS) is None


def test_violation_is_deduplicated_per_period_and_severity():
    init_db()
    with session_scope() as session:
        session.query(PolicyViolation).delete()
        session.query(CallLog).delete()
        _add_call(session, "research", 0.85)
        session.flush()
        first = governance.record_violation_if_needed(session, "research", WHEN, BUDGETS)
        session.flush()
        second = governance.record_violation_if_needed(session, "research", WHEN, BUDGETS)
        assert first is not None
        assert second is None  # same WARN already recorded this period

        count = session.execute(
            select(PolicyViolation).where(
                PolicyViolation.team == "research", PolicyViolation.severity == "WARN"
            )
        ).all()
        assert len(count) == 1


def test_mtd_spend_ignores_other_months():
    init_db()
    may = datetime(2026, 5, 20, tzinfo=timezone.utc)
    with session_scope() as session:
        session.query(CallLog).delete()
        _add_call(session, "research", 5.0, when=may)   # previous month
        _add_call(session, "research", 0.30, when=WHEN)  # current month
        session.flush()
        spend = governance.team_mtd_spend(session, "research", WHEN)
        assert spend == 0.30
