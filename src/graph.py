"""Shared Resource Graph query helper with pagination."""

from __future__ import annotations

from typing import TYPE_CHECKING

from azure.mgmt.resourcegraph.models import (
    QueryRequest,
    QueryRequestOptions,
)

from src.config import config

if TYPE_CHECKING:
    from src.azure_clients import AzureClients


def run_resource_graph_query(
    clients: AzureClients,
    query: str,
) -> list[dict[str, str]]:
    """Execute a Resource Graph query with automatic pagination.

    Paginates using ``$skipToken`` until all results are collected.
    Each page requests up to ``config.resource_query_limit`` rows.
    """
    all_rows: list[dict[str, str]] = []
    options = QueryRequestOptions(top=config.resource_query_limit)
    request = QueryRequest(
        query=query,
        subscriptions=clients.subscription_ids,
        options=options,
    )

    while True:
        response = clients.graph.resources(query=request)
        if response.data:
            for row in response.data:
                if isinstance(row, dict):
                    all_rows.append(  # noqa: PERF401
                        {k: str(v) for k, v in row.items()}
                    )

        skip_token = getattr(response, "skip_token", None)
        if not skip_token:
            break
        if request.options:
            request.options.skip_token = skip_token

    return all_rows
