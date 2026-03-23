"""AG-UI server — exposes the cost agent as an SSE streaming endpoint."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from ag_ui.core import (
    RunFinishedEvent,
    ToolCallArgsEvent,
    ToolCallEndEvent,
    ToolCallStartEvent,
)
from agent_framework_ag_ui import (
    AgentFrameworkWorkflow,
    add_agent_framework_fastapi_endpoint,
)
from agent_framework_ag_ui._workflow_run import (
    _pending_request_events,
    run_workflow_stream,
)
from fastapi import FastAPI

from src.workflow import create_workflow

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from ag_ui.core import BaseEvent
    from agent_framework import Workflow

_TOOL_CALL_EVENTS = (ToolCallStartEvent, ToolCallArgsEvent, ToolCallEndEvent)


def _build_workflow(_thread_id: str) -> Workflow:
    builder, _ = create_workflow(inject_clients=True)
    return builder.build()


class _CostAgentWorkflow(AgentFrameworkWorkflow):
    """Adapts the HandoffBuilder workflow for CopilotKit compatibility.

    Fixes two issues:
    1. Filters stale tool results from previous turns (multi-turn crash).
    2. Strips internal TOOL_CALL events that lack proper START/END pairs,
       which cause CopilotKit to error with "Cannot send RUN_FINISHED
       while tool calls are still active".
    """

    async def run(
        self, input_data: dict[str, Any]
    ) -> AsyncGenerator[BaseEvent]:
        thread_id = self._thread_id_from_input(input_data)
        workflow = self._resolve_workflow(thread_id)

        pending = await _pending_request_events(workflow)
        if not pending:
            messages = input_data.get("messages") or []
            input_data = {
                **input_data,
                "messages": [
                    m for m in messages if m.get("role") != "tool"
                ],
            }

        async for event in run_workflow_stream(input_data, workflow):
            if isinstance(event, _TOOL_CALL_EVENTS):
                continue
            if isinstance(event, RunFinishedEvent) and getattr(
                event, "interrupt", None
            ):
                yield RunFinishedEvent(
                    run_id=event.run_id,
                    thread_id=event.thread_id,
                )
                continue
            yield event


def _setup_tracing() -> None:
    conn_str = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if not conn_str:
        print("TRACING: No APPLICATIONINSIGHTS_CONNECTION_STRING, skipping")
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
        print("TRACING: Enabled — exporting to Application Insights")
    except Exception as exc:
        print(f"TRACING: Failed — {exc}")


logger = logging.getLogger("azure-cost-agent")


@asynccontextmanager
async def lifespan(_app: FastAPI):  # type: ignore[no-untyped-def]
    _setup_tracing()
    logger.info("Azure Cost Agent started")
    yield
    logger.info("Azure Cost Agent shutting down")


app = FastAPI(title="Azure Cost Agent", lifespan=lifespan)
add_agent_framework_fastapi_endpoint(
    app,
    _CostAgentWorkflow(
        workflow_factory=_build_workflow,
        name="azure-cost-agent",
    ),
    "/",
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
