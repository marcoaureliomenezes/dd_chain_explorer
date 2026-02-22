output "api_key_consumption_table_name" {
  value = aws_dynamodb_table.api_key_consumption.name
}

output "api_key_semaphore_table_name" {
  value = aws_dynamodb_table.api_key_semaphore.name
}

output "popular_contracts_table_name" {
  value = aws_dynamodb_table.popular_contracts.name
}
