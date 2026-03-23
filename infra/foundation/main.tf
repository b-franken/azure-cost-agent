# ─── Naming ──────────────────────────────────────────────────

module "naming" {
  source  = "Azure/naming/azurerm"
  version = "0.4.3"

  suffix = [var.project_name]
}

# ─── Resource Group ──────────────────────────────────────────

resource "azurerm_resource_group" "this" {
  name     = module.naming.resource_group.name_unique
  location = var.location
  tags     = var.tags
}

# ─── User-Assigned Managed Identity ──────────────────────────

resource "azurerm_user_assigned_identity" "agent" {
  name                = "id-${var.project_name}-agent"
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
  tags                = var.tags
}

# ─── AI Foundry + Project + Model ────────────────────────────

module "ai_foundry" {
  source  = "Azure/avm-ptn-aiml-ai-foundry/azurerm"
  version = "0.10.1"

  base_name                  = var.project_name
  location                   = azurerm_resource_group.this.location
  resource_group_resource_id = azurerm_resource_group.this.id

  ai_foundry = {
    create_ai_agent_service = var.enable_foundry_agent_service
    name                    = module.naming.cognitive_account.name_unique
  }

  ai_model_deployments = {
    "model" = {
      name = var.model_name
      model = {
        format  = "OpenAI"
        name    = var.model_name
        version = var.model_version
      }
      scale = {
        type     = "GlobalStandard"
        capacity = var.model_capacity
      }
    }
  }

  ai_projects = {
    main = {
      name                       = "${var.project_name}-project"
      description                = "Main AI project"
      display_name               = "${var.project_name} Project"
      create_project_connections = var.enable_foundry_agent_service
      storage_account_connection = var.enable_foundry_agent_service ? {
        new_resource_map_key = "main"
      } : {}
      ai_search_connection = var.enable_foundry_agent_service ? {
        new_resource_map_key = "main"
      } : {}
      cosmos_db_connection = var.enable_foundry_agent_service ? {
        new_resource_map_key = "main"
      } : {}
    }
  }

  storage_account_definition = var.enable_foundry_agent_service ? {
    main = {}
  } : {}

  ai_search_definition = var.enable_foundry_agent_service ? {
    main = {
      sku           = "basic"
      replica_count = 1
    }
  } : {}

  cosmosdb_definition = var.enable_foundry_agent_service ? {
    main = {
      secondary_regions = [
        {
          location          = var.location
          zone_redundant    = false
          failover_priority = 0
        }
      ]
      automatic_failover_enabled        = false
      multiple_write_locations_enabled   = false
      public_network_access_enabled      = true
    }
  } : {}

  create_byor              = var.enable_foundry_agent_service
  create_private_endpoints = false
  tags                     = var.tags
}


# ─── RBAC ────────────────────────────────────────────────────

resource "azurerm_role_assignment" "agent_openai_user" {
  scope                = module.ai_foundry.resource_id
  role_definition_name = "Cognitive Services OpenAI User"
  principal_id         = azurerm_user_assigned_identity.agent.principal_id
  principal_type       = "ServicePrincipal"
}

resource "azurerm_role_assignment" "agent_ai_developer" {
  scope                = module.ai_foundry.resource_id
  role_definition_name = "Azure AI Developer"
  principal_id         = azurerm_user_assigned_identity.agent.principal_id
  principal_type       = "ServicePrincipal"
}

resource "azurerm_role_assignment" "agent_acr_pull" {
  scope                = module.acr.resource_id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.agent.principal_id
  principal_type       = "ServicePrincipal"
}

resource "azurerm_role_assignment" "agent_cost_reader" {
  scope                = "/subscriptions/${var.subscription_id}"
  role_definition_name = "Cost Management Reader"
  principal_id         = azurerm_user_assigned_identity.agent.principal_id
  principal_type       = "ServicePrincipal"
}

resource "azurerm_role_assignment" "agent_reader" {
  scope                = "/subscriptions/${var.subscription_id}"
  role_definition_name = "Reader"
  principal_id         = azurerm_user_assigned_identity.agent.principal_id
  principal_type       = "ServicePrincipal"
}

# ─── Container Registry ─────────────────────────────────────

module "acr" {
  source  = "Azure/avm-res-containerregistry-registry/azurerm"
  version = "0.5.1"

  name                    = module.naming.container_registry.name_unique
  resource_group_name     = azurerm_resource_group.this.name
  location                = azurerm_resource_group.this.location
  sku                     = var.acr_sku
  zone_redundancy_enabled = var.acr_sku == "Premium"
  tags                    = var.tags
}

# ─── Log Analytics ───────────────────────────────────────────

module "log_analytics" {
  source  = "Azure/avm-res-operationalinsights-workspace/azurerm"
  version = "0.5.1"

  name                = module.naming.log_analytics_workspace.name_unique
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location

  log_analytics_workspace_retention_in_days      = 30
  log_analytics_workspace_sku                    = "PerGB2018"
  log_analytics_workspace_internet_ingestion_enabled = var.enable_private_networking ? "false" : "true"
  log_analytics_workspace_internet_query_enabled     = var.enable_private_networking ? "false" : "true"
  tags                                               = var.tags
}

module "app_insights" {
  source  = "Azure/avm-res-insights-component/azurerm"
  version = "0.3.0"

  name                = module.naming.application_insights.name_unique
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
  workspace_id = module.log_analytics.resource_id
  tags                = var.tags
}
