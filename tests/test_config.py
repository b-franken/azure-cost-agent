"""Tests for centralized configuration."""

from __future__ import annotations

import os
from unittest.mock import patch

from src.config import AgentConfig


class TestAgentConfig:
    def test_defaults(self) -> None:
        config = AgentConfig()
        assert config.anomaly_threshold == 2.0
        assert config.budget_risk_threshold == 0.80
        assert config.cpu_underutil_threshold == 10.0
        assert config.resource_query_limit == 500
        assert config.max_input_length == 4000

    def test_env_override(self) -> None:
        with patch.dict(os.environ, {"COST_AGENT_ANOMALY_THRESHOLD": "3.5"}):
            config = AgentConfig()
            assert config.anomaly_threshold == 3.5

    def test_frozen(self) -> None:
        import pytest

        config = AgentConfig()
        with pytest.raises(AttributeError):
            config.anomaly_threshold = 99.0  # type: ignore[misc]
