# Azure Cost Agent

Multi-agent Azure cost optimizer built on [Microsoft Agent Framework](https://github.com/microsoft/agent-framework). Ask questions about your Azure spend in natural language — get answers backed by real Azure API data with cost impact analysis.

## Agents

| Agent | Capabilities |
|-------|-------------|
| **Cost Analyzer** | Spend breakdowns by resource group/service/resource, period comparisons, top spenders |
| **Waste Detector** | Idle VMs, orphaned disks/NICs/IPs, oversized resources — with monthly cost per finding |
| **Advisor** | Azure Advisor cost recommendations sorted by impact, RI/SP coverage analysis |
| **Anomaly Detector** | Daily cost spike detection against rolling baseline |
| **Budget Tracker** | Budget utilization, burn rate forecasting |
| **Tag Analyzer** | Untagged resources, tag coverage by type, missing tag key detection |
| **Reporter** | Aggregated optimization report with prioritized action plan and total savings potential |

## Quick start

```bash
git clone <repo-url>
cd azure-cost-agent
pip install uv && uv sync
cp .env.example .env   # fill in your values
az login
make chat              # opens Chainlit UI at http://localhost:8000
```

## Modes

| Mode | Command | Description |
|------|---------|-------------|
| Chat UI | `make chat` | Chainlit chat interface on port 8000 |
| AG-UI API | `make api` | SSE streaming endpoint on port 8000 (for programmatic access) |
| CopilotKit | `make frontend` | Experimental React UI on port 3000 (requires `make api` running) |
| DevUI | `make devui` | Agent Framework development UI on port 8080 |
| CLI | `make run` | Interactive terminal REPL |
| MCP Server | `make mcp` | Expose tools via Model Context Protocol (stdio) |

### CopilotKit (experimental)

CopilotKit has known incompatibilities with the HandoffBuilder workflow pattern — see [frontend/README.md](frontend/README.md) for details.

```bash
make api        # Terminal 1: AG-UI backend on :8000
make frontend   # Terminal 2: CopilotKit UI on :3000
```

### MCP server

Add to your Claude Code or VS Code MCP config:

```json
{
  "mcpServers": {
    "azure-cost-agent": {
      "command": "uv",
      "args": ["run", "python", "-m", "src.mcp"],
      "cwd": "/path/to/azure-cost-agent"
    }
  }
}
```

## RBAC requirements

The identity running the agent needs these roles on the target subscription(s):

| Role | Scope | Why |
|------|-------|-----|
| `Cost Management Reader` | Subscription | Cost queries, budget data |
| `Reader` | Subscription | Resource Graph queries, Advisor recommendations |
| `Cognitive Services OpenAI User` | AI Foundry resource | Model access |
| `Azure AI Developer` | AI Foundry resource | Foundry project access |
| `AcrPull` | Container Registry | Image pull (Container App deployment only) |

## Configuration

All thresholds are configurable via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `COST_AGENT_ANOMALY_THRESHOLD` | 2.0 | Spike detection multiplier |
| `COST_AGENT_BUDGET_RISK_THRESHOLD` | 0.80 | Budget at-risk percentage |
| `COST_AGENT_CPU_THRESHOLD` | 10.0 | VM underutilization CPU % |
| `COST_AGENT_QUERY_LIMIT` | 500 | Max resources per Resource Graph query |

## Deployment

See [infra/README.md](infra/README.md) for Terraform deployment to Azure Container Apps.

## Security

Prompt injection protection is provided by Azure OpenAI's built-in [Prompt Shields](https://learn.microsoft.com/azure/foundry/openai/concepts/content-filter-prompt-shields), enabled by default on all deployments.

The default POC deployment uses **public endpoints** for simplicity. For production:

- Set `enable_private_networking = true` in your tfvars
- Use `acr_sku = "Premium"` (required for private endpoints)

See [SECURITY.md](SECURITY.md) for full details.

## Known limitations

- **Multi-turn conversation**: Each message creates a fresh workflow (no conversation memory). This is a [known HandoffBuilder limitation](https://github.com/microsoft/agent-framework/issues/3097) in agent-framework RC5.
- **GenAI tracing**: `AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING=true` crashes due to a bug in azure-ai-projects 2.0.1. Basic tracing (dependencies, custom metrics) works without it.
- **CopilotKit**: The AG-UI integration has [incompatibilities with HandoffBuilder](frontend/README.md). Use Chainlit (`make chat`) instead.

## Development

```bash
make test       # pytest
make lint       # ruff check
make format     # ruff format
make typecheck  # mypy --strict
make check      # all of the above
```

## License

[MIT](LICENSE)
