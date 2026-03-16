data "aws_caller_identity" "current" {}

locals {
  ecr_base        = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.region}.amazonaws.com"
  ecr_image_stream = "${local.ecr_base}/onchain-stream-txs:${var.docker_image_stream}"
  ecr_image_batch  = "${local.ecr_base}/onchain-batch-txs:${var.docker_image_batch}"

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
      value = data.terraform_remote_state.msk.outputs.msk_bootstrap_brokers_sasl_iam  # SASL/IAM (port 9098)
    },
    {
      name  = "KAFKA_MSK_IAM"
      value = "true"          # TODO-A05: habilita get_msk_iam_config() nos jobs Python
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
      name  = "DYNAMODB_TABLE"
      value = data.terraform_remote_state.dynamodb.outputs.dynamodb_table_name
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
