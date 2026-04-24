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
output "kinesis_stream_names" {
  value = module.kinesis.stream_names
}
output "kinesis_stream_arns" {
  value = module.kinesis.stream_arns
}
output "firehose_arns" {
  value = module.kinesis.firehose_arns
}
output "sqs_queue_urls" {
  value = module.sqs.queue_urls
}
output "sqs_queue_arns" {
  value = module.sqs.queue_arns
}
output "sqs_dlq_arns" {
  value = module.sqs.dlq_arns
}
