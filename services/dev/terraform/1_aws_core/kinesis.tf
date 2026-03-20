###############################################################################
# terraform_dev/kinesis.tf
#
# Kinesis Data Streams + Firehose para o ambiente DEV.
# Containers locais acessam via IAM user credentials (AWS_ACCESS_KEY_ID).
###############################################################################

module "kinesis" {
  source = "../../../modules/kinesis"

  environment = var.environment
  region      = var.region
  common_tags = local.common_tags

  streams = {
    "mainnet-blocks-data" = {
      stream_mode      = "ON_DEMAND"
      retention_period  = 24
    }
    "mainnet-transactions-data" = {
      stream_mode      = "ON_DEMAND"
      retention_period  = 24
    }
    "mainnet-transactions-decoded" = {
      stream_mode      = "ON_DEMAND"
      retention_period  = 24
    }
  }

  firehose_enabled       = true
  firehose_s3_bucket_arn = aws_s3_bucket.ingestion.arn
  firehose_s3_prefix     = "raw/"
}
