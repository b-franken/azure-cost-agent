"""Anomaly Detector agent — proactive cost spike detection."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Annotated

from agent_framework import FunctionInvocationContext, tool
from azure.mgmt.costmanagement.models import (
    QueryAggregation,
    QueryDataset,
    QueryDefinition,
    QueryTimePeriod,
)
from pydantic import Field

from src.agents._context import get_clients
from src.config import config

if TYPE_CHECKING:
    from src.azure_clients import AzureClients

INSTRUCTIONS = """\
You are a cost anomaly detection specialist.

Rules:
- Use detect_anomalies to find unexpected cost spikes.
- Use get_daily_trend to show day-by-day cost progression.
- Flag any day where cost exceeds 2x the 30-day average.
- Present anomalies with the date, cost, and percentage above baseline.
"""

DESCRIPTION = (
    "Detects cost anomalies and spend spikes by comparing daily costs "
    "against rolling baselines"
)


def _query_daily_costs(
    clients: AzureClients,
    days: int,
) -> list[tuple[str, float]]:
    """Query daily costs for the given period."""
    end = datetime.now(tz=UTC)
    start = end - timedelta(days=days)

    query_def = QueryDefinition(
        type="ActualCost",
        timeframe="Custom",
        time_period=QueryTimePeriod(from_property=start, to=end),
        dataset=QueryDataset(
            granularity="Daily",
            aggregation={
                "totalCost": QueryAggregation(
                    name="PreTaxCost",
                    function="Sum",
                ),
            },
        ),
    )

    by_date: dict[str, float] = {}
    for scope in clients.cost_scopes:
        result = clients.cost.query.usage(scope=scope, parameters=query_def)
        if not result or not result.rows:
            continue
        for row in result.rows:
            date_val = str(row[1])[:10]
            by_date[date_val] = by_date.get(date_val, 0.0) + float(row[0])

    if not by_date:
        return []

    return sorted(by_date.items(), key=lambda x: x[0])


@tool
def detect_anomalies(
    days: Annotated[
        int,
        Field(description="Number of days to analyze for anomalies"),
    ] = 30,
    threshold: Annotated[
        float,
        Field(description="Multiplier above average to flag as anomaly"),
    ] = config.anomaly_threshold,
    ctx: FunctionInvocationContext | None = None,
) -> str:
    """Detect days where cost exceeds the threshold multiplied by the average."""
    clients = get_clients(ctx)
    daily = _query_daily_costs(clients, days)

    if not daily:
        return "No daily cost data available."

    total = sum(cost for _, cost in daily)
    avg = total / len(daily)

    anomalies = [
        (date, cost, ((cost - avg) / avg) * 100)
        for date, cost in daily
        if cost > avg * threshold
    ]

    if not anomalies:
        return (
            f"No anomalies detected in the last {days} days.\nDaily average: {avg:.2f}"
        )

    lines = [
        f"Cost Anomalies (>{threshold}x daily average of {avg:.2f}):\n",
        f"{'Date':<12} {'Cost':>10} {'Above avg':>12}",
        "-" * 36,
    ]
    for date, cost, pct in sorted(anomalies, key=lambda x: -x[1]):
        lines.append(f"{date:<12} {cost:>10.2f} {pct:>+11.1f}%")

    lines.append(f"\n{len(anomalies)} anomalous days found.")
    return "\n".join(lines)


@tool
def get_daily_trend(
    days: Annotated[
        int,
        Field(description="Number of days to show"),
    ] = 14,
    ctx: FunctionInvocationContext | None = None,
) -> str:
    """Show day-by-day cost trend for the specified period."""
    clients = get_clients(ctx)
    daily = _query_daily_costs(clients, days)

    if not daily:
        return "No daily cost data available."

    lines = [
        f"Daily Cost Trend (last {days} days):\n",
        f"{'Date':<12} {'Cost':>10}",
        "-" * 24,
    ]
    total = 0.0
    for date, cost in daily:
        total += cost
        lines.append(f"{date:<12} {cost:>10.2f}")

    lines.append("-" * 24)
    lines.append(f"{'Total':<12} {total:>10.2f}")
    lines.append(f"{'Avg/day':<12} {total / len(daily):>10.2f}")
    return "\n".join(lines)
