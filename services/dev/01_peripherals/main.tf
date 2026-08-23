###############################################################################
# dev/01_peripherals/main.tf
#
# S3 + DynamoDB + CloudWatch para DEV.
###############################################################################

terraform {
  required_version = "~> 1.9"

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

data "aws_caller_identity" "current" {}

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

  # folder_prefixes intentionally omitted (T-B.6, B5): the raw/.keep placeholder
  # object this module would declare is not live in the real bucket (deleted
  # out-of-band by the dev ingestion process), so declaring it here would be a
  # permanent apply-time diff. Auto Loader does not require the prefix to
  # pre-exist.
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
  common_tags       = local.common_tags
  log_group_name    = "/apps/dm-chain-explorer"
  retention_in_days = 3
}

# ---------------------------------------------------------------------------
# IAM: Unity Catalog storage-credential role for DEV (T-B.12, DRIFT-22)
#
# Load-bearing, orphan-imported: this role already exists live (created
# 2026-02-23, outside any prior Terraform state) and backs the dev Unity
# Catalog external location. Declared here to match the live role exactly —
# see the `import` block below — so applying this stack is a 0-diff. The UC
# principal ARN and ExternalId are variables, never literals (public repo).
# tags/tags_all are intentionally ignored: this role predates the
# project_version tagging convention, and provider default_tags would
# otherwise add a project_version tag on the very first plan after import.
# ---------------------------------------------------------------------------

data "aws_iam_policy_document" "databricks_dev_s3_role_assume" {
  statement {
    sid     = "DatabricksUnityCatalogAssume"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "AWS"
      identifiers = [var.databricks_uc_principal_arn]
    }
    condition {
      test     = "StringEquals"
      variable = "sts:ExternalId"
      values   = [var.databricks_dev_uc_external_id]
    }
  }
  statement {
    sid     = "SelfAssume"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/dm-databricks-dev-s3-role"]
    }
    condition {
      test     = "StringEquals"
      variable = "sts:ExternalId"
      values   = [var.databricks_dev_uc_external_id]
    }
  }
}

resource "aws_iam_role" "databricks_dev_s3_role" {
  name               = "dm-databricks-dev-s3-role"
  description        = "Role para o Databricks Free Edition acessar o S3 DEV (Unity Catalog external location)"
  assume_role_policy = data.aws_iam_policy_document.databricks_dev_s3_role_assume.json
  tags               = local.common_tags

  lifecycle {
    ignore_changes = [tags, tags_all]
  }
}

# NOTE — the live policy grants both dm-chain-explorer-dev-ingestion and
# dm-chain-explorer-hml-ingestion (the latter is not a canonical bucket name
# from SPEC v0.5.0 B2 — likely drift from an earlier naming scheme). Mirrored
# verbatim here for a 0-diff import; not corrected in this release (out of
# T-B.12's scope, recorded as a CLOSURE observation).
data "aws_iam_policy_document" "databricks_dev_s3_policy" {
  statement {
    effect = "Allow"
    actions = [
      "s3:PutObject",
      "s3:GetObjectAttributes",
      "s3:GetObject",
      "s3:DeleteObject",
    ]
    resources = [
      "${module.s3_ingestion.bucket_arn}/*",
      "arn:aws:s3:::dm-chain-explorer-hml-ingestion/*",
    ]
  }
  statement {
    effect = "Allow"
    actions = [
      "s3:ListBucket",
      "s3:GetBucketLocation",
    ]
    resources = [
      module.s3_ingestion.bucket_arn,
      "arn:aws:s3:::dm-chain-explorer-hml-ingestion",
    ]
  }
}

resource "aws_iam_role_policy" "databricks_dev_s3_policy" {
  name   = "dm-databricks-dev-s3-policy"
  role   = aws_iam_role.databricks_dev_s3_role.id
  policy = data.aws_iam_policy_document.databricks_dev_s3_policy.json
}

# Declarative import (Terraform >= 1.5, this stack pins ~> 1.9): `terraform
# plan`/`apply` performs the import automatically. Documented fallback for
# the coordinator if a declarative import is not desired for this apply:
#   terraform import 'aws_iam_role.databricks_dev_s3_role' dm-databricks-dev-s3-role
#   terraform import 'aws_iam_role_policy.databricks_dev_s3_policy' dm-databricks-dev-s3-role:dm-databricks-dev-s3-policy
import {
  to = aws_iam_role.databricks_dev_s3_role
  id = "dm-databricks-dev-s3-role"
}

import {
  to = aws_iam_role_policy.databricks_dev_s3_policy
  id = "dm-databricks-dev-s3-role:dm-databricks-dev-s3-policy"
}
