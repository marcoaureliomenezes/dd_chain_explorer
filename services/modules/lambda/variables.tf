variable "environment" {
  description = "Deployment environment (dev/hml/prd)"
  type        = string
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

variable "function_name" {
  description = "Lambda function name (without env suffix)"
  type        = string
}

variable "description" {
  description = "Lambda function description"
  type        = string
  default     = ""
}

variable "handler" {
  description = "Lambda handler (file.function)"
  type        = string
  default     = "handler.handler"
}

variable "runtime" {
  description = "Lambda runtime"
  type        = string
  default     = "python3.12"
}

variable "timeout" {
  description = "Lambda timeout in seconds"
  type        = number
  default     = 60
}

variable "memory_size" {
  description = "Lambda memory in MB"
  type        = number
  default     = 128
}

variable "source_file" {
  description = "Path to the Lambda source file to zip"
  type        = string
}

variable "output_zip_path" {
  description = "Path for the output zip file"
  type        = string
}

variable "role_arn" {
  description = "IAM role ARN for the Lambda function"
  type        = string
}

variable "environment_variables" {
  description = "Environment variables for the Lambda function"
  type        = map(string)
  default     = {}
}

variable "s3_trigger_bucket_arn" {
  description = "ARN of the S3 bucket that triggers the Lambda"
  type        = string
  default     = ""
}

variable "s3_trigger_bucket_name" {
  description = "Name of the S3 bucket that triggers the Lambda"
  type        = string
  default     = ""
}

variable "s3_trigger_prefix" {
  description = "S3 key prefix filter for the trigger"
  type        = string
  default     = ""
}

variable "s3_trigger_suffix" {
  description = "S3 key suffix filter for the trigger"
  type        = string
  default     = ""
}
