###############################################################################
# hml/07_ecs/main.tf
#
# ECS Cluster persistente para HML + ECR repositories.
# Task definitions e services são gerenciados pelo workflow deploy_streaming_apps.
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
    key            = "hml/ecs/terraform.tfstate"
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

data "terraform_remote_state" "vpc" {
  backend = "s3"
  config = {
    bucket = "dm-chain-explorer-terraform-state"
    key    = "hml/vpc/terraform.tfstate"
    region = "sa-east-1"
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

module "ecs" {
  source = "../../modules/ecs"

  environment               = var.environment
  region                    = var.region
  common_tags               = local.common_tags
  name_prefix               = "dm-chain-explorer"
  cluster_name              = "dm-chain-explorer-ecs-hml"
  cloudwatch_log_group_name = "/ecs/dm-chain-explorer-hml"
  vpc_id                    = data.terraform_remote_state.vpc.outputs.vpc_id

  ecr_repositories = {
    "onchain-stream-txs" = {}
    "onchain-batch-txs"  = {}
  }
}
