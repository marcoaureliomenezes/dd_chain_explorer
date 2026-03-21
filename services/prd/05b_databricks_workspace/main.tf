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
    key            = "prd/databricks-workspace/terraform.tfstate"
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
# Databricks workspace-level provider
# host e token vêm dos outputs do módulo 05a_databricks_account via
# TF_VAR_workspace_host e TF_VAR_workspace_token injetados pelo CI.
# Localmente: configure ~/.databrickscfg [prd-workspace] com host + token,
# ou exporte TF_VAR_workspace_host / TF_VAR_workspace_token manualmente.
# ---------------------------------------------------------------------------
provider "databricks" {
  alias = "workspace"
  host  = var.workspace_host
  token = var.workspace_token
}

# Remote states
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

data "terraform_remote_state" "databricks_account" {
  backend = "s3"
  config = {
    bucket = "dm-chain-explorer-terraform-state"
    key    = "prd/databricks-account/terraform.tfstate"
    region = "sa-east-1"
  }
}
