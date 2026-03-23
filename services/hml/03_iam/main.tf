###############################################################################
# hml/03_iam/main.tf
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
    key            = "hml/iam/terraform.tfstate"
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

data "aws_caller_identity" "current" {}

locals {
  # S3 bucket ARNs — hardcoded to avoid remote-state dependency during destroy
  raw_bucket_arn        = "arn:aws:s3:::dm-chain-explorer-hml-raw"
  lakehouse_bucket_arn  = "arn:aws:s3:::dm-chain-explorer-hml-lakehouse"
  databricks_bucket_arn = "arn:aws:s3:::dm-chain-explorer-hml-databricks"

  common_tags = {
    "owner"       = "marco-menezes"
    "managed-by"  = "terraform"
    "cost-center" = "dd-chain-explorer"
    "environment" = var.environment
    "project"     = "dd-chain-explorer"
  }
}

module "iam" {
  source = "../../modules/iam"

  environment           = var.environment
  region                = var.region
  common_tags           = local.common_tags
  account_id            = data.aws_caller_identity.current.account_id
  name_prefix           = "dm-chain-explorer"
  create_ecs_roles      = true
  kinesis_stream_suffix = "hml"
  sqs_queue_suffix      = "hml"
  dynamodb_table_name   = var.dynamodb_table_name
  raw_bucket_arn        = local.raw_bucket_arn
  lakehouse_bucket_arn  = local.lakehouse_bucket_arn

  create_databricks_roles = true
  databricks_account_id   = var.databricks_account_id
  databricks_account_uuid = var.databricks_account_uuid
  databricks_bucket_arn   = local.databricks_bucket_arn
}

# Firehose role (HML-specific — não está no módulo iam genérico)
data "aws_iam_policy_document" "firehose_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["firehose.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "sts:ExternalId"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}

resource "aws_iam_role" "firehose" {
  name               = "dm-chain-explorer-firehose-role-hml"
  assume_role_policy = data.aws_iam_policy_document.firehose_assume.json
  tags               = local.common_tags
}

resource "aws_iam_role_policy" "firehose_s3" {
  name = "dm-chain-explorer-firehose-s3-hml"
  role = aws_iam_role.firehose.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3WriteAccess"
        Effect = "Allow"
        Action = [
          "s3:AbortMultipartUpload", "s3:GetBucketLocation", "s3:GetObject",
          "s3:ListBucket", "s3:ListBucketMultipartUploads", "s3:PutObject",
        ]
        Resource = [
          local.raw_bucket_arn,
          "${local.raw_bucket_arn}/*",
        ]
      },
      {
        Sid    = "KinesisReadAccess"
        Effect = "Allow"
        Action = [
          "kinesis:DescribeStream", "kinesis:GetShardIterator",
          "kinesis:GetRecords", "kinesis:ListShards",
        ]
        Resource = ["arn:aws:kinesis:${var.region}:*:stream/*-hml"]
      }
    ]
  })
}
