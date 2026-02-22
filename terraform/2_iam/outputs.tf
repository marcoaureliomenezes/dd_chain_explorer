output "ecs_task_execution_role_arn" {
  value = aws_iam_role.ecs_task_execution.arn
}

output "ecs_task_role_arn" {
  value = aws_iam_role.ecs_task.arn
}

output "databricks_cross_account_role_arn" {
  value = aws_iam_role.databricks_cross_account.arn
}
