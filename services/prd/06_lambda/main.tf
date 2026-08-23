terraform {
  required_version = "~> 1.9"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 4.60.0"
    }
  }

  backend "s3" {
    bucket         = "dm-chain-explorer-terraform-state"
    key            = "prd/lambda/terraform.tfstate"
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
    key    = "prd/peripherals/terraform.tfstate"
    region = "sa-east-1"
  }
}

data "terraform_remote_state" "dynamodb" {
  backend = "s3"
  config = {
    bucket = "dm-chain-explorer-terraform-state"
    key    = "prd/peripherals/terraform.tfstate"
    region = "sa-east-1"
  }
}

data "aws_caller_identity" "current" {}

# ---------------------------------------------------------------------------
# CloudWatch Log Groups for the kept Lambda functions (T-B.14, F-09/DRIFT-24)
#
# Both groups already exist live (Lambda auto-creates them on first invoke)
# but outside any Terraform state. Declared here with an explicit retention
# so Terraform owns it (AC-10's clean plan is the proof, never CLI-clicked),
# and imported so the apply is a 0-diff against the live groups.
# ---------------------------------------------------------------------------

resource "aws_cloudwatch_log_group" "contracts_ingestion" {
  name              = "/aws/lambda/${aws_lambda_function.contracts_ingestion.function_name}"
  retention_in_days = 30
  tags              = local.common_tags
}

resource "aws_cloudwatch_log_group" "gold_to_dynamodb" {
  name              = "/aws/lambda/${aws_lambda_function.gold_to_dynamodb.function_name}"
  retention_in_days = 30
  tags              = local.common_tags
}

# Declarative import (Terraform >= 1.5, this stack pins ~> 1.9). Documented
# fallback for the coordinator:
#   terraform import 'aws_cloudwatch_log_group.contracts_ingestion' /aws/lambda/dm-dd-chain-explorer-prd-contracts-ingestion
#   terraform import 'aws_cloudwatch_log_group.gold_to_dynamodb' /aws/lambda/dm-dd-chain-explorer-prd-gold-to-dynamodb
import {
  to = aws_cloudwatch_log_group.contracts_ingestion
  id = "/aws/lambda/${local.name_prefix}-contracts-ingestion"
}

import {
  to = aws_cloudwatch_log_group.gold_to_dynamodb
  id = "/aws/lambda/${local.name_prefix}-gold-to-dynamodb"
}
