variable "region" {
  type    = string
  default = "sa-east-1"
}

variable "environment" {
  type    = string
  default = "hml"
}

variable "dynamodb_table_name" {
  type    = string
  default = "dm-chain-explorer-hml"
}

variable "databricks_account_id" {
  description = "Databricks AWS account ID for cross-account trust"
  type        = string
  default     = "414351767826" # Databricks production account ID
}

variable "databricks_account_uuid" {
  description = "Databricks account UUID — used as ExternalId in the cross-account trust policy"
  type        = string
  sensitive   = true
  default     = "f28000a4-f27e-4231-8ae4-20fa34ba09fd"
}
