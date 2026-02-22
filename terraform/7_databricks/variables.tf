variable "region" {
  default = "sa-east-1"
}

variable "environment" {
  default = "prod"
}

variable "databricks_account_id" {
  description = "Databricks account UUID (found in accounts.cloud.databricks.com)"
  type        = string
  sensitive   = true
}

variable "databricks_client_id" {
  description = "Databricks service principal client ID (OAuth M2M)"
  type        = string
  sensitive   = true
}

variable "databricks_client_secret" {
  description = "Databricks service principal client secret (OAuth M2M)"
  type        = string
  sensitive   = true
}

variable "databricks_workspace_token" {
  description = "Databricks personal access token for workspace-level resources"
  type        = string
  sensitive   = true
  default     = "" # set after workspace is created
}

variable "workspace_name" {
  default = "dm-chain-explorer-prod"
  type    = string
}
