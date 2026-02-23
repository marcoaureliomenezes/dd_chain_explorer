# -----------------------------------------------------------------------
# ECS Cluster
# -----------------------------------------------------------------------
resource "aws_ecs_cluster" "dm" {
  name = "dm-chain-explorer-ecs"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = local.common_tags
}

resource "aws_ecs_cluster_capacity_providers" "dm" {
  cluster_name       = aws_ecs_cluster.dm.name
  capacity_providers = ["FARGATE", "FARGATE_SPOT"]

  default_capacity_provider_strategy {
    capacity_provider = "FARGATE_SPOT"
    weight            = 1
  }
}

# -----------------------------------------------------------------------
# CloudWatch Log Group for ECS tasks
# -----------------------------------------------------------------------
resource "aws_cloudwatch_log_group" "ecs_apps" {
  name              = "/ecs/dm-chain-explorer"
  retention_in_days = 7
  tags              = local.common_tags
}

# -----------------------------------------------------------------------
# AWS Cloud Map — private DNS namespace for inter-service discovery
# -----------------------------------------------------------------------
resource "aws_service_discovery_private_dns_namespace" "dm" {
  name        = "dm-chain-explorer.local"
  description = "Private DNS for ECS service discovery"
  vpc         = data.terraform_remote_state.vpc.outputs.vpc_id
  tags        = local.common_tags
}

resource "aws_service_discovery_service" "schema_registry" {
  name = "dm-schema-registry"

  dns_config {
    namespace_id = aws_service_discovery_private_dns_namespace.dm.id

    dns_records {
      type = "A"
      ttl  = 10
    }

    routing_policy = "MULTIVALUE"
  }

  health_check_custom_config {
    failure_threshold = 1
  }
}

# -----------------------------------------------------------------------
# Configuração de rede compartilhada
# ECS tasks ficam na subnet pública com IP público — sem NAT Gateway
# -----------------------------------------------------------------------
locals {
  ecs_network_config = {
    subnets          = [data.terraform_remote_state.vpc.outputs.public_subnet_id]
    security_groups  = [data.terraform_remote_state.vpc.outputs.sg_ecs_tasks_id]
    assign_public_ip = true
  }
}

# -----------------------------------------------------------------------
# Task Definitions — Python Streaming Apps
# -----------------------------------------------------------------------

# Job 1 — Mined Blocks Watcher
resource "aws_ecs_task_definition" "mined_blocks_watcher" {
  family                   = "dm-mined-blocks-watcher"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = data.terraform_remote_state.iam.outputs.ecs_task_execution_role_arn
  task_role_arn            = data.terraform_remote_state.iam.outputs.ecs_task_role_arn

  container_definitions = jsonencode([{
    name      = "mined-blocks-watcher"
    image     = var.docker_image_stream
    essential = true
    command = [
      "python", "-u", "/app/1_mined_blocks_watcher.py",
      "/app/configs/producers.ini"
    ]
    environment = concat(local.common_stream_env, [
      { name = "TOPIC_LOGS",                value = "mainnet.0.application.logs" },
      { name = "TOPIC_MINED_BLOCKS_EVENTS", value = "mainnet.1.mined_blocks.events" },
      { name = "CLOCK_FREQUENCY",           value = "1" },
      { name = "AKV_SECRET_NAME",           value = "/web3-api-keys/alchemy/api-key-1" },
    ])
    logConfiguration = local.log_config
  }])

  tags = local.common_tags
}

# Job 2 — Orphan Blocks Watcher
resource "aws_ecs_task_definition" "orphan_blocks_watcher" {
  family                   = "dm-orphan-blocks-watcher"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = data.terraform_remote_state.iam.outputs.ecs_task_execution_role_arn
  task_role_arn            = data.terraform_remote_state.iam.outputs.ecs_task_role_arn

  container_definitions = jsonencode([{
    name      = "orphan-blocks-watcher"
    image     = var.docker_image_stream
    essential = true
    command = [
      "python", "-u", "/app/2_orphan_blocks_watcher.py",
      "/app/configs/producers.ini", "/app/configs/consumers.ini"
    ]
    environment = concat(local.common_stream_env, [
      { name = "TOPIC_LOGS",                value = "mainnet.0.application.logs" },
      { name = "TOPIC_MINED_BLOCKS_EVENTS", value = "mainnet.1.mined_blocks.events" },
      { name = "CONSUMER_GROUP_ID",         value = "cg_orphan_block_events" },
      { name = "NUM_CONFIRMATIONS",         value = "10" },
      { name = "AKV_SECRET_NAME",           value = "/web3-api-keys/alchemy/api-key-2" },
    ])
    logConfiguration = local.log_config
  }])

  tags = local.common_tags
}

# Job 3 — Block Data Crawler
resource "aws_ecs_task_definition" "block_data_crawler" {
  family                   = "dm-block-data-crawler"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = data.terraform_remote_state.iam.outputs.ecs_task_execution_role_arn
  task_role_arn            = data.terraform_remote_state.iam.outputs.ecs_task_role_arn

  container_definitions = jsonencode([{
    name      = "block-data-crawler"
    image     = var.docker_image_stream
    essential = true
    command = [
      "python", "-u", "/app/3_block_data_crawler.py",
      "/app/configs/producers.ini", "/app/configs/consumers.ini"
    ]
    environment = concat(local.common_stream_env, [
      { name = "TOPIC_LOGS",                    value = "mainnet.0.application.logs" },
      { name = "TOPIC_MINED_BLOCKS_EVENTS",     value = "mainnet.1.mined_blocks.events" },
      { name = "TOPIC_MINED_BLOCKS",            value = "mainnet.2.blocks.data" },
      { name = "TOPIC_TXS_HASH_IDS",            value = "mainnet.3.block.txs.hash_id" },
      { name = "TOPIC_TXS_HASH_IDS_PARTITIONS", value = "8" },
      { name = "CONSUMER_GROUP",                value = "cg_block_data_crawler" },
      { name = "TXS_PER_BLOCK",                 value = "50" },
      { name = "AKV_SECRET_NAME",               value = "/web3-api-keys/alchemy/api-key-2" },
    ])
    logConfiguration = local.log_config
  }])

  tags = local.common_tags
}

# Job 4 — Raw Transactions Crawler (múltiplas réplicas)
resource "aws_ecs_task_definition" "mined_txs_crawler" {
  family                   = "dm-mined-txs-crawler"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = data.terraform_remote_state.iam.outputs.ecs_task_execution_role_arn
  task_role_arn            = data.terraform_remote_state.iam.outputs.ecs_task_role_arn

  container_definitions = jsonencode([{
    name      = "mined-txs-crawler"
    image     = var.docker_image_stream
    essential = true
    command = [
      "python", "-u", "/app/4_mined_txs_crawler.py",
      "/app/configs/producers.ini", "/app/configs/consumers.ini"
    ]
    environment = concat(local.common_stream_env, [
      { name = "TOPIC_LOGS",        value = "mainnet.0.application.logs" },
      { name = "TOPIC_TXS_HASH_IDS", value = "mainnet.3.block.txs.hash_id" },
      { name = "TOPIC_TXS_DATA",    value = "mainnet.4.transactions.data" },
      { name = "CONSUMER_GROUP",    value = "cg_mined_raw_txs" },
      # Notação compacta: expande para /web3-api-keys/infura/api-key-1 .. api-key-17
      { name = "AKV_SECRET_NAMES",  value = "/web3-api-keys/infura/api-key-1-17" },
    ])
    logConfiguration = local.log_config
  }])

  tags = local.common_tags
}

# Job 5 — Transaction Input Decoder
resource "aws_ecs_task_definition" "txs_input_decoder" {
  family                   = "dm-txs-input-decoder"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = data.terraform_remote_state.iam.outputs.ecs_task_execution_role_arn
  task_role_arn            = data.terraform_remote_state.iam.outputs.ecs_task_role_arn

  container_definitions = jsonencode([{
    name      = "txs-input-decoder"
    image     = var.docker_image_stream
    essential = true
    command = [
      "python", "-u", "/app/5_txs_input_decoder.py",
      "/app/configs/producers.ini", "/app/configs/consumers.ini"
    ]
    environment = concat(local.common_stream_env, [
      { name = "TOPIC_LOGS",        value = "mainnet.0.application.logs" },
      { name = "TOPIC_TXS_DATA",    value = "mainnet.4.transactions.data" },
      { name = "TOPIC_TXS_DECODED", value = "mainnet.5.transactions.input_decoded" },
      { name = "CONSUMER_GROUP",    value = "cg_txs_input_decoder" },
      { name = "SSM_ETHERSCAN_KEY", value = "/etherscan-api-keys/api-key-1" },
      { name = "ABI_CACHE_DIR",     value = "/tmp/abi_cache" },
    ])
    logConfiguration = local.log_config
  }])

  tags = local.common_tags
}

# -----------------------------------------------------------------------
# ECS Services — Python Streaming Apps
# -----------------------------------------------------------------------

resource "aws_ecs_service" "mined_blocks_watcher" {
  name            = "dm-mined-blocks-watcher"
  cluster         = aws_ecs_cluster.dm.id
  task_definition = aws_ecs_task_definition.mined_blocks_watcher.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = local.ecs_network_config.subnets
    security_groups  = local.ecs_network_config.security_groups
    assign_public_ip = local.ecs_network_config.assign_public_ip
  }

  tags = local.common_tags

  lifecycle { ignore_changes = [task_definition] }
}

resource "aws_ecs_service" "orphan_blocks_watcher" {
  name            = "dm-orphan-blocks-watcher"
  cluster         = aws_ecs_cluster.dm.id
  task_definition = aws_ecs_task_definition.orphan_blocks_watcher.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = local.ecs_network_config.subnets
    security_groups  = local.ecs_network_config.security_groups
    assign_public_ip = local.ecs_network_config.assign_public_ip
  }

  tags = local.common_tags

  lifecycle { ignore_changes = [task_definition] }
}

resource "aws_ecs_service" "block_data_crawler" {
  name            = "dm-block-data-crawler"
  cluster         = aws_ecs_cluster.dm.id
  task_definition = aws_ecs_task_definition.block_data_crawler.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = local.ecs_network_config.subnets
    security_groups  = local.ecs_network_config.security_groups
    assign_public_ip = local.ecs_network_config.assign_public_ip
  }

  tags = local.common_tags

  lifecycle { ignore_changes = [task_definition] }
}

resource "aws_ecs_service" "mined_txs_crawler" {
  name            = "dm-mined-txs-crawler"
  cluster         = aws_ecs_cluster.dm.id
  task_definition = aws_ecs_task_definition.mined_txs_crawler.arn
  desired_count   = 8
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = local.ecs_network_config.subnets
    security_groups  = local.ecs_network_config.security_groups
    assign_public_ip = local.ecs_network_config.assign_public_ip
  }

  tags = local.common_tags

  lifecycle { ignore_changes = [task_definition] }
}

resource "aws_ecs_service" "txs_input_decoder" {
  name            = "dm-txs-input-decoder"
  cluster         = aws_ecs_cluster.dm.id
  task_definition = aws_ecs_task_definition.txs_input_decoder.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = local.ecs_network_config.subnets
    security_groups  = local.ecs_network_config.security_groups
    assign_public_ip = local.ecs_network_config.assign_public_ip
  }

  tags = local.common_tags

  lifecycle { ignore_changes = [task_definition] }
}

# ---------------------------------------------------------------------------
# Schema Registry — Confluent CP Schema Registry backed by MSK
# ---------------------------------------------------------------------------

resource "aws_ecs_task_definition" "schema_registry" {
  family                   = "dm-schema-registry"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = data.terraform_remote_state.iam.outputs.ecs_task_execution_role_arn
  task_role_arn            = data.terraform_remote_state.iam.outputs.ecs_task_role_arn

  container_definitions = jsonencode([{
    name      = "schema-registry"
    image     = "confluentinc/cp-schema-registry:7.6.0"
    essential = true
    portMappings = [{
      containerPort = 8081
      hostPort      = 8081
      protocol      = "tcp"
    }]
    environment = [
      { name = "SCHEMA_REGISTRY_HOST_NAME",                              value = "schema-registry" },
      { name = "SCHEMA_REGISTRY_LISTENERS",                              value = "http://0.0.0.0:8081" },
      { name = "SCHEMA_REGISTRY_KAFKASTORE_BOOTSTRAP_SERVERS",           value = data.terraform_remote_state.msk.outputs.msk_bootstrap_brokers },
      { name = "SCHEMA_REGISTRY_KAFKASTORE_TOPIC",                       value = "_schemas" },
      { name = "SCHEMA_REGISTRY_KAFKASTORE_TOPIC_REPLICATION_FACTOR",    value = "2" },
      { name = "SCHEMA_REGISTRY_SCHEMA_REGISTRY_INTER_INSTANCE_PROTOCOL", value = "http" },
    ]
    logConfiguration = local.log_config
  }])

  tags = local.common_tags
}

resource "aws_ecs_service" "schema_registry" {
  name            = "dm-schema-registry"
  cluster         = aws_ecs_cluster.dm.id
  task_definition = aws_ecs_task_definition.schema_registry.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = local.ecs_network_config.subnets
    security_groups  = local.ecs_network_config.security_groups
    assign_public_ip = local.ecs_network_config.assign_public_ip
  }

  service_registries {
    registry_arn = aws_service_discovery_service.schema_registry.arn
  }

  tags = local.common_tags

  lifecycle { ignore_changes = [task_definition] }
}
