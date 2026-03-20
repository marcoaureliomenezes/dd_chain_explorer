###############################################################################
# terraform/9_dynamodb/outputs.tf
###############################################################################

output "dynamodb_table_name" {
  description = "Nome da tabela DynamoDB"
  value       = aws_dynamodb_table.chain_explorer.name
}

output "dynamodb_table_arn" {
  description = "ARN da tabela DynamoDB"
  value       = aws_dynamodb_table.chain_explorer.arn
}
