# Security

## Reporting vulnerabilities

If you discover a security vulnerability, please report it by opening a private issue or contacting the maintainer directly. Do not open a public issue for security vulnerabilities.

## Credentials

- Never commit `.env` files, `*.auto.tfvars`, or `terraform.tfstate` files
- The agent uses Azure Managed Identity in production (no stored secrets)
- Local development uses `az login` (Azure CLI credential)

## Content safety and prompt injection

Prompt injection protection is handled by Azure OpenAI's built-in content filters, not by application-level code. Every Azure OpenAI deployment automatically includes the [`DefaultV2` safety policy](https://learn.microsoft.com/azure/foundry/openai/concepts/default-safety-policies):

- **Prompt Shields** (enabled by default) — blocks jailbreak and prompt injection attempts
- **Content filters** (medium threshold) — blocks harmful content in prompts and completions
- **Protected material detection** — prevents copyright violations in output

To customize filter thresholds: Azure AI Foundry portal → Guardrails + Controls → Content Filters.

Application-level protections:

- Input length limit (configurable via `COST_AGENT_MAX_INPUT`, default 4000 chars)
- KQL injection prevention on tag key parameters (`src/agents/tag_analyzer.py`)
- OData filter sanitization on pricing API queries (`src/pricing.py`)

## Cloud Adoption Framework alignment

This project follows [Azure CAF AI](https://learn.microsoft.com/azure/cloud-adoption-framework/scenarios/ai/) recommendations for POC deployments:

- Managed identities (no stored credentials)
- RBAC (least-privilege: Cost Management Reader, Reader, OpenAI User)
- Content filtering (Azure OpenAI Prompt Shields, enabled by default)
- Infrastructure as Code (Terraform with Azure Verified Modules)
- Monitoring (Application Insights + Log Analytics)

For production, additionally implement:

- Virtual Network integration (`enable_private_networking = true`)
- Private endpoints for AI Foundry and ACR
- Azure DDoS Protection for internet-facing endpoints
- Microsoft Defender for Cloud AI security posture management
- Multi-region deployment for high availability
- Microsoft Purview for data classification and DLP

## Default deployment

The POC Terraform configuration deploys with **public endpoints**. This is suitable for evaluation only.

For production, enable private networking — see [infra/README.md](infra/README.md).
