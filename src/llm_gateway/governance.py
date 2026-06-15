"""Governance layer (Phase 6, see ADR-007).

Evaluates a team's month-to-date spend against its configured budget and records
a `PolicyViolation` event when a threshold is crossed. Budgets/thresholds are
policy-as-config (`config/budgets.yaml`) — this module only enforces; it never
hardcodes a limit.

Evaluation runs in the same transaction as the call that triggered it, and is
de-duplicated so a sustained overspend logs one WARN and one OVER event per team
per month, not one per call.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .budgets import BudgetBook, get_budget_book
from .models import CallLog, PolicyViolation

logger = logging.getLogger(__name__)


def period_key(when: datetime) -> str:
    return f"{when.year:04d}-{when.month:02d}"


def _period_bounds(when: datetime) -> tuple[datetime, datetime]:
    start = datetime(when.year, when.month, 1, tzinfo=timezone.utc)
    end = (
        datetime(when.year + 1, 1, 1, tzinfo=timezone.utc)
        if when.month == 12
        else datetime(when.year, when.month + 1, 1, tzinfo=timezone.utc)
    )
    return start, end


def team_mtd_spend(session: Session, team: str, when: datetime) -> float:
    """Month-to-date spend for a team, computed with portable date bounds
    (no SQLite/Postgres date-function differences)."""
    start, end = _period_bounds(when)
    total = session.execute(
        select(func.coalesce(func.sum(CallLog.cost_usd), 0.0)).where(
            CallLog.team == team,
            CallLog.created_at >= start,
            CallLog.created_at < end,
        )
    ).scalar_one()
    return float(total or 0.0)


def _severity(pct_used: float, threshold_pct: float) -> str | None:
    if pct_used >= 100.0:
        return "OVER"
    if pct_used >= threshold_pct:
        return "WARN"
    return None


def record_violation_if_needed(
    session: Session,
    team: str,
    when: datetime | None = None,
    budgets: BudgetBook | None = None,
) -> PolicyViolation | None:
    """Check a team's MTD spend and, if it has crossed its threshold, record a
    de-duplicated PolicyViolation. Returns the new event, or None."""
    when = when or datetime.now(timezone.utc)
    budgets = budgets or get_budget_book()
    budget = budgets.for_team(team)

    actual = team_mtd_spend(session, team, when)
    pct = (actual / budget.monthly_budget_usd * 100.0) if budget.monthly_budget_usd else float("inf")
    severity = _severity(pct, budget.alert_threshold_pct)
    if severity is None:
        return None

    period = period_key(when)
    exists = session.execute(
        select(PolicyViolation.id).where(
            PolicyViolation.team == team,
            PolicyViolation.period == period,
            PolicyViolation.severity == severity,
        )
    ).first()
    if exists:
        return None

    msg = (
        f"Team '{team}' reached {pct:.0f}% of its ${budget.monthly_budget_usd:.2f} "
        f"{period} budget (threshold {budget.alert_threshold_pct:.0f}%)."
    )
    violation = PolicyViolation(
        team=team,
        period=period,
        severity=severity,
        budget_usd=budget.monthly_budget_usd,
        actual_usd=round(actual, 6),
        threshold_pct=budget.alert_threshold_pct,
        pct_used=round(pct, 1) if pct != float("inf") else 0.0,
        message=msg,
    )
    session.add(violation)
    logger.warning("Policy violation recorded: %s", msg)
    return violation


def evaluate_all_teams(session: Session, when: datetime | None = None) -> list[PolicyViolation]:
    """Run the check for every team that has a configured budget or any spend.
    Useful as a manual/scheduled sweep (not just at call time)."""
    when = when or datetime.now(timezone.utc)
    budgets = get_budget_book()
    teams = set(budgets.teams)
    teams.update(t for (t,) in session.execute(select(CallLog.team).distinct()).all())
    out: list[PolicyViolation] = []
    for team in sorted(teams):
        v = record_violation_if_needed(session, team, when, budgets)
        if v is not None:
            out.append(v)
    return out
