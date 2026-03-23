# Infrastructure

Terraform configuration using [Azure Verified Modules](https://azure.github.io/Azure-Verified-Modules/) (AVM).

## Security

The default POC configuration uses **public endpoints**. This is intentional for quick evaluation but not suitable for production.

For production, set in your tfvars:

```hcl
enable_private_networking = true
acr_sku                   = "Premium"   # required for private endpoints
```

This enables:
- VNet integration for the Container App Environment
- Private endpoints for AI Foundry and ACR
- Zone redundancy for the Container App Environment

See `foundation/environments/production.tfvars.example` for a complete example.

## Structure

```
infra/
├── foundation/         # Deploy first — shared resources
├── container-app/      # Container Apps deployment
└── foundry-agent/      # Foundry Hosted Agent (via azd or SDK)
```

## Foundation resources

| Resource | Module |
|----------|--------|
| AI Foundry + Project + Model deployment | `Azure/avm-ptn-aiml-ai-foundry/azurerm` |
| Container Registry | `Azure/avm-res-containerregistry-registry/azurerm` |
| Log Analytics Workspace | `Azure/avm-res-operationalinsights-workspace/azurerm` |
| Application Insights | `Azure/avm-res-insights-component/azurerm` |
| User-Assigned Managed Identity | `azurerm_user_assigned_identity` |
| RBAC assignments (5x) | `azurerm_role_assignment` |

With `enable_foundry_agent_service = true`, also creates Cosmos DB, AI Search, and Storage Account for the Foundry Agent Service.

## Deploy: Container App

### 1. Foundation

```bash
cd infra/foundation
terraform init
terraform apply -var-file=poc.tfvars
```

Create `poc.tfvars`:

```hcl
subscription_id = "your-subscription-id"
project_name    = "costag"
location        = "swedencentral"
```

### 2. Build and push image

```bash
cd ../..
ACR_NAME=$(cd infra/foundation && terraform output -raw acr_login_server | cut -d. -f1)
az acr login --name $ACR_NAME
docker build --platform linux/amd64 -t $ACR_NAME.azurecr.io/azure-cost-agent:v1 .
docker push $ACR_NAME.azurecr.io/azure-cost-agent:v1
```

### 3. Container App

```bash
cd infra/container-app
terraform init
```

Create your tfvars from the example:

```bash
cp poc.tfvars.example poc.auto.tfvars
```

Fill in values from foundation outputs (`terraform output` in the foundation directory), then:

```bash
terraform apply
```

### 4. Verify

```bash
curl $(terraform output -raw container_app_url)/health
```

## Deploy: Foundry Hosted Agent

```bash
cd infra/foundation
terraform apply -var-file=poc-foundry.tfvars
```

Then build, push, and deploy via `azd up` or the Python SDK. See [foundry-agent/README.md](foundry-agent/README.md).
