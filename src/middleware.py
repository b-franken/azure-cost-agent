"""Agent middleware — logging, input validation, and dependency injection."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from agent_framework import (
    AgentContext,
    AgentMiddleware,
    AgentResponse,
    FunctionInvocationContext,
    FunctionMiddleware,
    Message,
    MiddlewareTermination,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from src.azure_clients import AzureClients

logger = logging.getLogger(__name__)


class LoggingAgentMiddleware(AgentMiddleware):
    """Logs agent run duration."""

    async def process(
        self,
        context: AgentContext,
        call_next: Callable[[], Awaitable[None]],
    ) -> None:
        last = context.messages[-1] if context.messages else None
        preview = (last.text or "")[:120] if last else "(no input)"
        logger.info("Agent run | input: %s", preview)
        start = time.monotonic()
        await call_next()
        logger.info("Agent run | %.2fs", time.monotonic() - start)


class LoggingFunctionMiddleware(FunctionMiddleware):
    """Logs tool call name and duration."""

    async def process(
        self,
        context: FunctionInvocationContext,
        call_next: Callable[[], Awaitable[None]],
    ) -> None:
        logger.info("Tool call: %s", context.function.name)
        start = time.monotonic()
        await call_next()
        duration = time.monotonic() - start
        logger.info("Tool %s | %.2fs", context.function.name, duration)


class InputGuardMiddleware(AgentMiddleware):
    """Rejects inputs that are too long."""

    def __init__(self, max_length: int = 4000) -> None:
        self._max_length = max_length

    async def process(
        self,
        context: AgentContext,
        call_next: Callable[[], Awaitable[None]],
    ) -> None:
        last = context.messages[-1] if context.messages else None
        if last and last.text and len(last.text) > self._max_length:
            context.result = AgentResponse(
                messages=[
                    Message(
                        "assistant",
                        [
                            f"Message too long ({len(last.text)} chars, "
                            f"max {self._max_length}).",
                        ],
                    ),
                ],
            )
            raise MiddlewareTermination(result=context.result)
        await call_next()


class ClientInjectionMiddleware(AgentMiddleware):
    """Injects Azure SDK clients via function_invocation_kwargs.

    Uses AgentContext.function_invocation_kwargs so that all tools
    receive azure_clients and monitor_client in ctx.kwargs — regardless
    of whether the workflow is invoked via CLI, hosting adapter, or tests.

    See: https://learn.microsoft.com/agent-framework/agents/middleware/runtime-context
    """

    def __init__(self, azure_clients: AzureClients) -> None:
        self._azure_clients = azure_clients

    async def process(
        self,
        context: AgentContext,
        call_next: Callable[[], Awaitable[None]],
    ) -> None:
        context.function_invocation_kwargs.setdefault(
            "azure_clients", self._azure_clients
        )
        context.function_invocation_kwargs.setdefault(
            "monitor_client", self._azure_clients.monitor
        )
        await call_next()
