locals {
  placeholder_image = "mcr.microsoft.com/k8se/quickstart:latest"
}

# ─── Container App Environment ───────────────────────────────

module "container_env" {
  source  = "Azure/avm-res-app-managedenvironment/azurerm"
  version = "0.3.0"

  name                = "cae-cost-agent"
  resource_group_name = var.resource_group_name
  location            = var.location

  log_analytics_workspace = {
    resource_id = var.log_analytics_resource_id
  }

  zone_redundancy_enabled = var.enable_private_networking
}

# ─── Container App ───────────────────────────────────────────

module "container_app" {
  source  = "Azure/avm-res-app-containerapp/azurerm"
  version = "0.7.4"

  name                                  = "azure-cost-agent"
  resource_group_name                   = var.resource_group_name
  resource_group_id                     = "/subscriptions/${var.subscription_id}/resourceGroups/${var.resource_group_name}"
  location                              = var.location
  container_app_environment_resource_id = module.container_env.resource_id
  revision_mode                         = "Single"

  managed_identities = {
    user_assigned_resource_ids = [var.agent_identity_id]
  }

  template = {
    containers = [
      {
        name   = "azure-cost-agent"
        image  = var.container_image
        cpu    = 0.5
        memory = "1Gi"
        env = [
          {
            name  = "AZURE_AI_PROJECT_ENDPOINT"
            value = var.project_endpoint
          },
          {
            name  = "AZURE_OPENAI_RESPONSES_DEPLOYMENT_NAME"
            value = var.model_name
          },
          {
            name  = "AZURE_SUBSCRIPTION_IDS"
            value = var.subscription_id
          },
          {
            name  = "AZURE_CLIENT_ID"
            value = var.agent_identity_client_id
          },
          {
            name  = "APPLICATIONINSIGHTS_CONNECTION_STRING"
            value = var.app_insights_connection_string
          },
          {
            name  = "ENABLE_INSTRUMENTATION"
            value = "true"
          },
          {
            name  = "AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING"
            value = "true"
          },
        ]
      }
    ]
  }

  ingress = {
    allow_insecure_connections = false
    external_enabled           = true
    target_port                = 8000
    traffic_weight = [{
      latest_revision = true
      percentage      = 100
    }]
  }

  registries = var.container_image != local.placeholder_image ? [{
    server   = var.acr_login_server
    identity = var.agent_identity_id
  }] : []

  tags = var.tags
}

module "frontend" {
  source  = "Azure/avm-res-app-containerapp/azurerm"
  version = "0.7.4"

  name                                  = "cost-agent-frontend"
  resource_group_name                   = var.resource_group_name
  resource_group_id                     = "/subscriptions/${var.subscription_id}/resourceGroups/${var.resource_group_name}"
  location                              = var.location
  container_app_environment_resource_id = module.container_env.resource_id
  revision_mode                         = "Single"

  template = {
    min_replicas = 1
    containers = [
      {
        name   = "frontend"
        image  = var.frontend_image
        cpu    = 0.5
        memory = "1Gi"
        env = [
          {
            name  = "AZURE_AI_PROJECT_ENDPOINT"
            value = var.project_endpoint
          },
          {
            name  = "AZURE_OPENAI_RESPONSES_DEPLOYMENT_NAME"
            value = var.model_name
          },
          {
            name  = "AZURE_SUBSCRIPTION_IDS"
            value = var.subscription_id
          },
          {
            name  = "AZURE_CLIENT_ID"
            value = var.agent_identity_client_id
          },
          {
            name  = "APPLICATIONINSIGHTS_CONNECTION_STRING"
            value = var.app_insights_connection_string
          },
          {
            name  = "ENABLE_INSTRUMENTATION"
            value = "true"
          },
          {
            name  = "AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING"
            value = "true"
          },
        ]
      }
    ]
  }

  ingress = {
    allow_insecure_connections = false
    external_enabled           = true
    target_port                = 8000
    traffic_weight = [{
      latest_revision = true
      percentage      = 100
    }]
  }

  registries = var.frontend_image != local.placeholder_image ? [{
    server   = var.acr_login_server
    identity = var.agent_identity_id
  }] : []

  managed_identities = {
    user_assigned_resource_ids = [var.agent_identity_id]
  }

  tags = var.tags
}

output "container_app_url" {
  value = module.container_app.fqdn_url
}

output "frontend_url" {
  value = module.frontend.fqdn_url
}
