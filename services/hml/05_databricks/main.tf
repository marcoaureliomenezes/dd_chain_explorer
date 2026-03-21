###############################################################################
# hml/05_databricks/main.tf
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
    key            = "hml/databricks/terraform.tfstate"
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

provider "databricks" {
  alias   = "accounts"
  host    = "https://accounts.cloud.databricks.com"
  profile = var.databricks_accounts_profile
}

provider "databricks" {
  alias = "workspace"
  host  = databricks_mws_workspaces.dm.workspace_url
  token = databricks_mws_workspaces.dm.token[0].token_value
}

data "databricks_current_config" "accounts" {
  provider = databricks.accounts
}

data "terraform_remote_state" "vpc" {
  backend = "s3"
  config = {
    bucket = "dm-chain-explorer-terraform-state"
    key    = "hml/vpc/terraform.tfstate"
    region = "sa-east-1"
  }
}

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

locals {
  common_tags = {
    "owner"       = "marco-menezes"
    "managed-by"  = "terraform"
    "cost-center" = "dd-chain-explorer"
    "environment" = var.environment
    "project"     = "dd-chain-explorer"
  }
}
