output "databricks_cluster_id" {
  value = var.create_cluster ? databricks_cluster.dm[0].id : null
}

output "databricks_catalog_prd" {
  value = databricks_catalog.prd.name
}
