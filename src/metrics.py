"""Azure Monitor metrics — CPU and memory utilization data."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from azure.core.exceptions import HttpResponseError, ResourceNotFoundError

from src.config import config

if TYPE_CHECKING:
    from azure.mgmt.monitor import MonitorManagementClient


def _get_metric_average(
    client: MonitorManagementClient,
    resource_id: str,
    metric_name: str,
    days: int = config.metric_lookback_days,
) -> float | None:
    """Get the average value of a metric over the last N days.

    Returns None if metrics are unavailable.
    """
    end = datetime.now(tz=UTC)
    start = end - timedelta(days=days)
    timespan = f"{start.isoformat()}/{end.isoformat()}"

    try:
        result = client.metrics.list(
            resource_uri=resource_id,
            timespan=timespan,
            metricnames=metric_name,
            aggregation="Average",
            interval="P1D",
        )
    except (HttpResponseError, ResourceNotFoundError):
        return None

    for metric in result.value:
        for ts in metric.timeseries:
            if not ts.data:
                continue
            values = [d.average for d in ts.data if d.average is not None]
            if values:
                return round(sum(values) / len(values), 1)
    return None


def get_avg_cpu(
    client: MonitorManagementClient,
    resource_id: str,
    days: int = config.metric_lookback_days,
) -> float | None:
    """Get average CPU percentage over the last N days."""
    return _get_metric_average(client, resource_id, "Percentage CPU", days)


def get_avg_memory(
    client: MonitorManagementClient,
    resource_id: str,
    days: int = config.metric_lookback_days,
) -> float | None:
    """Get average available memory in GB over the last N days.

    Only available on VMs with the Azure Monitor Agent installed.
    """
    avg_bytes = _get_metric_average(client, resource_id, "Available Memory Bytes", days)
    if avg_bytes is None:
        return None
    return round(avg_bytes / (1024**3), 1)
