variable "environment" {
  description = "Deployment environment (dev/hml/prd)"
  type        = string
}

variable "region" {
  description = "AWS region"
  type        = string
  default     = "sa-east-1"
}

variable "common_tags" {
  description = "Common resource tags"
  type        = map(string)
  default     = {}
}

variable "name_prefix" {
  description = "Resource name prefix"
  type        = string
  default     = "dm-chain-explorer"
}

variable "account_id" {
  description = "AWS account ID"
  type        = string
}

# ── ECS roles ────────────────────────────────────────────────────────────────
variable "create_ecs_roles" {
  description = "Whether to create ECS task execution and task roles"
  type        = bool
  default     = true
}

variable "kinesis_stream_suffix" {
  description = "Suffix appended to kinesis stream names in IAM policy (e.g. 'prd' or 'hml')"
  type        = string
}

variable "sqs_queue_suffix" {
  description = "Suffix appended to SQS queue names in IAM policy"
  type        = string
}

variable "raw_bucket_arn" {
  description = "ARN of the raw ingestion S3 bucket"
  type        = string
  default     = ""
}

variable "lakehouse_bucket_arn" {
  description = "ARN of the lakehouse S3 bucket"
  type        = string
  default     = ""
}

variable "dynamodb_table_name" {
  description = "Name of the DynamoDB table the ECS task role may access"
  type        = string
}

# ── Databricks roles (PRD only) ──────────────────────────────────────────────
variable "create_databricks_roles" {
  description = "Whether to create Databricks cross-account and cluster roles"
  type        = bool
  default     = false
}

variable "databricks_account_id" {
  description = "Databricks AWS account ID (for cross-account trust)"
  type        = string
  default     = ""
}

variable "databricks_account_uuid" {
  description = "Databricks account UUID (ExternalId condition)"
  type        = string
  default     = ""
}

variable "databricks_bucket_arn" {
  description = "ARN of the Databricks-dedicated S3 bucket"
  type        = string
  default     = ""
}

# ── Lambda roles ─────────────────────────────────────────────────────────────
variable "create_lambda_role" {
  description = "Whether to create Lambda execution role"
  type        = bool
  default     = false
}

variable "lambda_dynamodb_table_arn" {
  description = "DynamoDB table ARN the Lambda may write to"
  type        = string
  default     = ""
}

variable "lambda_s3_source_bucket_arn" {
  description = "S3 bucket ARN the Lambda may read from"
  type        = string
  default     = ""
}
