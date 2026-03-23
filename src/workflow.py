"""Agent workflow construction — triage + specialist handoff graph."""

from __future__ import annotations

from typing import Any

from agent_framework.orchestrations import HandoffBuilder
from dotenv import load_dotenv

from src.agents import (
    advisor,
    anomaly_detector,
    budget_tracker,
    cost_analyzer,
    reporter,
    tag_analyzer,
    waste_detector,
)
from src.azure_clients import AzureClients, create_azure_clients
from src.factory import create_client
from src.memory import create_history_provider
from src.middleware import (
    InputGuardMiddleware,
    LoggingAgentMiddleware,
    LoggingFunctionMiddleware,
)

TRIAGE_INSTRUCTIONS = """\
You are a triage agent for Azure cost optimization.
Route questions to the appropriate specialist:

{agents}

Rules:
- Questions about spend, bills, or cost breakdowns → cost-analyzer
- Questions about idle, unused, or orphaned resources → waste-detector
- Questions about Azure Advisor or recommendations → advisor
- Questions about reports or summaries → reporter
- Questions about cost spikes or anomalies → anomaly-detector
- Questions about budgets or forecasts → budget-tracker
- Questions about tags, tagging, or cost allocation → tag-analyzer
- If unclear, ask the user to clarify.
"""

AGENTS_CONFIG = [
    {
        "name": "cost-analyzer",
        "instructions": cost_analyzer.INSTRUCTIONS,
        "description": cost_analyzer.DESCRIPTION,
        "tools": [
            cost_analyzer.query_costs,
            cost_analyzer.compare_periods,
            cost_analyzer.top_spenders,
            cost_analyzer.export_cost_diff,
        ],
    },
    {
        "name": "waste-detector",
        "instructions": waste_detector.INSTRUCTIONS,
        "description": waste_detector.DESCRIPTION,
        "tools": [
            waste_detector.find_idle_resources,
            waste_detector.find_orphaned_resources,
            waste_detector.find_oversized_resources,
            waste_detector.find_stale_resources,
            waste_detector.find_underutilized_vms,
        ],
    },
    {
        "name": "advisor",
        "instructions": advisor.INSTRUCTIONS,
        "description": advisor.DESCRIPTION,
        "tools": [
            advisor.get_prioritized_recommendations,
            advisor.get_reservation_recommendations,
            advisor.get_reservation_coverage,
            advisor.compare_sku_pricing,
        ],
    },
    {
        "name": "anomaly-detector",
        "instructions": anomaly_detector.INSTRUCTIONS,
        "description": anomaly_detector.DESCRIPTION,
        "tools": [
            anomaly_detector.detect_anomalies,
            anomaly_detector.get_daily_trend,
        ],
    },
    {
        "name": "budget-tracker",
        "instructions": budget_tracker.INSTRUCTIONS,
        "description": budget_tracker.DESCRIPTION,
        "tools": [
            budget_tracker.get_budget_status,
            budget_tracker.get_budget_forecast,
        ],
    },
    {
        "name": "tag-analyzer",
        "instructions": tag_analyzer.INSTRUCTIONS,
        "description": tag_analyzer.DESCRIPTION,
        "tools": [
            tag_analyzer.find_untagged_resources,
            tag_analyzer.find_resources_missing_tag,
            tag_analyzer.tag_coverage_report,
        ],
    },
    {
        "name": "reporter",
        "instructions": reporter.INSTRUCTIONS,
        "description": reporter.DESCRIPTION,
        "tools": [reporter.generate_summary],
    },
]


def create_workflow(
    *,
    inject_clients: bool = False,
) -> tuple[HandoffBuilder, AzureClients]:
    load_dotenv()

    azure_clients = create_azure_clients()
    client = create_client()

    function_middleware: list[Any] = [LoggingFunctionMiddleware()]
    if inject_clients:
        from src.middleware import ClientInjectionMiddleware

        function_middleware.insert(0, ClientInjectionMiddleware(azure_clients))

    middleware = [
        InputGuardMiddleware(),
        LoggingAgentMiddleware(),
        *function_middleware,
    ]

    specialists = [
        client.as_agent(
            name=str(cfg["name"]),
            instructions=str(cfg["instructions"]),
            description=str(cfg["description"]),
            tools=cfg["tools"],
            middleware=middleware,
        )
        for cfg in AGENTS_CONFIG
    ]

    agent_descriptions = "\n".join(f"- {a.name}: {a.description}" for a in specialists)

    triage = client.as_agent(
        name="triage",
        instructions=TRIAGE_INSTRUCTIONS.format(agents=agent_descriptions),
        description="Routes questions to the right specialist",
        context_providers=[create_history_provider()],
        middleware=[
            InputGuardMiddleware(),
            LoggingAgentMiddleware(),
        ],
    )

    builder = (
        HandoffBuilder(
            name="cost_optimizer",
            participants=[triage, *specialists],
        )
        .with_start_agent(triage)
        .with_autonomous_mode(
            agents=[triage],
            turn_limits={"triage": 1},
        )
    )

    builder = builder.add_handoff(triage, specialists)

    return builder, azure_clients
