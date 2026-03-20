###############################################################################
# terraform_dev/cloudwatch.tf
#
# CloudWatch Log Group + Firehose delivery para o ambiente DEV.
###############################################################################

module "cloudwatch_logs" {
  source = "../../../modules/cloudwatch_logs"

  environment            = var.environment
  region                 = var.region
  common_tags            = local.common_tags
  log_group_name         = "/apps/dm-chain-explorer"
  retention_in_days      = 7
  firehose_enabled       = true
  firehose_s3_bucket_arn = aws_s3_bucket.ingestion.arn
  firehose_s3_prefix     = "raw/app_logs/"
  firehose_buffer_size_mb         = 5
  firehose_buffer_interval_seconds = 300
}
