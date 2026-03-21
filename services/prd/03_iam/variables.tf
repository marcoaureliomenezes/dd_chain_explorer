variable "region" {
  default = "sa-east-1"
  type    = string
}

variable "environment" {
  default = "prd"
  type    = string
}

variable "databricks_account_id" {
  description = "Databricks AWS account ID for cross-account trust"
  type        = string
  default     = "414351767826" # Databricks production account ID
}

variable "databricks_account_uuid" {
  description = "Databricks account UUID (found in accounts.cloud.databricks.com) — used as ExternalId in the cross-account trust policy"
  type        = string
  sensitive   = true
  default     = "f28000a4-f27e-4231-8ae4-20fa34ba09fd"
}

variable "version" {
  description = "Project version from VERSION file — propagated to resource tags"
  type        = string
  default     = "0.0.0"
}
