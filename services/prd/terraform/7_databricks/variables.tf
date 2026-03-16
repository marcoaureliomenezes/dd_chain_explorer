variable "region" {
  default = "sa-east-1"
}

variable "environment" {
  default = "prd"
}

# ---------------------------------------------------------------------------
# Databricks authentication — via ~/.databrickscfg profiles
# ---------------------------------------------------------------------------
# Em desenvolvimento local, configure o arquivo ~/.databrickscfg com as seções
# [prd] e [prd-workspace] (veja scripts/setup_databricks_profiles.sh).
#
# Em CI/CD (GitHub Actions) as credenciais são injetadas via env vars:
#   DATABRICKS_ACCOUNT_ID, DATABRICKS_CLIENT_ID, DATABRICKS_CLIENT_SECRET
# As env vars têm precedência sobre o profile — o default abaixo é ignorado.
# ---------------------------------------------------------------------------
variable "databricks_accounts_profile" {
  description = "Perfil no ~/.databrickscfg para operações account-level (criação do workspace, metastore)"
  type        = string
  default     = "prd"
}

variable "workspace_name" {
  default = "dm-chain-explorer-prd"
  type    = string
}

variable "databricks_bucket_name" {
  description = "S3 bucket for Unity Catalog metastore root, Spark checkpoints and raw staging"
  default     = "dm-chain-explorer-databricks"
  type        = string
}

