terraform {
  required_version = ">= 1.3.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 4.60.0"
    }
    databricks = {
      source  = "databricks/databricks"
      version = ">= 1.36.0"
    }
  }

  backend "s3" {
    bucket         = "dm-chain-explorer-terraform-state"
    key            = "databricks/terraform.tfstate"
    region         = "sa-east-1"
    dynamodb_table = "dm-chain-explorer-terraform-lock"
    encrypt        = true
  }
}

# AWS provider
provider "aws" {
  region = var.region

  default_tags {
    tags = local.common_tags
  }
}

# ---------------------------------------------------------------------------
# Databricks account-level provider
# ---------------------------------------------------------------------------
# Autenticação (prioridade decrescente — a primeira que funcionar é usada):
#   1. Variáveis de ambiente (CI/CD / GitHub Actions):
#        DATABRICKS_ACCOUNT_ID, DATABRICKS_CLIENT_ID, DATABRICKS_CLIENT_SECRET
#   2. Perfil local (~/.databrickscfg):
#        profile = var.databricks_accounts_profile  (default: "prd")
#        Seção [prd] deve conter: host, account_id, client_id, client_secret
#
# NUNCA passe credenciais como variáveis Terraform ou -var-file.
# ---------------------------------------------------------------------------
provider "databricks" {
  alias   = "accounts"
  host    = "https://accounts.cloud.databricks.com"
  profile = var.databricks_accounts_profile
}

# ---------------------------------------------------------------------------
# Databricks workspace-level provider
# ---------------------------------------------------------------------------
# host  → URL do workspace criado pelo recurso databricks_mws_workspaces.dm
# token → bootstrap token gerado automaticamente pelo próprio recurso
#
# Para operações no workspace após destroy/recreate, o token é regenerado
# automaticamente — sem intervenção manual.
# ---------------------------------------------------------------------------
provider "databricks" {
  alias = "workspace"
  host  = databricks_mws_workspaces.dm.workspace_url
  token = databricks_mws_workspaces.dm.token[0].token_value
}

# ---------------------------------------------------------------------------
# Databricks account_id — lido diretamente do provider (perfil/env vars)
# Evita hardcode ou variáveis com credenciais
# ---------------------------------------------------------------------------
data "databricks_current_config" "accounts" {
  provider = databricks.accounts
}

# Remote states
data "terraform_remote_state" "vpc" {
  backend = "s3"
  config = {
    bucket = "dm-chain-explorer-terraform-state"
    key    = "vpc/terraform.tfstate"
    region = "sa-east-1"
  }
}

data "terraform_remote_state" "iam" {
  backend = "s3"
  config = {
    bucket = "dm-chain-explorer-terraform-state"
    key    = "iam/terraform.tfstate"
    region = "sa-east-1"
  }
}

data "terraform_remote_state" "s3" {
  backend = "s3"
  config = {
    bucket = "dm-chain-explorer-terraform-state"
    key    = "s3/terraform.tfstate"
    region = "sa-east-1"
  }
}
