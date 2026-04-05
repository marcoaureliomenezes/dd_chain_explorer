###############################################################################
# hml/05b_databricks_workspace/main.tf
# Workspace-level Databricks resources (catalog, external locations,
# storage credential, instance profile, cluster).
# Depends on hml/05_databricks state being applied first.
###############################################################################

terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
    databricks = {
      source  = "databricks/databricks"
      version = ">= 1.36.0"
    }
  }

  backend "s3" {
    bucket         = "dm-chain-explorer-terraform-state"
    key            = "hml/databricks-workspace/terraform.tfstate"
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

# Workspace-level auth: uses the bootstrap token generated in 05_databricks.
provider "databricks" {
  alias = "workspace"
  host  = data.terraform_remote_state.databricks_account.outputs.workspace_url
  token = data.terraform_remote_state.databricks_account.outputs.token_value
}

# ── Remote states ──────────────────────────────────────────────────────────

data "terraform_remote_state" "iam" {
  backend = "s3"
  config = {
    bucket = "dm-chain-explorer-terraform-state"
    key    = "hml/iam/terraform.tfstate"
    region = "sa-east-1"
  }
}

data "terraform_remote_state" "peripherals" {
  backend = "s3"
  config = {
    bucket = "dm-chain-explorer-terraform-state"
    key    = "hml/peripherals/terraform.tfstate"
    region = "sa-east-1"
  }
}

data "terraform_remote_state" "databricks_account" {
  backend = "s3"
  config = {
    bucket = "dm-chain-explorer-terraform-state"
    key    = "hml/databricks/terraform.tfstate"
    region = "sa-east-1"
  }
}

locals {
  common_tags = {
    "owner"       = "marco-menezes"
    "managed-by"  = "terraform"
    "cost-center" = "dd-chain-explorer"
    "environment" = var.environment
    "project"     = "dd-chain-explorer"
  }
}
