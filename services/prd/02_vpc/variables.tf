variable "region" {
  description = "AWS region"
  default     = "sa-east-1"
  type        = string
}

variable "environment" {
  description = "Deployment environment (prd/dev)"
  default     = "prd"
  type        = string
}

# ------------------ VPC ------------------
variable "cidr_vpc" {
  description = "CIDR block for the VPC"
  default     = "10.0.0.0/16"
  type        = string
}

# ------------------ Public subnet (ECS tasks, sem NAT GW) ------------------
variable "cidr_public_subnet_1" {
  default = "10.0.1.0/24"
  type    = string
}
variable "az_public_subnet_1" {
  default = "sa-east-1a"
  type    = string
}

# ------------------ Private subnets (MSK brokers, 2 AZs) ------------------
variable "cidr_private_subnet_1" {
  default = "10.0.10.0/24"
  type    = string
}
variable "az_private_subnet_1" {
  default = "sa-east-1a"
  type    = string
}

variable "cidr_private_subnet_2" {
  default = "10.0.11.0/24"
  type    = string
}
variable "az_private_subnet_2" {
  default = "sa-east-1b"
  type    = string
}

variable "project_version" {
  description = "Project version from VERSION file — propagated to resource tags"
  type        = string
  default     = "0.0.0"
}
