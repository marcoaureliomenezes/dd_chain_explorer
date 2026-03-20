###############################################################################
# modules/kinesis/main.tf
#
# Creates Kinesis Data Streams and (optionally) Firehose Delivery Streams
# that deliver data from Kinesis to S3.
#
# Usage:
#   module "kinesis" {
#     source = "../../modules/kinesis"
#     environment   = "prd"
#     common_tags   = local.common_tags
#     streams = {
#       "mainnet-blocks-data"          = { stream_mode = "ON_DEMAND" }
#       "mainnet-transactions-data"    = { stream_mode = "ON_DEMAND" }
#       "mainnet-transactions-decoded" = { stream_mode = "ON_DEMAND" }
#     }
#     firehose_enabled       = true
#     firehose_s3_bucket_arn = "arn:aws:s3:::dm-chain-explorer-lakehouse"
#     firehose_s3_prefix     = "raw/"
#   }
###############################################################################

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

data "aws_caller_identity" "current" {}

# ---------------------------------------------------------------------------
# Kinesis Data Streams
# ---------------------------------------------------------------------------

resource "aws_kinesis_stream" "this" {
  for_each = var.streams

  name             = "${each.key}-${var.environment}"
  retention_period = each.value.retention_period
  encryption_type  = each.value.encryption_type

  stream_mode_details {
    stream_mode = each.value.stream_mode
  }

  # shard_count is only relevant for PROVISIONED mode
  shard_count = each.value.stream_mode == "PROVISIONED" ? each.value.shard_count : null

  tags = merge(var.common_tags, {
    Name = "${each.key}-${var.environment}"
  })
}

# ---------------------------------------------------------------------------
# IAM Role for Firehose (created only if firehose_enabled and no role provided)
# ---------------------------------------------------------------------------

locals {
  create_firehose_role = var.firehose_enabled && var.firehose_role_arn == ""
  firehose_role_arn    = local.create_firehose_role ? aws_iam_role.firehose[0].arn : var.firehose_role_arn
}

resource "aws_iam_role" "firehose" {
  count = local.create_firehose_role ? 1 : 0

  name = "dm-${var.environment}-firehose-kinesis-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "firehose.amazonaws.com"
      }
      Action = "sts:AssumeRole"
      Condition = {
        StringEquals = {
          "sts:ExternalId" = data.aws_caller_identity.current.account_id
        }
      }
    }]
  })

  tags = var.common_tags
}

resource "aws_iam_role_policy" "firehose" {
  count = local.create_firehose_role ? 1 : 0

  name = "dm-${var.environment}-firehose-kinesis-policy"
  role = aws_iam_role.firehose[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "KinesisReadAccess"
        Effect = "Allow"
        Action = [
          "kinesis:DescribeStream",
          "kinesis:GetShardIterator",
          "kinesis:GetRecords",
          "kinesis:ListShards",
        ]
        Resource = [for s in aws_kinesis_stream.this : s.arn]
      },
      {
        Sid    = "S3WriteAccess"
        Effect = "Allow"
        Action = [
          "s3:AbortMultipartUpload",
          "s3:GetBucketLocation",
          "s3:GetObject",
          "s3:ListBucket",
          "s3:ListBucketMultipartUploads",
          "s3:PutObject",
        ]
        Resource = [
          var.firehose_s3_bucket_arn,
          "${var.firehose_s3_bucket_arn}/*",
        ]
      },
    ]
  })
}

# ---------------------------------------------------------------------------
# Firehose Delivery Streams (Kinesis → S3)
# ---------------------------------------------------------------------------

resource "aws_kinesis_firehose_delivery_stream" "this" {
  for_each = var.firehose_enabled ? var.streams : {}

  name        = "firehose-${each.key}-${var.environment}"
  destination = "extended_s3"

  kinesis_source_configuration {
    kinesis_stream_arn = aws_kinesis_stream.this[each.key].arn
    role_arn           = local.firehose_role_arn
  }

  extended_s3_configuration {
    role_arn   = local.firehose_role_arn
    bucket_arn = var.firehose_s3_bucket_arn

    prefix              = "${var.firehose_s3_prefix}${each.key}/year=!{timestamp:yyyy}/month=!{timestamp:MM}/day=!{timestamp:dd}/hour=!{timestamp:HH}/"
    error_output_prefix = "${var.firehose_s3_prefix}${each.key}_errors/!{firehose:error-output-type}/year=!{timestamp:yyyy}/month=!{timestamp:MM}/day=!{timestamp:dd}/hour=!{timestamp:HH}/"

    buffering_size     = var.firehose_buffer_size_mb
    buffering_interval = var.firehose_buffer_interval_seconds
    compression_format = var.firehose_compression
  }

  tags = merge(var.common_tags, {
    Name = "firehose-${each.key}-${var.environment}"
  })
}
