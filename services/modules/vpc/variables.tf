variable "environment" {
  description = "Deployment environment (dev/hml/prd)"
  type        = string
}

variable "region" {
  description = "AWS region"
  type        = string
  default     = "sa-east-1"
}

variable "common_tags" {
  description = "Common resource tags"
  type        = map(string)
  default     = {}
}

variable "name_prefix" {
  description = "Resource name prefix (e.g. dm-chain-explorer)"
  type        = string
  default     = "dm-chain-explorer"
}

variable "cidr_vpc" {
  description = "CIDR block for the VPC"
  type        = string
}

variable "cidr_public_subnet_1" {
  description = "CIDR for public subnet 1 (ECS tasks)"
  type        = string
}

variable "az_public_subnet_1" {
  description = "AZ for public subnet 1"
  type        = string
  default     = "sa-east-1a"
}

variable "cidr_private_subnet_1" {
  description = "CIDR for private subnet 1 (Databricks)"
  type        = string
  default     = ""
}

variable "az_private_subnet_1" {
  description = "AZ for private subnet 1"
  type        = string
  default     = "sa-east-1a"
}

variable "cidr_private_subnet_2" {
  description = "CIDR for private subnet 2 (Databricks, second AZ)"
  type        = string
  default     = ""
}

variable "az_private_subnet_2" {
  description = "AZ for private subnet 2"
  type        = string
  default     = "sa-east-1b"
}

variable "enable_private_subnets" {
  description = "Whether to create private subnets (needed for Databricks)"
  type        = bool
  default     = false
}

variable "enable_s3_endpoint" {
  description = "Whether to create S3 VPC Gateway Endpoint"
  type        = bool
  default     = true
}
