###############################################################################
# modules/cloudwatch_logs/variables.tf
#
# Input variables for CloudWatch Log Group + Firehose subscription module.
###############################################################################

variable "environment" {
  description = "Environment name (dev, hml, prd)"
  type        = string
}

variable "region" {
  description = "AWS region"
  type        = string
  default     = "sa-east-1"
}

variable "common_tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
  default     = {}
}

# ---------------------------------------------------------------------------
# CloudWatch Log Group
# ---------------------------------------------------------------------------

variable "log_group_name" {
  description = "Name of the CloudWatch Log Group"
  type        = string
  default     = "/apps/dm-chain-explorer"
}

variable "retention_in_days" {
  description = "Number of days to retain log events (0 = never expire)"
  type        = number
  default     = 30
}

# ---------------------------------------------------------------------------
# Firehose delivery (CloudWatch Logs → S3)
# ---------------------------------------------------------------------------

variable "firehose_enabled" {
  description = "Whether to create a Firehose delivery stream for logs → S3"
  type        = bool
  default     = true
}

variable "firehose_s3_bucket_arn" {
  description = "ARN of the S3 bucket for Firehose log delivery"
  type        = string
  default     = ""
}

variable "firehose_s3_prefix" {
  description = "S3 key prefix for Firehose log delivery"
  type        = string
  default     = "raw/app_logs/"
}

variable "firehose_buffer_size_mb" {
  description = "Firehose buffer size in MB (1–128)"
  type        = number
  default     = 5
}

variable "firehose_buffer_interval_seconds" {
  description = "Firehose buffer interval in seconds (60–900)"
  type        = number
  default     = 300
}
