###############################################################################
# prd/04_peripherals/peripherals.tf
#
# Consolida 3_kinesis_sqs + 4_s3 + 9_dynamodb em um único módulo Terraform.
###############################################################################

# ---------------------------------------------------------------------------
# S3 Buckets
# ---------------------------------------------------------------------------

module "s3_raw" {
  source = "../../modules/s3"

  environment = var.environment
  region      = var.region
  common_tags = local.common_tags
  bucket_name = var.raw_bucket_name

  lifecycle_rules = [
    {
      id     = "raw-data-lifecycle"
      prefix = ""
      transitions = [
        { days = 30, storage_class = "STANDARD_IA" },
        { days = 90, storage_class = "GLACIER" },
      ]
    }
  ]
}

module "s3_lakehouse" {
  source = "../../modules/s3"

  environment        = var.environment
  region             = var.region
  common_tags        = local.common_tags
  bucket_name        = var.lakehouse_bucket_name
  ownership_controls = "BucketOwnerPreferred"

  lifecycle_rules = [
    {
      id     = "lakehouse-ia-lifecycle"
      prefix = ""
      transitions = [
        { days = 90, storage_class = "STANDARD_IA" },
      ]
    }
  ]

  folder_prefixes = ["bronze", "silver", "gold"]
}

module "s3_databricks" {
  source = "../../modules/s3"

  environment        = var.environment
  region             = var.region
  common_tags        = local.common_tags
  bucket_name        = var.databricks_bucket_name
  ownership_controls = "BucketOwnerPreferred"

  lifecycle_rules = [
    {
      id     = "databricks-ia-lifecycle"
      prefix = ""
      transitions = [
        { days = 90, storage_class = "STANDARD_IA" },
      ]
    },
    {
      id              = "checkpoints-expiry"
      prefix          = "checkpoints/"
      expiration_days = 365
    }
  ]

  folder_prefixes = ["checkpoints", "staging", "unity-catalog"]
}

# ---------------------------------------------------------------------------
# Kinesis Data Streams + Firehose → S3 Lakehouse
# ---------------------------------------------------------------------------

module "kinesis" {
  source = "../../modules/kinesis"

  environment = var.environment
  region      = var.region
  common_tags = local.common_tags

  streams = {
    "mainnet-transactions-data" = {
      stream_mode      = "PROVISIONED"
      shard_count      = 1
      retention_period = 24
      encryption_type  = "NONE"
    }
  }

  firehose_enabled       = true
  firehose_s3_bucket_arn = module.s3_lakehouse.bucket_arn
  firehose_s3_prefix     = "raw/"

  firehose_direct_put_streams = {
    "mainnet-blocks-data"          = {}
    "mainnet-transactions-decoded" = {}
  }
}

# ---------------------------------------------------------------------------
# SQS Queues + Dead Letter Queues
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# CloudWatch Log Group + Firehose → S3 Lakehouse
# ---------------------------------------------------------------------------

module "cloudwatch_logs" {
  source = "../../modules/cloudwatch_logs"

  environment            = var.environment
  region                 = var.region
  common_tags            = local.common_tags
  log_group_name         = "/apps/dm-chain-explorer"
  retention_in_days      = 30
  firehose_enabled       = true
  firehose_s3_bucket_arn = module.s3_lakehouse.bucket_arn
  firehose_s3_prefix     = "raw/app_logs/"
  firehose_buffer_size_mb          = 5
  firehose_buffer_interval_seconds = 300
}

# ---------------------------------------------------------------------------
# DynamoDB — single-table design
# ---------------------------------------------------------------------------

module "dynamodb" {
  source = "../../modules/dynamodb"

  environment            = var.environment
  common_tags            = local.common_tags
  table_name             = var.dynamodb_table_name
  point_in_time_recovery = true
}
