variable "region" {
  default = "sa-east-1"
  type    = string
}

variable "environment" {
  default = "prd"
  type    = string
}

variable "databricks_account_id" {
  description = "Databricks AWS account ID for cross-account trust"
  type        = string
  default     = "414351767826" # Databricks production account ID
}

variable "databricks_account_uuid" {
  description = "Databricks account UUID (found in accounts.cloud.databricks.com) — used as ExternalId in the cross-account trust policy"
  type        = string
  sensitive   = true
  default     = "f28000a4-f27e-4231-8ae4-20fa34ba09fd"
}

variable "project_version" {
  description = "Project version from VERSION file — propagated to resource tags"
  type        = string
  default     = "0.0.0"
}

# -----------------------------------------------------------------------
# GitHub Actions OIDC (ADR-R6-3/R6-6/R6-7) — see oidc.tf
# -----------------------------------------------------------------------
variable "github_org" {
  description = "GitHub organization/owner that owns the Actions repo (OIDC sub claim)"
  type        = string
  default     = "marcoaureliomenezes"
}

variable "github_repo" {
  description = "GitHub repository name that runs the Actions workflows (OIDC sub claim)"
  type        = string
  default     = "dd_chain_explorer"
}

variable "github_default_branch" {
  description = "Default branch ref trusted by the read-only plan role (drift/auto-bump contexts)"
  type        = string
  default     = "master"
}

variable "github_oidc_provider_arn" {
  description = "ARN of the operator-created GitHub OIDC identity provider (OP-R6-2). Empty string => look it up via data source by URL; the provider itself is NEVER created by this terraform."
  type        = string
  default     = ""
}

variable "tf_state_bucket" {
  description = "S3 bucket holding terraform remote state — granted to deploy roles (rw) and the read-only plan role (read)"
  type        = string
  default     = "dm-chain-explorer-terraform-state"
}

variable "tf_state_lock_table" {
  description = "DynamoDB table holding the terraform state lock — granted to deploy roles (rw) and the read-only plan role (read)"
  type        = string
  default     = "dm-chain-explorer-terraform-lock"
}
