# Foundry Hosted Agent Deployment

The Foundry Agent Service resources (Cosmos DB, AI Search, Storage, Capability Host) are deployed by the **foundation** layer when `enable_foundry_agent_service = true`.

## Deploy

```bash
# 1. Deploy foundation with Foundry Agent Service enabled
cd ../foundation
terraform apply -var-file=poc-foundry.tfvars

# 2. Build and push the container image
cd ../..
docker build --platform linux/amd64 -t azure-cost-agent .
az acr login --name <acr-from-output>
docker tag azure-cost-agent <acr>.azurecr.io/azure-cost-agent:v1
docker push <acr>.azurecr.io/azure-cost-agent:v1

# 3. Deploy the hosted agent via azd
azd ai agent init --project-id /subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<account>/projects/<project>
azd up
```

## Alternative: Python SDK

```python
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import HostedAgentDefinition, ProtocolVersionRecord, AgentProtocol
from azure.identity import DefaultAzureCredential

project = AIProjectClient(
    endpoint="<project-endpoint>",
    credential=DefaultAzureCredential(),
    allow_preview=True,
)

agent = project.agents.create_version(
    agent_name="azure-cost-agent",
    definition=HostedAgentDefinition(
        container_protocol_versions=[
            ProtocolVersionRecord(protocol=AgentProtocol.RESPONSES, version="v1")
        ],
        cpu="1",
        memory="2Gi",
        image="<acr>.azurecr.io/azure-cost-agent:v1",
        environment_variables={
            "AZURE_AI_PROJECT_ENDPOINT": "<project-endpoint>",
            "AZURE_OPENAI_RESPONSES_DEPLOYMENT_NAME": "gpt-4.1-mini",
            "AZURE_SUBSCRIPTION_IDS": "<subscription-id>",
        },
    ),
)
```
