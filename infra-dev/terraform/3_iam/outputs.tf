###############################################################################
# terraform_dev/3_iam/outputs.tf
###############################################################################

output "databricks_s3_role_arn" {
  description = "ARN da IAM role que o Databricks usa para acessar o S3 DEV"
  value       = aws_iam_role.databricks_s3.arn
}

output "databricks_s3_role_name" {
  description = "Nome da IAM role"
  value       = aws_iam_role.databricks_s3.name
}
