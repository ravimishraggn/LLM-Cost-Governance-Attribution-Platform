"""Application configuration, loaded from environment / `.env`.

Centralizes every tunable so the gateway's behaviour is config-driven rather
than hardcoded (a theme that recurs across the platform — see ADR-003 on
externalized pricing).
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Behaviour
    gateway_mock_mode: bool = True

    # Storage
    database_url: str = "sqlite:///./llm_gov.db"

    # Pricing (Phase 2) — external, updatable rate card (see ADR-003)
    pricing_config_path: str = "config/pricing.yaml"

    # Observability (Phase 3) — Langfuse tracing (see ADR-004). Off by default;
    # a no-op tracer is used unless enabled AND both keys are present.
    langfuse_enabled: bool = False
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str = "https://cloud.langfuse.com"

    # Model router (Phase 4) — rule-based routing (see ADR-005)
    router_enabled: bool = True
    routing_config_path: str = "config/routing.yaml"

    # Provider credentials (only required when mock mode is off)
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    aws_region: str = "us-east-1"


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
