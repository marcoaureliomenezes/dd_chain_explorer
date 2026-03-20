###############################################################################
# prd/3_kinesis_sqs/main.tf
#
# Substitui o módulo 3_msk/ — Kinesis Data Streams, SQS Queues,
# CloudWatch Log Group e Firehose Delivery Streams para produção.
###############################################################################

terraform {
  required_version = ">= 1.3.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }

  backend "s3" {
    bucket         = "dm-chain-explorer-terraform-state"
    key            = "kinesis_sqs/terraform.tfstate"
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

data "terraform_remote_state" "s3" {
  backend = "s3"
  config = {
    bucket = "dm-chain-explorer-terraform-state"
    key    = "s3/terraform.tfstate"
    region = "sa-east-1"
  }
}
