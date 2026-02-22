###############################################################################
# terraform/8_elasticache/outputs.tf
###############################################################################

output "redis_primary_endpoint" {
  description = "Endpoint primário do ElastiCache Redis (usar em REDIS_HOST)"
  value       = aws_elasticache_replication_group.redis.primary_endpoint_address
}

output "redis_port" {
  description = "Porta do ElastiCache Redis (6380 = TLS)"
  value       = aws_elasticache_replication_group.redis.port
}

output "redis_security_group_id" {
  description = "ID do Security Group do Redis"
  value       = aws_security_group.redis.id
}
