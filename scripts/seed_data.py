"""Seed the call-log DB with ~30 days of realistic, varied data so the Phase 5
dashboard has something to show. Inserts CallLog rows directly (with historical
timestamps) rather than going through the gateway, so we can spread spend across
dates and teams.

Run: `python scripts/seed_data.py [--calls N] [--reset]`
"""

from __future__ import annotations

import argparse
import os
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
os.environ.setdefault("GATEWAY_MOCK_MODE", "true")

from llm_gateway.db import engine, init_db, session_scope  # noqa: E402
from llm_gateway.models import CallLog  # noqa: E402
from llm_gateway.pricing import get_pricing_book  # noqa: E402
from llm_gateway.schemas import Provider  # noqa: E402

# (team, project, agent, use_case, provider, served_model, requested_model, in_range, out_range)
# requested_model != served_model marks a routed (downgraded) call.
WORKLOADS = [
    ("recruiting", "resume-screening", "parser", "extract-fields", Provider.OPENAI, "gpt-4o-mini", "gpt-4o-mini", (800, 1500), (150, 400)),
    ("support", "ticket-triage", "classifier", "categorize", Provider.ANTHROPIC, "claude-haiku-4-5", "claude-haiku-4-5", (500, 1000), (80, 200)),
    ("support", "ticket-triage", "responder", "draft-reply", Provider.BEDROCK, "anthropic.claude-haiku-4-5-v1:0", "anthropic.claude-haiku-4-5-v1:0", (600, 1200), (200, 500)),
    ("research", "market-analysis", "analyst", "deep-reasoning", Provider.ANTHROPIC, "claude-opus-4-8", "claude-opus-4-8", (3000, 6000), (1500, 3000)),
    ("marketing", "campaigns", "copywriter", "tagline", Provider.ANTHROPIC, "claude-haiku-4-5", "claude-opus-4-8", (20, 60), (10, 40)),
    ("analytics", "kpi-bot", "checker", "yes-no", Provider.OPENAI, "gpt-4o-mini", "gpt-4o", (20, 80), (5, 20)),
]

# Rough daily call volume per workload (gives teams different spend profiles).
DAILY_VOLUME = {
    "extract-fields": 40,
    "categorize": 60,
    "draft-reply": 30,
    "deep-reasoning": 8,
    "tagline": 15,
    "yes-no": 50,
}


def seed(num_days: int, reset: bool) -> None:
    init_db()
    book = get_pricing_book()
    rng = random.Random(42)
    now = datetime.now(timezone.utc)

    with session_scope() as session:
        if reset:
            session.query(CallLog).delete()

        inserted = 0
        for day_offset in range(num_days):
            day = now - timedelta(days=day_offset)
            for (team, project, agent, use_case, provider, model, requested, in_r, out_r) in WORKLOADS:
                # jitter volume +/- 30%
                base = DAILY_VOLUME[use_case]
                count = max(1, int(base * rng.uniform(0.7, 1.3)))
                for _ in range(count):
                    p_in = rng.randint(*in_r)
                    p_out = rng.randint(*out_r)
                    cost = book.cost(provider, model, p_in, p_out)
                    routed = requested != model
                    savings = (book.cost(provider, requested, p_in, p_out) - cost) if routed else 0.0
                    ts = day - timedelta(
                        hours=rng.randint(0, 23), minutes=rng.randint(0, 59), seconds=rng.randint(0, 59)
                    )
                    session.add(
                        CallLog(
                            created_at=ts,
                            team=team,
                            project=project,
                            agent_name=agent,
                            use_case=use_case,
                            provider=provider.value,
                            model=model,
                            prompt_tokens=p_in,
                            completion_tokens=p_out,
                            total_tokens=p_in + p_out,
                            cost_usd=cost,
                            latency_ms=rng.uniform(150, 1800),
                            request_messages="[seeded]",
                            response_text="[seeded]",
                            requested_model=requested,
                            routed=routed,
                            estimated_savings_usd=max(savings, 0.0),
                        )
                    )
                    inserted += 1

    with session_scope() as session:
        total = session.query(CallLog).count()
    print(f"Seeded {inserted} calls across {num_days} days. Total rows now: {total}")
    print(f"DB: {engine.url}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Seed the call-log DB with sample data.")
    ap.add_argument("--calls", type=int, default=30, help="number of days of history to generate")
    ap.add_argument("--reset", action="store_true", help="delete existing rows first")
    args = ap.parse_args()
    seed(num_days=args.calls, reset=args.reset)


if __name__ == "__main__":
    main()
