###############################################################################
# prd/3_kinesis_sqs/kinesis_sqs.tf
#
# Kinesis Data Streams + Firehose + SQS + CloudWatch para PRD.
# Substitui o MSK Serverless (3_msk/) e o Schema Registry (6_ecs/).
###############################################################################

# ---------------------------------------------------------------------------
# Kinesis Data Streams + Firehose → S3 (lakehouse bucket)
# ---------------------------------------------------------------------------

module "kinesis" {
  source = "../../modules/kinesis"

  environment = var.environment
  region      = var.region
  common_tags = local.common_tags

  streams = {
    "mainnet-blocks-data" = {
      stream_mode      = "ON_DEMAND"
      retention_period  = 24
    }
    "mainnet-transactions-data" = {
      stream_mode      = "ON_DEMAND"
      retention_period  = 24
    }
    "mainnet-transactions-decoded" = {
      stream_mode      = "ON_DEMAND"
      retention_period  = 24
    }
  }

  firehose_enabled       = true
  firehose_s3_bucket_arn = data.terraform_remote_state.s3.outputs.lakehouse_bucket_arn
  firehose_s3_prefix     = "raw/"
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
# CloudWatch Log Group + Firehose → S3 (logs)
# ---------------------------------------------------------------------------

module "cloudwatch_logs" {
  source = "../../modules/cloudwatch_logs"

  environment            = var.environment
  region                 = var.region
  common_tags            = local.common_tags
  log_group_name         = "/apps/dm-chain-explorer"
  retention_in_days      = 30
  firehose_enabled       = true
  firehose_s3_bucket_arn = data.terraform_remote_state.s3.outputs.lakehouse_bucket_arn
  firehose_s3_prefix     = "raw/app_logs/"
  firehose_buffer_size_mb         = 5
  firehose_buffer_interval_seconds = 300
}
