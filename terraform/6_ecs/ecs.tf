# -----------------------------------------------------------------------
# ECS Cluster
# -----------------------------------------------------------------------
resource "aws_ecs_cluster" "dm" {
  name = "dm-chain-explorer-ecs"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_ecs_cluster_capacity_providers" "dm" {
  cluster_name       = aws_ecs_cluster.dm.name
  capacity_providers = ["FARGATE", "FARGATE_SPOT"]

  default_capacity_provider_strategy {
    capacity_provider = "FARGATE"
    weight            = 1
  }
}

# -----------------------------------------------------------------------
# CloudWatch Log Group for ECS tasks
# -----------------------------------------------------------------------
resource "aws_cloudwatch_log_group" "ecs_apps" {
  name              = "/ecs/dm-chain-explorer"
  retention_in_days = 7
}

# -----------------------------------------------------------------------
# Task Definitions — Python Streaming Apps
# -----------------------------------------------------------------------

locals {
  log_config = {
    logDriver = "awslogs"
    options = {
      awslogs-group         = aws_cloudwatch_log_group.ecs_apps.name
      awslogs-region        = var.region
      awslogs-stream-prefix = "ecs"
    }
  }
}

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
    command   = ["python", "-u", "/app/1_mined_blocks_watcher.py"]
    environment = concat(local.common_stream_env, [
      { name = "TOPIC_LOGS", value = "mainnet.0.application.logs" },
      { name = "TOPIC_MINED_BLOCKS_EVENTS", value = "mainnet.1.mined_blocks.events" },
      { name = "CLOCK_FREQUENCY", value = "1" },
      { name = "AKV_SECRET_NAME", value = "alchemy-api-key-1" },
    ])
    logConfiguration = local.log_config
  }])
}

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
    command   = ["python", "-u", "/app/2_orphan_blocks_watcher.py"]
    environment = concat(local.common_stream_env, [
      { name = "TOPIC_LOGS", value = "mainnet.0.application.logs" },
      { name = "TOPIC_MINED_BLOCKS_EVENTS", value = "mainnet.1.mined_blocks.events" },
      { name = "CONSUMER_GROUP_ID", value = "cg_orphan_block_events" },
      { name = "AKV_SECRET_NAME", value = "alchemy-api-key-2" },
    ])
    logConfiguration = local.log_config
  }])
}

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
    command   = ["python", "-u", "/app/3_block_data_crawler.py"]
    environment = concat(local.common_stream_env, [
      { name = "TOPIC_LOGS", value = "mainnet.0.application.logs" },
      { name = "TOPIC_MINED_BLOCKS_EVENTS", value = "mainnet.1.mined_blocks.events" },
      { name = "TOPIC_MINED_BLOCKS", value = "mainnet.2.blocks.data" },
      { name = "TOPIC_TXS_HASH_IDS", value = "mainnet.3.block.txs.hash_id" },
      { name = "CONSUMER_GROUP", value = "cg_block_data_crawler" },
      { name = "CLOCK_FREQUENCY", value = "1" },
      { name = "TXS_PER_BLOCK", value = "50" },
      { name = "AKV_SECRET_NAME", value = "alchemy-api-key-2" },
    ])
    logConfiguration = local.log_config
  }])
}

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
    command   = ["python", "-u", "/app/4_mined_txs_crawler.py"]
    environment = concat(local.common_stream_env, [
      { name = "TOPIC_LOGS", value = "mainnet.0.application.logs" },
      { name = "TOPIC_TXS_HASH_IDS", value = "mainnet.3.block.txs.hash_id" },
      { name = "TOPIC_TXS_DATA", value = "mainnet.4.transactions.data" },
      { name = "CONSUMER_GROUP", value = "cg_mined_raw_txs" },
      { name = "AKV_SECRET_NAMES", value = "infura-api-key-1-12" },
    ])
    logConfiguration = local.log_config
  }])
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
    subnets          = data.terraform_remote_state.vpc.outputs.private_subnet_ids
    security_groups  = [data.terraform_remote_state.vpc.outputs.sg_ecs_tasks_id]
    assign_public_ip = false
  }

  lifecycle {
    ignore_changes = [task_definition]
  }
}

resource "aws_ecs_service" "orphan_blocks_watcher" {
  name            = "dm-orphan-blocks-watcher"
  cluster         = aws_ecs_cluster.dm.id
  task_definition = aws_ecs_task_definition.orphan_blocks_watcher.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = data.terraform_remote_state.vpc.outputs.private_subnet_ids
    security_groups  = [data.terraform_remote_state.vpc.outputs.sg_ecs_tasks_id]
    assign_public_ip = false
  }

  lifecycle {
    ignore_changes = [task_definition]
  }
}

resource "aws_ecs_service" "block_data_crawler" {
  name            = "dm-block-data-crawler"
  cluster         = aws_ecs_cluster.dm.id
  task_definition = aws_ecs_task_definition.block_data_crawler.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = data.terraform_remote_state.vpc.outputs.private_subnet_ids
    security_groups  = [data.terraform_remote_state.vpc.outputs.sg_ecs_tasks_id]
    assign_public_ip = false
  }

  lifecycle {
    ignore_changes = [task_definition]
  }
}

resource "aws_ecs_service" "mined_txs_crawler" {
  name            = "dm-mined-txs-crawler"
  cluster         = aws_ecs_cluster.dm.id
  task_definition = aws_ecs_task_definition.mined_txs_crawler.arn
  desired_count   = 8 # multiple replicas to parallelize tx fetching
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = data.terraform_remote_state.vpc.outputs.private_subnet_ids
    security_groups  = [data.terraform_remote_state.vpc.outputs.sg_ecs_tasks_id]
    assign_public_ip = false
  }

  lifecycle {
    ignore_changes = [task_definition]
  }
}
