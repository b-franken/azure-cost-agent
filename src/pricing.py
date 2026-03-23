"""Azure Retail Prices API — real-time SKU pricing without authentication."""

from __future__ import annotations

import re
from functools import lru_cache

import httpx

_BASE_URL = "https://prices.azure.com/api/retail/prices"
_API_VERSION = "2023-01-01-preview"
_HOURS_PER_MONTH = 730
_SAFE_INPUT = re.compile(r"^[a-zA-Z0-9_ -]+$")
_RETRY_TRANSPORT = httpx.HTTPTransport(retries=3)


def _validate_input(value: str, label: str) -> None:
    if not _SAFE_INPUT.match(value):
        msg = f"Invalid {label}: {value!r}"
        raise ValueError(msg)


@lru_cache(maxsize=256)
def get_sku_price(
    sku_name: str,
    region: str,
    service_name: str = "Virtual Machines",
    currency: str = "USD",
) -> float | None:
    """Get retail price per hour for a SKU in a region.

    Uses the public Azure Retail Prices API — no authentication needed.
    Returns None if the SKU/region combination is not found.
    """
    _validate_input(sku_name, "sku_name")
    _validate_input(region, "region")
    _validate_input(service_name, "service_name")

    odata_filter = (
        f"armSkuName eq '{sku_name}' "
        f"and armRegionName eq '{region}' "
        f"and priceType eq 'Consumption' "
        f"and serviceName eq '{service_name}'"
    )
    with httpx.Client(transport=_RETRY_TRANSPORT) as client:
        response = client.get(
            _BASE_URL,
            params={
                "api-version": _API_VERSION,
                "$filter": odata_filter,
                "currencyCode": currency,
            },
            timeout=15,
        )
    response.raise_for_status()
    items = response.json().get("Items", [])
    if not items:
        return None
    return float(items[0]["retailPrice"])


def get_monthly_cost(
    sku_name: str,
    region: str,
    service_name: str = "Virtual Machines",
    currency: str = "USD",
) -> float | None:
    """Get estimated monthly cost (price_per_hour * 730 hours)."""
    hourly = get_sku_price(sku_name, region, service_name, currency)
    if hourly is None:
        return None
    return round(hourly * _HOURS_PER_MONTH, 2)


def compare_sku_costs(
    current_sku: str,
    target_sku: str,
    region: str,
    service_name: str = "Virtual Machines",
    currency: str = "USD",
) -> dict[str, str | float | None]:
    """Compare monthly costs between two SKUs in the same region."""
    current_cost = get_monthly_cost(current_sku, region, service_name, currency)
    target_cost = get_monthly_cost(target_sku, region, service_name, currency)
    savings = None
    if current_cost is not None and target_cost is not None:
        savings = round(current_cost - target_cost, 2)
    return {
        "current_sku": current_sku,
        "target_sku": target_sku,
        "current_monthly": current_cost,
        "target_monthly": target_cost,
        "monthly_savings": savings,
    }
