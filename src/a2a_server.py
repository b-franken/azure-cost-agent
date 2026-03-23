"""A2A server — exposes the cost agent via the Agent-to-Agent protocol."""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

import uvicorn
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from a2a.utils.message import new_agent_text_message
from dotenv import load_dotenv

from src.workflow import create_workflow

if TYPE_CHECKING:
    from a2a.server.events import EventQueue

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

PORT = int(os.getenv("A2A_PORT", "9100"))


class CostAgentExecutor(AgentExecutor):
    """Runs the cost agent workflow for incoming A2A requests."""

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        user_input = context.get_user_input()
        logger.info("A2A request: %s", user_input[:100])

        builder, _ = create_workflow(inject_clients=True)
        workflow = builder.build()
        agent = workflow.as_agent(name="azure-cost-agent")
        response = await agent.run(user_input)

        await event_queue.enqueue_event(
            new_agent_text_message(response.text or "(no response)")
        )

    async def cancel(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        raise NotImplementedError


AGENT_CARD = AgentCard(
    name="Azure Cost Agent",
    description=(
        "Multi-agent Azure cost optimizer. Analyzes spend, finds waste "
        "with cost impact, checks tag coverage, detects anomalies, "
        "tracks budgets, and generates optimization reports."
    ),
    url=f"http://localhost:{PORT}/",
    version="0.1.0",
    default_input_modes=["text"],
    default_output_modes=["text"],
    capabilities=AgentCapabilities(streaming=False),
    skills=[
        AgentSkill(
            id="cost-analysis",
            name="Cost Analysis",
            description=(
                "Spend breakdowns, period comparisons, top spenders, CSV export"
            ),
            tags=["cost", "spend", "finops"],
            examples=[
                "What are my top 5 most expensive resources?",
                "Compare costs for the last 30 days",
                "Export cost diff by resource group",
            ],
        ),
        AgentSkill(
            id="waste-detection",
            name="Waste Detection",
            description=(
                "Find idle, orphaned, and oversized resources with monthly cost impact"
            ),
            tags=["waste", "optimization", "idle"],
            examples=[
                "Find orphaned disks",
                "Show me idle resources with cost impact",
            ],
        ),
        AgentSkill(
            id="tag-governance",
            name="Tag Governance",
            description="Tag coverage analysis and untagged resource detection",
            tags=["tags", "governance", "compliance"],
            examples=[
                "Show tag coverage by resource type",
                "Which resources are missing the cost-center tag?",
            ],
        ),
        AgentSkill(
            id="cost-report",
            name="Optimization Report",
            description="Full cost optimization report with prioritized action plan",
            tags=["report", "optimization", "savings"],
            examples=["Generate a full cost report"],
        ),
    ],
)


def main() -> None:
    load_dotenv()

    handler = DefaultRequestHandler(
        agent_executor=CostAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )

    server = A2AStarletteApplication(
        agent_card=AGENT_CARD,
        http_handler=handler,
    )

    logger.info("Azure Cost Agent A2A server on http://localhost:%d", PORT)
    logger.info("Agent Card: http://localhost:%d/.well-known/agent-card.json", PORT)
    uvicorn.run(server.build(), host="0.0.0.0", port=PORT)  # noqa: S104


if __name__ == "__main__":
    main()
