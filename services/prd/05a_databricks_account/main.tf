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
    key            = "prd/databricks-account/terraform.tfstate"
    region         = "sa-east-1"
    dynamodb_table = "dm-chain-explorer-terraform-lock"
    encrypt        = true
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = local.common_tags
  }
}

# ---------------------------------------------------------------------------
# Databricks account-level provider
# Autenticação via env vars (CI): DATABRICKS_ACCOUNT_ID, DATABRICKS_CLIENT_ID, DATABRICKS_CLIENT_SECRET
# Autenticação local: perfil ~/.databrickscfg [prd]
# ---------------------------------------------------------------------------
provider "databricks" {
  alias   = "accounts"
  host    = "https://accounts.cloud.databricks.com"
  profile = var.databricks_accounts_profile
}

data "databricks_current_config" "accounts" {
  provider = databricks.accounts
}

# Remote states
data "terraform_remote_state" "vpc" {
  backend = "s3"
  config = {
    bucket = "dm-chain-explorer-terraform-state"
    key    = "prd/vpc/terraform.tfstate"
    region = "sa-east-1"
  }
}

data "terraform_remote_state" "iam" {
  backend = "s3"
  config = {
    bucket = "dm-chain-explorer-terraform-state"
    key    = "prd/iam/terraform.tfstate"
    region = "sa-east-1"
  }
}

data "terraform_remote_state" "s3" {
  backend = "s3"
  config = {
    bucket = "dm-chain-explorer-terraform-state"
    key    = "prd/peripherals/terraform.tfstate"
    region = "sa-east-1"
  }
}
