variable "region" {
  description = "AWS region"
  default     = "sa-east-1"
  type        = string
}

variable "environment" {
  description = "Deployment environment (prod/dev)"
  default     = "prod"
  type        = string
}

# ------------------ VPC ------------------
variable "cidr_vpc" {
  description = "CIDR block for the VPC"
  default     = "10.0.0.0/16"
  type        = string
}

# ------------------ Public subnets (NAT GW) ------------------
variable "cidr_public_subnet_1" {
  default = "10.0.1.0/24"
  type    = string
}
variable "az_public_subnet_1" {
  default = "sa-east-1a"
  type    = string
}

variable "cidr_public_subnet_2" {
  default = "10.0.2.0/24"
  type    = string
}
variable "az_public_subnet_2" {
  default = "sa-east-1b"
  type    = string
}

# ------------------ Private subnets (ECS + MSK) ------------------
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

variable "cidr_private_subnet_3" {
  default = "10.0.12.0/24"
  type    = string
}
variable "az_private_subnet_3" {
  default = "sa-east-1c"
  type    = string
}
