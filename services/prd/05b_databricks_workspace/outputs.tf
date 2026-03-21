output "databricks_cluster_id" {
  value = databricks_cluster.dm.id
}

output "databricks_catalog_prd" {
  value = databricks_catalog.prd.name
}
