###############################################################################
# terraform_dev/3_iam/variables.tf
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
  description = "Nome do bucket S3 de ingestão que a role terá acesso."
  type        = string
  default     = "dm-chain-explorer-dev-ingestion"
}

variable "databricks_unity_catalog_iam_arn" {
  description = "ARN IAM do Unity Catalog Databricks (retornado pela storage credential). Obtido via: databricks storage-credentials get dm-dev-s3-credential | jq .aws_iam_role.unity_catalog_iam_arn"
  type        = string
  # Obtido da storage credential após criação
  default     = "arn:aws:iam::414351767826:role/unity-catalog-prod-UCMasterRole-14S5ZJVKOTYTL"
}

variable "storage_credential_external_id" {
  description = "External ID da storage credential Databricks. Obtido via: databricks storage-credentials get dm-dev-s3-credential | jq .aws_iam_role.external_id"
  type        = string
  # Obtido da storage credential após criação
  default     = "b330dc4d-b546-4931-b75c-bc084d35714a"
}
