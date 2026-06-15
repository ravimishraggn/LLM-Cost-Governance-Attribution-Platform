"""Per-team budgets, loaded from config (Phase 5 / ADR-007).

Policy-as-config: budgets and alert thresholds are data, not code, so they can
be tuned without a deploy. The dashboard uses these for budget-vs-actual; Phase 6
uses them to flag policy violations.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from .config import get_settings

logger = logging.getLogger(__name__)

DEFAULT_BUDGET_USD = 100.0
DEFAULT_THRESHOLD_PCT = 80.0


@dataclass(frozen=True)
class TeamBudget:
    monthly_budget_usd: float
    alert_threshold_pct: float


class BudgetBook:
    def __init__(self, raw: dict):
        self.currency: str = str(raw.get("currency", "USD"))
        self.period: str = str(raw.get("period", "monthly"))
        d = raw.get("default") or {}
        self.default = TeamBudget(
            float(d.get("monthly_budget_usd", DEFAULT_BUDGET_USD)),
            float(d.get("alert_threshold_pct", DEFAULT_THRESHOLD_PCT)),
        )
        self._teams: dict[str, TeamBudget] = {
            name: TeamBudget(
                float(cfg.get("monthly_budget_usd", self.default.monthly_budget_usd)),
                float(cfg.get("alert_threshold_pct", self.default.alert_threshold_pct)),
            )
            for name, cfg in (raw.get("teams") or {}).items()
        }

    def for_team(self, team: str) -> TeamBudget:
        return self._teams.get(team, self.default)

    @property
    def teams(self) -> dict[str, TeamBudget]:
        return dict(self._teams)

    def as_dict(self) -> dict:
        return {
            "currency": self.currency,
            "period": self.period,
            "default": vars(self.default),
            "teams": {name: vars(b) for name, b in self._teams.items()},
        }


def _load_book() -> BudgetBook:
    path = Path(get_settings().budgets_config_path)
    if not path.exists():
        logger.warning("Budgets config not found at %s; using defaults only", path)
        return BudgetBook({})
    with path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    return BudgetBook(raw)


@lru_cache
def get_budget_book() -> BudgetBook:
    """Cached budget book singleton."""
    return _load_book()


def reload_budget_book() -> BudgetBook:
    get_budget_book.cache_clear()
    return get_budget_book()
