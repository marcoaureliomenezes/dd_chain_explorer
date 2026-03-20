###############################################################################
# modules/cloudwatch_logs/main.tf
#
# Creates a CloudWatch Log Group and (optionally) a Firehose Delivery Stream
# that delivers log events to S3 via a Subscription Filter.
#
# Usage:
#   module "cloudwatch_logs" {
#     source = "../../modules/cloudwatch_logs"
#     environment            = "prd"
#     common_tags            = local.common_tags
#     log_group_name         = "/apps/dm-chain-explorer"
#     retention_in_days      = 30
#     firehose_enabled       = true
#     firehose_s3_bucket_arn = "arn:aws:s3:::dm-chain-explorer-lakehouse"
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
# CloudWatch Log Group
# ---------------------------------------------------------------------------

resource "aws_cloudwatch_log_group" "this" {
  name              = "${var.log_group_name}-${var.environment}"
  retention_in_days = var.retention_in_days

  tags = merge(var.common_tags, {
    Name = "${var.log_group_name}-${var.environment}"
  })
}

# ---------------------------------------------------------------------------
# IAM Role for Firehose (CW Logs → S3)
# ---------------------------------------------------------------------------

resource "aws_iam_role" "firehose_logs" {
  count = var.firehose_enabled ? 1 : 0

  name = "dm-${var.environment}-firehose-cw-logs-role"

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

resource "aws_iam_role_policy" "firehose_logs" {
  count = var.firehose_enabled ? 1 : 0

  name = "dm-${var.environment}-firehose-cw-logs-policy"
  role = aws_iam_role.firehose_logs[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
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
# IAM Role for CloudWatch Logs to put records into Firehose
# ---------------------------------------------------------------------------

resource "aws_iam_role" "cw_to_firehose" {
  count = var.firehose_enabled ? 1 : 0

  name = "dm-${var.environment}-cw-to-firehose-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "logs.${var.region}.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })

  tags = var.common_tags
}

resource "aws_iam_role_policy" "cw_to_firehose" {
  count = var.firehose_enabled ? 1 : 0

  name = "dm-${var.environment}-cw-to-firehose-policy"
  role = aws_iam_role.cw_to_firehose[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "firehose:PutRecord",
        "firehose:PutRecordBatch",
      ]
      Resource = [aws_kinesis_firehose_delivery_stream.logs[0].arn]
    }]
  })
}

# ---------------------------------------------------------------------------
# Firehose Delivery Stream (CloudWatch Logs → S3)
#
# NOTE: CloudWatch Logs subscription filters ALWAYS send gzip-compressed
# data to Firehose. With compression_format = "GZIP", the S3 files are
# double-gzipped (outer = Firehose, inner = CW Logs envelope).
# The DLT pipeline handles this via binaryFile Auto Loader format.
# ---------------------------------------------------------------------------

resource "aws_kinesis_firehose_delivery_stream" "logs" {
  count = var.firehose_enabled ? 1 : 0

  name        = "firehose-app-logs-${var.environment}"
  destination = "extended_s3"

  extended_s3_configuration {
    role_arn   = aws_iam_role.firehose_logs[0].arn
    bucket_arn = var.firehose_s3_bucket_arn

    prefix              = "${var.firehose_s3_prefix}year=!{timestamp:yyyy}/month=!{timestamp:MM}/day=!{timestamp:dd}/hour=!{timestamp:HH}/"
    error_output_prefix = "${var.firehose_s3_prefix}errors/!{firehose:error-output-type}/year=!{timestamp:yyyy}/month=!{timestamp:MM}/day=!{timestamp:dd}/hour=!{timestamp:HH}/"

    buffering_size     = var.firehose_buffer_size_mb
    buffering_interval = var.firehose_buffer_interval_seconds
    compression_format = "GZIP"
  }

  tags = merge(var.common_tags, {
    Name = "firehose-app-logs-${var.environment}"
  })
}

# ---------------------------------------------------------------------------
# Subscription Filter (CloudWatch Logs → Firehose)
# ---------------------------------------------------------------------------

resource "aws_cloudwatch_log_subscription_filter" "to_firehose" {
  count = var.firehose_enabled ? 1 : 0

  name            = "dm-${var.environment}-logs-to-firehose"
  log_group_name  = aws_cloudwatch_log_group.this.name
  filter_pattern  = "" # empty = all log events
  destination_arn = aws_kinesis_firehose_delivery_stream.logs[0].arn
  role_arn        = aws_iam_role.cw_to_firehose[0].arn
}
