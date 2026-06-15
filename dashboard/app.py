"""Chargeback & reporting dashboard (Phase 5, see ADR-006).

A Streamlit app over the call-log DB: cost by team/project over time, cost by
model, top use cases, routing savings, and budget-vs-actual with alert
thresholds.

Run:  streamlit run dashboard/app.py
(Seed some data first:  python scripts/seed_data.py --reset)
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd  # noqa: E402
import plotly.express as px  # noqa: E402
import streamlit as st  # noqa: E402

from llm_gateway import reporting  # noqa: E402
from llm_gateway.budgets import get_budget_book, reload_budget_book  # noqa: E402

st.set_page_config(page_title="LLM Cost Governance", page_icon="💸", layout="wide")

STATUS_COLORS = {"OK": "#1D9E75", "WARN": "#BA7517", "OVER": "#A32D2D"}


@st.cache_data(ttl=30)
def _load() -> pd.DataFrame:
    return reporting.load_calls()


def main() -> None:
    st.title("LLM Cost Governance & Attribution")
    st.caption("FinOps for LLMs — spend attribution, model mix, routing savings, and budgets.")

    df = _load()

    if df.empty:
        st.warning(
            "No call data yet. Seed some with `python scripts/seed_data.py --reset`, "
            "then refresh."
        )
        st.stop()

    # ---- Sidebar filters ----
    st.sidebar.header("Filters")
    teams = sorted(df["team"].unique())
    selected_teams = st.sidebar.multiselect("Teams", teams, default=teams)

    min_d, max_d = df["created_at"].min().date(), df["created_at"].max().date()
    date_range = st.sidebar.date_input("Date range", value=(min_d, max_d), min_value=min_d, max_value=max_d)
    if st.sidebar.button("Reload budgets config"):
        reload_budget_book()
        st.sidebar.success("Budgets reloaded.")

    mask = df["team"].isin(selected_teams)
    if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
        start, end = date_range
        mask &= (df["created_at"].dt.date >= start) & (df["created_at"].dt.date <= end)
    fdf = df[mask]

    # ---- KPIs ----
    savings = reporting.routing_savings(fdf)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total spend", f"${fdf['cost_usd'].sum():,.2f}")
    c2.metric("Total calls", f"{len(fdf):,}")
    c3.metric("Total tokens", f"{int(fdf['total_tokens'].sum()):,}")
    c4.metric("Est. routing savings", f"${savings['total_savings_usd']:,.2f}", f"{savings['routed_pct']}% routed")

    st.divider()

    # ---- Cost by team over time ----
    st.subheader("Cost by team over time")
    ts = reporting.cost_by_team_over_time(fdf, freq="D")
    if not ts.empty:
        fig = px.area(ts, x="date", y="cost_usd", color="team", labels={"cost_usd": "Cost (USD)"})
        fig.update_layout(margin=dict(t=10, b=10), legend_title_text="Team")
        st.plotly_chart(fig, use_container_width=True)

    left, right = st.columns(2)

    # ---- Cost by model ----
    with left:
        st.subheader("Cost by model")
        bm = reporting.cost_by_model(fdf)
        fig = px.bar(bm, x="cost_usd", y="model", orientation="h", labels={"cost_usd": "Cost (USD)", "model": ""})
        fig.update_layout(margin=dict(t=10, b=10), yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig, use_container_width=True)

    # ---- Top use cases ----
    with right:
        st.subheader("Top 10 use cases by cost")
        tu = reporting.top_use_cases(fdf, n=10)
        fig = px.bar(tu, x="cost_usd", y="use_case", orientation="h", labels={"cost_usd": "Cost (USD)", "use_case": ""})
        fig.update_layout(margin=dict(t=10, b=10), yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ---- Routing savings ----
    st.subheader("Routing savings achieved")
    sav_team = reporting.savings_by_team(fdf)
    if sav_team.empty:
        st.info("No routed calls in the current selection.")
    else:
        fig = px.bar(sav_team, x="team", y="estimated_savings_usd", labels={"estimated_savings_usd": "Est. savings (USD)", "team": ""})
        fig.update_layout(margin=dict(t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Estimated savings are a counterfactual: the requested model's rate applied to actual tokens, minus what we paid (ADR-005).")

    st.divider()

    # ---- Budget vs actual (current month) ----
    now = datetime.now(timezone.utc)
    st.subheader(f"Budget vs. actual — {now:%B %Y}")
    bva = reporting.budget_vs_actual(df, get_budget_book(), when=now)  # use full df: budgets are org-wide
    if selected_teams:
        bva = bva[bva["team"].isin(selected_teams)]

    if bva.empty:
        st.info("No budgets configured.")
    else:
        fig = px.bar(
            bva, x="team", y="actual_usd", color="status",
            color_discrete_map=STATUS_COLORS,
            labels={"actual_usd": "Actual spend (USD)", "team": ""},
        )
        # overlay budget as markers
        fig.add_scatter(x=bva["team"], y=bva["budget_usd"], mode="markers", name="Budget", marker=dict(symbol="line-ew-open", size=28, line=dict(width=3, color="#5F5E5A")))
        fig.update_layout(margin=dict(t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)

        styled = bva.style.format(
            {"actual_usd": "${:,.2f}", "budget_usd": "${:,.2f}", "pct_used": "{:.1f}%", "threshold_pct": "{:.0f}%"}
        ).apply(
            lambda row: [f"background-color: {STATUS_COLORS.get(row['status'], '')}22"] * len(row), axis=1
        )
        st.dataframe(styled, use_container_width=True, hide_index=True)

        over = bva[bva["status"] == "OVER"]["team"].tolist()
        warn = bva[bva["status"] == "WARN"]["team"].tolist()
        if over:
            st.error(f"Over budget: {', '.join(over)}")
        if warn:
            st.warning(f"Approaching budget (>= threshold): {', '.join(warn)}")


if __name__ == "__main__":
    main()
