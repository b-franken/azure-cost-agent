"""Chainlit chat UI for the Azure Cost Agent."""

from __future__ import annotations

import logging
import os

import chainlit as cl

from src.workflow import create_workflow

logger = logging.getLogger("azure-cost-agent.ui")


def _setup_tracing() -> None:
    conn_str = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if not conn_str:
        return
    try:
        from agent_framework.observability import (
            create_resource,
            enable_instrumentation,
        )
        from azure.monitor.opentelemetry import configure_azure_monitor

        configure_azure_monitor(
            connection_string=conn_str,
            resource=create_resource(),
        )
        enable_instrumentation()
        print("TRACING: Enabled")
    except Exception as exc:
        print(f"TRACING: Failed — {exc}")


_tracing_initialized = False


@cl.on_chat_start
async def start() -> None:
    global _tracing_initialized
    if not _tracing_initialized:
        _setup_tracing()
        _tracing_initialized = True

    await cl.Message(
        content=(
            "Ask me about your Azure costs, waste, budgets, tags, "
            "or generate a full optimization report."
        ),
    ).send()


@cl.on_message
async def on_message(message: cl.Message) -> None:
    builder, _ = create_workflow(inject_clients=True)
    workflow = builder.build()
    agent = workflow.as_agent(name="azure-cost-agent")

    msg = cl.Message(content="")

    try:
        async for update in agent.run(message.content, stream=True):
            if update.text:
                await msg.stream_token(update.text)
        await msg.update()
    except Exception as exc:
        print(f"AGENT ERROR: {exc}")
        await cl.Message(content="Something went wrong. Please try again.").send()
