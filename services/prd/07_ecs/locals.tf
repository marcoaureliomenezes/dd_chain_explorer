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

    "version"     = var.version
  }

  # Variáveis de ambiente comuns a todos os jobs de streaming.
  # Os nomes devem corresponder exatamente ao os.getenv() nos scripts Python.
  # Pós-migração Kafka → Kinesis/SQS/CloudWatch (ver docs/migrar_kafka.md).
  common_stream_env = [
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
      name  = "DYNAMODB_TABLE"
      value = data.terraform_remote_state.dynamodb.outputs.dynamodb_table_name
    },
    # --- Kinesis Data Streams ---
    {
      name  = "KINESIS_STREAM_BLOCKS"
      value = data.terraform_remote_state.kinesis_sqs.outputs.kinesis_stream_names["mainnet-blocks-data"]
    },
    {
      name  = "KINESIS_STREAM_TRANSACTIONS"
      value = data.terraform_remote_state.kinesis_sqs.outputs.kinesis_stream_names["mainnet-transactions-data"]
    },
    {
      name  = "KINESIS_STREAM_DECODED"
      value = data.terraform_remote_state.kinesis_sqs.outputs.kinesis_stream_names["mainnet-transactions-decoded"]
    },
    # --- SQS Queues ---
    {
      name  = "SQS_QUEUE_URL_MINED_BLOCKS"
      value = data.terraform_remote_state.kinesis_sqs.outputs.sqs_queue_urls["mainnet-mined-blocks-events"]
    },
    {
      name  = "SQS_QUEUE_URL_TXS_HASH_IDS"
      value = data.terraform_remote_state.kinesis_sqs.outputs.sqs_queue_urls["mainnet-block-txs-hash-id"]
    },
    # --- CloudWatch Logs ---
    {
      name  = "CLOUDWATCH_LOG_GROUP"
      value = data.terraform_remote_state.kinesis_sqs.outputs.cloudwatch_log_group_name
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
