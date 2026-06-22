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
