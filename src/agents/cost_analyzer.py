"""Cost Analyzer agent — queries Azure Cost Management for spend data."""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Annotated, Any

from agent_framework import FunctionInvocationContext, tool
from azure.mgmt.costmanagement.models import (
    QueryAggregation,
    QueryDataset,
    QueryDefinition,
    QueryGrouping,
    QueryTimePeriod,
)
from pydantic import Field

from src.agents._context import get_clients

if TYPE_CHECKING:
    from src.azure_clients import AzureClients


def _query_all_scopes(
    clients: AzureClients,
    query_def: QueryDefinition,
) -> list[list[Any]]:
    all_rows: list[list[Any]] = []
    for scope in clients.cost_scopes:
        result = clients.cost.query.usage(scope=scope, parameters=query_def)
        if result and result.rows:
            all_rows.extend(result.rows)
    return all_rows


def _aggregate_rows(rows: list[list[Any]]) -> list[list[Any]]:
    merged: dict[str, list[Any]] = {}
    for row in rows:
        cost, key = float(row[0]), str(row[1])
        currency = row[2] if len(row) > 2 else ""
        if key in merged:
            merged[key][0] += cost
        else:
            merged[key] = [cost, key, currency]
    return list(merged.values())


INSTRUCTIONS = """\
You are a cost analysis specialist for Azure subscriptions.

Rules:
- Always use tools to get real data before answering.
- Present costs in a clear table format.
- Highlight significant changes (>10%) compared to previous periods.
- Round currency values to 2 decimal places.
- If the user asks about trends, use compare_periods.
"""

DESCRIPTION = "Analyzes Azure spend: breakdowns by resource group, service, or resource"


def _build_query(
    timeframe: str,
    group_by: str,
    days: int | None = None,
) -> tuple[QueryDefinition, str]:
    """Build a Cost Management query definition."""
    aggregation = {
        "totalCost": QueryAggregation(
            name="PreTaxCost",
            function="Sum",
        ),
    }
    grouping = [QueryGrouping(type="Dimension", name=group_by)]

    time_period = None
    if timeframe == "Custom" and days:
        end = datetime.now(tz=UTC)
        start = end - timedelta(days=days)
        time_period = QueryTimePeriod(
            from_property=start,
            to=end,
        )

    query_def = QueryDefinition(
        type="ActualCost",
        timeframe=timeframe,
        time_period=time_period,
        dataset=QueryDataset(
            granularity="None",
            aggregation=aggregation,
            grouping=grouping,
        ),
    )
    return query_def, group_by


def _format_rows(rows: list[list[Any]], group_label: str) -> str:
    if not rows:
        return "No cost data found for this period."

    lines: list[str] = [f"{'Name':<40} {'Cost':>12} {'Currency':>8}"]
    lines.append("-" * 62)

    total = 0.0
    for row in rows:
        cost, name = float(row[0]), str(row[1])
        currency = str(row[2]) if len(row) > 2 and row[2] else "USD"
        total += cost
        lines.append(f"{name:<40} {cost:>12.2f} {currency:>8}")

    lines.append("-" * 62)
    lines.append(f"{'TOTAL':<40} {total:>12.2f}")
    return "\n".join(lines)


@tool
def query_costs(
    timeframe: Annotated[
        str,
        Field(
            description=(
                "Time range: MonthToDate, TheLastMonth, "
                "BillingMonthToDate, or TheLastBillingMonth"
            ),
        ),
    ] = "MonthToDate",
    group_by: Annotated[
        str,
        Field(
            description=(
                "Group costs by: ResourceGroupName, ServiceName, or ResourceId"
            ),
        ),
    ] = "ResourceGroupName",
    ctx: FunctionInvocationContext | None = None,
) -> str:
    """Query Azure costs grouped by a dimension."""
    clients = get_clients(ctx)
    query_def, label = _build_query(timeframe, group_by)
    rows = _aggregate_rows(_query_all_scopes(clients, query_def))
    if not rows:
        return "No cost data returned."
    rows.sort(key=lambda r: -r[0])
    return _format_rows(rows, label)


@tool
def compare_periods(
    days: Annotated[
        int,
        Field(description="Period length in days to compare"),
    ] = 30,
    ctx: FunctionInvocationContext | None = None,
) -> str:
    """Compare current period costs with the previous period."""
    clients = get_clients(ctx)

    now = datetime.now(tz=UTC)
    current_start = now - timedelta(days=days)
    previous_start = current_start - timedelta(days=days)

    base_dataset = QueryDataset(
        granularity="None",
        aggregation={
            "totalCost": QueryAggregation(
                name="PreTaxCost",
                function="Sum",
            ),
        },
        grouping=[
            QueryGrouping(type="Dimension", name="ResourceGroupName"),
        ],
    )

    current_query = QueryDefinition(
        type="ActualCost",
        timeframe="Custom",
        time_period=QueryTimePeriod(
            from_property=current_start,
            to=now,
        ),
        dataset=base_dataset,
    )
    previous_query = QueryDefinition(
        type="ActualCost",
        timeframe="Custom",
        time_period=QueryTimePeriod(
            from_property=previous_start,
            to=current_start,
        ),
        dataset=base_dataset,
    )

    current_rows = _query_all_scopes(clients, current_query)
    previous_rows = _query_all_scopes(clients, previous_query)

    current_total = sum(float(r[0]) for r in current_rows)
    previous_total = sum(float(r[0]) for r in previous_rows)

    if previous_total > 0:
        delta_pct = ((current_total - previous_total) / previous_total) * 100
        direction = "up" if delta_pct > 0 else "down"
        arrow = "\u2191" if delta_pct > 0 else "\u2193"
    else:
        delta_pct = 0.0
        direction = "flat"
        arrow = "\u2192"

    return (
        f"Period comparison ({days} days):\n"
        f"  Current:  {current_total:>10.2f}\n"
        f"  Previous: {previous_total:>10.2f}\n"
        f"  Change:   {arrow} {abs(delta_pct):.1f}% {direction}"
    )


@tool
def top_spenders(
    count: Annotated[
        int,
        Field(description="Number of top resources to return"),
    ] = 10,
    ctx: FunctionInvocationContext | None = None,
) -> str:
    """Find the most expensive resources this month."""
    clients = get_clients(ctx)
    query_def, _ = _build_query("MonthToDate", "ResourceId")
    rows = _aggregate_rows(_query_all_scopes(clients, query_def))
    if not rows:
        return "No cost data found."

    sorted_rows = sorted(
        rows,
        key=lambda r: float(r[0]),
        reverse=True,
    )[:count]

    lines = [f"Top {count} most expensive resources (month to date):\n"]
    for i, row in enumerate(sorted_rows, 1):
        cost = float(row[0])
        resource_id = str(row[1]).split("/")[-1] or str(row[1])
        lines.append(f"  {i}. {resource_id}: {cost:.2f}")

    total = sum(float(r[0]) for r in rows)
    lines.append(f"\nTotal subscription spend: {total:.2f}")
    return "\n".join(lines)


def _build_period_queries(
    days: int,
    group_by: str,
) -> tuple[QueryDefinition, QueryDefinition]:
    now = datetime.now(tz=UTC)
    current_start = now - timedelta(days=days)
    previous_start = current_start - timedelta(days=days)

    dataset = QueryDataset(
        granularity="None",
        aggregation={
            "totalCost": QueryAggregation(name="PreTaxCost", function="Sum"),
        },
        grouping=[QueryGrouping(type="Dimension", name=group_by)],
    )

    current = QueryDefinition(
        type="ActualCost",
        timeframe="Custom",
        time_period=QueryTimePeriod(from_property=current_start, to=now),
        dataset=dataset,
    )
    previous = QueryDefinition(
        type="ActualCost",
        timeframe="Custom",
        time_period=QueryTimePeriod(from_property=previous_start, to=current_start),
        dataset=dataset,
    )
    return previous, current


def _rows_to_dict(rows: list[list[Any]]) -> dict[str, float]:
    result: dict[str, float] = {}
    for row in rows:
        cost, key = float(row[0]), str(row[1])
        result[key] = result.get(key, 0.0) + cost
    return result


@tool
def export_cost_diff(
    days: Annotated[
        int,
        Field(description="Period length in days to compare"),
    ] = 30,
    group_by: Annotated[
        str,
        Field(
            description=("Group by: ResourceGroupName, SubscriptionId, or ServiceName"),
        ),
    ] = "ResourceGroupName",
    ctx: FunctionInvocationContext | None = None,
) -> str:
    """Export a CSV cost comparison between current and previous period."""
    clients = get_clients(ctx)

    previous_query, current_query = _build_period_queries(days, group_by)
    previous_data = _rows_to_dict(_query_all_scopes(clients, previous_query))
    current_data = _rows_to_dict(_query_all_scopes(clients, current_query))

    all_keys = sorted(set(previous_data) | set(current_data))
    if not all_keys:
        return "No cost data available for the selected period."

    label = group_by.replace("Name", "").replace("Id", "")
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            label,
            f"Previous {days}d",
            f"Current {days}d",
            "Difference",
            "Change %",
        ]
    )

    prev_total = 0.0
    curr_total = 0.0

    for key in all_keys:
        prev = previous_data.get(key, 0.0)
        curr = current_data.get(key, 0.0)
        diff = curr - prev
        pct = (diff / prev * 100) if prev > 0 else 0.0

        display_key = key.split("/")[-1] if "/" in key else key
        writer.writerow(
            [
                display_key,
                f"{prev:.2f}",
                f"{curr:.2f}",
                f"{diff:+.2f}",
                f"{pct:+.1f}%",
            ]
        )
        prev_total += prev
        curr_total += curr

    total_diff = curr_total - prev_total
    total_pct = (total_diff / prev_total * 100) if prev_total > 0 else 0.0
    writer.writerow(
        [
            "TOTAL",
            f"{prev_total:.2f}",
            f"{curr_total:.2f}",
            f"{total_diff:+.2f}",
            f"{total_pct:+.1f}%",
        ]
    )

    return output.getvalue()
