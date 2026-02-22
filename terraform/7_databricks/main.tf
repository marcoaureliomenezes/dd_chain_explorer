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

# AWS provider: creates the S3 cross-account bucket policy and VPC peering config
provider "aws" {
  region = var.region

  default_tags {
    tags = local.common_tags
  }
}

# Databricks account-level provider (to create the workspace itself)
provider "databricks" {
  alias         = "accounts"
  host          = "https://accounts.cloud.databricks.com"
  account_id    = var.databricks_account_id
  client_id     = var.databricks_client_id
  client_secret = var.databricks_client_secret
}

# Databricks workspace-level provider (populated after workspace creation)
provider "databricks" {
  alias = "workspace"
  host  = databricks_mws_workspaces.dm.workspace_url
  token = var.databricks_workspace_token
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
