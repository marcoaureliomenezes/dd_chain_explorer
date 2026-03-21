###############################################################################
# prd/04_peripherals/main.tf
#
# S3 buckets + Kinesis Data Streams + Firehose + SQS + CloudWatch + DynamoDB
# para o ambiente PRD — recursos "periféricos" consumidos por ECS, Lambda e
# Databricks.
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
    key            = "prd/peripherals/terraform.tfstate"
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
