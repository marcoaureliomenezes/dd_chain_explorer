locals {
  common_tags = {
    "owner"       = "marco-menezes"
    "managed-by"  = "terraform"
    "cost-center" = "dd-chain-explorer"
    "environment" = var.environment
    "project"     = "dd-chain-explorer"
  }

  # Variáveis de ambiente comuns a todos os jobs de streaming.
  # Os nomes devem corresponder exatamente ao os.getenv() nos scripts Python.
  common_stream_env = [
    {
      name  = "KAFKA_BROKERS"
      value = data.terraform_remote_state.msk.outputs.msk_bootstrap_brokers
    },
    {
      name  = "NETWORK"
      value = "mainnet"
    },
    {
      name  = "APP_ENV"
      value = "prod"
    },
    {
      name  = "AWS_DEFAULT_REGION"
      value = var.region
    },
    {
      name  = "SCHEMA_REGISTRY_URL"   # Confluent SR rodando no ECS, acessível via Cloud Map DNS
      value = "http://dm-schema-registry.dm-chain-explorer.local:8081"
    },
    {
      name  = "REDIS_HOST"
      value = data.terraform_remote_state.elasticache.outputs.redis_primary_endpoint
    },
    {
      name  = "REDIS_PORT"
      value = tostring(data.terraform_remote_state.elasticache.outputs.redis_port)
    },
    {
      name  = "REDIS_DB_APK_SEMAPHORE"
      value = "0"
    },
    {
      name  = "REDIS_DB_APK_COUNTER"
      value = "1"
    },
    {
      name  = "REDIS_DB_BLOCK_CACHE"
      value = "2"
    },
    {
      name  = "REDIS_DB_SEMAPHORE_DISPLAY"
      value = "3"
    },
  ]

  log_config = {
    logDriver = "awslogs"
    options = {
      awslogs-group         = aws_cloudwatch_log_group.ecs_apps.name
      awslogs-region        = var.region
      awslogs-stream-prefix = "ecs"
    }
  }
}
