variable "region" {
  type    = string
  default = "sa-east-1"
}

variable "environment" {
  type    = string
  default = "hml"
}

variable "databricks_accounts_profile" {
  type    = string
  default = "hml"
}

variable "workspace_name" {
  type    = string
  default = "dm-chain-explorer-hml"
}

variable "workspace_admin_email" {
  type    = string
  default = "marcoaurelioreislima@gmail.com"
}

variable "assign_workspace_admin" {
  description = "Set true to enable databricks_mws_permission_assignment for the workspace admin. Requires Identity Federation enabled on the workspace."
  type        = bool
  default     = false
}
