data "archive_file" "this" {
  type        = "zip"
  source_file = var.source_file
  output_path = var.output_zip_path
}

resource "aws_lambda_function" "this" {
  function_name = "${var.name_prefix}-${var.function_name}-${var.environment}"
  description   = var.description
  role          = var.role_arn

  filename         = data.archive_file.this.output_path
  source_code_hash = data.archive_file.this.output_base64sha256
  handler          = var.handler
  runtime          = var.runtime
  timeout          = var.timeout
  memory_size      = var.memory_size

  dynamic "environment" {
    for_each = length(var.environment_variables) > 0 ? [1] : []
    content {
      variables = var.environment_variables
    }
  }

  tags = var.common_tags
}

resource "aws_lambda_permission" "s3_invoke" {
  count         = var.s3_trigger_bucket_arn != "" ? 1 : 0
  statement_id  = "AllowS3Invoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.this.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = var.s3_trigger_bucket_arn
}

resource "aws_s3_bucket_notification" "trigger" {
  count  = var.s3_trigger_bucket_name != "" ? 1 : 0
  bucket = var.s3_trigger_bucket_name

  lambda_function {
    lambda_function_arn = aws_lambda_function.this.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = var.s3_trigger_prefix
    filter_suffix       = var.s3_trigger_suffix
  }

  depends_on = [aws_lambda_permission.s3_invoke]
}
