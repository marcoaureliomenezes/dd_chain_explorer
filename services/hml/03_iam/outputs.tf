output "ecs_task_execution_role_arn" {
  value = module.iam.ecs_task_execution_role_arn
}

output "ecs_task_role_arn" {
  value = module.iam.ecs_task_role_arn
}

output "firehose_role_arn" {
  value = aws_iam_role.firehose.arn
}

output "databricks_cross_account_role_arn" {
  value = module.iam.databricks_cross_account_role_arn
}

output "databricks_cluster_instance_profile_arn" {
  value = module.iam.databricks_cluster_instance_profile_arn
}
