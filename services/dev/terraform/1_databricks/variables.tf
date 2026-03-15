###############################################################################
# terraform_dev/1_databricks/variables.tf
###############################################################################

variable "databricks_host" {
  description = "URL do workspace Databricks."
  type        = string
  default     = "https://dbc-409f1007-5779.cloud.databricks.com"
}

variable "databricks_token" {
  description = "Personal Access Token do admin Databricks (para gerenciar storage credentials e external locations)."
  type        = string
  sensitive   = true
  default     = ""
}

variable "databricks_client_id" {
  description = "Client ID do Service Principal Databricks (alternativa ao token)."
  type        = string
  sensitive   = true
  default     = ""
}

variable "databricks_client_secret" {
  description = "Client Secret do Service Principal Databricks."
  type        = string
  sensitive   = true
  default     = ""
}

variable "environment" {
  description = "Nome do ambiente."
  type        = string
  default     = "dev"
}

variable "bucket_name" {
  description = "Nome do bucket S3 de ingestão DEV."
  type        = string
  default     = "dm-chain-explorer-dev-ingestion"
}

variable "iam_role_arn" {
  description = "ARN da IAM role criada em 3_iam/ para o Databricks acessar o S3."
  type        = string
  default     = "arn:aws:iam::016098071081:role/dm-databricks-dev-s3-role"
}
