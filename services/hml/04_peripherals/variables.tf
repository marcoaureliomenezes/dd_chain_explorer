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
  description = "ExternalId condition on the hml storage-credential trust policy. Defaults to the same value already used by dm-databricks-dev-s3-role, matching this project's single Databricks Free Edition account; T-C.7 confirms/overrides once the hml storage credential exists (databricks storage-credentials get)."
  type        = string
  sensitive   = true
  default     = "REDACTED-UC-EXTERNAL-ID"
}
