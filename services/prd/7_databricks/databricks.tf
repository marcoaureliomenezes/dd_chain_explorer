# -----------------------------------------------------------------------
# Databricks MWS Credentials
# Links the Databricks account to the AWS cross-account IAM role
# -----------------------------------------------------------------------
resource "databricks_mws_credentials" "dm" {
  provider         = databricks.accounts
  account_id       = data.databricks_current_config.accounts.account_id
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
          AWS = [
            data.terraform_remote_state.iam.outputs.databricks_cross_account_role_arn,
            "arn:aws:iam::414351767826:root",
          ]
        }
        Action = [
          "s3:GetObject",
          "s3:GetObjectVersion",
          "s3:PutObject",
          "s3:PutObjectAcl",
          "s3:DeleteObject",
          "s3:DeleteObjectVersion",
          "s3:ListBucket",
          "s3:ListBucketVersions",
          "s3:GetBucketLocation",
          "s3:GetBucketAcl",
          "s3:GetBucketVersioning",
          "s3:GetEncryptionConfiguration",
          "s3:GetLifecycleConfiguration",
          "s3:PutLifecycleConfiguration",
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
  account_id                 = data.databricks_current_config.accounts.account_id
  storage_configuration_name = "dm-chain-explorer-storage"
  bucket_name                = data.terraform_remote_state.s3.outputs.databricks_bucket_name
}

# -----------------------------------------------------------------------
# Databricks MWS Network (VPC peering for private connectivity)
# -----------------------------------------------------------------------
resource "databricks_mws_networks" "dm" {
  provider           = databricks.accounts
  account_id         = data.databricks_current_config.accounts.account_id
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
  account_id      = data.databricks_current_config.accounts.account_id
  workspace_name  = var.workspace_name
  aws_region      = var.region
  credentials_id  = databricks_mws_credentials.dm.credentials_id
  storage_configuration_id = databricks_mws_storage_configurations.dm.storage_configuration_id
  network_id      = databricks_mws_networks.dm.network_id

  is_no_public_ip_enabled = true

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

  lifecycle { prevent_destroy = true }
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

# -----------------------------------------------------------------------
# S3 bucket policy — Databricks bucket
# Grants cross-account role + cluster instance profile access
# -----------------------------------------------------------------------
data "aws_iam_policy_document" "databricks_bucket_access" {
  # Databricks AWS control-plane needs direct access for DBFS root validation
  statement {
    sid = "DatabricksControlPlaneAccess"
    actions = [
      "s3:GetObject",
      "s3:GetObjectVersion",
      "s3:PutObject",
      "s3:PutObjectAcl",
      "s3:DeleteObject",
      "s3:ListBucket",
      "s3:GetBucketLocation",
    ]
    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::414351767826:root"]
    }
    resources = [
      "arn:aws:s3:::${var.databricks_bucket_name}",
      "arn:aws:s3:::${var.databricks_bucket_name}/*",
    ]
  }

  statement {
    sid = "DatabricksCrossAccountAccess"
    actions = [
      "s3:GetObject",
      "s3:GetObjectVersion",
      "s3:PutObject",
      "s3:PutObjectAcl",
      "s3:DeleteObject",
      "s3:ListBucket",
      "s3:GetBucketLocation",
      "s3:GetEncryptionConfiguration",
      "s3:GetLifecycleConfiguration",
    ]
    principals {
      type        = "AWS"
      identifiers = [data.terraform_remote_state.iam.outputs.databricks_cross_account_role_arn]
    }
    resources = [
      "arn:aws:s3:::${var.databricks_bucket_name}",
      "arn:aws:s3:::${var.databricks_bucket_name}/*",
    ]
  }

  statement {
    sid = "DatabricksClusterAccess"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:ListBucket",
      "s3:GetBucketLocation",
      "s3:GetEncryptionConfiguration",
    ]
    principals {
      type        = "AWS"
      identifiers = [data.terraform_remote_state.iam.outputs.databricks_cluster_role_arn]
    }
    resources = [
      "arn:aws:s3:::${var.databricks_bucket_name}",
      "arn:aws:s3:::${var.databricks_bucket_name}/*",
    ]
  }
}

resource "aws_s3_bucket_policy" "databricks_bucket" {
  bucket = var.databricks_bucket_name
  policy = data.aws_iam_policy_document.databricks_bucket_access.json
}

# -----------------------------------------------------------------------
# Unity Catalog — Metastore (account-level)
# -----------------------------------------------------------------------
resource "databricks_metastore" "dm" {
  provider      = databricks.accounts
  name          = "dm-chain-explorer-metastore"
  # storage_root removido: usamos external tables com paths S3 explícitos.
  # External locations (lakehouse, raw) fornecem acesso aos buckets.
  region        = var.region
  force_destroy = false

  lifecycle { prevent_destroy = true }
}

resource "databricks_metastore_assignment" "dm" {
  provider     = databricks.accounts
  workspace_id = databricks_mws_workspaces.dm.workspace_id
  metastore_id = databricks_metastore.dm.id
}

# Default data-access config for the metastore (uses cross-account role)
resource "databricks_metastore_data_access" "default" {
  provider     = databricks.accounts
  metastore_id = databricks_metastore.dm.id
  name         = "dm-metastore-data-access"
  is_default   = true

  aws_iam_role {
    role_arn = data.terraform_remote_state.iam.outputs.databricks_cross_account_role_arn
  }
}

# -----------------------------------------------------------------------
# Unity Catalog — External location for Databricks bucket (workspace-level)
# -----------------------------------------------------------------------
resource "databricks_external_location" "databricks" {
  provider        = databricks.workspace
  name            = "dm-databricks-location"
  url             = "s3://${var.databricks_bucket_name}"
  credential_name = databricks_storage_credential.lakehouse.id
  comment         = "External location for Databricks checkpoints, staging and Unity Catalog"

  depends_on = [databricks_metastore_assignment.dm]
}

# -----------------------------------------------------------------------
# Unity Catalog — prd catalog (workspace-level)
# -----------------------------------------------------------------------
resource "databricks_catalog" "prd" {
  provider     = databricks.workspace
  name         = "prd"
  comment      = "Production Unity Catalog"
  storage_root = "s3://${data.terraform_remote_state.s3.outputs.databricks_bucket_name}/unity-catalog/prd"

  depends_on = [databricks_metastore_assignment.dm]

  lifecycle { prevent_destroy = true }
}

# -----------------------------------------------------------------------
# Workspace admin user (account-level, identity federation)
# -----------------------------------------------------------------------
data "databricks_user" "admin" {
  provider  = databricks.accounts
  user_name = var.workspace_admin_email
}

resource "databricks_mws_permission_assignment" "admin" {
  provider     = databricks.accounts
  workspace_id = databricks_mws_workspaces.dm.workspace_id
  principal_id = data.databricks_user.admin.id
  permissions  = ["ADMIN"]
}

# -----------------------------------------------------------------------
# Databricks Instance Profile — registers cluster EC2 role with Databricks
# -----------------------------------------------------------------------
resource "databricks_instance_profile" "cluster" {
  provider             = databricks.workspace
  instance_profile_arn = data.terraform_remote_state.iam.outputs.databricks_cluster_instance_profile_arn

  depends_on = [databricks_metastore_assignment.dm]
}

# -----------------------------------------------------------------------
# Databricks Cluster — minimal (1 worker + 1 driver, auto-terminate 60 min)
# -----------------------------------------------------------------------
data "databricks_spark_version" "latest_lts" {
  provider          = databricks.workspace
  long_term_support = true
}

data "databricks_node_type" "smallest" {
  provider      = databricks.workspace
  min_memory_gb = 4
}

resource "databricks_cluster" "dm" {
  provider                = databricks.workspace
  cluster_name            = "dm-chain-explorer-cluster"
  spark_version           = data.databricks_spark_version.latest_lts.id
  node_type_id            = data.databricks_node_type.smallest.id
  num_workers             = 1
  autotermination_minutes = 60

  aws_attributes {
    instance_profile_arn   = databricks_instance_profile.cluster.id
    availability           = "SPOT_WITH_FALLBACK"
    zone_id                = "auto"
    ebs_volume_type        = "GENERAL_PURPOSE_SSD"
    ebs_volume_count       = 1
    ebs_volume_size        = 32
    first_on_demand        = 1
  }

  spark_conf = {
    "spark.databricks.delta.preview.enabled" = "true"
  }

  custom_tags = {
    "owner"       = "marco-menezes"
    "cost-center" = "dd-chain-explorer"
    "environment" = var.environment
    "project"     = "dd-chain-explorer"
    "managed-by"  = "terraform"
  }

  depends_on = [databricks_metastore_assignment.dm]
}
