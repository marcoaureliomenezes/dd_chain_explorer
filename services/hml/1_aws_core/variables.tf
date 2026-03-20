###############################################################################
# terraform_hml/variables.tf
###############################################################################

variable "region" {
  description = "AWS region"
  type        = string
  default     = "sa-east-1"
}

variable "environment" {
  description = "Nome do ambiente"
  type        = string
  default     = "hml"
}

variable "ingestion_bucket_name" {
  description = "Bucket S3 para ingestão Kafka → S3 no ambiente HML (lido pelos DABs Free Edition)"
  type        = string
  default     = "dm-chain-explorer-hml-ingestion"
}

variable "dynamodb_table_name" {
  description = "Tabela DynamoDB single-table para os streaming apps em HML"
  type        = string
  default     = "dm-chain-explorer-hml"
}

variable "ecs_task_execution_role_name" {
  description = "Nome da IAM role para execução de ECS tasks HML (pull ECR + CloudWatch logs)"
  type        = string
  default     = "dm-hml-ecs-task-execution-role"
}

variable "ecs_task_role_name" {
  description = "Nome da IAM role de negócio das ECS tasks HML (DynamoDB + S3)"
  type        = string
  default     = "dm-hml-ecs-task-role"
}
