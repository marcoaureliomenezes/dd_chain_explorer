variable "region" {
  type    = string
  default = "sa-east-1"
}

variable "environment" {
  type    = string
  default = "dev"
}

variable "bucket_name" {
  type    = string
  default = "dm-chain-explorer-dev-ingestion"
}

variable "dynamodb_table_name" {
  type    = string
  default = "dm-chain-explorer-dev"
}

variable "version" {
  description = "Project version from VERSION file — propagated to resource tags"
  type        = string
  default     = "0.0.0"
}
