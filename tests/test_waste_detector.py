"""Tests for waste detector agent tools."""

from __future__ import annotations

from unittest.mock import MagicMock

from src.agents.waste_detector import (
    _format_with_cost,
    _run_query,
    find_idle_resources,
    find_orphaned_resources,
    find_oversized_resources,
    find_underutilized_vms,
)


def _make_ctx(**kwargs: object) -> MagicMock:
    ctx = MagicMock()
    ctx.kwargs = kwargs
    return ctx


def _make_graph_response(
    columns: list[str],
    rows: list[list[str]],
) -> MagicMock:
    response = MagicMock()
    response.data = [dict(zip(columns, row, strict=True)) for row in rows]
    response.skip_token = None
    return response


def _empty_response() -> MagicMock:
    response = MagicMock()
    response.data = None
    response.skip_token = None
    return response


class TestFormat:
    def test_formats_rows(self) -> None:
        rows = [
            {
                "name": "vm-test",
                "resourceGroup": "rg-dev",
                "location": "westeurope",
                "powerState": "VM deallocated",
            },
        ]
        output, cost = _format_with_cost("Stopped VMs", rows)
        assert "vm-test" in output
        assert "rg-dev" in output
        assert "(1)" in output
        assert cost == 0.0

    def test_empty_results(self) -> None:
        output, cost = _format_with_cost("Stopped VMs", [])
        assert "none found" in output
        assert cost == 0.0


class TestRunQuery:
    def test_returns_dicts(self) -> None:
        clients = MagicMock()
        clients.subscription_id = "test-sub"
        clients.graph.resources.return_value = _make_graph_response(
            ["name", "resourceGroup"],
            [["vm-1", "rg-prod"]],
        )
        rows = _run_query(clients, "test query")
        assert len(rows) == 1
        assert rows[0]["name"] == "vm-1"

    def test_handles_empty(self) -> None:
        clients = MagicMock()
        clients.subscription_id = "test-sub"
        clients.graph.resources.return_value = _empty_response()
        assert _run_query(clients, "test") == []


class TestFindIdleResources:
    def test_finds_stopped_vms_and_empty_plans(self) -> None:
        clients = MagicMock()
        clients.subscription_id = "test-sub"

        vm_resp = _make_graph_response(
            ["name", "resourceGroup", "location", "vmSize", "powerState", "id"],
            [
                [
                    "vm-idle",
                    "rg-dev",
                    "westeurope",
                    "Standard_D4s_v5",
                    "VM deallocated",
                    "/sub/vm",
                ]
            ],
        )
        empty_plan_resp = _make_graph_response(
            ["name", "resourceGroup", "location", "sku", "tier", "id"],
            [["asp-unused", "rg-dev", "westeurope", "S1", "Standard", "/sub/asp"]],
        )
        empty_lb = _empty_response()

        clients.graph.resources.side_effect = [
            vm_resp,
            empty_plan_resp,
            empty_lb,
            _empty_response(),
        ]
        ctx = _make_ctx(azure_clients=clients)
        result = find_idle_resources(ctx=ctx)
        assert "vm-idle" in result
        assert "asp-unused" in result


class TestFindOrphanedResources:
    def test_finds_orphaned_disks(self) -> None:
        clients = MagicMock()
        clients.subscription_id = "test-sub"

        disk_resp = _make_graph_response(
            ["name", "resourceGroup", "location", "sku", "sizeGb", "id"],
            [["disk-orphan", "rg-prod", "eastus", "Premium_LRS", "128", "/sub/disk"]],
        )
        clients.graph.resources.side_effect = [
            disk_resp,
            _empty_response(),
            _empty_response(),
            _empty_response(),
            _empty_response(),
        ]
        ctx = _make_ctx(azure_clients=clients)
        result = find_orphaned_resources(ctx=ctx)
        assert "disk-orphan" in result
        assert "Premium_LRS" in result


class TestFindOversizedResources:
    def test_finds_premium_databases(self) -> None:
        clients = MagicMock()
        clients.subscription_id = "test-sub"

        db_resp = _make_graph_response(
            ["name", "resourceGroup", "location", "tier", "capacity", "id"],
            [["db-dev", "rg-dev", "westeurope", "Premium", "125", "/sub/db"]],
        )
        clients.graph.resources.side_effect = [db_resp, _empty_response()]
        ctx = _make_ctx(azure_clients=clients)
        result = find_oversized_resources(ctx=ctx)
        assert "db-dev" in result
        assert "Premium" in result


class TestFindUnderutilizedVms:
    def test_finds_low_cpu_vms(self) -> None:
        clients = MagicMock()
        clients.subscription_id = "test-sub"
        monitor = MagicMock()

        vm_resp = _make_graph_response(
            ["name", "resourceGroup", "location", "vmSize", "id"],
            [["vm-quiet", "rg-prod", "eastus", "Standard_D8s_v5", "/sub/vm-quiet"]],
        )
        clients.graph.resources.return_value = vm_resp
        ctx = _make_ctx(azure_clients=clients, monitor_client=monitor)

        from unittest.mock import patch

        with patch("src.metrics.get_avg_cpu", return_value=3.2):
            result = find_underutilized_vms(10.0, ctx=ctx)
        assert "vm-quiet" in result
        assert "3.2%" in result
        assert "Standard_D8s_v5" in result

    def test_no_monitor_client(self) -> None:
        clients = MagicMock()
        ctx = _make_ctx(azure_clients=clients)
        result = find_underutilized_vms(10.0, ctx=ctx)
        assert "Monitor client not configured" in result


class TestPricing:
    def test_get_sku_price(self) -> None:
        from unittest.mock import patch

        from src.pricing import get_monthly_cost

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "Items": [{"retailPrice": 0.096}],
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response

        with patch("src.pricing.httpx.Client", return_value=mock_client):
            cost = get_monthly_cost("Standard_D2s_v5", "swedencentral")
        assert cost is not None
        assert cost == round(0.096 * 730, 2)

    def test_compare_sku_costs(self) -> None:
        from unittest.mock import patch

        from src.pricing import compare_sku_costs

        def mock_get(*args: object, **kwargs: object) -> MagicMock:
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            url_filter = str(kwargs.get("params", {}).get("$filter", ""))
            if "D8s_v5" in url_filter:
                resp.json.return_value = {"Items": [{"retailPrice": 0.384}]}
            else:
                resp.json.return_value = {"Items": [{"retailPrice": 0.096}]}
            return resp

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.side_effect = mock_get

        with patch("src.pricing.httpx.Client", return_value=mock_client):
            result = compare_sku_costs(
                "Standard_D8s_v5",
                "Standard_D2s_v5",
                "swedencentral",
            )
        assert result["monthly_savings"] is not None
        assert result["monthly_savings"] > 0
