variable "region" {
  type    = string
  default = "sa-east-1"
}

variable "environment" {
  type    = string
  default = "hml"
}

variable "create_cluster" {
  description = "Whether to create the Databricks interactive cluster. Set false in CI to avoid data sources that need a running workspace."
  type        = bool
  default     = false
}
