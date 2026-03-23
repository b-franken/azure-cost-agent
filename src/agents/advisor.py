"""Advisor agent — retrieves and prioritizes Azure Advisor cost recommendations."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Annotated, Any

from agent_framework import FunctionInvocationContext, tool
from pydantic import Field

from src.agents._context import get_clients
from src.config import config

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from src.azure_clients import AzureClients

INSTRUCTIONS = """\
You are an Azure Advisor specialist focused on cost optimization.

Rules:
- Always use get_prioritized_recommendations first — it sorts by impact.
- Use get_reservation_recommendations for RI/savings plan questions.
- Use get_reservation_coverage to analyze current RI/SP utilization.
- Present the top recommendations clearly with impact and affected resource.
- When asked about total savings potential, sum the High-impact items.
"""

DESCRIPTION = (
    "Retrieves and prioritizes Azure Advisor cost recommendations: "
    "rightsizing, reservations, unused resources, and RI/SP coverage"
)

_IMPACT_ORDER = {"High": 0, "Medium": 1, "Low": 2, "Unknown": 3}


def _extract_recommendation(rec: object) -> dict[str, str]:
    """Extract fields from an Advisor recommendation object."""
    impact = getattr(rec, "impact", None) or "Unknown"
    short_desc = getattr(rec, "short_description", None)
    problem = getattr(short_desc, "problem", None) or "—" if short_desc else "—"
    solution = getattr(short_desc, "solution", None) or "—" if short_desc else "—"

    metadata = getattr(rec, "resource_metadata", None)
    resource_id = ""
    if metadata and getattr(metadata, "resource_id", None):
        resource_id = metadata.resource_id

    resource_name = resource_id.split("/")[-1] if resource_id else "unknown"
    category = _classify(problem)

    return {
        "impact": str(impact),
        "problem": str(problem),
        "solution": str(solution),
        "resource": resource_name,
        "resource_id": resource_id,
        "category": category,
    }


def _classify(problem: str) -> str:
    """Classify a recommendation into a category."""
    lower = problem.lower()
    if any(kw in lower for kw in ("right-size", "rightsize", "resize", "scale")):
        return "Rightsizing"
    if any(kw in lower for kw in ("reserved", "reservation", "savings plan")):
        return "Reservations"
    if any(kw in lower for kw in ("unused", "idle", "shutdown", "deallocate")):
        return "Unused resources"
    return "Other"


@tool
def get_prioritized_recommendations(
    ctx: FunctionInvocationContext | None = None,
) -> str:
    """Get cost recommendations sorted by impact (High → Medium → Low)."""
    clients = get_clients(ctx)
    recs = _fetch_cost_recommendations(clients)

    if not recs:
        return "No cost optimization recommendations from Azure Advisor."

    by_category: dict[str, list[dict[str, str]]] = {}
    for rec in recs:
        by_category.setdefault(rec["category"], []).append(rec)

    lines = [f"Azure Advisor Cost Recommendations ({len(recs)}):\n"]

    for category, items in by_category.items():
        lines.append(f"\n  {category} ({len(items)}):")
        lines.extend(
            f"    [{item['impact'].upper()}] {item['problem']}\n"
            f"      Resource: {item['resource']}\n"
            f"      Fix: {item['solution']}"
            for item in items
        )

    high_count = sum(1 for r in recs if r["impact"] == "High")
    if high_count:
        lines.append(f"\n  {high_count} high-impact items — address these first.")

    return "\n".join(lines)


def _fetch_cost_recommendations(clients: AzureClients) -> list[dict[str, str]]:
    raw: list[object] = []
    for sub_id in clients.subscription_ids:
        advisor = clients.advisor_for(sub_id)
        raw.extend(
            advisor.recommendations.list(
                filter="Category eq 'Cost'",
                top=config.max_recommendations,
            ),
        )
    recs = [_extract_recommendation(r) for r in raw]
    recs.sort(key=lambda r: _IMPACT_ORDER.get(r["impact"], 99))
    return recs


@tool
def get_reservation_recommendations(
    ctx: FunctionInvocationContext | None = None,
) -> str:
    """Get reserved instance and savings plan recommendations."""
    clients = get_clients(ctx)
    all_recs = _fetch_cost_recommendations(clients)
    recs = [r for r in all_recs if r["category"] == "Reservations"]

    if not recs:
        return "No reservation or savings plan recommendations found."

    lines = [f"Reservation Recommendations ({len(recs)}):\n"]
    lines.extend(
        f"  - {rec['problem']}\n"
        f"    Resource: {rec['resource']}\n"
        f"    Action: {rec['solution']}"
        for rec in recs
    )
    return "\n".join(lines)


@tool
def get_reservation_coverage(
    ctx: FunctionInvocationContext | None = None,
) -> str:
    """Analyze current RI and Savings Plan utilization and coverage."""
    from datetime import UTC, datetime, timedelta

    from azure.core.exceptions import HttpResponseError
    from azure.mgmt.consumption import ConsumptionManagementClient

    clients = get_clients(ctx)

    end = datetime.now(tz=UTC)
    start = end - timedelta(days=180)

    details: list[Any] = []
    summaries: list[Any] = []

    for sub_id in clients.subscription_ids:
        consumption = ConsumptionManagementClient(clients.credential, sub_id)
        scope = f"/subscriptions/{sub_id}"

        try:
            details.extend(
                consumption.reservations_details.list(
                    resource_scope=scope,
                    start_date=start.isoformat(),
                    end_date=end.isoformat(),
                )
            )
        except HttpResponseError:
            logger.warning("Failed to fetch reservation details for %s", sub_id)

        try:
            summaries.extend(
                consumption.reservations_summaries.list(
                    resource_scope=scope,
                    grain="monthly",
                )
            )
        except HttpResponseError:
            logger.warning("Failed to fetch reservation summaries for %s", sub_id)

    if not summaries and not details:
        return (
            "No reservation data found. "
            "This may indicate no active RIs or Savings Plans."
        )

    lines = ["Reservation Coverage Summary:\n"]

    for summary in summaries[-6:]:
        usage_date = getattr(summary, "usage_date", "unknown")
        avg_util = getattr(summary, "avg_utilization_percentage", 0)
        reserved_hrs = getattr(summary, "reserved_hours", 0)
        used_hrs = getattr(summary, "used_hours", 0)

        ri_pct = config.reservation_util_threshold * 100
        status = "LOW" if avg_util < ri_pct else "OK"
        lines.append(
            f"  {usage_date}: {avg_util:.1f}% utilized "
            f"({used_hrs:.0f}/{reserved_hrs:.0f} hrs) [{status}]"
        )

    low_util = [
        s
        for s in summaries[-6:]
        if getattr(s, "avg_utilization_percentage", 100) < ri_pct
    ]
    if low_util:
        lines.append(
            f"\n{len(low_util)} month(s) with <{ri_pct:.0f}% utilization — "
            "consider resizing or exchanging reservations."
        )

    return "\n".join(lines)


@tool
def compare_sku_pricing(
    current_sku: Annotated[
        str,
        Field(description="Current SKU name (e.g. Standard_D8s_v5)"),
    ],
    target_sku: Annotated[
        str,
        Field(description="Target SKU name to compare (e.g. Standard_D2s_v5)"),
    ],
    region: Annotated[
        str,
        Field(description="Azure region (e.g. westeurope)"),
    ],
    service_name: Annotated[
        str,
        Field(description="Azure service name"),
    ] = "Virtual Machines",
    ctx: FunctionInvocationContext | None = None,
) -> str:
    """Compare monthly cost between two SKUs in the same region."""
    from src.pricing import compare_sku_costs

    result = compare_sku_costs(current_sku, target_sku, region, service_name)
    current = result["current_monthly"]
    target = result["target_monthly"]
    savings = result["monthly_savings"]

    if current is None or target is None:
        return (
            f"Could not find pricing for one or both SKUs "
            f"({current_sku}, {target_sku}) in {region}."
        )

    return (
        f"SKU Comparison ({region}):\n"
        f"  {current_sku}: ${current:.2f}/mo\n"
        f"  {target_sku}: ${target:.2f}/mo\n"
        f"  Savings: ${savings:.2f}/mo"
    )
