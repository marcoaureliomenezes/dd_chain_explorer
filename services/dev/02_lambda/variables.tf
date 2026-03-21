variable "region" {
  type    = string
  default = "sa-east-1"
}

variable "environment" {
  type    = string
  default = "dev"
}

variable "version" {
  description = "Project version from VERSION file — propagated to resource tags"
  type        = string
  default     = "0.0.0"
}
