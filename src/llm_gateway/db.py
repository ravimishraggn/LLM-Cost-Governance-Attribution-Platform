"""Database engine and session management.

SQLAlchemy is used so the storage backend is swappable via `DATABASE_URL`:
SQLite for local/MVP, Postgres for production — no code change required.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from .config import get_settings
from .models import Base


def _make_engine():
    url = get_settings().database_url
    kwargs: dict = {"future": True}
    if url.startswith("sqlite"):
        # check_same_thread is a SQLite-only concern (FastAPI serves from a threadpool).
        kwargs["connect_args"] = {"check_same_thread": False}
        # In-memory SQLite gives each *connection* its own empty DB. Pin a single
        # shared connection so tables and rows persist across sessions (used in tests).
        if ":memory:" in url:
            kwargs["poolclass"] = StaticPool
    return create_engine(url, **kwargs)


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def init_db() -> None:
    """Create tables if they don't exist. Safe to call on every startup."""
    Base.metadata.create_all(bind=engine)


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional session scope — commits on success, rolls back on error."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
