variable "region" {
  type    = string
  default = "sa-east-1"
}

variable "environment" {
  type    = string
  default = "hml"
}

variable "raw_bucket_name" {
  description = "Canonical HML raw-data bucket name (SPEC v0.5.0 §2.2 B2)"
  type        = string
  default     = "dm-chain-explorer-hml-raw-data"
}

variable "lakehouse_bucket_name" {
  description = "Canonical HML lakehouse bucket name (SPEC v0.5.0 §2.2 B2)"
  type        = string
  default     = "dm-chain-explorer-hml-lakehouse"
}

variable "databricks_uc_principal_arn" {
  description = "Databricks Unity Catalog master-role ARN trusted by the storage-credential role. Never a literal in a public repo consumer file — mirrors the dev role's live trust principal."
  type        = string
  default     = "arn:aws:iam::414351767826:role/unity-catalog-prod-UCMasterRole-14S5ZJVKOTYTL"
}

variable "databricks_hml_uc_external_id" {
  description = "Databricks UC storage-credential ExternalId — supplied via TF_VAR_<name> from the repository secret DATABRICKS_UC_EXTERNAL_ID; never a literal in this public repo."
  type        = string
  sensitive   = true
}

variable "uc_role_self_assume" {
  description = "Include the SelfAssume trust statement on dm-databricks-hml-s3-role. Set to false ONLY on the very first apply (the role must exist before it can be named as a principal); the default second apply adds it."
  type        = bool
  default     = true
}
