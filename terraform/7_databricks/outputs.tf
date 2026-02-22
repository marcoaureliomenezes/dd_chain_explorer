output "databricks_workspace_url" {
  value = databricks_mws_workspaces.dm.workspace_url
}

output "databricks_workspace_id" {
  value = databricks_mws_workspaces.dm.workspace_id
}

output "databricks_token" {
  value     = databricks_mws_workspaces.dm.token[0].token_value
  sensitive = true
}
