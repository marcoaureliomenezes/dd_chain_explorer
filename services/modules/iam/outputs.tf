output "ecs_task_execution_role_arn" {
  value = var.create_ecs_roles ? aws_iam_role.ecs_task_execution[0].arn : null
}

output "ecs_task_execution_role_name" {
  value = var.create_ecs_roles ? aws_iam_role.ecs_task_execution[0].name : null
}

output "ecs_task_role_arn" {
  value = var.create_ecs_roles ? aws_iam_role.ecs_task[0].arn : null
}

output "ecs_task_role_name" {
  value = var.create_ecs_roles ? aws_iam_role.ecs_task[0].name : null
}

output "databricks_cross_account_role_arn" {
  value = var.create_databricks_roles ? aws_iam_role.databricks_cross_account[0].arn : null
}

output "databricks_cluster_role_arn" {
  value = var.create_databricks_roles ? aws_iam_role.databricks_cluster[0].arn : null
}

output "databricks_cluster_instance_profile_arn" {
  value = var.create_databricks_roles ? aws_iam_instance_profile.databricks_cluster[0].arn : null
}

output "lambda_role_arn" {
  value = var.create_lambda_role ? aws_iam_role.lambda[0].arn : null
}
