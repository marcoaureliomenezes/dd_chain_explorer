data "aws_caller_identity" "current" {}

locals {
  ecr_base         = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.region}.amazonaws.com"
  ecr_image_stream = "${local.ecr_base}/onchain-stream-txs:${var.docker_image_stream}"
  ecr_image_batch  = "${local.ecr_base}/onchain-batch-txs:${var.docker_image_batch}"

  common_tags = {
    "owner"       = "marco-menezes"
    "managed-by"  = "terraform"
    "cost-center" = "dd-chain-explorer"
    "environment" = var.environment
    "project"     = "dd-chain-explorer"

    "project_version" = var.project_version
  }

  log_config = {
    logDriver = "awslogs"
    options = {
      awslogs-group         = aws_cloudwatch_log_group.ecs_apps.name
      awslogs-region        = var.region
      awslogs-stream-prefix = "ecs"
    }
  }
}
