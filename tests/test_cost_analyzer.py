"""Tests for cost analyzer agent tools."""

from __future__ import annotations

from unittest.mock import MagicMock

from src.agents.cost_analyzer import (
    _build_query,
    _format_rows,
    compare_periods,
    query_costs,
    top_spenders,
)


def _make_ctx(clients: object) -> MagicMock:
    ctx = MagicMock()
    ctx.kwargs = {"azure_clients": clients}
    return ctx


def _make_query_result(
    rows: list[list[object]],
    columns: list[str] | None = None,
) -> MagicMock:
    result = MagicMock()
    result.rows = rows
    if columns is None:
        columns = ["PreTaxCost", "GroupName", "Currency"]
    col_mocks = []
    for name in columns:
        col = MagicMock()
        col.name = name
        col_mocks.append(col)
    result.columns = col_mocks
    return result


class TestBuildQuery:
    def test_month_to_date(self) -> None:
        query_def, label = _build_query("MonthToDate", "ResourceGroupName")
        assert query_def.type == "ActualCost"
        assert query_def.timeframe == "MonthToDate"
        assert query_def.time_period is None
        assert label == "ResourceGroupName"

    def test_custom_timeframe(self) -> None:
        query_def, _ = _build_query("Custom", "ServiceName", days=30)
        assert query_def.timeframe == "Custom"
        assert query_def.time_period is not None


class TestFormatRows:
    def test_formats_rows(self) -> None:
        rows = [
            [487.32, "rg-production", "USD"],
            [123.45, "rg-staging", "USD"],
        ]
        output = _format_rows(rows, "ResourceGroupName")
        assert "rg-production" in output
        assert "487.32" in output
        assert "TOTAL" in output
        assert "610.77" in output

    def test_empty_result(self) -> None:
        output = _format_rows([], "ResourceGroupName")
        assert "No cost data" in output


class TestQueryCosts:
    def test_returns_formatted_costs(self) -> None:
        clients = MagicMock()
        clients.cost_scopes = ["/subscriptions/test-sub"]
        clients.cost.query.usage.return_value = _make_query_result(
            [[250.00, "rg-web", "EUR"]],
        )
        ctx = _make_ctx(clients)
        result = query_costs("MonthToDate", "ResourceGroupName", ctx=ctx)
        assert "rg-web" in result
        assert "250.00" in result

    def test_handles_none_result(self) -> None:
        clients = MagicMock()
        clients.cost_scopes = ["/subscriptions/test-sub"]
        clients.cost.query.usage.return_value = None
        ctx = _make_ctx(clients)
        result = query_costs("MonthToDate", ctx=ctx)
        assert "No cost data" in result


class TestComparePeriods:
    def test_shows_increase(self) -> None:
        clients = MagicMock()
        clients.cost_scopes = ["/subscriptions/test-sub"]
        current = _make_query_result([[200.0, "rg-1"]])
        previous = _make_query_result([[100.0, "rg-1"]])
        clients.cost.query.usage.side_effect = [current, previous]
        ctx = _make_ctx(clients)
        result = compare_periods(30, ctx=ctx)
        assert "100.0%" in result
        assert "up" in result

    def test_shows_decrease(self) -> None:
        clients = MagicMock()
        clients.cost_scopes = ["/subscriptions/test-sub"]
        current = _make_query_result([[50.0, "rg-1"]])
        previous = _make_query_result([[100.0, "rg-1"]])
        clients.cost.query.usage.side_effect = [current, previous]
        ctx = _make_ctx(clients)
        result = compare_periods(30, ctx=ctx)
        assert "50.0%" in result
        assert "down" in result


class TestTopSpenders:
    def test_returns_top_resources(self) -> None:
        clients = MagicMock()
        clients.cost_scopes = ["/subscriptions/test-sub"]
        clients.cost.query.usage.return_value = _make_query_result(
            [
                [500.0, "/sub/rg/providers/type/expensive-vm"],
                [10.0, "/sub/rg/providers/type/cheap-disk"],
                [200.0, "/sub/rg/providers/type/mid-db"],
            ],
        )
        ctx = _make_ctx(clients)
        result = top_spenders(2, ctx=ctx)
        assert "expensive-vm" in result
        assert "mid-db" in result
        assert "1." in result
        assert "2." in result
