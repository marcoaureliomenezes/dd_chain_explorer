variable "region" {
  description = "AWS region"
  default     = "sa-east-1"
  type        = string
}

variable "rm_state_bucket" {
  description = "Name of the S3 bucket to store terraform remote state"
  type        = string
  default     = "dm-chain-explorer-terraform-state"
}
