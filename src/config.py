"""Centralized agent configuration with environment variable overrides.

All thresholds and limits are defined here instead of scattered as magic
numbers. Override any value via COST_AGENT_* environment variables.

Example:
    COST_AGENT_ANOMALY_THRESHOLD=3.0  (default: 2.0)
    COST_AGENT_QUERY_LIMIT=1000       (default: 500)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env_float(key: str, default: float) -> float:
    return float(os.environ.get(key, default))


def _env_int(key: str, default: int) -> int:
    return int(os.environ.get(key, default))


@dataclass(frozen=True)
class AgentConfig:
    anomaly_threshold: float = field(
        default_factory=lambda: _env_float("COST_AGENT_ANOMALY_THRESHOLD", 2.0),
    )
    budget_risk_threshold: float = field(
        default_factory=lambda: _env_float("COST_AGENT_BUDGET_RISK_THRESHOLD", 0.80),
    )
    cpu_underutil_threshold: float = field(
        default_factory=lambda: _env_float("COST_AGENT_CPU_THRESHOLD", 10.0),
    )
    reservation_util_threshold: float = field(
        default_factory=lambda: _env_float("COST_AGENT_RI_THRESHOLD", 0.70),
    )
    max_recommendations: int = field(
        default_factory=lambda: _env_int("COST_AGENT_MAX_RECOMMENDATIONS", 50),
    )
    resource_query_limit: int = field(
        default_factory=lambda: _env_int("COST_AGENT_QUERY_LIMIT", 500),
    )
    metric_lookback_days: int = field(
        default_factory=lambda: _env_int("COST_AGENT_METRIC_DAYS", 30),
    )
    max_input_length: int = field(
        default_factory=lambda: _env_int("COST_AGENT_MAX_INPUT", 4000),
    )


config = AgentConfig()
