###############################################################################
# prd/04_peripherals/variables.tf
###############################################################################

variable "region" {
  description = "AWS region"
  type        = string
  default     = "sa-east-1"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "prd"
}

variable "raw_bucket_name" {
  description = "Name of the raw data S3 bucket"
  type        = string
  default     = "dm-chain-explorer-raw-data"
}

variable "lakehouse_bucket_name" {
  description = "Name of the lakehouse S3 bucket"
  type        = string
  default     = "dm-chain-explorer-lakehouse"
}

variable "databricks_bucket_name" {
  description = "Name of the Databricks S3 bucket"
  type        = string
  default     = "dm-chain-explorer-databricks"
}

variable "dynamodb_table_name" {
  description = "DynamoDB single-table name"
  type        = string
  default     = "dm-chain-explorer"
}

variable "project_version" {
  description = "Project version from VERSION file — propagated to resource tags"
  type        = string
  default     = "0.0.0"
}
