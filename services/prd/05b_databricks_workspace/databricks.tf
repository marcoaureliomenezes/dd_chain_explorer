# -----------------------------------------------------------------------
# Unity Catalog — Storage Credential (workspace-level)
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

# -----------------------------------------------------------------------
# Unity Catalog — External Locations (workspace-level)
# -----------------------------------------------------------------------
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

resource "databricks_external_location" "databricks" {
  provider        = databricks.workspace
  name            = "dm-databricks-location"
  url             = "s3://${var.databricks_bucket_name}"
  credential_name = databricks_storage_credential.lakehouse.id
  comment         = "External location for Databricks checkpoints, staging and Unity Catalog"

  depends_on = [databricks_storage_credential.lakehouse]
}

# -----------------------------------------------------------------------
# Unity Catalog — prd catalog (workspace-level)
# -----------------------------------------------------------------------
resource "databricks_catalog" "prd" {
  provider     = databricks.workspace
  name         = "prd"
  comment      = "Production Unity Catalog"
  storage_root = "s3://${data.terraform_remote_state.s3.outputs.databricks_bucket_name}/unity-catalog/prd"

  lifecycle { prevent_destroy = true }
}

# -----------------------------------------------------------------------
# Databricks Instance Profile (workspace-level)
# -----------------------------------------------------------------------
resource "databricks_instance_profile" "cluster" {
  provider             = databricks.workspace
  instance_profile_arn = data.terraform_remote_state.iam.outputs.databricks_cluster_instance_profile_arn
}

# -----------------------------------------------------------------------
# Databricks Cluster (workspace-level)
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
}
