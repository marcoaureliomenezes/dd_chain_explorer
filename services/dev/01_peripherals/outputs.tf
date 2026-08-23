output "ingestion_bucket_arn" {
  value = module.s3_ingestion.bucket_arn
}
output "ingestion_bucket_name" {
  value = module.s3_ingestion.bucket_name
}
output "dynamodb_table_name" {
  value = module.dynamodb.table_name
}
output "dynamodb_table_arn" {
  value = module.dynamodb.table_arn
}
output "cloudwatch_log_group_name" {
  value = module.cloudwatch_logs.log_group_name
}
output "databricks_dev_s3_role_arn" {
  value = aws_iam_role.databricks_dev_s3_role.arn
}
