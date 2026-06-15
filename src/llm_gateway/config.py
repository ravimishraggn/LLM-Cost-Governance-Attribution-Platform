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

    # Provider credentials (only required when mock mode is off)
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    aws_region: str = "us-east-1"


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
