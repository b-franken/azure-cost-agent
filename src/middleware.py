"""Agent middleware — logging, input validation, and dependency injection."""

from __future__ import annotations

import logging
import os
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


def _sensitive_data_enabled() -> bool:
    return os.getenv("ENABLE_SENSITIVE_DATA", "false").lower() == "true"


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
    """Logs tool calls. Arguments and results only when ENABLE_SENSITIVE_DATA=true."""

    async def process(
        self,
        context: FunctionInvocationContext,
        call_next: Callable[[], Awaitable[None]],
    ) -> None:
        name = context.function.name
        logger.info("Tool call: %s", name)
        start = time.monotonic()
        await call_next()
        duration = time.monotonic() - start
        if _sensitive_data_enabled() and context.result:
            result_preview = str(context.result)[:200]
            logger.info("Tool %s | %.2fs | result: %s", name, duration, result_preview)
        else:
            logger.info("Tool %s | %.2fs", name, duration)


class InputGuardMiddleware(AgentMiddleware):
    """Rejects inputs that are too long or conversations that exceed turn limits."""

    def __init__(self, max_length: int = 4000, max_turns: int = 50) -> None:
        self._max_length = max_length
        self._max_turns = max_turns

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

        user_turns = sum(1 for m in context.messages if m.role == "user")
        if user_turns > self._max_turns:
            context.result = AgentResponse(
                messages=[
                    Message(
                        "assistant",
                        [
                            f"Conversation reached the {self._max_turns}-turn limit. "
                            "Please start a new conversation.",
                        ],
                    ),
                ],
            )
            raise MiddlewareTermination(result=context.result)

        await call_next()


class ClientInjectionMiddleware(AgentMiddleware):
    """Injects Azure SDK clients via function_invocation_kwargs."""

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
