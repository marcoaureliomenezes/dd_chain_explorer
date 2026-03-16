###############################################################################
# Lambda: gold_to_dynamodb
#
# Triggered by S3 PutObject events on the Gold exports prefix.
# Reads JSON rows and batch-writes them to DynamoDB (CONSUMPTION entity).
###############################################################################

# ---- IAM Role for Lambda ----
resource "aws_iam_role" "gold_to_dynamodb_lambda" {
  name = "${local.name_prefix}-gold-to-dynamodb-lambda"

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

resource "aws_iam_role_policy" "gold_to_dynamodb_lambda" {
  name = "${local.name_prefix}-gold-to-dynamodb-policy"
  role = aws_iam_role.gold_to_dynamodb_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:BatchWriteItem",
          "dynamodb:PutItem",
        ]
        Resource = aws_dynamodb_table.chain_explorer.arn
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
        ]
        Resource = "${aws_s3_bucket.ingestion.arn}/exports/*"
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

# ---- Lambda function ----
data "archive_file" "gold_to_dynamodb" {
  type        = "zip"
  source_file = "${path.module}/../../../lambda/gold_to_dynamodb/handler.py"
  output_path = "${path.module}/.lambda_zip/gold_to_dynamodb.zip"
}

resource "aws_lambda_function" "gold_to_dynamodb" {
  function_name = "${local.name_prefix}-gold-to-dynamodb"
  description   = "Syncs Gold API key consumption data from S3 to DynamoDB"
  role          = aws_iam_role.gold_to_dynamodb_lambda.arn

  filename         = data.archive_file.gold_to_dynamodb.output_path
  source_code_hash = data.archive_file.gold_to_dynamodb.output_base64sha256
  handler          = "handler.handler"
  runtime          = "python3.12"
  timeout          = 60
  memory_size      = 128

  environment {
    variables = {
      DYNAMODB_TABLE = var.dynamodb_table_name
    }
  }

  tags = local.common_tags
}

# ---- S3 trigger ----
resource "aws_lambda_permission" "s3_invoke" {
  statement_id  = "AllowS3Invoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.gold_to_dynamodb.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.ingestion.arn
}

resource "aws_s3_bucket_notification" "gold_export" {
  bucket = aws_s3_bucket.ingestion.id

  lambda_function {
    lambda_function_arn = aws_lambda_function.gold_to_dynamodb.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "exports/gold_api_keys/"
    filter_suffix       = ".json"
  }

  depends_on = [aws_lambda_permission.s3_invoke]
}
