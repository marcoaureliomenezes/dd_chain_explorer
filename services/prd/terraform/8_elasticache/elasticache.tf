###############################################################################
# terraform/8_elasticache/elasticache.tf
#
# ElastiCache Redis — substitui Redis local em PROD.
#
# Decisões de arquitetura:
#   - Cluster mode DESABILITADO: permite múltiplos databases (db=0..15) — mantendo
#     a mesma convenção dos scripts Python (db=0 semáforo, db=1 contador, db=2 cache)
#   - TLS em trânsito (transit_encryption_enabled = true)
#   - Auth token opcional — recomendado em PROD
#   - Single-node (num_cache_clusters=1) adequado para o volume de dados atual
#     (cache de hashes de blocos + semáforo de API keys)
#
# NOTA: Security Group definido em 1_vpc/network.tf (aws_security_group.elasticache).
#       Referenciado via remote state: data.terraform_remote_state.vpc.outputs.sg_elasticache_id
###############################################################################

# ----- Subnet Group ---------------------------------------------------------

resource "aws_elasticache_subnet_group" "redis" {
  name       = "${local.name_prefix}-redis-subnet-group"
  subnet_ids = data.terraform_remote_state.vpc.outputs.private_subnet_ids
  tags       = local.common_tags
}

# ----- Parameter Group (Redis 7 sem cluster mode) ---------------------------

resource "aws_elasticache_parameter_group" "redis" {
  name   = "${local.name_prefix}-redis7-params"
  family = "redis7"
  tags   = local.common_tags

  # Habilita keyspace notifications para expiração de chaves (útil para TTL do semáforo)
  parameter {
    name  = "notify-keyspace-events"
    value = "Ex"
  }
}

# ----- Replication Group (single-node, cluster mode off) --------------------

resource "aws_elasticache_replication_group" "redis" {
  replication_group_id = "${local.name_prefix}-redis"
  description          = "Redis para cache de blocos e semaforo de API keys - ${var.environment}"

  node_type      = var.node_type
  engine_version = var.redis_version
  port           = 6380 # TLS port

  # Single-node: 1 nó primário, sem réplicas (pode escalar depois)
  num_cache_clusters         = 1
  multi_az_enabled           = false
  automatic_failover_enabled = false

  subnet_group_name    = aws_elasticache_subnet_group.redis.name
  security_group_ids   = [data.terraform_remote_state.vpc.outputs.sg_elasticache_id]
  parameter_group_name = aws_elasticache_parameter_group.redis.name

  # Segurança
  transit_encryption_enabled = true
  auth_token                 = var.auth_token # null = sem auth token (não recomendado em PROD real)
  at_rest_encryption_enabled = true

  # Manutenção
  maintenance_window       = "sun:03:00-sun:04:00"
  snapshot_retention_limit = 1
  snapshot_window          = "02:00-03:00"

  apply_immediately = true

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-redis" })
}
