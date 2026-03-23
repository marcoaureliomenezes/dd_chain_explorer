###############################################################################
# hml/04_peripherals/main.tf
#
# S3 buckets + DynamoDB + CloudWatch + Kinesis + SQS para HML.
# Todos os recursos são persistentes e gerenciados pelo Terraform.
# CI/CD cria apenas: ECS cluster + Security Group (efêmeros por run).
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
    key            = "hml/peripherals/terraform.tfstate"
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

# ---------------------------------------------------------------------------
# S3: raw ingestion bucket
# ---------------------------------------------------------------------------

module "s3_raw" {
  source = "../../modules/s3"

  environment = var.environment
  region      = var.region
  common_tags = local.common_tags
  bucket_name = var.raw_bucket_name

  lifecycle_rules = [
    {
      id              = "expire-hml-data"
      prefix          = ""
      expiration_days = 7
    }
  ]

  folder_prefixes = ["raw", "raw/app_logs"]
}

# ---------------------------------------------------------------------------
# S3: lakehouse bucket (Databricks HML catalog)
# ---------------------------------------------------------------------------

module "s3_lakehouse" {
  source = "../../modules/s3"

  environment        = var.environment
  region             = var.region
  common_tags        = local.common_tags
  bucket_name        = var.lakehouse_bucket_name
  ownership_controls = "BucketOwnerPreferred"

  lifecycle_rules = [
    {
      id              = "expire-hml-lakehouse"
      prefix          = ""
      expiration_days = 30
    }
  ]

  folder_prefixes = ["bronze", "silver", "gold"]
}

# ---------------------------------------------------------------------------
# S3: Databricks-specific bucket (metastore, checkpoints, staging)
# ---------------------------------------------------------------------------

module "s3_databricks" {
  source = "../../modules/s3"

  environment        = var.environment
  region             = var.region
  common_tags        = local.common_tags
  bucket_name        = var.databricks_bucket_name
  ownership_controls = "BucketOwnerPreferred"

  lifecycle_rules = [
    {
      id              = "expire-hml-databricks"
      prefix          = ""
      expiration_days = 30
    }
  ]

  folder_prefixes = ["checkpoints", "staging", "unity-catalog"]
}

# ---------------------------------------------------------------------------
# DynamoDB — single-table design
# ---------------------------------------------------------------------------

module "dynamodb" {
  source = "../../modules/dynamodb"

  environment            = var.environment
  common_tags            = local.common_tags
  table_name             = var.dynamodb_table_name
  point_in_time_recovery = false
}

# ---------------------------------------------------------------------------
# CloudWatch Log Group (persistent — ECS tasks and Firehose reference this)
# ---------------------------------------------------------------------------

module "cloudwatch_logs" {
  source = "../../modules/cloudwatch_logs"

  environment            = var.environment
  region                 = var.region
  common_tags            = local.common_tags
  log_group_name         = "/apps/dm-chain-explorer"
  retention_in_days      = 3
  firehose_enabled       = true
  firehose_s3_bucket_arn = module.s3_raw.bucket_arn
  firehose_s3_prefix     = "raw/app_logs/"
  firehose_buffer_size_mb          = 1
  firehose_buffer_interval_seconds = 60
}

# ---------------------------------------------------------------------------
# Kinesis Data Streams + Firehose → S3 Lakehouse
# Buffer menor que PRD (1 MB / 60 s) para testes de integração mais rápidos
# ---------------------------------------------------------------------------

module "kinesis" {
  source = "../../modules/kinesis"

  environment = var.environment
  region      = var.region
  common_tags = local.common_tags

  streams = {
    "mainnet-blocks-data"          = { stream_mode = "ON_DEMAND", retention_period = 24, encryption_type = "NONE" }
    "mainnet-transactions-data"    = { stream_mode = "ON_DEMAND", retention_period = 24, encryption_type = "NONE" }
    "mainnet-transactions-decoded" = { stream_mode = "ON_DEMAND", retention_period = 24, encryption_type = "NONE" }
  }

  firehose_enabled               = true
  firehose_s3_bucket_arn         = module.s3_lakehouse.bucket_arn
  firehose_s3_prefix             = "raw/"
  firehose_buffer_size_mb        = 1
  firehose_buffer_interval_seconds = 60
}

# ---------------------------------------------------------------------------
# SQS Queues + Dead Letter Queues
# ---------------------------------------------------------------------------

module "sqs" {
  source = "../../modules/sqs"

  environment = var.environment
  common_tags = local.common_tags

  queues = {
    "mainnet-mined-blocks-events" = { visibility_timeout_seconds = 30, receive_wait_time_seconds = 20, dlq_enabled = true, dlq_max_receive_count = 3 }
    "mainnet-block-txs-hash-id"   = { visibility_timeout_seconds = 60, receive_wait_time_seconds = 20, dlq_enabled = true, dlq_max_receive_count = 3 }
  }
}
