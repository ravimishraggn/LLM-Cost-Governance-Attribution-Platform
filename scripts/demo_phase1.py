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

SAMPLE_CALLS = [
    (Provider.OPENAI, "gpt-4o-mini", "recruiting", "resume-screening", "parser", "extract-fields"),
    (Provider.ANTHROPIC, "claude-haiku-4-5", "support", "ticket-triage", "classifier", "categorize"),
    (Provider.ANTHROPIC, "claude-opus-4-8", "research", "market-analysis", "analyst", "deep-reasoning"),
    (Provider.BEDROCK, "anthropic.claude-haiku-4-5-v1:0", "support", "ticket-triage", "responder", "draft-reply"),
]


def main() -> None:
    init_db()
    for provider, model, team, project, agent, use_case in SAMPLE_CALLS:
        req = CompletionRequest(
            provider=provider,
            model=model,
            messages=[
                Message(role=Role.SYSTEM, content="You are a helpful enterprise assistant."),
                Message(role=Role.USER, content="Process this request and respond concisely."),
            ],
            metadata=CallMetadata(team=team, project=project, agent_name=agent, use_case=use_case),
        )
        resp = gateway.complete(req)
        print(
            f"#{resp.id} {team:<10} {provider.value:<10} {model:<32} "
            f"tokens={resp.usage.total_tokens:<4} cost=${resp.cost_usd:.6f} "
            f"{resp.latency_ms:.1f}ms"
        )

    with session_scope() as session:
        total = session.query(CallLog).count()
    print(f"\nTotal calls logged: {total}")


if __name__ == "__main__":
    main()
