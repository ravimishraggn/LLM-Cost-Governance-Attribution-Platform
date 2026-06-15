"""Pydantic contracts for the gateway's public API.

The `CallMetadata` block is the heart of the platform: every call MUST carry
attribution. The API rejects calls that don't (see ADR-002).
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Provider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    BEDROCK = "bedrock"


class Role(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class Message(BaseModel):
    role: Role
    content: str


class CallMetadata(BaseModel):
    """Attribution tags. Required on every call — this is what makes cost
    chargeback possible."""

    team: str = Field(..., min_length=1, examples=["recruiting-platform"])
    project: str = Field(..., min_length=1, examples=["candidate-screening"])
    agent_name: str = Field(..., min_length=1, examples=["resume-parser"])
    use_case: str = Field(..., min_length=1, examples=["extract-structured-fields"])


class CompletionRequest(BaseModel):
    provider: Provider
    model: str = Field(..., examples=["gpt-4o-mini"])
    messages: list[Message] = Field(..., min_length=1)
    metadata: CallMetadata
    max_tokens: int | None = Field(default=512, ge=1)
    temperature: float | None = Field(default=0.7, ge=0.0, le=2.0)


class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class CompletionResponse(BaseModel):
    """Normalized response returned to the caller, identical in shape no matter
    which provider served the request."""

    id: int | None = None
    provider: Provider
    model: str  # the model that actually served the call (post-routing)
    content: str
    usage: Usage
    cost_usd: float
    latency_ms: float
    metadata: CallMetadata

    # Routing outcome (Phase 4)
    requested_model: str
    routed: bool = False
    estimated_savings_usd: float = 0.0
