terraform {
  required_version = ">= 1.3.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 4.60.0"
    }
  }

  backend "s3" {
    bucket         = "dm-chain-explorer-terraform-state"
    key            = "prd/iam/terraform.tfstate"
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

# Remote state — VPC outputs (for Databricks cross-account role)
data "terraform_remote_state" "vpc" {
  backend = "s3"
  config = {
    bucket = "dm-chain-explorer-terraform-state"
    key    = "prd/vpc/terraform.tfstate"
    region = "sa-east-1"
  }
}

data "aws_caller_identity" "current" {}

# S3 ARNs derived from account ID — works during both apply and destroy
locals {
  account_id             = data.aws_caller_identity.current.account_id
  raw_bucket_arn         = "arn:aws:s3:::dm-chain-explorer-raw-data"
  lakehouse_bucket_arn   = "arn:aws:s3:::dm-chain-explorer-prd-lakehouse"
  databricks_bucket_arn  = "arn:aws:s3:::dm-chain-explorer-databricks"
}
