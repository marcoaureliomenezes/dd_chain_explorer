###############################################################################
# terraform_dev/variables.tf
###############################################################################

variable "region" {
  description = "AWS region"
  type        = string
  default     = "sa-east-1"
}

variable "environment" {
  description = "Nome do ambiente."
  type        = string
  default     = "dev"
}

variable "bucket_name" {
  description = "Nome do bucket S3 para ingestão de dados do Kafka para o Databricks Free Edition."
  type        = string
  default     = "dm-chain-explorer-dev-ingestion"
}

variable "dynamodb_table_name" {
  description = "Nome da tabela DynamoDB (single-table design) que substitui o Redis."
  type        = string
  default     = "dm-chain-explorer"
}
