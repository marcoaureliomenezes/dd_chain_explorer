variable "region" {
  type    = string
  default = "sa-east-1"
}

variable "environment" {
  type    = string
  default = "hml"
}

variable "cidr_vpc" {
  type    = string
  default = "10.1.0.0/16"
}

variable "cidr_public_subnet_1" {
  type    = string
  default = "10.1.1.0/24"
}

variable "az_public_subnet_1" {
  type    = string
  default = "sa-east-1a"
}

variable "enable_private_subnets" {
  type    = bool
  default = true
}

variable "cidr_private_subnet_1" {
  type    = string
  default = "10.1.10.0/24"
}

variable "az_private_subnet_1" {
  type    = string
  default = "sa-east-1a"
}

variable "cidr_private_subnet_2" {
  type    = string
  default = "10.1.11.0/24"
}

variable "az_private_subnet_2" {
  type    = string
  default = "sa-east-1b"
}
