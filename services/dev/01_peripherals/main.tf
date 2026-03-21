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
    "owner"       = "marco-menezes"
    "managed-by"  = "terraform"
    "cost-center" = "dd-chain-explorer"
    "environment" = var.environment
    "project"     = "dd-chain-explorer"
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

module "kinesis" {
  source = "../../modules/kinesis"

  environment = var.environment
  region      = var.region
  common_tags = local.common_tags

  streams = {
    "mainnet-blocks-data" = {
      stream_mode      = "PROVISIONED"
      shard_count      = 1
      retention_period = 24
    }
    "mainnet-transactions-data" = {
      stream_mode      = "PROVISIONED"
      shard_count      = 1
      retention_period = 24
    }
    "mainnet-transactions-decoded" = {
      stream_mode      = "PROVISIONED"
      shard_count      = 1
      retention_period = 24
    }
  }

  firehose_enabled       = true
  firehose_s3_bucket_arn = module.s3_ingestion.bucket_arn
  firehose_s3_prefix     = "raw/"
}

module "sqs" {
  source = "../../modules/sqs"

  environment = var.environment
  common_tags = local.common_tags

  queues = {
    "mainnet-mined-blocks-events" = {
      visibility_timeout_seconds = 30
      receive_wait_time_seconds  = 20
      dlq_enabled                = true
      dlq_max_receive_count      = 3
    }
    "mainnet-block-txs-hash-id" = {
      visibility_timeout_seconds = 60
      receive_wait_time_seconds  = 20
      dlq_enabled                = true
      dlq_max_receive_count      = 3
    }
  }
}

module "cloudwatch_logs" {
  source = "../../modules/cloudwatch_logs"

  environment            = var.environment
  region                 = var.region
  common_tags            = local.common_tags
  log_group_name         = "/apps/dm-chain-explorer"
  retention_in_days      = 3
  firehose_enabled       = true
  firehose_s3_bucket_arn = module.s3_ingestion.bucket_arn
  firehose_s3_prefix     = "raw/app_logs/"
  firehose_buffer_size_mb          = 1
  firehose_buffer_interval_seconds = 60
}
