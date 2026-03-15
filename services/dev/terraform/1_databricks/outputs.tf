###############################################################################
# terraform_dev/1_databricks/outputs.tf
###############################################################################

output "storage_credential_id" {
  description = "ID da storage credential no Databricks"
  value       = databricks_storage_credential.dev_s3.id
}

output "external_location_url" {
  description = "URL da external location no Databricks"
  value       = databricks_external_location.dev_ingestion.url
}

output "external_location_name" {
  description = "Nome da external location no Databricks"
  value       = databricks_external_location.dev_ingestion.name
}
