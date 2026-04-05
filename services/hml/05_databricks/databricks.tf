resource "databricks_mws_credentials" "dm" {
  provider         = databricks.accounts
  account_id       = data.databricks_current_config.accounts.account_id
  credentials_name = "dm-chain-explorer-credentials-hml"
  role_arn         = data.terraform_remote_state.iam.outputs.databricks_cross_account_role_arn
}

resource "aws_s3_bucket_policy" "databricks_lakehouse_access" {
  bucket = data.terraform_remote_state.peripherals.outputs.lakehouse_bucket_name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid    = "DatabricksRootS3Access"
      Effect = "Allow"
      Principal = {
        AWS = [
          data.terraform_remote_state.iam.outputs.databricks_cross_account_role_arn,
          "arn:aws:iam::414351767826:root",
        ]
      }
      Action = [
        "s3:GetObject", "s3:GetObjectVersion", "s3:PutObject", "s3:PutObjectAcl",
        "s3:DeleteObject", "s3:DeleteObjectVersion", "s3:ListBucket",
        "s3:ListBucketVersions", "s3:GetBucketLocation", "s3:GetBucketAcl",
        "s3:GetBucketVersioning", "s3:GetEncryptionConfiguration",
        "s3:GetLifecycleConfiguration", "s3:PutLifecycleConfiguration",
      ]
      Resource = [
        data.terraform_remote_state.peripherals.outputs.lakehouse_bucket_arn,
        "${data.terraform_remote_state.peripherals.outputs.lakehouse_bucket_arn}/*",
      ]
    }]
  })
}

data "aws_iam_policy_document" "databricks_bucket_access" {
  statement {
    sid = "DatabricksControlPlaneAccess"
    actions = [
      "s3:GetObject", "s3:GetObjectVersion", "s3:PutObject", "s3:PutObjectAcl",
      "s3:DeleteObject", "s3:ListBucket", "s3:GetBucketLocation",
    ]
    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::414351767826:root"]
    }
    resources = [
      data.terraform_remote_state.peripherals.outputs.databricks_bucket_arn,
      "${data.terraform_remote_state.peripherals.outputs.databricks_bucket_arn}/*",
    ]
  }

  statement {
    sid = "DatabricksCrossAccountAccess"
    actions = [
      "s3:GetObject", "s3:GetObjectVersion", "s3:PutObject", "s3:PutObjectAcl",
      "s3:DeleteObject", "s3:ListBucket", "s3:GetBucketLocation",
      "s3:GetEncryptionConfiguration", "s3:GetLifecycleConfiguration",
    ]
    principals {
      type        = "AWS"
      identifiers = [data.terraform_remote_state.iam.outputs.databricks_cross_account_role_arn]
    }
    resources = [
      data.terraform_remote_state.peripherals.outputs.databricks_bucket_arn,
      "${data.terraform_remote_state.peripherals.outputs.databricks_bucket_arn}/*",
    ]
  }

  statement {
    sid = "DatabricksClusterAccess"
    actions = [
      "s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket",
      "s3:GetBucketLocation", "s3:GetEncryptionConfiguration",
    ]
    principals {
      type        = "AWS"
      identifiers = [data.terraform_remote_state.iam.outputs.databricks_cluster_role_arn]
    }
    resources = [
      data.terraform_remote_state.peripherals.outputs.databricks_bucket_arn,
      "${data.terraform_remote_state.peripherals.outputs.databricks_bucket_arn}/*",
    ]
  }
}

resource "aws_s3_bucket_policy" "databricks_bucket_access" {
  bucket = data.terraform_remote_state.peripherals.outputs.databricks_bucket_name
  policy = data.aws_iam_policy_document.databricks_bucket_access.json
}

resource "databricks_mws_storage_configurations" "dm" {
  provider                   = databricks.accounts
  account_id                 = data.databricks_current_config.accounts.account_id
  storage_configuration_name = "dm-chain-explorer-storage-hml"
  bucket_name                = data.terraform_remote_state.peripherals.outputs.databricks_bucket_name
}

resource "databricks_mws_networks" "dm" {
  provider           = databricks.accounts
  account_id         = data.databricks_current_config.accounts.account_id
  network_name       = "dm-chain-explorer-network-hml"
  vpc_id             = data.terraform_remote_state.vpc.outputs.vpc_id
  subnet_ids         = data.terraform_remote_state.vpc.outputs.private_subnet_ids
  security_group_ids = [data.terraform_remote_state.vpc.outputs.sg_ecs_tasks_id]
}

resource "databricks_mws_workspaces" "dm" {
  provider                 = databricks.accounts
  account_id               = data.databricks_current_config.accounts.account_id
  workspace_name           = var.workspace_name
  aws_region               = var.region
  credentials_id           = databricks_mws_credentials.dm.credentials_id
  storage_configuration_id = databricks_mws_storage_configurations.dm.storage_configuration_id
  network_id               = databricks_mws_networks.dm.network_id
  is_no_public_ip_enabled  = true

  token {
    comment = "Terraform bootstrap token"
  }
}

resource "databricks_metastore" "dm" {
  provider      = databricks.accounts
  name          = "dm-chain-explorer-metastore-hml"
  region        = var.region
  force_destroy = true
}

resource "databricks_metastore_assignment" "dm" {
  provider     = databricks.accounts
  workspace_id = databricks_mws_workspaces.dm.workspace_id
  metastore_id = databricks_metastore.dm.id
}

resource "databricks_metastore_data_access" "default" {
  provider     = databricks.accounts
  metastore_id = databricks_metastore.dm.id
  name         = "dm-metastore-data-access-hml"
  is_default   = true

  aws_iam_role {
    role_arn = data.terraform_remote_state.iam.outputs.databricks_cross_account_role_arn
  }
}

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
