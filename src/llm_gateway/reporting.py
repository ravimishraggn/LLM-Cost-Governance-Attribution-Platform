"""Reporting / aggregation layer for the chargeback dashboard (Phase 5).

These are pure functions over a pandas DataFrame of call logs, deliberately kept
separate from the Streamlit UI so they can be unit-tested without a browser and
reused by any future reporting surface (a React app, a scheduled CSV, an API).

Aggregation is done in pandas rather than SQL so the logic is identical on
SQLite (MVP) and Postgres (prod) — no per-dialect date functions.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from . import db
from .budgets import BudgetBook

CALL_COLUMNS = [
    "created_at",
    "team",
    "project",
    "agent_name",
    "use_case",
    "provider",
    "model",
    "requested_model",
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "cost_usd",
    "latency_ms",
    "routed",
    "estimated_savings_usd",
]


def load_calls(engine=None) -> pd.DataFrame:
    """Load all call logs into a DataFrame (created_at parsed to datetime)."""
    engine = engine or db.engine
    cols = ", ".join(CALL_COLUMNS)
    df = pd.read_sql(f"SELECT {cols} FROM call_logs", engine, parse_dates=["created_at"])
    if not df.empty:
        df["created_at"] = pd.to_datetime(df["created_at"], utc=True)
        # SQLite returns BOOLEAN as 0/1; normalize so boolean masking works.
        df["routed"] = df["routed"].astype(bool)
    return df


def load_violations(engine=None) -> pd.DataFrame:
    """Load recorded policy-violation events (Phase 6)."""
    engine = engine or db.engine
    df = pd.read_sql(
        "SELECT created_at, team, period, severity, budget_usd, actual_usd, "
        "threshold_pct, pct_used, message FROM policy_violations",
        engine,
        parse_dates=["created_at"],
    )
    if not df.empty:
        df["created_at"] = pd.to_datetime(df["created_at"], utc=True)
    return df


def to_csv(df: pd.DataFrame) -> str:
    """Serialize a frame to CSV text — used for the compliance audit export."""
    return df.to_csv(index=False)


def _empty(*columns: str) -> pd.DataFrame:
    return pd.DataFrame(columns=list(columns))


def cost_by_team_over_time(df: pd.DataFrame, freq: str = "D") -> pd.DataFrame:
    """Long-format daily (or freq) cost per team: columns [date, team, cost_usd]."""
    if df.empty:
        return _empty("date", "team", "cost_usd")
    g = (
        df.set_index("created_at")
        .groupby("team")["cost_usd"]
        .resample(freq)
        .sum()
        .reset_index()
        .rename(columns={"created_at": "date"})
    )
    return g


def cost_by_model(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return _empty("model", "cost_usd", "calls", "total_tokens")
    g = (
        df.groupby("model")
        .agg(cost_usd=("cost_usd", "sum"), calls=("cost_usd", "size"), total_tokens=("total_tokens", "sum"))
        .reset_index()
        .sort_values("cost_usd", ascending=False)
    )
    return g


def top_use_cases(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    if df.empty:
        return _empty("use_case", "cost_usd", "calls")
    g = (
        df.groupby("use_case")
        .agg(cost_usd=("cost_usd", "sum"), calls=("cost_usd", "size"))
        .reset_index()
        .sort_values("cost_usd", ascending=False)
        .head(n)
    )
    return g


def routing_savings(df: pd.DataFrame) -> dict:
    """Headline routing numbers."""
    if df.empty:
        return {"total_savings_usd": 0.0, "routed_calls": 0, "total_calls": 0, "routed_pct": 0.0}
    routed_calls = int(df["routed"].sum())
    total_calls = int(len(df))
    return {
        "total_savings_usd": float(df["estimated_savings_usd"].sum()),
        "routed_calls": routed_calls,
        "total_calls": total_calls,
        "routed_pct": round(100.0 * routed_calls / total_calls, 1) if total_calls else 0.0,
    }


def savings_by_team(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return _empty("team", "estimated_savings_usd")
    g = (
        df[df["routed"]]
        .groupby("team")["estimated_savings_usd"]
        .sum()
        .reset_index()
        .sort_values("estimated_savings_usd", ascending=False)
    )
    return g


def _current_period_mask(df: pd.DataFrame, when: datetime | None = None) -> pd.Series:
    when = when or datetime.now(timezone.utc)
    return (df["created_at"].dt.year == when.year) & (df["created_at"].dt.month == when.month)


def budget_vs_actual(
    df: pd.DataFrame, budgets: BudgetBook, when: datetime | None = None
) -> pd.DataFrame:
    """Per-team actual spend this month vs. budget, with a status flag.

    Status: OK < threshold% <= WARN < 100% <= OVER.
    Includes teams that have a budget configured even if they have no spend yet.
    """
    rows: list[dict] = []
    if df.empty:
        actuals = {}
    else:
        period = df[_current_period_mask(df, when)]
        actuals = period.groupby("team")["cost_usd"].sum().to_dict()

    teams = set(actuals) | set(budgets.teams)
    for team in sorted(teams):
        b = budgets.for_team(team)
        actual = float(actuals.get(team, 0.0))
        pct = (actual / b.monthly_budget_usd * 100.0) if b.monthly_budget_usd else 0.0
        if pct >= 100.0:
            status = "OVER"
        elif pct >= b.alert_threshold_pct:
            status = "WARN"
        else:
            status = "OK"
        rows.append(
            {
                "team": team,
                "actual_usd": round(actual, 6),
                "budget_usd": b.monthly_budget_usd,
                "pct_used": round(pct, 1),
                "threshold_pct": b.alert_threshold_pct,
                "status": status,
            }
        )
    return pd.DataFrame(rows, columns=["team", "actual_usd", "budget_usd", "pct_used", "threshold_pct", "status"])
