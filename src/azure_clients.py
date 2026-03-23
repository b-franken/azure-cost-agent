"""Azure management SDK clients for cost optimization."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from azure.identity import AzureCliCredential, ManagedIdentityCredential
from azure.mgmt.advisor import AdvisorManagementClient
from azure.mgmt.costmanagement import CostManagementClient
from azure.mgmt.monitor import MonitorManagementClient
from azure.mgmt.resourcegraph import ResourceGraphClient


def get_credential() -> ManagedIdentityCredential | AzureCliCredential:
    """Select credential based on environment: Managed Identity or CLI."""
    client_id = os.getenv("AZURE_CLIENT_ID")
    if client_id:
        return ManagedIdentityCredential(client_id=client_id)
    return AzureCliCredential()


@dataclass(frozen=True)
class AzureClients:
    """Holds all Azure management clients."""

    cost: CostManagementClient
    graph: ResourceGraphClient
    monitor: MonitorManagementClient
    subscription_ids: list[str]
    _credential: ManagedIdentityCredential | AzureCliCredential = field(
        repr=False,
    )
    management_group_id: str | None = None

    @property
    def cost_scope(self) -> str:
        if self.management_group_id:
            mg = self.management_group_id
            return f"/providers/Microsoft.Management/managementGroups/{mg}"
        return f"/subscriptions/{self.subscription_ids[0]}"

    @property
    def cost_scopes(self) -> list[str]:
        if self.management_group_id:
            return [self.cost_scope]
        return [f"/subscriptions/{sid}" for sid in self.subscription_ids]

    @property
    def credential(self) -> ManagedIdentityCredential | AzureCliCredential:
        return self._credential

    def advisor_for(self, subscription_id: str) -> AdvisorManagementClient:
        """Create an Advisor client for a specific subscription."""
        return AdvisorManagementClient(self._credential, subscription_id)


def create_azure_clients() -> AzureClients:
    """Create Azure management clients from environment variables.

    Reads AZURE_SUBSCRIPTION_IDS (comma-separated) and optionally
    AZURE_MANAGEMENT_GROUP_ID for cross-subscription queries.
    """
    raw = os.getenv("AZURE_SUBSCRIPTION_IDS", "")
    subscription_ids = [s.strip() for s in raw.split(",") if s.strip()]
    if not subscription_ids:
        single = os.getenv("AZURE_SUBSCRIPTION_ID", "")
        if single:
            subscription_ids = [single]

    if not subscription_ids:
        msg = "Set AZURE_SUBSCRIPTION_IDS or AZURE_SUBSCRIPTION_ID in .env"
        raise ValueError(msg)

    management_group_id = os.getenv("AZURE_MANAGEMENT_GROUP_ID")
    credential = get_credential()

    return AzureClients(
        cost=CostManagementClient(credential),
        graph=ResourceGraphClient(credential=credential),
        monitor=MonitorManagementClient(credential, subscription_ids[0]),
        subscription_ids=subscription_ids,
        management_group_id=management_group_id,
        _credential=credential,
    )
