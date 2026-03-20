###############################################################################
# modules/sqs/main.tf
#
# Creates SQS Standard Queues with optional Dead Letter Queues and
# optional IP-based access restriction (for DEV environments).
#
# Usage:
#   module "sqs" {
#     source = "../../modules/sqs"
#     environment = "prd"
#     common_tags = local.common_tags
#     queues = {
#       "mainnet-mined-blocks-events" = { visibility_timeout_seconds = 30 }
#       "mainnet-block-txs-hash-id"   = { visibility_timeout_seconds = 60 }
#     }
#   }
###############################################################################

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

# ---------------------------------------------------------------------------
# Dead Letter Queues (created first so main queues can reference them)
# ---------------------------------------------------------------------------

resource "aws_sqs_queue" "dlq" {
  for_each = { for k, v in var.queues : k => v if v.dlq_enabled }

  name                      = "${each.key}-dlq-${var.environment}"
  message_retention_seconds = 1209600 # 14 days — max retention for DLQ analysis

  tags = merge(var.common_tags, {
    Name = "${each.key}-dlq-${var.environment}"
  })
}

# ---------------------------------------------------------------------------
# Main SQS Queues
# ---------------------------------------------------------------------------

resource "aws_sqs_queue" "this" {
  for_each = var.queues

  name                       = "${each.key}-${var.environment}"
  visibility_timeout_seconds = each.value.visibility_timeout_seconds
  message_retention_seconds  = each.value.message_retention_seconds
  max_message_size           = each.value.max_message_size
  receive_wait_time_seconds  = each.value.receive_wait_time_seconds
  delay_seconds              = each.value.delay_seconds

  redrive_policy = each.value.dlq_enabled ? jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq[each.key].arn
    maxReceiveCount     = each.value.dlq_max_receive_count
  }) : null

  tags = merge(var.common_tags, {
    Name = "${each.key}-${var.environment}"
  })
}

# ---------------------------------------------------------------------------
# Optional IP-based queue policy (DEV only — restrict SendMessage/ReceiveMessage)
# ---------------------------------------------------------------------------

resource "aws_sqs_queue_policy" "ip_restrict" {
  for_each = length(var.ip_allowlist) > 0 ? var.queues : {}

  queue_url = aws_sqs_queue.this[each.key].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowFromSpecificIPs"
        Effect    = "Allow"
        Principal = "*"
        Action = [
          "sqs:SendMessage",
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
          "sqs:GetQueueUrl",
        ]
        Resource = aws_sqs_queue.this[each.key].arn
        Condition = {
          IpAddress = {
            "aws:SourceIp" = var.ip_allowlist
          }
        }
      },
    ]
  })
}
