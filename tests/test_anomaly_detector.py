"""Tests for anomaly detector agent tools."""

from __future__ import annotations

from unittest.mock import MagicMock

from src.agents.anomaly_detector import detect_anomalies, get_daily_trend


def _make_ctx(clients: object) -> MagicMock:
    ctx = MagicMock()
    ctx.kwargs = {"azure_clients": clients}
    return ctx


def _make_daily_result(rows: list[list]) -> MagicMock:
    result = MagicMock()
    result.rows = rows
    return result


class TestDetectAnomalies:
    def test_finds_spike(self) -> None:
        clients = MagicMock()
        clients.cost_scopes = ["/subscriptions/test-sub"]
        clients.cost.query.usage.return_value = _make_daily_result(
            [
                [10.0, "20260301"],
                [10.0, "20260302"],
                [10.0, "20260303"],
                [50.0, "20260304"],
                [10.0, "20260305"],
            ]
        )
        ctx = _make_ctx(clients)
        result = detect_anomalies(30, 2.0, ctx=ctx)
        assert "20260304" in result
        assert "spike" in result.lower() or "50" in result

    def test_no_anomalies(self) -> None:
        clients = MagicMock()
        clients.cost_scopes = ["/subscriptions/test-sub"]
        clients.cost.query.usage.return_value = _make_daily_result(
            [
                [10.0, "20260301"],
                [11.0, "20260302"],
                [10.5, "20260303"],
            ]
        )
        ctx = _make_ctx(clients)
        result = detect_anomalies(30, 2.0, ctx=ctx)
        assert "no" in result.lower() or "0 anomalies" in result.lower()

    def test_empty_data(self) -> None:
        clients = MagicMock()
        clients.cost_scopes = ["/subscriptions/test-sub"]
        clients.cost.query.usage.return_value = _make_daily_result([])
        ctx = _make_ctx(clients)
        result = detect_anomalies(30, 2.0, ctx=ctx)
        assert "no" in result.lower()


class TestGetDailyTrend:
    def test_returns_trend_table(self) -> None:
        clients = MagicMock()
        clients.cost_scopes = ["/subscriptions/test-sub"]
        clients.cost.query.usage.return_value = _make_daily_result(
            [
                [10.0, "20260301"],
                [20.0, "20260302"],
            ]
        )
        ctx = _make_ctx(clients)
        result = get_daily_trend(14, ctx=ctx)
        assert "20260301" in result
        assert "20260302" in result

    def test_empty_data(self) -> None:
        clients = MagicMock()
        clients.cost_scopes = ["/subscriptions/test-sub"]
        clients.cost.query.usage.return_value = _make_daily_result([])
        ctx = _make_ctx(clients)
        result = get_daily_trend(14, ctx=ctx)
        assert "no" in result.lower()
