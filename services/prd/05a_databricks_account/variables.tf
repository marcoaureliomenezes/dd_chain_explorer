variable "region" {
  default = "sa-east-1"
}

variable "environment" {
  default = "prd"
}

variable "databricks_accounts_profile" {
  description = "Perfil no ~/.databrickscfg para operações account-level"
  type        = string
  default     = "prd"
}

variable "workspace_name" {
  default = "dm-chain-explorer-prd"
  type    = string
}

variable "workspace_admin_email" {
  description = "E-mail do administrador do workspace Databricks"
  default     = "marcoaurelioreislima@gmail.com"
  type        = string
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
