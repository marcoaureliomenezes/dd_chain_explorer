###############################################################################
# modules/cloudwatch_logs/outputs.tf
###############################################################################

output "log_group_name" {
  description = "Full name of the CloudWatch Log Group"
  value       = aws_cloudwatch_log_group.this.name
}

output "log_group_arn" {
  description = "ARN of the CloudWatch Log Group"
  value       = aws_cloudwatch_log_group.this.arn
}
