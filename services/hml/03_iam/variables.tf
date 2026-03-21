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
  description = "Databricks AWS account ID (cross-account trust)"
  type        = string
  default     = ""
}

variable "databricks_account_uuid" {
  description = "Databricks ExternalId condition"
  type        = string
  default     = ""
}
