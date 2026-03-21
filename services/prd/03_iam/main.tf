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

# S3 bucket data sources (avoid remote state dependency during destroy)
data "aws_s3_bucket" "raw" {
  bucket = "dm-chain-explorer-raw"
}

data "aws_s3_bucket" "lakehouse" {
  bucket = "dm-chain-explorer-lakehouse"
}

data "aws_s3_bucket" "databricks" {
  bucket = "dm-chain-explorer-databricks"
}
