###############################################################################
# modules/cloudwatch_logs/main.tf
#
# Creates a CloudWatch Log Group. The capture-layer log-delivery branch was
# retired with the capture layer in v0.4.0 — see specs/memory/architecture.md
# ADR for the capture-deprecation record.
#
# Usage:
#   module "cloudwatch_logs" {
#     source = "../../modules/cloudwatch_logs"
#     environment       = "prd"
#     common_tags       = local.common_tags
#     log_group_name    = "/apps/dm-chain-explorer"
#     retention_in_days = 30
#   }
###############################################################################

terraform {
  required_version = "~> 1.9"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

# ---------------------------------------------------------------------------
# CloudWatch Log Group
# ---------------------------------------------------------------------------

resource "aws_cloudwatch_log_group" "this" {
  name              = "${var.log_group_name}-${var.environment}"
  retention_in_days = var.retention_in_days

  tags = merge(var.common_tags, {
    Name = "${var.log_group_name}-${var.environment}"
  })
}
