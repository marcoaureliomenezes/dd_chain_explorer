variable "region" {
  default = "sa-east-1"
  type    = string
}

variable "environment" {
  default = "prd"
  type    = string
}

variable "kafka_version" {
  description = "Kafka version for MSK cluster"
  default     = "3.6.0"
  type        = string
}

variable "broker_instance_type" {
  description = "MSK broker instance type (minimal cost)"
  default     = "kafka.t3.small"
  type        = string
}

variable "broker_ebs_size_gb" {
  description = "EBS storage per broker in GB"
  default     = 20
  type        = number
}
