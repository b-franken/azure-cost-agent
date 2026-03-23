variable "subscription_id" {
  type = string
}

variable "resource_group_name" {
  type        = string
  description = "Resource group from foundation deployment."
}

variable "location" {
  type    = string
  default = "swedencentral"
}

variable "log_analytics_resource_id" {
  type        = string
  description = "Log Analytics workspace resource ID from foundation."
}

variable "acr_login_server" {
  type        = string
  description = "ACR login server from foundation."
}

variable "agent_identity_id" {
  type        = string
  description = "UAMI resource ID from foundation."
}

variable "agent_identity_client_id" {
  type        = string
  description = "UAMI client ID from foundation."
}

variable "project_endpoint" {
  type        = string
  description = "Azure OpenAI project endpoint from foundation."
}

variable "model_name" {
  type    = string
  default = "gpt-4.1-mini"
}

variable "app_insights_connection_string" {
  type      = string
  sensitive = true
}

variable "container_image" {
  type        = string
  default     = "mcr.microsoft.com/k8se/quickstart:latest"
  description = "Backend container image. Set to ACR image after first deploy."
}

variable "frontend_image" {
  type        = string
  default     = "mcr.microsoft.com/k8se/quickstart:latest"
  description = "Frontend container image. Set to ACR image after first deploy."
}

variable "enable_private_networking" {
  type    = bool
  default = false
}

variable "tags" {
  type    = map(string)
  default = {}
}
