"""Tests for tag analyzer agent tools."""

from __future__ import annotations

from unittest.mock import MagicMock

from src.agents.tag_analyzer import (
    find_resources_missing_tag,
    find_untagged_resources,
    tag_coverage_report,
)


def _make_ctx(clients: object) -> MagicMock:
    ctx = MagicMock()
    ctx.kwargs = {"azure_clients": clients}
    return ctx


def _mock_graph_response(rows: list[dict]) -> MagicMock:
    response = MagicMock()
    response.data = rows
    response.skip_token = None
    return response


class TestFindUntaggedResources:
    def test_finds_untagged(self) -> None:
        clients = MagicMock()
        clients.subscription_ids = ["test-sub"]
        clients.graph.resources.return_value = _mock_graph_response(
            [
                {
                    "name": "vm-1",
                    "type": "Microsoft.Compute/virtualMachines",
                    "resourceGroup": "rg-1",
                    "location": "westeurope",
                },
            ]
        )
        ctx = _make_ctx(clients)
        result = find_untagged_resources(ctx=ctx)
        assert "vm-1" in result
        assert "1 resource" in result.lower() or "1" in result

    def test_no_untagged(self) -> None:
        clients = MagicMock()
        clients.subscription_ids = ["test-sub"]
        clients.graph.resources.return_value = _mock_graph_response([])
        ctx = _make_ctx(clients)
        result = find_untagged_resources(ctx=ctx)
        assert "all" in result.lower() or "0" in result or "no" in result.lower()


class TestFindResourcesMissingTag:
    def test_finds_missing(self) -> None:
        clients = MagicMock()
        clients.subscription_ids = ["test-sub"]
        clients.graph.resources.return_value = _mock_graph_response(
            [
                {
                    "name": "vm-1",
                    "type": "Microsoft.Compute/virtualMachines",
                    "resourceGroup": "rg-1",
                },
            ]
        )
        ctx = _make_ctx(clients)
        result = find_resources_missing_tag("environment", ctx=ctx)
        assert "vm-1" in result

    def test_invalid_tag_key(self) -> None:
        ctx = _make_ctx(MagicMock())
        result = find_resources_missing_tag("'; DROP TABLE--", ctx=ctx)
        assert "invalid" in result.lower()

    def test_all_tagged(self) -> None:
        clients = MagicMock()
        clients.subscription_ids = ["test-sub"]
        clients.graph.resources.return_value = _mock_graph_response([])
        ctx = _make_ctx(clients)
        result = find_resources_missing_tag("environment", ctx=ctx)
        assert "all" in result.lower()


class TestTagCoverageReport:
    def test_returns_coverage_table(self) -> None:
        clients = MagicMock()
        clients.subscription_ids = ["test-sub"]
        clients.graph.resources.return_value = _mock_graph_response(
            [
                {"type": "virtualMachines", "total": 10, "tagged": 8},
            ]
        )
        ctx = _make_ctx(clients)
        result = tag_coverage_report(ctx=ctx)
        assert "virtualMachines" in result or "Coverage" in result
