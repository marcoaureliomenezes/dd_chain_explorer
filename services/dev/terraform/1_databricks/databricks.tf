###############################################################################
# terraform_dev/1_databricks/databricks.tf
#
# Storage Credential + External Location no Unity Catalog Databricks.
#
# Fluxo:
#   1. storage_credential: registra a IAM role no Databricks como credencial
#   2. external_location: mapeia s3://bucket/ → credencial → Unity Catalog
#   3. Grants: permite que o catálogo DEV use esta external location
###############################################################################

# ── Storage Credential ────────────────────────────────────────────────────────

resource "databricks_storage_credential" "dev_s3" {
  name    = "dm-dev-s3-credential"
  comment = "Credencial para acesso ao bucket S3 de ingestão DEV via IAM role"

  aws_iam_role {
    role_arn = var.iam_role_arn
  }
}

# ── External Location ─────────────────────────────────────────────────────────

resource "databricks_external_location" "dev_ingestion" {
  name            = "dm-dev-ingestion"
  url             = "s3://${var.bucket_name}"
  credential_name = databricks_storage_credential.dev_s3.id
  comment         = "External location para ingestão DEV — Spark writes Parquet aqui, DLT lê"

  depends_on = [databricks_storage_credential.dev_s3]
}

# ── Grants ────────────────────────────────────────────────────────────────────

# Permissão para o catálogo DEV ler/escrever via esta external location
resource "databricks_grants" "dev_ingestion_location" {
  external_location = databricks_external_location.dev_ingestion.id

  grant {
    principal  = "account users"
    privileges = ["READ_FILES", "WRITE_FILES", "CREATE_EXTERNAL_TABLE"]
  }

  depends_on = [databricks_external_location.dev_ingestion]
}
