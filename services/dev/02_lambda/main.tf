###############################################################################
# dev/02_lambda/main.tf
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
    key            = "dev/lambda/terraform.tfstate"
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

data "terraform_remote_state" "peripherals" {
  backend = "s3"
  config = {
    bucket = "dm-chain-explorer-terraform-state"
    key    = "dev/peripherals/terraform.tfstate"
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
    "project_version" = var.project_version
  }

  name_prefix = "dm-chain-explorer"
}

# ---- IAM Role for Lambda ----
resource "aws_iam_role" "gold_to_dynamodb_lambda" {
  name = "${local.name_prefix}-gold-to-dynamodb-lambda-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy" "gold_to_dynamodb_lambda" {
  name = "${local.name_prefix}-gold-to-dynamodb-policy-${var.environment}"
  role = aws_iam_role.gold_to_dynamodb_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["dynamodb:BatchWriteItem", "dynamodb:PutItem"]
        Resource = data.terraform_remote_state.peripherals.outputs.dynamodb_table_arn
      },
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = "${data.terraform_remote_state.peripherals.outputs.ingestion_bucket_arn}/exports/*"
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

module "lambda_gold_to_dynamodb" {
  source = "../../modules/lambda"

  environment    = var.environment
  common_tags    = local.common_tags
  name_prefix    = local.name_prefix
  function_name  = "gold-to-dynamodb"
  description    = "Syncs Gold API key consumption data from S3 to DynamoDB"
  handler        = "handler.handler"
  runtime        = "python3.12"
  timeout        = 60
  memory_size    = 128
  role_arn       = aws_iam_role.gold_to_dynamodb_lambda.arn
  source_file    = "${path.module}/../../../apps/lambda/gold_to_dynamodb/handler.py"
  output_zip_path = "${path.module}/.lambda_zip/gold_to_dynamodb.zip"

  environment_variables = {
    DYNAMODB_TABLE = data.terraform_remote_state.peripherals.outputs.dynamodb_table_name
  }

  s3_trigger_bucket_arn  = data.terraform_remote_state.peripherals.outputs.ingestion_bucket_arn
  s3_trigger_bucket_name = data.terraform_remote_state.peripherals.outputs.ingestion_bucket_name
  s3_trigger_prefix      = "exports/gold_api_keys/"
  s3_trigger_suffix      = ".json"
}
