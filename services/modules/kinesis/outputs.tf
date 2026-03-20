###############################################################################
# modules/kinesis/outputs.tf
###############################################################################

output "stream_arns" {
  description = "Map of stream logical name → ARN"
  value       = { for k, v in aws_kinesis_stream.this : k => v.arn }
}

output "stream_names" {
  description = "Map of stream logical name → full stream name (includes environment suffix)"
  value       = { for k, v in aws_kinesis_stream.this : k => v.name }
}

output "firehose_arns" {
  description = "Map of stream logical name → Firehose delivery stream ARN"
  value       = { for k, v in aws_kinesis_firehose_delivery_stream.this : k => v.arn }
}

output "firehose_role_arn" {
  description = "ARN of the IAM role used by Firehose (empty if externally provided)"
  value       = local.create_firehose_role ? aws_iam_role.firehose[0].arn : var.firehose_role_arn
}
