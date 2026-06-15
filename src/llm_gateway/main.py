"""FastAPI application exposing the gateway over HTTP.

Run: `uvicorn llm_gateway.main:app --reload`
Docs: http://localhost:8000/docs
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Response

from . import __version__, gateway
from .budgets import get_budget_book, reload_budget_book
from .config import get_settings
from .db import init_db, session_scope
from .governance import evaluate_all_teams
from .observability import get_tracer
from .pricing import get_pricing_book, reload_pricing_book
from . import reporting
from .router import get_router, reload_router
from .schemas import CompletionRequest, CompletionResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()  # create tables on startup
    yield
    get_tracer().flush()  # drain any buffered traces on shutdown


app = FastAPI(
    title="LLM Cost Governance & Attribution Platform",
    version=__version__,
    description="FinOps for LLMs — a unified gateway that tags, costs, and logs every model call.",
    lifespan=lifespan,
)


@app.get("/health", tags=["ops"])
def health() -> dict:
    return {
        "status": "ok",
        "version": __version__,
        "mock_mode": get_settings().gateway_mock_mode,
        "tracing_enabled": get_tracer().enabled,
    }


@app.post("/v1/completions", response_model=CompletionResponse, tags=["gateway"])
def create_completion(request: CompletionRequest) -> CompletionResponse:
    """Single entry point for LLM calls. The required `metadata` block is
    validated by Pydantic before we get here — unattributed calls are rejected
    with a 422, which is the whole point of the platform (ADR-002)."""
    return gateway.complete(request)


@app.get("/pricing", tags=["cost"])
def pricing() -> dict:
    """Inspect the currently loaded pricing book (ADR-003)."""
    return get_pricing_book().as_dict()


@app.post("/admin/reload-pricing", tags=["cost"])
def reload_pricing() -> dict:
    """Reload the pricing YAML from disk without restarting — lets ops update
    rates live when a provider changes prices."""
    book = reload_pricing_book()
    return {"reloaded": True, "version": book.version, "model_count": book.model_count}


@app.get("/routing", tags=["routing"])
def routing() -> dict:
    """Inspect the active routing rules (ADR-005)."""
    return get_router().as_dict()


@app.post("/admin/reload-routing", tags=["routing"])
def reload_routing() -> dict:
    """Reload routing rules from disk without restarting."""
    reload_router()
    return {"reloaded": True}


@app.get("/budgets", tags=["governance"])
def budgets() -> dict:
    """Inspect the active per-team budgets (policy-as-config, ADR-007)."""
    return get_budget_book().as_dict()


@app.post("/admin/reload-budgets", tags=["governance"])
def reload_budgets() -> dict:
    book = reload_budget_book()
    return {"reloaded": True, "teams": list(book.teams)}


@app.get("/governance/violations", tags=["governance"])
def violations() -> list[dict]:
    """List recorded policy-violation events."""
    df = reporting.load_violations()
    return df.to_dict(orient="records")


@app.post("/governance/evaluate", tags=["governance"])
def evaluate() -> dict:
    """Sweep every team now and record any newly-crossed budget thresholds."""
    when = datetime.now(timezone.utc)
    with session_scope() as session:
        new = evaluate_all_teams(session, when)
        recorded = [{"team": v.team, "severity": v.severity, "pct_used": v.pct_used} for v in new]
    return {"new_violations": len(recorded), "details": recorded}


@app.get("/audit/calls.csv", tags=["governance"])
def audit_calls_csv() -> Response:
    """Audit export: every logged call as CSV, for compliance review."""
    csv = reporting.to_csv(reporting.load_calls())
    return Response(
        content=csv,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_calls.csv"},
    )


@app.get("/audit/violations.csv", tags=["governance"])
def audit_violations_csv() -> Response:
    """Audit export: all policy-violation events as CSV."""
    csv = reporting.to_csv(reporting.load_violations())
    return Response(
        content=csv,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_violations.csv"},
    )
