"""FastAPI application exposing the gateway over HTTP.

Run: `uvicorn llm_gateway.main:app --reload`
Docs: http://localhost:8000/docs
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from . import __version__, gateway
from .config import get_settings
from .db import init_db
from .observability import get_tracer
from .pricing import get_pricing_book, reload_pricing_book
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
