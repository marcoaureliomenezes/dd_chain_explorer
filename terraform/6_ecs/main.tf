terraform {
  required_version = ">= 1.3.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 4.60.0"
    }
  }

  backend "s3" {
    bucket         = "dm-chain-explorer-terraform-state"
    key            = "ecs/terraform.tfstate"
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
    key    = "vpc/terraform.tfstate"
    region = "sa-east-1"
  }
}

data "terraform_remote_state" "iam" {
  backend = "s3"
  config = {
    bucket = "dm-chain-explorer-terraform-state"
    key    = "iam/terraform.tfstate"
    region = "sa-east-1"
  }
}

data "terraform_remote_state" "msk" {
  backend = "s3"
  config = {
    bucket = "dm-chain-explorer-terraform-state"
    key    = "msk/terraform.tfstate"
    region = "sa-east-1"
  }
}

data "terraform_remote_state" "dynamodb" {
  backend = "s3"
  config = {
    bucket = "dm-chain-explorer-terraform-state"
    key    = "dynamodb/terraform.tfstate"
    region = "sa-east-1"
  }
}
