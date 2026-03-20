###############################################################################
# prd/3_kinesis_sqs/variables.tf
###############################################################################

variable "region" {
  description = "AWS region"
  type        = string
  default     = "sa-east-1"
}

variable "environment" {
  description = "Nome do ambiente"
  type        = string
  default     = "prd"
}
