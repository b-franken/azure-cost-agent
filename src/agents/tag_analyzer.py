"""Tag Analyzer agent — tag hygiene and cost allocation analysis."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Annotated

from agent_framework import FunctionInvocationContext, tool
from pydantic import Field

from src.agents._context import get_clients
from src.graph import run_resource_graph_query

_VALID_TAG_KEY = re.compile(r"^[a-zA-Z0-9_.\-]+$")

if TYPE_CHECKING:
    from src.azure_clients import AzureClients

INSTRUCTIONS = """\
You are a tag governance specialist for Azure subscriptions.

Rules:
- Use find_untagged_resources to identify resources missing required tags.
- Use tag_coverage_report to show cost allocation completeness.
- Present findings with resource name, type, resource group, and location.
- Flag untagged resources as a governance risk.
"""

DESCRIPTION = (
    "Analyzes tag hygiene: finds untagged resources and measures "
    "cost allocation completeness"
)

_UNTAGGED_RESOURCES = """\
resources
| where tags == '{{}}' or isnull(tags)
| where type !in (
    'microsoft.network/networkwatchers',
    'microsoft.security/assessments',
    'microsoft.advisor/recommendations'
)
| project name, type, resourceGroup, location, subscriptionId, id
"""

_TAG_COVERAGE = """\
resources
| where type !in (
    'microsoft.network/networkwatchers',
    'microsoft.security/assessments',
    'microsoft.advisor/recommendations'
)
| extend hasTag = iff(tags != '{{}}' and isnotnull(tags), true, false)
| summarize
    total = count(),
    tagged = countif(hasTag),
    untagged = countif(not(hasTag))
    by type
| extend coverage = round(100.0 * tagged / total, 1)
| order by untagged desc
"""

_MISSING_TAG_KEY = """\
resources
| where isnotnull(tags) and tags != '{{}}'
| where not(tags has '{tag_key}')
| project name, type, resourceGroup, location, tags, id
"""


def _run_graph_query(
    clients: AzureClients,
    query: str,
) -> list[dict[str, str]]:
    return run_resource_graph_query(clients, query)


@tool
def find_untagged_resources(
    ctx: FunctionInvocationContext | None = None,
) -> str:
    """Find resources with no tags at all."""
    clients = get_clients(ctx)
    rows = _run_graph_query(clients, _UNTAGGED_RESOURCES)

    if not rows:
        return "All resources have at least one tag."

    lines = [f"Untagged Resources ({len(rows)}):\n"]
    for row in rows:
        name = row.get("name", "unknown")
        rtype = row.get("type", "").split("/")[-1]
        rg = row.get("resourceGroup", "")
        loc = row.get("location", "")
        lines.append(f"  - {name} ({rtype}) [{rg}, {loc}]")

    lines.append(f"\n{len(rows)} resources have zero tags.")
    return "\n".join(lines)


@tool
def find_resources_missing_tag(
    tag_key: Annotated[
        str,
        Field(description="Tag key to check for (e.g. 'environment', 'cost-center')"),
    ],
    ctx: FunctionInvocationContext | None = None,
) -> str:
    """Find resources missing a specific tag key."""
    if not _VALID_TAG_KEY.match(tag_key):
        return f"Invalid tag key: '{tag_key}'. Use alphanumeric, _, ., -."

    clients = get_clients(ctx)
    query = _MISSING_TAG_KEY.replace("{tag_key}", tag_key)
    rows = _run_graph_query(clients, query)

    if not rows:
        return f"All tagged resources have the '{tag_key}' tag."

    lines = [f"Resources missing '{tag_key}' tag ({len(rows)}):\n"]
    for row in rows:
        name = row.get("name", "unknown")
        rtype = row.get("type", "").split("/")[-1]
        rg = row.get("resourceGroup", "")
        lines.append(f"  - {name} ({rtype}) [{rg}]")

    return "\n".join(lines)


@tool
def tag_coverage_report(
    ctx: FunctionInvocationContext | None = None,
) -> str:
    """Show tag coverage percentage by resource type."""
    clients = get_clients(ctx)
    rows = _run_graph_query(clients, _TAG_COVERAGE)

    if not rows:
        return "No resources found."

    lines = [
        "Tag Coverage by Resource Type:\n",
        f"{'Type':<45} {'Total':>6} {'Tagged':>7} {'Coverage':>9}",
        "-" * 70,
    ]
    total_all = 0
    tagged_all = 0
    for row in rows:
        rtype = row.get("type", "unknown").split("/")[-1]
        total = int(row.get("total", "0"))
        tagged = int(row.get("tagged", "0"))
        coverage = float(row.get("coverage", "0"))
        total_all += total
        tagged_all += tagged
        lines.append(f"{rtype:<45} {total:>6} {tagged:>7} {coverage:>8.1f}%")

    overall = round(100.0 * tagged_all / total_all, 1) if total_all else 0
    lines.append("-" * 70)
    lines.append(f"{'OVERALL':<45} {total_all:>6} {tagged_all:>7} {overall:>8.1f}%")
    return "\n".join(lines)
