###############################################################################
# terraform/9_dynamodb/variables.tf
###############################################################################

variable "aws_region" {
  description = "Região AWS"
  type        = string
  default     = "sa-east-1"
}

variable "project" {
  description = "Nome do projeto"
  type        = string
  default     = "data-master"
}

variable "environment" {
  description = "Ambiente (prd, staging)"
  type        = string
  default     = "prd"
}

variable "dynamodb_table_name" {
  description = "Nome da tabela DynamoDB (single-table design)"
  type        = string
  default     = "dm-chain-explorer"
}
