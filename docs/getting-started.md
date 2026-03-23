# Getting Started

## Prerequisites

- **Python 3.13+** — [download](https://www.python.org/downloads/)
- **uv** — `pip install uv`
- **Azure CLI** — [install](https://learn.microsoft.com/cli/azure/install-azure-cli)
- **Azure subscription** with Cost Management enabled
- **Azure OpenAI** deployment (gpt-4.1-mini or similar)

## Setup

```bash
git clone <repo-url>
cd azure-cost-agent
uv sync
```

## Configure Azure

### 1. Log in

```bash
az login
```

### 2. Create `.env`

```bash
cp .env.example .env
```

Edit `.env` with your values:

```
AZURE_AI_PROJECT_ENDPOINT=https://<your-hub>.openai.azure.com/
AZURE_OPENAI_RESPONSES_DEPLOYMENT_NAME=gpt-4.1-mini
AZURE_SUBSCRIPTION_IDS=<your-subscription-id>
```

Find your subscription ID:

```bash
az account show --query id -o tsv
```

For multiple subscriptions, comma-separate:

```
AZURE_SUBSCRIPTION_IDS=sub-id-1,sub-id-2
```

### 3. Assign RBAC roles

```bash
SUB_ID=$(az account show --query id -o tsv)
USER_ID=$(az ad signed-in-user show --query id -o tsv)

az role assignment create --assignee $USER_ID \
  --role "Cost Management Reader" \
  --scope /subscriptions/$SUB_ID

az role assignment create --assignee $USER_ID \
  --role "Reader" \
  --scope /subscriptions/$SUB_ID
```

If using Azure OpenAI, also assign on your AI Foundry resource:

```bash
az role assignment create --assignee $USER_ID \
  --role "Cognitive Services OpenAI User" \
  --scope /subscriptions/$SUB_ID/resourceGroups/<your-rg>/providers/Microsoft.CognitiveServices/accounts/<your-account>
```

### 4. Run

```bash
make chat    # Web UI at http://localhost:8000
make run     # CLI mode
```

## Example questions

```
What did I spend this month?
What are my top 10 most expensive resources?
Compare this month's spend with last month
Are there any idle VMs or orphaned disks?
Show me untagged resources
What does Azure Advisor recommend?
Generate a full cost optimization report
```

## Docker

```bash
make docker-build
make docker-run      # uses .env file, exposes port 8000
```

Open `http://localhost:8000` after the container starts. The health endpoint is at `/health`.

## Troubleshooting

| Error | Fix |
|-------|-----|
| `Set AZURE_SUBSCRIPTION_IDS` | Copy `.env.example` to `.env` and fill in values |
| `DefaultAzureCredential failed` | Run `az login` |
| `HttpResponseError 403` | Check RBAC roles are assigned |
| `HttpResponseError 429` | Rate limited — wait and retry |
| `No cost data returned` | Subscription may not have cost data yet (new subscriptions need 24-48h) |
