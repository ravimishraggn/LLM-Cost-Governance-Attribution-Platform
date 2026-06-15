"""Phase 1 demo — fire a few tagged calls through the gateway (mock mode) and
print the resulting call log. Run: `python scripts/demo_phase1.py`

Useful both as a manual smoke test and as a seed of realistic-looking data for
the dashboard in later phases.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Make `src/` importable when run directly.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
os.environ.setdefault("GATEWAY_MOCK_MODE", "true")

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

# (provider, model, team, project, agent, use_case, prompt)
SAMPLE_CALLS = [
    (Provider.OPENAI, "gpt-4o-mini", "recruiting", "resume-screening", "parser", "extract-fields",
     "Extract the candidate's name and email."),
    (Provider.ANTHROPIC, "claude-haiku-4-5", "support", "ticket-triage", "classifier", "categorize",
     "Is this ticket about billing or tech support?"),
    # Genuinely complex -> the router keeps the expensive model.
    (Provider.ANTHROPIC, "claude-opus-4-8", "research", "market-analysis", "analyst", "deep-reasoning",
     "Analyze the competitive landscape and reason through the 3-year outlook."),
    # Trivial task sent to an expensive model -> the router downgrades it.
    (Provider.ANTHROPIC, "claude-opus-4-8", "marketing", "campaigns", "copywriter", "tagline",
     "Write a 5-word greeting."),
    (Provider.OPENAI, "gpt-4o", "analytics", "kpi-bot", "checker", "yes-no",
     "Reply yes or no: is 42 greater than 10?"),
]


def main() -> None:
    init_db()
    total_savings = 0.0
    for provider, model, team, project, agent, use_case, prompt in SAMPLE_CALLS:
        req = CompletionRequest(
            provider=provider,
            model=model,
            messages=[
                Message(role=Role.SYSTEM, content="You are a helpful enterprise assistant."),
                Message(role=Role.USER, content=prompt),
            ],
            metadata=CallMetadata(team=team, project=project, agent_name=agent, use_case=use_case),
        )
        resp = gateway.complete(req)
        total_savings += resp.estimated_savings_usd
        routing = (
            f"ROUTED {resp.requested_model} -> {resp.model} (saved ${resp.estimated_savings_usd:.6f})"
            if resp.routed
            else f"kept {resp.model}"
        )
        print(
            f"#{resp.id} {team:<10} {provider.value:<10} "
            f"tokens={resp.usage.total_tokens:<4} cost=${resp.cost_usd:.6f}  {routing}"
        )

    with session_scope() as session:
        total = session.query(CallLog).count()
    print(f"\nTotal calls logged: {total}")
    print(f"Estimated routing savings this run: ${total_savings:.6f}")


if __name__ == "__main__":
    main()
