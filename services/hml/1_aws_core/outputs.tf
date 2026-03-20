###############################################################################
# terraform_hml/outputs.tf
#
# Os ARNs das roles são usados como GitHub Secrets nos workflows de CI/CD:
#   ECS_TASK_EXECUTION_ROLE_ARN  ← hml_ecs_task_execution_role_arn
#   ECS_TASK_ROLE_ARN            ← hml_ecs_task_role_arn
###############################################################################

output "hml_ingestion_bucket_name" {
  description = "Nome do bucket S3 de ingestão HML"
  value       = aws_s3_bucket.hml_ingestion.bucket
}

output "hml_ingestion_bucket_arn" {
  description = "ARN do bucket S3 de ingestão HML"
  value       = aws_s3_bucket.hml_ingestion.arn
}

output "hml_ecs_task_execution_role_arn" {
  description = "ARN da IAM role de execução ECS HML → usar como secret ECS_TASK_EXECUTION_ROLE_ARN"
  value       = aws_iam_role.hml_ecs_task_execution.arn
}

output "hml_ecs_task_role_arn" {
  description = "ARN da IAM task role ECS HML → usar como secret ECS_TASK_ROLE_ARN"
  value       = aws_iam_role.hml_ecs_task.arn
}

output "hml_firehose_role_arn" {
  description = "ARN da IAM role do Firehose HML → usada ao criar Firehose efêmeros em hml-provision"
  value       = aws_iam_role.hml_firehose.arn
}

output "hml_cloudwatch_log_group_name" {
  description = "Nome do CloudWatch Log Group HML → usado como CLOUDWATCH_LOG_GROUP nas ECS tasks"
  value       = module.cloudwatch_logs.log_group_name
}
