###############################################################################
# modules/kinesis/variables.tf
#
# Input variables for Kinesis Data Streams + Firehose Delivery module.
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
# Kinesis Data Streams
# ---------------------------------------------------------------------------

variable "streams" {
  description = <<-EOT
    Map of Kinesis Data Streams to create.
    Key   = logical name (used for resource naming).
    Value = object with stream configuration.
  EOT
  type = map(object({
    shard_count          = optional(number, 1)        # ignored when stream_mode = ON_DEMAND
    retention_period     = optional(number, 24)        # hours (24–8760)
    stream_mode          = optional(string, "ON_DEMAND") # ON_DEMAND or PROVISIONED
    encryption_type      = optional(string, "NONE")    # KMS or NONE (KMS requires kms_key_id)
  }))
}

# ---------------------------------------------------------------------------
# Firehose Delivery Streams (Kinesis → S3)
# ---------------------------------------------------------------------------

variable "firehose_enabled" {
  description = "Whether to create Firehose delivery streams for each Kinesis stream"
  type        = bool
  default     = true
}

variable "firehose_s3_bucket_arn" {
  description = "ARN of the S3 bucket for Firehose delivery"
  type        = string
  default     = ""
}

variable "firehose_s3_prefix" {
  description = "S3 key prefix for Firehose delivery (e.g. 'bronze/'). Stream name is appended automatically."
  type        = string
  default     = "raw/"
}

variable "firehose_buffer_size_mb" {
  description = "Firehose buffer size in MB before flushing to S3 (1–128)"
  type        = number
  default     = 64
}

variable "firehose_buffer_interval_seconds" {
  description = "Firehose buffer interval in seconds before flushing to S3 (60–900)"
  type        = number
  default     = 300
}

variable "firehose_compression" {
  description = "Compression format for Firehose S3 delivery (UNCOMPRESSED, GZIP, SNAPPY, etc.)"
  type        = string
  default     = "GZIP"
}

variable "firehose_role_arn" {
  description = "IAM role ARN for Firehose to read from Kinesis and write to S3. If empty, the module creates one."
  type        = string
  default     = ""
}
