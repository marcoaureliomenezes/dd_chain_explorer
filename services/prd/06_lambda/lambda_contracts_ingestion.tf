###############################################################################
# Lambda: contracts_ingestion (PROD)
#
# Triggered by EventBridge Scheduler (hourly).
# Fetches contract transactions from Etherscan API and writes JSON to S3.
# Databricks workflow then loads S3 → Bronze → Silver.
#
# Replaces: Airflow dag_hourly_2_contracts_transactions.py + DockerOperator
###############################################################################

# ---- Lambda Layer: dm_chain_utils + requests ----

resource "aws_lambda_layer_version" "dm_chain_utils" {
  layer_name          = "${local.name_prefix}-dm-chain-utils"
  filename            = "${path.module}/.lambda_zip/dm_chain_utils_layer.zip"
  source_code_hash    = filebase64sha256("${path.module}/.lambda_zip/dm_chain_utils_layer.zip")
  compatible_runtimes = ["python3.12"]
  description         = "dm_chain_utils library + requests for Lambda functions"
}

# ---- IAM Role ----

resource "aws_iam_role" "contracts_ingestion_lambda" {
  name = "${local.name_prefix}-contracts-ingestion-lambda"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy" "contracts_ingestion_lambda" {
  name = "${local.name_prefix}-contracts-ingestion-policy"
  role = aws_iam_role.contracts_ingestion_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:Query",
          "dynamodb:GetItem",
          "dynamodb:Scan",
        ]
        Resource = data.terraform_remote_state.dynamodb.outputs.dynamodb_table_arn
      },
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:HeadObject",
        ]
        Resource = "${data.terraform_remote_state.s3.outputs.raw_bucket_arn}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "ssm:GetParametersByPath",
          "ssm:GetParameter",
        ]
        Resource = [
          "arn:aws:ssm:${var.aws_region}:*:parameter/etherscan-api-keys/*",
          "arn:aws:ssm:${var.aws_region}:*:parameter/etherscan-api-keys",
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
        ]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

# ---- Lambda Function ----

data "archive_file" "contracts_ingestion" {
  type        = "zip"
  source_file = "${path.module}/../../../lambda/contracts_ingestion/handler.py"
  output_path = "${path.module}/.lambda_zip/contracts_ingestion.zip"
}

resource "aws_lambda_function" "contracts_ingestion" {
  function_name = "${local.name_prefix}-contracts-ingestion"
  description   = "Fetches contract transactions from Etherscan and writes JSON to S3"
  role          = aws_iam_role.contracts_ingestion_lambda.arn

  filename         = data.archive_file.contracts_ingestion.output_path
  source_code_hash = data.archive_file.contracts_ingestion.output_base64sha256
  handler          = "handler.handler"
  runtime          = "python3.12"
  timeout          = 300
  memory_size      = 256

  layers = [aws_lambda_layer_version.dm_chain_utils.arn]

  environment {
    variables = {
      S3_BUCKET            = data.terraform_remote_state.s3.outputs.raw_bucket_name
      S3_BUCKET_PREFIX     = "batch"
      NETWORK              = "mainnet"
      SSM_ETHERSCAN_PATH   = "/etherscan-api-keys"
      DYNAMODB_TABLE       = data.terraform_remote_state.dynamodb.outputs.dynamodb_table_name
      CLOUDWATCH_LOG_GROUP = data.terraform_remote_state.kinesis_sqs.outputs.cloudwatch_log_group_name
    }
  }

  tags = local.common_tags
}

# ---- EventBridge Scheduler (hourly) ----

resource "aws_iam_role" "eventbridge_contracts_ingestion" {
  name = "${local.name_prefix}-eb-contracts-ingestion"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "scheduler.amazonaws.com"
        }
      }
    ]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy" "eventbridge_invoke_contracts_ingestion" {
  name = "${local.name_prefix}-eb-invoke-contracts-ingestion"
  role = aws_iam_role.eventbridge_contracts_ingestion.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["lambda:InvokeFunction"]
        Resource = aws_lambda_function.contracts_ingestion.arn
      }
    ]
  })
}

resource "aws_scheduler_schedule" "contracts_ingestion_hourly" {
  name       = "${local.name_prefix}-contracts-ingestion-hourly"
  group_name = "default"

  schedule_expression          = "rate(1 hour)"
  schedule_expression_timezone = "America/Sao_Paulo"

  target {
    arn      = aws_lambda_function.contracts_ingestion.arn
    role_arn = aws_iam_role.eventbridge_contracts_ingestion.arn
  }

  flexible_time_window {
    mode = "OFF"
  }
}
