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
output "kinesis_stream_names" {
  value = module.kinesis.stream_names
}
output "kinesis_stream_arns" {
  value = module.kinesis.stream_arns
}
output "firehose_direct_put_stream_names" {
  value = module.kinesis.firehose_direct_put_stream_names
}
output "sqs_queue_urls" {
  value = module.sqs.queue_urls
}
output "sqs_queue_arns" {
  value = module.sqs.queue_arns
}
output "cloudwatch_log_group_name" {
  value = module.cloudwatch_logs.log_group_name
}
