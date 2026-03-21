###############################################################################
# terraform_hml/cloudwatch.tf
#
# CloudWatch Log Group + Firehose delivery para o ambiente HML.
#
# Persistent resource — the log group and Firehose subscription survive
# across CI/CD runs.  Ephemeral ECS tasks write to this log group;
# the Firehose delivers app logs to S3 raw/app_logs/ for the DLT
# pipeline (dm-app-logs) to consume in the HML catalog.
###############################################################################

module "cloudwatch_logs" {
  source = "../../modules/cloudwatch_logs"

  environment            = var.environment
  region                 = var.region
  common_tags            = local.common_tags
  log_group_name         = "/apps/dm-chain-explorer"
  retention_in_days      = 3
  firehose_enabled       = true
  firehose_s3_bucket_arn = aws_s3_bucket.hml_ingestion.arn
  firehose_s3_prefix     = "raw/app_logs/"
  firehose_buffer_size_mb         = 1
  firehose_buffer_interval_seconds = 60
}
