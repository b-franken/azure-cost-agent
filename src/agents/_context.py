"""Tool context utilities."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from agent_framework import FunctionInvocationContext

    from src.azure_clients import AzureClients


def get_clients(ctx: FunctionInvocationContext | None) -> AzureClients:
    """Extract AzureClients from the tool invocation context.

    The framework always injects ctx at runtime; the None default
    exists only to satisfy the function signature.
    """
    if ctx is None:
        msg = "FunctionInvocationContext not injected by framework"
        raise RuntimeError(msg)
    return cast("AzureClients", ctx.kwargs["azure_clients"])
