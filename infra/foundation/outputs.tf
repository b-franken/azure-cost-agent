output "resource_group_name" {
  value = azurerm_resource_group.this.name
}

output "resource_group_id" {
  value = azurerm_resource_group.this.id
}

output "location" {
  value = azurerm_resource_group.this.location
}

output "ai_foundry_name" {
  value = module.ai_foundry.ai_foundry_name
}

output "ai_foundry_resource_id" {
  value = module.ai_foundry.resource_id
}

output "project_endpoint" {
  description = "AI Foundry project endpoint — use as AZURE_AI_PROJECT_ENDPOINT"
  value       = "https://${module.ai_foundry.ai_foundry_name}.services.ai.azure.com/api/projects/${var.project_name}-project"
}

output "openai_endpoint" {
  description = "Azure OpenAI endpoint"
  value       = "https://${module.ai_foundry.ai_foundry_name}.openai.azure.com/"
}

output "acr_login_server" {
  value = module.acr.resource.login_server
}

output "acr_resource_id" {
  value = module.acr.resource_id
}

output "agent_identity_id" {
  description = "UAMI resource ID — for Container App or Foundry agent"
  value       = azurerm_user_assigned_identity.agent.id
}

output "agent_identity_client_id" {
  description = "UAMI client ID — use as AZURE_CLIENT_ID"
  value       = azurerm_user_assigned_identity.agent.client_id
}

output "agent_identity_principal_id" {
  value = azurerm_user_assigned_identity.agent.principal_id
}

output "log_analytics_resource_id" {
  value = module.log_analytics.resource_id
}

output "app_insights_connection_string" {
  value     = module.app_insights.connection_string
  sensitive = true
}

output "subscription_id" {
  value = var.subscription_id
}

output "model_name" {
  value = var.model_name
}
