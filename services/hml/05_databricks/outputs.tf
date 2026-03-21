output "workspace_url" {
  value = databricks_mws_workspaces.dm.workspace_url
}

output "workspace_id" {
  value = databricks_mws_workspaces.dm.workspace_id
}

output "cluster_id" {
  value = databricks_cluster.dm.id
}
