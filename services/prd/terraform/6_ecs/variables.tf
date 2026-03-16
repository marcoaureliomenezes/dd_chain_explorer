variable "region" { default = "sa-east-1" }
variable "environment" { default = "prd" }

variable "docker_image_stream" {
  description = "Docker image for onchain-stream-txs apps (ECR). Defaults to :latest; CI overrides with the commit SHA tag."
  default     = "latest"
}

variable "docker_image_batch" {
  description = "Docker image for onchain-batch-txs apps (ECR). Defaults to :latest; CI overrides with the commit SHA tag."
  default     = "latest"
}


