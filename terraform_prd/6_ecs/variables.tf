variable "region" { default = "sa-east-1" }
variable "environment" { default = "prd" }

variable "docker_image_stream" {
  description = "Docker image for onchain-stream-txs apps (DockerHub)"
  default     = "marcoaureliomenezes/onchain-stream-txs:1.0.4"
}

variable "docker_image_batch" {
  description = "Docker image for onchain-batch-txs apps (DockerHub)"
  default     = "marcoaureliomenezes/onchain-batch-txs:1.0.0"
}


