###############################################################################
# prd/04_peripherals/peripherals.tf
#
# Consolida os módulos de peripherals (S3 + DynamoDB + CloudWatch) em um único
# módulo Terraform. The capture-era streaming stack was retired in v0.4.0.
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

module "s3_artifacts" {
  source = "../../modules/s3"

  environment        = var.environment
  region             = var.region
  common_tags        = local.common_tags
  bucket_name        = var.artifacts_bucket_name
  versioning_enabled = true
  ownership_controls = "BucketOwnerEnforced"
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
  # ISSUE-029 / AWS-03: folder_prefixes removed. Delta tables under Unity Catalog must NOT
  # carry medallion-tier prefixes (bronze/silver/gold) in S3 paths — UC manages external
  # locations independently. The .keep placeholder objects must be deleted from the bucket
  # after terraform apply (see handoff sidecar for the aws s3 rm commands).
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
# CloudWatch Log Group (the capture-layer log-delivery branch was retired — v0.4.0)
# ---------------------------------------------------------------------------

module "cloudwatch_logs" {
  source = "../../modules/cloudwatch_logs"

  environment       = var.environment
  common_tags       = local.common_tags
  log_group_name    = "/apps/dm-chain-explorer"
  retention_in_days = 30
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
