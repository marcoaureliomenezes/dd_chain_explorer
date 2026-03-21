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
