"""Expose the cost agent as an MCP server.

Other agents and tools (VS Code Copilot, Foundry agents) can call our
cost analysis tools via the Model Context Protocol.

Uses a single ChatAgent with all tools — WorkflowAgent does not
support as_mcp_server().

Usage:
    python -m src.mcp

See: https://learn.microsoft.com/agent-framework/agents/tools/local-mcp-tools
"""

from __future__ import annotations

import anyio
from dotenv import load_dotenv
from mcp.server.stdio import stdio_server

from src.factory import create_client
from src.middleware import ClientInjectionMiddleware, InputGuardMiddleware
from src.workflow import AGENTS_CONFIG


async def run() -> None:
    load_dotenv()

    from src.azure_clients import create_azure_clients

    azure_clients = create_azure_clients()
    client = create_client()

    all_tools = [tool for cfg in AGENTS_CONFIG for tool in cfg["tools"]]

    agent = client.as_agent(
        name="azure-cost-agent",
        instructions="You are an Azure cost optimization assistant.",
        tools=all_tools,
        middleware=[
            InputGuardMiddleware(),
            ClientInjectionMiddleware(azure_clients),
        ],
    )

    server = agent.as_mcp_server(
        server_name="azure-cost-agent",
        version="1.0",
    )

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    anyio.run(run)
