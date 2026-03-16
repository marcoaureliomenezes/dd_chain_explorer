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
    key            = "lambda/terraform.tfstate"
    region         = "sa-east-1"
    dynamodb_table = "dm-chain-explorer-terraform-lock"
    encrypt        = true
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = local.common_tags
  }
}

# Remote state references
data "terraform_remote_state" "s3" {
  backend = "s3"
  config = {
    bucket = "dm-chain-explorer-terraform-state"
    key    = "s3/terraform.tfstate"
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
