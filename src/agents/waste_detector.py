"""Waste Detector agent — finds idle, orphaned, and oversized resources."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

import httpx
from agent_framework import FunctionInvocationContext, tool
from pydantic import Field

from src.agents._context import get_clients
from src.graph import run_resource_graph_query
from src.pricing import get_monthly_cost

if TYPE_CHECKING:
    from collections.abc import Callable

    from src.azure_clients import AzureClients

INSTRUCTIONS = """\
You are a waste detection specialist for Azure subscriptions.

Rules:
- Always use tools to find real resource data before answering.
- Present findings with resource name, resource group, SKU, and cost impact.
- Show the total monthly savings potential at the end.
- Classify each finding as "safe to delete" or "needs investigation."
- For underutilized VMs, show the average CPU percentage and monthly cost.
"""

DESCRIPTION = (
    "Finds idle, orphaned, oversized, and stale Azure resources with cost impact"
)

_STOPPED_VMS = """\
resources
| where type == 'microsoft.compute/virtualmachines'
| extend powerState = tostring(
    properties.extended.instanceView.powerState.displayStatus)
| where powerState == 'VM deallocated'
    or powerState == 'VM stopped'
| project name, resourceGroup, location,
    vmSize = tostring(properties.hardwareProfile.vmSize),
    powerState, id
"""

_ORPHANED_DISKS = """\
resources
| where type == 'microsoft.compute/disks'
| where properties.diskState == 'Unattached'
| project name, resourceGroup, location,
    sku = tostring(sku.name),
    sizeGb = tostring(properties.diskSizeGB), id
"""

_ORPHANED_NICS = """\
resources
| where type == 'microsoft.network/networkinterfaces'
| where isnull(properties.virtualMachine.id)
    and isnull(properties.privateEndpoint.id)
| project name, resourceGroup, location, id
"""

_ORPHANED_PUBLIC_IPS = """\
resources
| where type == 'microsoft.network/publicipaddresses'
| where isnull(properties.ipConfiguration.id)
| project name, resourceGroup, location,
    sku = tostring(sku.name), id
"""

_EMPTY_APP_SERVICE_PLANS = """\
resources
| where type == 'microsoft.web/serverfarms'
| where properties.numberOfSites == 0
| project name, resourceGroup, location,
    sku = tostring(sku.name),
    tier = tostring(sku.tier), id
"""

_IDLE_LOAD_BALANCERS = """\
resources
| where type == 'microsoft.network/loadbalancers'
| where array_length(properties.backendAddressPools) == 0
| project name, resourceGroup, location,
    sku = tostring(sku.name), id
"""

_OVERSIZED_SQL_DATABASES = """\
resources
| where type == 'microsoft.sql/servers/databases'
| where name != 'master'
| where sku.tier in ('Premium', 'BusinessCritical')
| project name, resourceGroup, location,
    tier = tostring(sku.tier),
    capacity = tostring(sku.capacity), id
"""

_OVERSIZED_APP_PLANS = """\
resources
| where type == 'microsoft.web/serverfarms'
| where sku.tier in ('PremiumV2', 'PremiumV3', 'Premium')
| project name, resourceGroup, location,
    tier = tostring(sku.tier),
    sku = tostring(sku.name),
    sites = toint(properties.numberOfSites), id
"""

_OLD_SNAPSHOTS = """\
resources
| where type == 'microsoft.compute/snapshots'
| where properties.timeCreated < ago(30d)
| project name, resourceGroup, location,
    sku = tostring(sku.name),
    sizeGb = tostring(properties.diskSizeGB),
    created = tostring(properties.timeCreated), id
"""

_ORPHANED_NAT_GATEWAYS = """\
resources
| where type == 'microsoft.network/natgateways'
| where isnull(properties.subnets) or array_length(properties.subnets) == 0
| project name, resourceGroup, location, id
"""

_IDLE_APP_GATEWAYS = """\
resources
| where type == 'microsoft.network/applicationgateways'
| where array_length(properties.backendAddressPools) == 0
    or array_length(properties.backendAddressPools[0].properties.backendAddresses) == 0
| project name, resourceGroup, location,
    sku = tostring(properties.sku.name), id
"""

_EMPTY_STORAGE_ACCOUNTS = """\
resources
| where type == 'microsoft.storage/storageaccounts'
| project name, resourceGroup, location,
    sku = tostring(sku.name),
    kind = tostring(kind),
    created = tostring(properties.creationTime), id
"""

_UNPROTECTED_KEY_VAULTS = """\
resources
| where type == 'microsoft.keyvault/vaults'
| where properties.enableSoftDelete == true
    and properties.enablePurgeProtection != true
| project name, resourceGroup, location, id
"""

_RUNNING_VMS = """\
resources
| where type == 'microsoft.compute/virtualmachines'
| extend powerState = tostring(
    properties.extended.instanceView.powerState.displayStatus)
| where powerState == 'VM running'
| project name, resourceGroup, location,
    vmSize = tostring(properties.hardwareProfile.vmSize), id
"""


def _run_query(
    clients: AzureClients,
    query: str,
) -> list[dict[str, str]]:
    return run_resource_graph_query(clients, query)


def _estimate_cost(
    sku_name: str,
    region: str,
    service_name: str = "Virtual Machines",
) -> float | None:
    try:
        return get_monthly_cost(sku_name, region, service_name)
    except (httpx.HTTPError, ValueError, KeyError):
        return None


def _format_with_cost(
    label: str,
    rows: list[dict[str, str]],
    cost_fn: Callable[..., float | None] | None = None,
) -> tuple[str, float]:
    if not rows:
        return f"{label}: none found.", 0.0

    total_cost = 0.0
    lines = [f"{label} ({len(rows)}):\n"]

    for row in rows:
        name = row.get("name", "unknown")
        rg = row.get("resourceGroup", "")
        loc = row.get("location", "")

        extras = [
            f"{k}={v}"
            for k, v in row.items()
            if k not in {"name", "resourceGroup", "location", "subscriptionId", "id"}
            and v
        ]

        cost = cost_fn(row) if cost_fn else None
        if cost:
            total_cost += cost
            extras.append(f"~${cost:.2f}/mo")

        extra = f" ({', '.join(extras)})" if extras else ""
        lines.append(f"  - {name} [{rg}, {loc}]{extra}")

    if total_cost > 0:
        lines.append(f"\n  Subtotal: ~${total_cost:.2f}/mo")

    return "\n".join(lines), total_cost


def _vm_cost(row: dict[str, str]) -> float | None:
    return _estimate_cost(
        row.get("vmSize", ""),
        row.get("location", ""),
    )


def _disk_cost(row: dict[str, str]) -> float | None:
    return _estimate_cost(
        row.get("sku", ""),
        row.get("location", ""),
        "Storage",
    )


def _public_ip_cost(row: dict[str, str]) -> float | None:
    return _estimate_cost(
        row.get("sku", "Standard"),
        row.get("location", ""),
        "Virtual Network",
    )


@tool
def find_idle_resources(
    ctx: FunctionInvocationContext | None = None,
) -> str:
    """Find stopped VMs, empty plans, idle LBs, and idle app gateways."""
    clients = get_clients(ctx)

    vms_text, vms_cost = _format_with_cost(
        "Stopped/deallocated VMs",
        _run_query(clients, _STOPPED_VMS),
        _vm_cost,
    )
    plans_text, plans_cost = _format_with_cost(
        "Empty App Service plans",
        _run_query(clients, _EMPTY_APP_SERVICE_PLANS),
    )
    lbs_text, lbs_cost = _format_with_cost(
        "Idle load balancers",
        _run_query(clients, _IDLE_LOAD_BALANCERS),
    )
    appgw_text, _ = _format_with_cost(
        "Idle Application Gateways",
        _run_query(clients, _IDLE_APP_GATEWAYS),
    )

    total = vms_cost + plans_cost + lbs_cost
    parts = [vms_text, plans_text, lbs_text, appgw_text]
    if total > 0:
        parts.append(f"Total idle resource cost: ~${total:.2f}/mo")

    return "\n\n".join(parts)


@tool
def find_orphaned_resources(
    ctx: FunctionInvocationContext | None = None,
) -> str:
    """Find orphaned disks, NICs, public IPs, NAT gateways, and old snapshots."""
    clients = get_clients(ctx)

    disks_text, disks_cost = _format_with_cost(
        "Orphaned disks",
        _run_query(clients, _ORPHANED_DISKS),
        _disk_cost,
    )
    nics_text, _ = _format_with_cost(
        "Orphaned NICs",
        _run_query(clients, _ORPHANED_NICS),
    )
    ips_text, ips_cost = _format_with_cost(
        "Orphaned public IPs",
        _run_query(clients, _ORPHANED_PUBLIC_IPS),
        _public_ip_cost,
    )
    nat_text, _ = _format_with_cost(
        "Orphaned NAT Gateways",
        _run_query(clients, _ORPHANED_NAT_GATEWAYS),
    )
    snap_text, snap_cost = _format_with_cost(
        "Old snapshots (>30 days)",
        _run_query(clients, _OLD_SNAPSHOTS),
        _disk_cost,
    )

    total = disks_cost + ips_cost + snap_cost
    parts = [disks_text, nics_text, ips_text, nat_text, snap_text]
    if total > 0:
        parts.append(f"Total orphaned resource cost: ~${total:.2f}/mo")

    return "\n\n".join(parts)


@tool
def find_oversized_resources(
    ctx: FunctionInvocationContext | None = None,
) -> str:
    """Find Premium/BusinessCritical databases and Premium App Service plans."""
    clients = get_clients(ctx)

    dbs_text, _ = _format_with_cost(
        "Premium/BusinessCritical SQL databases",
        _run_query(clients, _OVERSIZED_SQL_DATABASES),
    )
    plans_text, _ = _format_with_cost(
        "Premium App Service plans",
        _run_query(clients, _OVERSIZED_APP_PLANS),
    )

    return "\n\n".join([dbs_text, plans_text])


@tool
def find_stale_resources(
    ctx: FunctionInvocationContext | None = None,
) -> str:
    """Find potentially unused storage accounts and soft-deleted Key Vaults."""
    clients = get_clients(ctx)

    storage_text, _ = _format_with_cost(
        "Storage accounts (review for usage)",
        _run_query(clients, _EMPTY_STORAGE_ACCOUNTS),
    )
    kv_text, _ = _format_with_cost(
        "Key Vaults with soft-delete but no purge protection",
        _run_query(clients, _UNPROTECTED_KEY_VAULTS),
    )

    return "\n\n".join([storage_text, kv_text])


@tool
def find_underutilized_vms(
    cpu_threshold: Annotated[
        float,
        Field(description="CPU % threshold — VMs below this are underutilized"),
    ] = 10.0,
    ctx: FunctionInvocationContext | None = None,
) -> str:
    """Find running VMs with average CPU below the threshold and show monthly cost."""
    clients = get_clients(ctx)
    monitor = ctx.kwargs.get("monitor_client") if ctx else None
    if monitor is None:
        return "Monitor client not configured — cannot check CPU metrics."

    from src.metrics import get_avg_cpu

    vms = _run_query(clients, _RUNNING_VMS)
    if not vms:
        return "No running VMs found."

    underutilized: list[str] = []
    total_cost = 0.0

    for vm in vms:
        resource_id = vm.get("id", "")
        if not resource_id:
            continue
        avg_cpu = get_avg_cpu(monitor, resource_id)
        if avg_cpu is not None and avg_cpu < cpu_threshold:
            name = vm.get("name", "unknown")
            size = vm.get("vmSize", "unknown")
            rg = vm.get("resourceGroup", "")
            cost = _vm_cost(vm)
            cost_str = f", ~${cost:.2f}/mo" if cost else ""
            if cost:
                total_cost += cost
            underutilized.append(
                f"  - {name} [{rg}] — {size}, avg CPU: {avg_cpu}%{cost_str}",
            )

    if not underutilized:
        return f"No VMs with avg CPU below {cpu_threshold}% found."

    header = f"Underutilized VMs (avg CPU < {cpu_threshold}%, last 30 days):\n"
    result = header + "\n".join(underutilized)
    if total_cost > 0:
        result += f"\n\nTotal underutilized VM cost: ~${total_cost:.2f}/mo"
    return result
