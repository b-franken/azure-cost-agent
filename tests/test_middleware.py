"""Tests for agent middleware."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.middleware import (
    ClientInjectionMiddleware,
    InputGuardMiddleware,
    LoggingAgentMiddleware,
)


def _make_context(text: str = "hello") -> MagicMock:
    ctx = MagicMock()
    msg = MagicMock()
    msg.text = text
    ctx.messages = [msg]
    ctx.function_invocation_kwargs = {}
    return ctx


class TestInputGuardMiddleware:
    @pytest.mark.asyncio
    async def test_allows_short_input(self) -> None:
        mw = InputGuardMiddleware(max_length=100)
        ctx = _make_context("short message")
        call_next = AsyncMock()
        await mw.process(ctx, call_next)
        call_next.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_rejects_long_input(self) -> None:
        from agent_framework import MiddlewareTermination

        mw = InputGuardMiddleware(max_length=10)
        ctx = _make_context("a" * 50)
        call_next = AsyncMock()
        with pytest.raises(MiddlewareTermination):
            await mw.process(ctx, call_next)
        call_next.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_allows_empty_messages(self) -> None:
        mw = InputGuardMiddleware(max_length=100)
        ctx = MagicMock()
        ctx.messages = []
        call_next = AsyncMock()
        await mw.process(ctx, call_next)
        call_next.assert_awaited_once()


class TestLoggingAgentMiddleware:
    @pytest.mark.asyncio
    async def test_calls_next(self) -> None:
        mw = LoggingAgentMiddleware()
        ctx = _make_context("test input")
        call_next = AsyncMock()
        await mw.process(ctx, call_next)
        call_next.assert_awaited_once()


class TestClientInjectionMiddleware:
    @pytest.mark.asyncio
    async def test_injects_clients(self) -> None:
        clients = MagicMock()
        clients.monitor = MagicMock()
        mw = ClientInjectionMiddleware(clients)
        ctx = _make_context()
        call_next = AsyncMock()
        await mw.process(ctx, call_next)
        assert ctx.function_invocation_kwargs["azure_clients"] is clients
        assert ctx.function_invocation_kwargs["monitor_client"] is clients.monitor
        call_next.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_does_not_overwrite_existing(self) -> None:
        clients = MagicMock()
        existing = MagicMock()
        mw = ClientInjectionMiddleware(clients)
        ctx = _make_context()
        ctx.function_invocation_kwargs["azure_clients"] = existing
        call_next = AsyncMock()
        await mw.process(ctx, call_next)
        assert ctx.function_invocation_kwargs["azure_clients"] is existing
