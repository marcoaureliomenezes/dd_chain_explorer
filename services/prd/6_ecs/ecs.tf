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
    image = local.ecr_image_stream
    essential = true
    command = [
      "python", "-u", "/app/1_mined_blocks_watcher.py",
      "/app/configs/producers.ini"
    ]
    environment = concat(local.common_stream_env, [
      { name = "CLOCK_FREQUENCY",  value = "1" },
      { name = "SSM_SECRET_NAME", value = "/web3-api-keys/alchemy/api-key-1" },
    ])
    healthCheck = {
      command     = ["CMD-SHELL", "kill -0 1 || exit 1"]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 60
    }
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
    image = local.ecr_image_stream
    essential = true
    command = [
      "python", "-u", "/app/2_orphan_blocks_watcher.py",
      "/app/configs/producers.ini", "/app/configs/consumers.ini"
    ]
    environment = concat(local.common_stream_env, [
      { name = "NUM_CONFIRMATIONS", value = "10" },
      { name = "SSM_SECRET_NAME",  value = "/web3-api-keys/alchemy/api-key-2" },
    ])
    healthCheck = {
      command     = ["CMD-SHELL", "kill -0 1 || exit 1"]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 60
    }
    logConfiguration = local.log_config
  }])

  tags = local.common_tags
}

# Job 3 — Block Data Crawler
resource "aws_ecs_task_definition" "block_data_crawler" {
  family                   = "dm-block-data-crawler"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = data.terraform_remote_state.iam.outputs.ecs_task_execution_role_arn
  task_role_arn            = data.terraform_remote_state.iam.outputs.ecs_task_role_arn

  container_definitions = jsonencode([{
    name      = "block-data-crawler"
    image = local.ecr_image_stream
    essential = true
    command = [
      "python", "-u", "/app/3_block_data_crawler.py",
      "/app/configs/producers.ini", "/app/configs/consumers.ini"
    ]
    environment = concat(local.common_stream_env, [
      { name = "TXS_PER_BLOCK",  value = "0" },
      { name = "SSM_SECRET_NAME", value = "/web3-api-keys/alchemy/api-key-2" },
    ])
    healthCheck = {
      command     = ["CMD-SHELL", "kill -0 1 || exit 1"]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 60
    }
    logConfiguration = local.log_config
  }])

  tags = local.common_tags
}

# Job 4 — Raw Transactions Crawler (múltiplas réplicas)
resource "aws_ecs_task_definition" "mined_txs_crawler" {
  family                   = "dm-mined-txs-crawler"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = data.terraform_remote_state.iam.outputs.ecs_task_execution_role_arn
  task_role_arn            = data.terraform_remote_state.iam.outputs.ecs_task_role_arn

  container_definitions = jsonencode([{
    name      = "mined-txs-crawler"
    image = local.ecr_image_stream
    essential = true
    command = [
      "python", "-u", "/app/4_mined_txs_crawler.py",
      "/app/configs/producers.ini", "/app/configs/consumers.ini"
    ]
    environment = concat(local.common_stream_env, [
      # Notação compacta: expande para /web3-api-keys/infura/api-key-1 .. api-key-17
      { name = "SSM_SECRET_NAMES", value = "/web3-api-keys/infura/api-key-1-17" },
    ])
    healthCheck = {
      command     = ["CMD-SHELL", "kill -0 1 || exit 1"]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 60
    }
    logConfiguration = local.log_config
  }])

  tags = local.common_tags
}

# Job 5 — Transaction Input Decoder
resource "aws_ecs_task_definition" "txs_input_decoder" {
  family                   = "dm-txs-input-decoder"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = data.terraform_remote_state.iam.outputs.ecs_task_execution_role_arn
  task_role_arn            = data.terraform_remote_state.iam.outputs.ecs_task_role_arn

  container_definitions = jsonencode([{
    name      = "txs-input-decoder"
    image = local.ecr_image_stream
    essential = true
    command = [
      "python", "-u", "/app/5_txs_input_decoder.py",
      "/app/configs/producers.ini", "/app/configs/consumers.ini"
    ]
    environment = concat(local.common_stream_env, [
      { name = "SSM_ETHERSCAN_PATH", value = "/etherscan-api-keys" },
      { name = "ABI_CACHE_DIR",     value = "/tmp/abi_cache" },
    ])
    healthCheck = {
      command     = ["CMD-SHELL", "kill -0 1 || exit 1"]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 60
    }
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
  desired_count   = 0
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = local.ecs_network_config.subnets
    security_groups  = local.ecs_network_config.security_groups
    assign_public_ip = local.ecs_network_config.assign_public_ip
  }

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  tags = local.common_tags

  lifecycle { ignore_changes = [task_definition, desired_count] }
}

resource "aws_ecs_service" "orphan_blocks_watcher" {
  name            = "dm-orphan-blocks-watcher"
  cluster         = aws_ecs_cluster.dm.id
  task_definition = aws_ecs_task_definition.orphan_blocks_watcher.arn
  desired_count   = 0
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = local.ecs_network_config.subnets
    security_groups  = local.ecs_network_config.security_groups
    assign_public_ip = local.ecs_network_config.assign_public_ip
  }

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  tags = local.common_tags

  lifecycle { ignore_changes = [task_definition, desired_count] }
}

resource "aws_ecs_service" "block_data_crawler" {
  name            = "dm-block-data-crawler"
  cluster         = aws_ecs_cluster.dm.id
  task_definition = aws_ecs_task_definition.block_data_crawler.arn
  desired_count   = 0
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = local.ecs_network_config.subnets
    security_groups  = local.ecs_network_config.security_groups
    assign_public_ip = local.ecs_network_config.assign_public_ip
  }

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  tags = local.common_tags

  lifecycle { ignore_changes = [task_definition, desired_count] }
}

resource "aws_ecs_service" "mined_txs_crawler" {
  name            = "dm-mined-txs-crawler"
  cluster         = aws_ecs_cluster.dm.id
  task_definition = aws_ecs_task_definition.mined_txs_crawler.arn
  desired_count   = 0
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = local.ecs_network_config.subnets
    security_groups  = local.ecs_network_config.security_groups
    assign_public_ip = local.ecs_network_config.assign_public_ip
  }

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  tags = local.common_tags

  lifecycle { ignore_changes = [task_definition, desired_count] }
}

resource "aws_ecs_service" "txs_input_decoder" {
  name            = "dm-txs-input-decoder"
  cluster         = aws_ecs_cluster.dm.id
  task_definition = aws_ecs_task_definition.txs_input_decoder.arn
  desired_count   = 0  # TODO-C03: PROD target = 3 réplicas para cobrir as 4 partições de mainnet.4
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = local.ecs_network_config.subnets
    security_groups  = local.ecs_network_config.security_groups
    assign_public_ip = local.ecs_network_config.assign_public_ip
  }

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  tags = local.common_tags

  lifecycle { ignore_changes = [task_definition, desired_count] }
}


# -----------------------------------------------------------------------
# ECR Repositories
# -----------------------------------------------------------------------
resource "aws_ecr_repository" "stream" {
  name                 = "onchain-stream-txs"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = local.common_tags
}

resource "aws_ecr_repository" "batch" {
  name                 = "onchain-batch-txs"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = local.common_tags
}
