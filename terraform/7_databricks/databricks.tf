# -----------------------------------------------------------------------
# Databricks MWS Credentials
# Links the Databricks account to the AWS cross-account IAM role
# -----------------------------------------------------------------------
resource "databricks_mws_credentials" "dm" {
  provider         = databricks.accounts
  account_id       = var.databricks_account_id
  credentials_name = "dm-chain-explorer-credentials"
  role_arn         = data.terraform_remote_state.iam.outputs.databricks_cross_account_role_arn
}

# -----------------------------------------------------------------------
# Databricks MWS Storage Configuration
# Points Databricks to the S3 bucket for DBFS root
# -----------------------------------------------------------------------
resource "aws_s3_bucket_policy" "databricks_access" {
  bucket = data.terraform_remote_state.s3.outputs.lakehouse_bucket_name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "DatabricksRootS3Access"
        Effect = "Allow"
        Principal = {
          AWS = data.terraform_remote_state.iam.outputs.databricks_cross_account_role_arn
        }
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket",
          "s3:GetBucketLocation",
        ]
        Resource = [
          data.terraform_remote_state.s3.outputs.lakehouse_bucket_arn,
          "${data.terraform_remote_state.s3.outputs.lakehouse_bucket_arn}/*",
        ]
      }
    ]
  })
}

resource "databricks_mws_storage_configurations" "dm" {
  provider                   = databricks.accounts
  account_id                 = var.databricks_account_id
  storage_configuration_name = "dm-chain-explorer-storage"
  bucket_name                = data.terraform_remote_state.s3.outputs.lakehouse_bucket_name
}

# -----------------------------------------------------------------------
# Databricks MWS Network (VPC peering for private connectivity)
# -----------------------------------------------------------------------
resource "databricks_mws_networks" "dm" {
  provider           = databricks.accounts
  account_id         = var.databricks_account_id
  network_name       = "dm-chain-explorer-network"
  vpc_id             = data.terraform_remote_state.vpc.outputs.vpc_id
  subnet_ids         = data.terraform_remote_state.vpc.outputs.private_subnet_ids
  security_group_ids = [data.terraform_remote_state.vpc.outputs.sg_ecs_tasks_id]
}

# -----------------------------------------------------------------------
# Databricks MWS Workspace
# -----------------------------------------------------------------------
resource "databricks_mws_workspaces" "dm" {
  provider        = databricks.accounts
  account_id      = var.databricks_account_id
  workspace_name  = var.workspace_name
  aws_region      = var.region
  credentials_id  = databricks_mws_credentials.dm.credentials_id
  storage_configuration_id = databricks_mws_storage_configurations.dm.storage_configuration_id
  network_id      = databricks_mws_networks.dm.network_id

  token {
    comment = "Terraform bootstrap token"
  }
}

# -----------------------------------------------------------------------
# Unity Catalog — External Location (mounts S3 lakehouse to Unity Catalog)
# -----------------------------------------------------------------------
resource "databricks_storage_credential" "lakehouse" {
  provider = databricks.workspace
  name     = "dm-lakehouse-credential"

  aws_iam_role {
    role_arn = data.terraform_remote_state.iam.outputs.databricks_cross_account_role_arn
  }

  comment = "Storage credential for dd-chain-explorer lakehouse S3 bucket"
}

resource "databricks_external_location" "lakehouse" {
  provider        = databricks.workspace
  name            = "dm-lakehouse-location"
  url             = "s3://${data.terraform_remote_state.s3.outputs.lakehouse_bucket_name}"
  credential_name = databricks_storage_credential.lakehouse.id
  comment         = "External location for Iceberg tables (Bronze/Silver/Gold)"
}

resource "databricks_external_location" "raw" {
  provider        = databricks.workspace
  name            = "dm-raw-location"
  url             = "s3://${data.terraform_remote_state.s3.outputs.raw_bucket_name}"
  credential_name = databricks_storage_credential.lakehouse.id
  comment         = "External location for raw ingestion data"
}
