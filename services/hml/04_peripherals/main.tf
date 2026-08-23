###############################################################################
# hml/04_peripherals/main.tf
#
# Minimal HML lane (SPEC v0.5.0 §2.2 B2): the two canonical buckets that the
# Databricks bundles reference, plus the Unity Catalog storage-credential
# role scoped to only those buckets. Every other HML resource (databricks
# bucket, DynamoDB table, CloudWatch log group, VPC, ECS, the legacy IAM
# stack) was removed — see DRIFT-13/DRIFT-22, disposed in CLOSURE.md.
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

# -----------------------------------------------------------------------
# T-A.2 rev2 HIGH — permissions-boundary retrofit. Every project
# `aws_iam_role` in this account carries the boundary `prd/00_bootstrap`
# exports, capping its effective permissions regardless of what its own
# inline policy grants. Read via `terraform_remote_state` (literal backend
# config, mirroring the peripherals remote-state pattern used elsewhere in
# this project), not a variable — keeps the CI `-var` surface unchanged.
# -----------------------------------------------------------------------
data "terraform_remote_state" "bootstrap" {
  backend = "s3"
  config = {
    bucket = "dm-chain-explorer-terraform-state"
    key    = "prd/bootstrap/terraform.tfstate"
    region = "sa-east-1"
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
# S3: raw ingestion bucket (canonical name — SPEC §2.2 B2)
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
}

# ---------------------------------------------------------------------------
# S3: lakehouse bucket (canonical name — SPEC §2.2 B2)
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
}

# ---------------------------------------------------------------------------
# IAM: Unity Catalog storage-credential role for HML (T-B.4/T-C.7, DRIFT-22)
#
# Trust mirrors the live `dm-databricks-dev-s3-role` structure: an assume
# statement for the Databricks Unity Catalog master role, plus a self-assume
# statement (required by UC storage-credential validation) — both gated on
# the same ExternalId condition. Principal ARN and ExternalId are variables,
# never literals (public repo) — T-C.7 supplies the real ExternalId once the
# hml storage credential exists; the defaults below assume the same
# Databricks Free Edition account already used for dev (single account,
# per-environment external locations) and MUST be confirmed against the
# actual `databricks storage-credentials get` output before the first apply.
# ---------------------------------------------------------------------------

data "aws_caller_identity" "current" {}

data "aws_iam_policy_document" "databricks_hml_s3_role_assume" {
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
      values   = [var.databricks_hml_uc_external_id]
    }
  }
  statement {
    sid     = "SelfAssume"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/dm-databricks-hml-s3-role"]
    }
    condition {
      test     = "StringEquals"
      variable = "sts:ExternalId"
      values   = [var.databricks_hml_uc_external_id]
    }
  }
}

resource "aws_iam_role" "databricks_hml_s3_role" {
  name                 = "dm-databricks-hml-s3-role"
  description          = "Role for Databricks (Free Edition) to access the HML S3 buckets via a Unity Catalog external location"
  assume_role_policy   = data.aws_iam_policy_document.databricks_hml_s3_role_assume.json
  permissions_boundary = data.terraform_remote_state.bootstrap.outputs.ci_boundary_policy_arn
  tags                 = local.common_tags
}

data "aws_iam_policy_document" "databricks_hml_s3_policy" {
  statement {
    sid    = "ObjectAccess"
    effect = "Allow"
    actions = [
      "s3:PutObject",
      "s3:GetObject",
      "s3:GetObjectAttributes",
      "s3:DeleteObject",
    ]
    resources = [
      "${module.s3_raw.bucket_arn}/*",
      "${module.s3_lakehouse.bucket_arn}/*",
    ]
  }
  statement {
    sid    = "BucketAccess"
    effect = "Allow"
    actions = [
      "s3:ListBucket",
      "s3:GetBucketLocation",
    ]
    resources = [
      module.s3_raw.bucket_arn,
      module.s3_lakehouse.bucket_arn,
    ]
  }
}

resource "aws_iam_role_policy" "databricks_hml_s3_policy" {
  name   = "dm-databricks-hml-s3-policy"
  role   = aws_iam_role.databricks_hml_s3_role.id
  policy = data.aws_iam_policy_document.databricks_hml_s3_policy.json
}
