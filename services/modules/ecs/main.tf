resource "aws_ecs_cluster" "this" {
  name = var.cluster_name

  setting {
    name  = "containerInsights"
    value = var.container_insights ? "enabled" : "disabled"
  }

  tags = var.common_tags
}

resource "aws_ecs_cluster_capacity_providers" "this" {
  cluster_name       = aws_ecs_cluster.this.name
  capacity_providers = var.capacity_providers

  default_capacity_provider_strategy {
    capacity_provider = var.default_capacity_provider
    weight            = 1
  }
}

resource "aws_cloudwatch_log_group" "ecs" {
  name              = var.cloudwatch_log_group_name
  retention_in_days = var.cloudwatch_log_retention_days
  tags              = var.common_tags
}

resource "aws_service_discovery_private_dns_namespace" "this" {
  name        = "${var.name_prefix}-${var.environment}.local"
  description = "Private DNS for ECS service discovery (${var.environment})"
  vpc         = var.vpc_id
  tags        = var.common_tags
}

resource "aws_ecr_repository" "this" {
  for_each = var.ecr_repositories

  name                 = each.key
  image_tag_mutability = each.value.image_tag_mutability
  force_delete         = each.value.force_delete

  image_scanning_configuration {
    scan_on_push = each.value.scan_on_push
  }

  tags = var.common_tags
}
