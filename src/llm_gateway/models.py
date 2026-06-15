"""SQLAlchemy ORM models — the canonical record of every LLM call.

One table, `call_logs`, is the single source of truth that both chargeback
reporting (Phase 5) and governance (Phase 6) read from.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CallLog(Base):
    __tablename__ = "call_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)

    # Attribution (from CallMetadata) — indexed because reports group by these.
    team: Mapped[str] = mapped_column(String(128), index=True)
    project: Mapped[str] = mapped_column(String(128), index=True)
    agent_name: Mapped[str] = mapped_column(String(128), index=True)
    use_case: Mapped[str] = mapped_column(String(256), index=True)

    # What was called
    provider: Mapped[str] = mapped_column(String(32), index=True)
    model: Mapped[str] = mapped_column(String(128), index=True)

    # Measurements
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)

    # Payloads (kept for audit; truncate/redact in production as policy requires)
    request_messages: Mapped[str] = mapped_column(Text, default="")
    response_text: Mapped[str] = mapped_column(Text, default="")

    # Routing bookkeeping (populated in Phase 4)
    requested_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    routed: Mapped[bool] = mapped_column(default=False)
    estimated_savings_usd: Mapped[float] = mapped_column(Float, default=0.0)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"<CallLog id={self.id} team={self.team!r} model={self.model!r} "
            f"cost=${self.cost_usd:.6f}>"
        )


class PolicyViolation(Base):
    """A governance event: a team crossed a budget threshold in a period.

    De-duplicated on (team, period, severity) so a single overspend produces one
    WARN and one OVER event per month, not one per call (Phase 6, ADR-007).
    """

    __tablename__ = "policy_violations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)

    team: Mapped[str] = mapped_column(String(128), index=True)
    period: Mapped[str] = mapped_column(String(7), index=True)  # "YYYY-MM"
    severity: Mapped[str] = mapped_column(String(8), index=True)  # "WARN" | "OVER"

    budget_usd: Mapped[float] = mapped_column(Float, default=0.0)
    actual_usd: Mapped[float] = mapped_column(Float, default=0.0)
    threshold_pct: Mapped[float] = mapped_column(Float, default=0.0)
    pct_used: Mapped[float] = mapped_column(Float, default=0.0)
    message: Mapped[str] = mapped_column(Text, default="")

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<PolicyViolation team={self.team!r} period={self.period} severity={self.severity}>"
