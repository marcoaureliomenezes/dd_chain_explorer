variable "region" {
  description = "AWS region for every stack this project provisions"
  type        = string
  default     = "sa-east-1"
}

variable "environment" {
  description = "Tag value only — this stack is account-level, not per-environment"
  type        = string
  default     = "prd"
}

variable "project_version" {
  description = "Project version from VERSION file — propagated to resource tags"
  type        = string
  default     = "0.0.0"
}

# -----------------------------------------------------------------------
# GitHub Actions OIDC (D14)
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

variable "github_oidc_provider_arn" {
  description = "ARN of the operator-created GitHub OIDC identity provider. Empty string => look it up via data source by URL; the provider itself is NEVER created by this terraform."
  type        = string
  default     = ""
}

variable "github_default_branch" {
  description = "Default branch ref trusted by the read-only plan role (drift detection, PRs into main)"
  type        = string
  default     = "main"
}

variable "github_deploy_branch" {
  description = "Branch the deploy/plan-on-PR workflows dispatch from; trusted by the read-only plan role"
  type        = string
  default     = "develop"
}

# -----------------------------------------------------------------------
# Terraform remote-state backend — granted to deploy roles (rw) and the
# read-only plan role (read-only, no lock-table access — the read-only
# plan path runs `terraform plan -lock=false`, F-04).
# -----------------------------------------------------------------------
variable "tf_state_bucket" {
  description = "S3 bucket holding terraform remote state"
  type        = string
  default     = "dm-chain-explorer-terraform-state"
}

variable "tf_state_lock_table" {
  description = "DynamoDB table holding the terraform state lock"
  type        = string
  default     = "dm-chain-explorer-terraform-lock"
}

# -----------------------------------------------------------------------
# Lambda layer artifact store (D15, T-B.14) — the read-only plan role
# writes the content-addressed layer object during plan_on_pr (K6); the
# deploy roles read it when applying the Lambda stacks.
# -----------------------------------------------------------------------
variable "artifacts_bucket" {
  description = "S3 bucket holding build artifacts (the Lambda layer zip), content-addressed by sha256"
  type        = string
  default     = "dm-chain-explorer-artifacts"
}

# -----------------------------------------------------------------------
# Project resource-name prefixes — every Allow statement's resource ARN is
# scoped to one of these, the terraform state bucket, the lock table, or
# the artifacts bucket. Never "*". Proven negatively by T-A.3b.
# -----------------------------------------------------------------------
variable "project_name_prefixes" {
  description = "AWS resource-name prefixes that belong to this project — the scoping boundary for every Allow statement below"
  type        = list(string)
  default     = ["dm-chain-explorer-", "dm-dd-chain-explorer-", "dm-databricks-"]
}

variable "project_ssm_path_prefixes" {
  description = "SSM parameter path prefixes this project's Lambdas read"
  type        = list(string)
  default     = ["/etherscan-api-keys/"]
}
