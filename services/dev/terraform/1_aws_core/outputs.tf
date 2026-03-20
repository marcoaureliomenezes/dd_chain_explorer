###############################################################################
# terraform_dev/outputs.tf
###############################################################################

output "ingestion_bucket_name" {
  description = "Nome do bucket S3 de ingestão DEV"
  value       = aws_s3_bucket.ingestion.bucket
}

output "ingestion_bucket_arn" {
  description = "ARN do bucket S3 de ingestão DEV"
  value       = aws_s3_bucket.ingestion.arn
}

output "dynamodb_table_name" {
  description = "Nome da tabela DynamoDB DEV"
  value       = aws_dynamodb_table.chain_explorer.name
}

output "dynamodb_table_arn" {
  description = "ARN da tabela DynamoDB DEV"
  value       = aws_dynamodb_table.chain_explorer.arn
}
