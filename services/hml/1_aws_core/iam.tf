###############################################################################
# terraform_hml/iam.tf
#
# IAM roles para ECS tasks do ambiente HML.
#
# Roles criadas:
#   1. dm-hml-ecs-task-execution-role
#      Usada pelo agente ECS para: pull ECR, escrever CloudWatch logs.
#      Attach: AmazonECSTaskExecutionRolePolicy (AWS managed)
#
#   2. dm-hml-ecs-task-role
#      Usada pelo código da aplicação dentro do container para:
#        - DynamoDB: GetItem, PutItem, UpdateItem, DeleteItem, Query, Scan
#        - S3: GetObject, PutObject, ListBucket (bucket hml-ingestion)
#        - Secrets Manager: GetSecretValue (API keys Etherscan, etc.)
###############################################################################

# ----------------------------------------------------------------
# Trust policy — permite que ECS tasks assuma as roles
# ----------------------------------------------------------------
data "aws_iam_policy_document" "ecs_task_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

# ----------------------------------------------------------------
# Role 1: Task Execution Role
# ----------------------------------------------------------------
resource "aws_iam_role" "hml_ecs_task_execution" {
  name               = var.ecs_task_execution_role_name
  assume_role_policy = data.aws_iam_policy_document.ecs_task_trust.json
  tags               = merge(local.common_tags, { Name = var.ecs_task_execution_role_name })
}

resource "aws_iam_role_policy_attachment" "hml_ecs_task_execution_managed" {
  role       = aws_iam_role.hml_ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# ----------------------------------------------------------------
# Role 2: Task Role (application permissions)
# ----------------------------------------------------------------
resource "aws_iam_role" "hml_ecs_task" {
  name               = var.ecs_task_role_name
  assume_role_policy = data.aws_iam_policy_document.ecs_task_trust.json
  tags               = merge(local.common_tags, { Name = var.ecs_task_role_name })
}

data "aws_iam_policy_document" "hml_ecs_task_permissions" {
  statement {
    sid    = "DynamoDBAccess"
    effect = "Allow"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:UpdateItem",
      "dynamodb:DeleteItem",
      "dynamodb:Query",
      "dynamodb:Scan",
      "dynamodb:BatchGetItem",
      "dynamodb:BatchWriteItem",
    ]
    # Wildcard: DynamoDB table is ephemeral (created/destroyed per CI/CD run)
    resources = [
      "arn:aws:dynamodb:${var.region}:*:table/*-hml",
      "arn:aws:dynamodb:${var.region}:*:table/*-hml/index/*",
    ]
  }

  statement {
    sid    = "S3HmlIngestionAccess"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:ListBucket",
    ]
    resources = [
      aws_s3_bucket.hml_ingestion.arn,
      "${aws_s3_bucket.hml_ingestion.arn}/*",
    ]
  }

  statement {
    sid    = "SecretsManagerReadOnly"
    effect = "Allow"
    actions = [
      "secretsmanager:GetSecretValue",
    ]
    resources = ["arn:aws:secretsmanager:${var.region}:*:secret:dm-chain-explorer-hml-*"]
  }

  statement {
    sid    = "SSMReadOnly"
    effect = "Allow"
    actions = [
      "ssm:GetParameter",
      "ssm:GetParametersByPath",
    ]
    resources = ["arn:aws:ssm:${var.region}:*:parameter/etherscan-api-keys*"]
  }

  statement {
    sid    = "KinesisAccess"
    effect = "Allow"
    actions = [
      "kinesis:PutRecord",
      "kinesis:PutRecords",
      "kinesis:GetRecords",
      "kinesis:GetShardIterator",
      "kinesis:DescribeStream",
      "kinesis:DescribeStreamSummary",
      "kinesis:ListShards",
    ]
    # Wildcard: Kinesis streams are ephemeral (created/destroyed per CI/CD run)
    resources = ["arn:aws:kinesis:${var.region}:*:stream/*-hml"]
  }

  statement {
    sid    = "SQSAccess"
    effect = "Allow"
    actions = [
      "sqs:SendMessage",
      "sqs:SendMessageBatch",
      "sqs:ReceiveMessage",
      "sqs:DeleteMessage",
      "sqs:DeleteMessageBatch",
      "sqs:GetQueueUrl",
      "sqs:GetQueueAttributes",
    ]
    # Wildcard: SQS queues are ephemeral (created/destroyed per CI/CD run)
    resources = [
      "arn:aws:sqs:${var.region}:*:*-hml",
      "arn:aws:sqs:${var.region}:*:*-dlq-hml",
    ]
  }

  statement {
    sid    = "CloudWatchLogsAccess"
    effect = "Allow"
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
      "logs:DescribeLogStreams",
    ]
    # Terraform-managed log group /apps/dm-chain-explorer-hml (cloudwatch.tf)
    resources = ["arn:aws:logs:${var.region}:*:log-group:/apps/dm-chain-explorer-hml*"]
  }
}

resource "aws_iam_role_policy" "hml_ecs_task_permissions" {
  name   = "dm-hml-ecs-task-permissions"
  role   = aws_iam_role.hml_ecs_task.id
  policy = data.aws_iam_policy_document.hml_ecs_task_permissions.json
}

# ----------------------------------------------------------------
# Role 3: Firehose Role (Firehose → S3)
# Persistent so ephemeral Firehose streams created via CLI can
# assume it without IAM propagation delay.
# ----------------------------------------------------------------
data "aws_caller_identity" "current" {}

resource "aws_iam_role" "hml_firehose" {
  name = "dm-hml-firehose-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "firehose.amazonaws.com"
      }
      Action = "sts:AssumeRole"
      Condition = {
        StringEquals = {
          "sts:ExternalId" = data.aws_caller_identity.current.account_id
        }
      }
    }]
  })

  tags = merge(local.common_tags, { Name = "dm-hml-firehose-role" })
}

resource "aws_iam_role_policy" "hml_firehose_s3" {
  name = "dm-hml-firehose-s3-policy"
  role = aws_iam_role.hml_firehose.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3WriteAccess"
        Effect = "Allow"
        Action = [
          "s3:AbortMultipartUpload",
          "s3:GetBucketLocation",
          "s3:GetObject",
          "s3:ListBucket",
          "s3:ListBucketMultipartUploads",
          "s3:PutObject",
        ]
        Resource = [
          aws_s3_bucket.hml_ingestion.arn,
          "${aws_s3_bucket.hml_ingestion.arn}/*",
        ]
      },
      {
        Sid    = "KinesisReadAccess"
        Effect = "Allow"
        Action = [
          "kinesis:DescribeStream",
          "kinesis:GetShardIterator",
          "kinesis:GetRecords",
          "kinesis:ListShards",
        ]
        # Wildcard: Kinesis streams are ephemeral (created/destroyed per CI/CD run)
        Resource = ["arn:aws:kinesis:${var.region}:*:stream/*-hml"]
      },
    ]
  })
}
