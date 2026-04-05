output "workspace_url" {
  value = databricks_mws_workspaces.dm.workspace_url
}

output "workspace_id" {
  value = databricks_mws_workspaces.dm.workspace_id
}

output "token_value" {
  value     = databricks_mws_workspaces.dm.token[0].token_value
  sensitive = true
}
