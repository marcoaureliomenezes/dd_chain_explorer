###############################################################################
# hml/02_vpc/main.tf
#
# VPC dedicada para o ambiente HML — isolada da PRD.
# Subnets públicas para ECS Fargate + subnets privadas para Databricks.
###############################################################################

terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }

  backend "s3" {
    bucket         = "dm-chain-explorer-terraform-state"
    key            = "hml/vpc/terraform.tfstate"
    region         = "sa-east-1"
    dynamodb_table = "dm-chain-explorer-terraform-lock"
    encrypt        = true
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = local.common_tags
  }
}

locals {
  common_tags = {
    "owner"       = "marco-menezes"
    "managed-by"  = "terraform"
    "cost-center" = "dd-chain-explorer"
    "environment" = var.environment
    "project"     = "dd-chain-explorer"
  }
}

module "vpc" {
  source = "../../modules/vpc"

  environment            = var.environment
  region                 = var.region
  common_tags            = local.common_tags
  name_prefix            = "dm-chain-explorer"
  cidr_vpc               = var.cidr_vpc
  cidr_public_subnet_1   = var.cidr_public_subnet_1
  az_public_subnet_1     = var.az_public_subnet_1
  enable_private_subnets = var.enable_private_subnets
  cidr_private_subnet_1  = var.cidr_private_subnet_1
  az_private_subnet_1    = var.az_private_subnet_1
  cidr_private_subnet_2  = var.cidr_private_subnet_2
  az_private_subnet_2    = var.az_private_subnet_2
  enable_s3_endpoint     = true
}
