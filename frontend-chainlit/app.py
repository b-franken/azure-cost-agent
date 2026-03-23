"""Chainlit chat UI for the Azure Cost Agent."""

from __future__ import annotations

import os
from datetime import UTC, datetime

import chainlit as cl

from src.workflow import create_workflow


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


def _looks_like_csv(text: str) -> bool:
    lines = text.strip().splitlines()
    if len(lines) < 2:
        return False
    first_commas = lines[0].count(",")
    return first_commas >= 2 and all(
        line.count(",") == first_commas for line in lines[:3]
    )


def _csv_filename() -> str:
    ts = datetime.now(tz=UTC).strftime("%Y%m%d-%H%M")
    return f"azure-cost-report-{ts}.csv"


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

    full_text = ""
    msg = cl.Message(content="")

    try:
        async for update in agent.run(message.content, stream=True):
            if update.text:
                full_text += update.text
                await msg.stream_token(update.text)
        await msg.update()

        if _looks_like_csv(full_text):
            file = cl.File(
                name=_csv_filename(),
                content=full_text.encode("utf-8"),
                mime="text/csv",
            )
            await cl.Message(
                content="Download:",
                elements=[file],
            ).send()

    except Exception as exc:
        print(f"AGENT ERROR: {exc}")
        await cl.Message(
            content="Something went wrong. Please try again.",
        ).send()
