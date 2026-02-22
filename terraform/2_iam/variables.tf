variable "region" {
  default = "sa-east-1"
  type    = string
}

variable "environment" {
  default = "prod"
  type    = string
}

variable "databricks_account_id" {
  description = "Databricks AWS account ID for cross-account trust"
  type        = string
  default     = "414351767826" # Databricks production account ID
}
