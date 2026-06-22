output "raw_bucket_arn" {
  value = module.s3_raw.bucket_arn
}
output "raw_bucket_name" {
  value = module.s3_raw.bucket_name
}
output "lakehouse_bucket_arn" {
  value = module.s3_lakehouse.bucket_arn
}
output "lakehouse_bucket_name" {
  value = module.s3_lakehouse.bucket_name
}
output "databricks_bucket_arn" {
  value = module.s3_databricks.bucket_arn
}
output "databricks_bucket_name" {
  value = module.s3_databricks.bucket_name
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
output "cloudwatch_log_group_arn" {
  value = module.cloudwatch_logs.log_group_arn
}
