variable "aws_region" {
  default = "sa-east-1"
}

variable "project" {
  default = "dd-chain-explorer"
}

variable "environment" {
  default = "prd"
}

variable "project_version" {
  description = "Project version from VERSION file — propagated to resource tags"
  type        = string
  default     = "0.0.0"
}

# ---- Lambda layer artifact (T-B.14, D15) ----
# layer_s3_bucket defaults to the artifacts bucket name (prd/04_peripherals);
# layer_s3_key/layer_sha256 have NO default — CI supplies them from
# scripts/build_lambda_layer.sh's output, so a plan run without them fails
# loudly instead of silently resolving a stale layer.
variable "layer_s3_bucket" {
  description = "S3 bucket holding the built Lambda layer zip"
  type        = string
  default     = "dm-chain-explorer-artifacts"
}

variable "layer_s3_key" {
  description = "S3 key of the built Lambda layer zip (content-addressed: lambda-layers/dm-chain-utils/<sha256>.zip)"
  type        = string
}

variable "layer_sha256" {
  description = "base64-encoded sha256 of the built Lambda layer zip (source_code_hash)"
  type        = string
}
