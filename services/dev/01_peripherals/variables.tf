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

variable "project_version" {
  description = "Project version from VERSION file — propagated to resource tags"
  type        = string
  default     = "0.0.0"
}

variable "databricks_uc_principal_arn" {
  description = "Databricks Unity Catalog master-role ARN trusted by the storage-credential role."
  type        = string
  default     = "arn:aws:iam::414351767826:role/unity-catalog-prod-UCMasterRole-14S5ZJVKOTYTL"
}

variable "databricks_dev_uc_external_id" {
  description = "Databricks UC storage-credential ExternalId — supplied via TF_VAR_<name> from the repository secret DATABRICKS_UC_EXTERNAL_ID; never a literal in this public repo."
  type        = string
  sensitive   = true
}
