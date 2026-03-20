###############################################################################
# modules/sqs/outputs.tf
###############################################################################

output "queue_urls" {
  description = "Map of queue logical name → SQS queue URL"
  value       = { for k, v in aws_sqs_queue.this : k => v.url }
}

output "queue_arns" {
  description = "Map of queue logical name → SQS queue ARN"
  value       = { for k, v in aws_sqs_queue.this : k => v.arn }
}

output "dlq_urls" {
  description = "Map of queue logical name → DLQ URL (only for queues with dlq_enabled)"
  value       = { for k, v in aws_sqs_queue.dlq : k => v.url }
}

output "dlq_arns" {
  description = "Map of queue logical name → DLQ ARN"
  value       = { for k, v in aws_sqs_queue.dlq : k => v.arn }
}
