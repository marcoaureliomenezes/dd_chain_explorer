###############################################################################
# prd/3_kinesis_sqs/outputs.tf
#
# Outputs consumed by 6_ecs (via terraform_remote_state) and GitHub Actions.
###############################################################################

# ---------------------------------------------------------------------------
# Kinesis
# ---------------------------------------------------------------------------

output "kinesis_stream_names" {
  description = "Map of Kinesis stream logical name → full stream name"
  value       = module.kinesis.stream_names
}

output "kinesis_stream_arns" {
  description = "Map of Kinesis stream logical name → ARN"
  value       = module.kinesis.stream_arns
}

output "firehose_arns" {
  description = "Map of Kinesis stream logical name → Firehose delivery stream ARN"
  value       = module.kinesis.firehose_arns
}

# ---------------------------------------------------------------------------
# SQS
# ---------------------------------------------------------------------------

output "sqs_queue_urls" {
  description = "Map of SQS queue logical name → queue URL"
  value       = module.sqs.queue_urls
}

output "sqs_queue_arns" {
  description = "Map of SQS queue logical name → ARN"
  value       = module.sqs.queue_arns
}

output "sqs_dlq_arns" {
  description = "Map of SQS queue logical name → DLQ ARN"
  value       = module.sqs.dlq_arns
}

# ---------------------------------------------------------------------------
# CloudWatch Logs
# ---------------------------------------------------------------------------

output "cloudwatch_log_group_name" {
  description = "CloudWatch Log Group name for application logs"
  value       = module.cloudwatch_logs.log_group_name
}

output "cloudwatch_log_group_arn" {
  description = "CloudWatch Log Group ARN"
  value       = module.cloudwatch_logs.log_group_arn
}
