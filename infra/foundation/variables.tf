variable "subscription_id" {
  type        = string
  description = "Azure subscription ID."
}

variable "project_name" {
  type        = string
  description = "Project name (3-7 chars, lowercase). Used as base for all resource naming."

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,5}[a-z0-9]$", var.project_name))
    error_message = "Must be 3-7 lowercase alphanumeric characters."
  }
}

variable "location" {
  type        = string
  default     = "swedencentral"
  description = "Azure region. Must support the Responses API."
}

variable "model_name" {
  type    = string
  default = "gpt-4.1-mini"
}

variable "model_version" {
  type    = string
  default = "2025-04-14"
}

variable "model_capacity" {
  type        = number
  default     = 100
  description = "Token-per-minute capacity (in thousands) for model deployments."
}

variable "enable_foundry_agent_service" {
  type        = bool
  default     = false
  description = "Enable Foundry Agent Service with BYO resources (Cosmos DB, AI Search, Storage)."
}

variable "enable_private_networking" {
  type        = bool
  default     = false
  description = "Enable private endpoints and VNet integration. Requires acr_sku = Premium."
}

variable "acr_sku" {
  type    = string
  default = "Basic"

  validation {
    condition     = contains(["Basic", "Standard", "Premium"], var.acr_sku)
    error_message = "ACR SKU must be Basic, Standard, or Premium."
  }
}

variable "tags" {
  type    = map(string)
  default = {}
}
