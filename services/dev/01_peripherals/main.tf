###############################################################################
# dev/terraform/04_peripherals/main.tf
#
# S3 + DynamoDB + Kinesis + SQS + CloudWatch para DEV.
###############################################################################

terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }

  backend "s3" {
    bucket         = "dm-chain-explorer-terraform-state"
    key            = "dev/peripherals/terraform.tfstate"
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

locals {
  common_tags = {
    "owner"           = "marco-menezes"
    "managed-by"      = "terraform"
    "cost-center"     = "dd-chain-explorer"
    "environment"     = var.environment
    "project"         = "dd-chain-explorer"
    "project_version" = var.project_version
  }
}

module "s3_ingestion" {
  source = "../../modules/s3"

  environment = var.environment
  region      = var.region
  common_tags = local.common_tags
  bucket_name = var.bucket_name

  lifecycle_rules = [
    {
      id              = "expire-dev-data"
      prefix          = ""
      expiration_days = 7
    }
  ]

  folder_prefixes = ["raw"]
}

module "dynamodb" {
  source = "../../modules/dynamodb"

  environment            = var.environment
  common_tags            = local.common_tags
  table_name             = var.dynamodb_table_name
  point_in_time_recovery = false
}

module "cloudwatch_logs" {
  source = "../../modules/cloudwatch_logs"

  environment       = var.environment
  region            = var.region
  common_tags       = local.common_tags
  log_group_name    = "/apps/dm-chain-explorer"
  retention_in_days = 3
  firehose_enabled  = false
}
