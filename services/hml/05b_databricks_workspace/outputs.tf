output "cluster_id" {
  value = var.create_cluster ? databricks_cluster.dm[0].id : null
}

output "catalog_name" {
  value = databricks_catalog.hml.name
}
