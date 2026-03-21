variable "region" {
  default = "sa-east-1"
}

variable "environment" {
  default = "prd"
}

variable "workspace_host" {
  description = "Databricks workspace URL — output do módulo 05a_databricks_account. Injetado via TF_VAR_workspace_host no CI."
  type        = string
}

variable "workspace_token" {
  description = "Databricks workspace bootstrap token — output do módulo 05a_databricks_account. Injetado via TF_VAR_workspace_token no CI."
  type        = string
  sensitive   = true
}

variable "databricks_bucket_name" {
  description = "S3 bucket for Unity Catalog metastore root, Spark checkpoints and raw staging"
  default     = "dm-chain-explorer-databricks"
  type        = string
}

variable "project_version" {
  description = "Project version from VERSION file"
  type        = string
  default     = "0.0.0"
}
