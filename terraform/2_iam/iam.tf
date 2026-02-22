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
    resources = ["*"]
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
# Access: MSK (Kafka), DynamoDB, S3, Secrets Manager
# -----------------------------------------------------------------------
resource "aws_iam_role" "ecs_task" {
  name               = "dm-chain-explorer-ecs-task-role"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_execution_assume.json
}

data "aws_iam_policy_document" "ecs_task_permissions" {
  # Kafka MSK: connect and describe cluster
  statement {
    sid = "MSKAccess"
    actions = [
      "kafka-cluster:Connect",
      "kafka-cluster:AlterCluster",
      "kafka-cluster:DescribeCluster",
      "kafka-cluster:DescribeTopic",
      "kafka-cluster:CreateTopic",
      "kafka-cluster:WriteData",
      "kafka-cluster:ReadData",
    ]
    resources = ["*"]
  }

  # DynamoDB: API key consumption table + popular contracts table
  statement {
    sid = "DynamoDBAccess"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:UpdateItem",
      "dynamodb:DeleteItem",
      "dynamodb:Query",
      "dynamodb:Scan",
      "dynamodb:BatchWriteItem",
    ]
    resources = ["*"]
  }

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
      data.terraform_remote_state.s3.outputs.raw_bucket_arn,
      "${data.terraform_remote_state.s3.outputs.raw_bucket_arn}/*",
      data.terraform_remote_state.s3.outputs.lakehouse_bucket_arn,
      "${data.terraform_remote_state.s3.outputs.lakehouse_bucket_arn}/*",
    ]
  }

  # Secrets Manager: read API keys (Alchemy, Infura, Etherscan)
  statement {
    sid = "SecretsManagerAccess"
    actions = [
      "secretsmanager:GetSecretValue",
      "secretsmanager:DescribeSecret",
    ]
    resources = ["*"]
  }

  # CloudWatch Logs: write application logs
  statement {
    sid = "CloudWatchLogs"
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "ecs_task" {
  name   = "dm-ecs-task-permissions"
  role   = aws_iam_role.ecs_task.id
  policy = data.aws_iam_policy_document.ecs_task_permissions.json
}

# -----------------------------------------------------------------------
# Databricks Cross-Account IAM Role
# Allows Databricks to access S3 buckets (lakehouse + raw)
# -----------------------------------------------------------------------
data "aws_iam_policy_document" "databricks_cross_account_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type = "AWS"
      # Databricks AWS control-plane account
      identifiers = ["arn:aws:iam::${var.databricks_account_id}:root"]
    }
    condition {
      test     = "StringEquals"
      variable = "sts:ExternalId"
      values   = ["databricks-cross-account"]
    }
  }
}

resource "aws_iam_role" "databricks_cross_account" {
  name               = "dm-chain-explorer-databricks-cross-account-role"
  assume_role_policy = data.aws_iam_policy_document.databricks_cross_account_assume.json
}

data "aws_iam_policy_document" "databricks_s3_access" {
  statement {
    sid = "DatabricksS3Lakehouse"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:ListBucket",
      "s3:GetBucketLocation",
      "s3:GetEncryptionConfiguration",
      "s3:GetLifecycleConfiguration",
    ]
    resources = [
      data.terraform_remote_state.s3.outputs.lakehouse_bucket_arn,
      "${data.terraform_remote_state.s3.outputs.lakehouse_bucket_arn}/*",
      data.terraform_remote_state.s3.outputs.raw_bucket_arn,
      "${data.terraform_remote_state.s3.outputs.raw_bucket_arn}/*",
    ]
  }
}

resource "aws_iam_role_policy" "databricks_s3" {
  name   = "dm-databricks-s3-access"
  role   = aws_iam_role.databricks_cross_account.id
  policy = data.aws_iam_policy_document.databricks_s3_access.json
}
