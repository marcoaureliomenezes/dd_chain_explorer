resource "databricks_storage_credential" "lakehouse" {
  provider = databricks.workspace
  name     = "dm-lakehouse-credential-hml"

  aws_iam_role {
    role_arn = data.terraform_remote_state.iam.outputs.databricks_cross_account_role_arn
  }

  comment = "Storage credential for dd-chain-explorer HML lakehouse S3 bucket"
}

resource "databricks_external_location" "lakehouse" {
  provider        = databricks.workspace
  name            = "dm-lakehouse-location-hml"
  url             = "s3://${data.terraform_remote_state.peripherals.outputs.lakehouse_bucket_name}"
  credential_name = databricks_storage_credential.lakehouse.id
  comment         = "External location for HML Iceberg tables (Bronze/Silver/Gold)"
}

resource "databricks_external_location" "raw" {
  provider        = databricks.workspace
  name            = "dm-raw-location-hml"
  url             = "s3://${data.terraform_remote_state.peripherals.outputs.raw_bucket_name}"
  credential_name = databricks_storage_credential.lakehouse.id
  comment         = "External location for HML raw ingestion data"
}

# NOTE: No external location for the databricks/workspace bucket — it overlaps
# with the DBFS/workspace root. Catalog storage is managed via metastore data access.

resource "databricks_catalog" "hml" {
  provider     = databricks.workspace
  name         = "hml"
  comment      = "HML Unity Catalog"
  storage_root = "s3://${data.terraform_remote_state.peripherals.outputs.databricks_bucket_name}/unity-catalog/hml"
}

# Instance profile and cluster are only needed when create_cluster = true.
# Registering the instance profile requires ec2:RunInstances on the cross-account role
# which is very broad; skip for the ephemeral HML environment.

data "databricks_spark_version" "latest_lts" {
  count             = var.create_cluster ? 1 : 0
  provider          = databricks.workspace
  long_term_support = true
}

data "databricks_node_type" "smallest" {
  count         = var.create_cluster ? 1 : 0
  provider      = databricks.workspace
  min_memory_gb = 4
}

resource "databricks_cluster" "dm" {
  count                   = var.create_cluster ? 1 : 0
  provider                = databricks.workspace
  cluster_name            = "dm-chain-explorer-cluster-hml"
  spark_version           = data.databricks_spark_version.latest_lts[0].id
  node_type_id            = data.databricks_node_type.smallest[0].id
  num_workers             = 1
  autotermination_minutes = 30

  aws_attributes {
    availability         = "SPOT_WITH_FALLBACK"
    zone_id              = "auto"
    ebs_volume_type      = "GENERAL_PURPOSE_SSD"
    ebs_volume_count     = 1
    ebs_volume_size      = 32
    first_on_demand      = 1
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
}
