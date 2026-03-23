"""Tests for Resource Graph query helper with pagination."""

from __future__ import annotations

from unittest.mock import MagicMock

from src.graph import run_resource_graph_query


def _make_response(
    data: list[dict[str, str]] | None,
    skip_token: str | None = None,
) -> MagicMock:
    response = MagicMock()
    response.data = data
    response.skip_token = skip_token
    return response


class TestRunResourceGraphQuery:
    def test_single_page(self) -> None:
        clients = MagicMock()
        clients.subscription_ids = ["sub-1"]
        clients.graph.resources.return_value = _make_response(
            [{"name": "vm-1", "rg": "rg-1"}],
        )
        rows = run_resource_graph_query(clients, "resources | take 1")
        assert len(rows) == 1
        assert rows[0]["name"] == "vm-1"

    def test_paginates_with_skip_token(self) -> None:
        clients = MagicMock()
        clients.subscription_ids = ["sub-1"]
        clients.graph.resources.side_effect = [
            _make_response(
                [{"name": "vm-1"}],
                skip_token="token-page-2",
            ),
            _make_response(
                [{"name": "vm-2"}],
                skip_token="token-page-3",
            ),
            _make_response(
                [{"name": "vm-3"}],
                skip_token=None,
            ),
        ]
        rows = run_resource_graph_query(clients, "resources")
        assert len(rows) == 3
        assert [r["name"] for r in rows] == ["vm-1", "vm-2", "vm-3"]
        assert clients.graph.resources.call_count == 3

    def test_empty_response(self) -> None:
        clients = MagicMock()
        clients.subscription_ids = ["sub-1"]
        clients.graph.resources.return_value = _make_response(None)
        rows = run_resource_graph_query(clients, "resources")
        assert rows == []

    def test_values_converted_to_strings(self) -> None:
        clients = MagicMock()
        clients.subscription_ids = ["sub-1"]
        clients.graph.resources.return_value = _make_response(
            [{"count": 42, "active": True}],
        )
        rows = run_resource_graph_query(clients, "resources")
        assert rows[0]["count"] == "42"
        assert rows[0]["active"] == "True"
