###############################################################################
# terraform_dev/sqs.tf
#
# SQS Queues + DLQs para o ambiente DEV.
# Acesso restrito ao IP público do desenvolvedor via queue policy.
###############################################################################

module "sqs" {
  source = "../../../modules/sqs"

  environment = var.environment
  common_tags = local.common_tags

  queues = {
    "mainnet-mined-blocks-events" = {
      visibility_timeout_seconds = 30
      receive_wait_time_seconds  = 20
      dlq_enabled                = true
      dlq_max_receive_count      = 3
    }
    "mainnet-block-txs-hash-id" = {
      visibility_timeout_seconds = 60
      receive_wait_time_seconds  = 20
      dlq_enabled                = true
      dlq_max_receive_count      = 3
    }
  }

  ip_allowlist = var.developer_ip_cidr != "" ? [var.developer_ip_cidr] : []
}
