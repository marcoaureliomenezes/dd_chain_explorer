variable "region" { default = "sa-east-1" }
variable "environment" { default = "prod" }

variable "docker_image_stream" {
  description = "Docker image for onchain-stream-txs apps (DockerHub)"
  default     = "marcoaureliomenezes/onchain-stream-txs:1.0.0"
}

variable "docker_image_batch" {
  description = "Docker image for onchain-batch-txs apps (DockerHub)"
  default     = "marcoaureliomenezes/onchain-batch-txs:1.0.0"
}

variable "aws_secrets_manager_secret_name" {
  description = "Name of the Secrets Manager secret holding API keys"
  default     = "dm-chain-explorer/api-keys"
}
