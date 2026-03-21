variable "region" {
  type    = string
  default = "sa-east-1"
}

variable "environment" {
  type    = string
  default = "hml"
}

variable "raw_bucket_name" {
  type    = string
  default = "dm-chain-explorer-hml-raw"
}

variable "lakehouse_bucket_name" {
  type    = string
  default = "dm-chain-explorer-hml-lakehouse"
}

variable "databricks_bucket_name" {
  type    = string
  default = "dm-chain-explorer-hml-databricks"
}

variable "dynamodb_table_name" {
  type    = string
  default = "dm-chain-explorer-hml"
}
