# -----------------------------------------------------------------------
# ECS Task Execution Role
# Used by ECS agent to pull images and send logs to CloudWatch
# -----------------------------------------------------------------------
data "aws_iam_policy_document" "ecs_task_execution_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ecs_task_execution" {
  name               = "dm-chain-explorer-ecs-task-execution-role"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_execution_assume.json
  tags               = local.common_tags
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution_managed" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Allow pulling from ECR and reading secrets from Secrets Manager
data "aws_iam_policy_document" "ecs_task_execution_extras" {
  statement {
    actions = [
      "secretsmanager:GetSecretValue",
      "kms:Decrypt"
    ]
    resources = ["arn:aws:secretsmanager:${var.region}:${data.aws_caller_identity.current.account_id}:secret:dm-chain-explorer-*"]
  }
}

resource "aws_iam_role_policy" "ecs_task_execution_extras" {
  name   = "dm-ecs-task-execution-extras"
  role   = aws_iam_role.ecs_task_execution.id
  policy = data.aws_iam_policy_document.ecs_task_execution_extras.json
}

# -----------------------------------------------------------------------
# ECS Task Role
# Used by the application running inside the container
# Access: CloudWatch Logs, DynamoDB, S3, SSM
#
# The capture-era streaming grants were removed with the capture layer
# (destroyed 2026-06-22, DRIFT-13/B1) — this role no longer needs
# stream/queue access.
# -----------------------------------------------------------------------
resource "aws_iam_role" "ecs_task" {
  name               = "dm-chain-explorer-ecs-task-role"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_execution_assume.json
  tags               = local.common_tags
}

data "aws_iam_policy_document" "ecs_task_permissions" {
  # S3: read/write to raw and lakehouse buckets
  statement {
    sid = "S3Access"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:ListBucket",
      "s3:GetBucketLocation",
    ]
    resources = [
      local.raw_bucket_arn,
      "${local.raw_bucket_arn}/*",
      local.lakehouse_bucket_arn,
      "${local.lakehouse_bucket_arn}/*",
    ]
  }

  # Secrets Manager: read API keys (Alchemy, Infura, Etherscan)
  statement {
    sid = "SecretsManagerAccess"
    actions = [
      "secretsmanager:GetSecretValue",
      "secretsmanager:DescribeSecret",
    ]
    resources = ["arn:aws:secretsmanager:${var.region}:${data.aws_caller_identity.current.account_id}:secret:dm-chain-explorer-*"]
  }

  # CloudWatch Logs: write application logs
  statement {
    sid = "CloudWatchLogs"
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = [
      "arn:aws:logs:${var.region}:${data.aws_caller_identity.current.account_id}:log-group:/apps/dm-chain-explorer*",
      "arn:aws:logs:${var.region}:${data.aws_caller_identity.current.account_id}:log-group:/ecs/dm-chain-explorer*",
    ]
  }

  # SSM Parameter Store: ler API keys (Alchemy, Infura, Etherscan) — caminho hierárquico
  statement {
    sid = "SSMParameterStore"
    actions = [
      "ssm:GetParameter",
      "ssm:GetParameters",
      "ssm:GetParametersByPath",
    ]
    resources = [
      "arn:aws:ssm:${var.region}:${data.aws_caller_identity.current.account_id}:parameter/web3-api-keys/*",
      "arn:aws:ssm:${var.region}:${data.aws_caller_identity.current.account_id}:parameter/etherscan-api-keys/*",
    ]
  }

  # DynamoDB: read/write to the single-table (dm-chain-explorer)
  statement {
    sid = "DynamoDBAccess"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:UpdateItem",
      "dynamodb:DeleteItem",
    ]
    resources = ["arn:aws:dynamodb:${var.region}:${data.aws_caller_identity.current.account_id}:table/dm-chain-explorer"]
  }
}

resource "aws_iam_role_policy" "ecs_task" {
  name   = "dm-ecs-task-permissions"
  role   = aws_iam_role.ecs_task.id
  policy = data.aws_iam_policy_document.ecs_task_permissions.json
}

# -----------------------------------------------------------------------
# NOTE — Databricks cross-account / cluster IAM roles (E2 role set) removed
# (DRIFT-13/B1). They served the PRD Databricks workspace, destroyed
# 2026-04-11 (ADR-002 — no prod workspace). The load-bearing Databricks UC
# credential for this project is `dm-databricks-dev-s3-role`
# (services/dev/01_peripherals, T-B.12) and `dm-databricks-hml-s3-role`
# (services/hml/04_peripherals, T-B.4) — neither depends on this stack.
# -----------------------------------------------------------------------
