# ── ECS Task Execution Role ───────────────────────────────────────────────────
data "aws_iam_policy_document" "ecs_task_execution_assume" {
  count = var.create_ecs_roles ? 1 : 0
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ecs_task_execution" {
  count              = var.create_ecs_roles ? 1 : 0
  name               = "${var.name_prefix}-ecs-task-execution-role-${var.environment}"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_execution_assume[0].json
  tags               = var.common_tags
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution_managed" {
  count      = var.create_ecs_roles ? 1 : 0
  role       = aws_iam_role.ecs_task_execution[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "ecs_task_execution_extras" {
  count = var.create_ecs_roles ? 1 : 0
  name  = "${var.name_prefix}-ecs-task-execution-extras-${var.environment}"
  role  = aws_iam_role.ecs_task_execution[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue", "kms:Decrypt"]
      Resource = "arn:aws:secretsmanager:${var.region}:${var.account_id}:secret:${var.name_prefix}-*"
    }]
  })
}

# ── ECS Task Role ─────────────────────────────────────────────────────────────
resource "aws_iam_role" "ecs_task" {
  count              = var.create_ecs_roles ? 1 : 0
  name               = "${var.name_prefix}-ecs-task-role-${var.environment}"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_execution_assume[0].json
  tags               = var.common_tags
}

resource "aws_iam_role_policy" "ecs_task" {
  count = var.create_ecs_roles ? 1 : 0
  name  = "${var.name_prefix}-ecs-task-permissions-${var.environment}"
  role  = aws_iam_role.ecs_task[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(
      [{
        Sid    = "KinesisAccess"
        Effect = "Allow"
        Action = [
          "kinesis:PutRecord", "kinesis:PutRecords", "kinesis:GetRecords",
          "kinesis:GetShardIterator", "kinesis:DescribeStream",
          "kinesis:DescribeStreamSummary", "kinesis:ListShards",
        ]
        Resource = "arn:aws:kinesis:*:*:stream/mainnet-*-${var.kinesis_stream_suffix}"
      },
      {
        Sid    = "SQSAccess"
        Effect = "Allow"
        Action = [
          "sqs:SendMessage", "sqs:SendMessageBatch", "sqs:ReceiveMessage",
          "sqs:DeleteMessage", "sqs:DeleteMessageBatch",
          "sqs:GetQueueUrl", "sqs:GetQueueAttributes",
        ]
        Resource = "arn:aws:sqs:*:*:mainnet-*-${var.sqs_queue_suffix}"
      },
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = [
          "arn:aws:logs:${var.region}:${var.account_id}:log-group:/apps/${var.name_prefix}*",
          "arn:aws:logs:${var.region}:${var.account_id}:log-group:/ecs/${var.name_prefix}*",
        ]
      },
      {
        Sid    = "SSMParameterStore"
        Effect = "Allow"
        Action = ["ssm:GetParameter", "ssm:GetParameters", "ssm:GetParametersByPath"]
        Resource = [
          "arn:aws:ssm:*:*:parameter/web3-api-keys/*",
          "arn:aws:ssm:*:*:parameter/etherscan-api-keys",
          "arn:aws:ssm:*:*:parameter/etherscan-api-keys/*",
        ]
      },
      {
        Sid    = "SecretsManagerAccess"
        Effect = "Allow"
        Action = ["secretsmanager:GetSecretValue", "secretsmanager:DescribeSecret"]
        Resource = "arn:aws:secretsmanager:${var.region}:${var.account_id}:secret:${var.name_prefix}-*"
      },
      {
        Sid    = "DynamoDBAccess"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem",
          "dynamodb:DeleteItem", "dynamodb:Query", "dynamodb:BatchWriteItem",
          "dynamodb:BatchGetItem", "dynamodb:Scan", "dynamodb:DescribeTable",
        ]
        Resource = "arn:aws:dynamodb:*:*:table/${var.dynamodb_table_name}"
      },
      {
        Sid    = "FirehoseAccess"
        Effect = "Allow"
        Action = ["firehose:PutRecord", "firehose:PutRecordBatch"]
        Resource = "arn:aws:firehose:*:*:deliverystream/firehose-mainnet-*-${var.kinesis_stream_suffix}"
      }],
      var.raw_bucket_arn != "" ? [{
        Sid    = "S3Access"
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket", "s3:GetBucketLocation"]
        Resource = [
          var.raw_bucket_arn, "${var.raw_bucket_arn}/*",
          var.lakehouse_bucket_arn, "${var.lakehouse_bucket_arn}/*",
        ]
      }] : []
    )
  })
}

# ── Databricks Cross-Account Role ─────────────────────────────────────────────

# Initial trust policy — Databricks account only.
# The self-assume statement is added AFTER role creation via null_resource below
# to avoid AWS's "invalid principal" error on CreateRole.
data "aws_iam_policy_document" "databricks_cross_account_assume_initial" {
  count = var.create_databricks_roles ? 1 : 0
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${var.databricks_account_id}:root"]
    }
    condition {
      test     = "StringEquals"
      variable = "sts:ExternalId"
      values   = [var.databricks_account_uuid]
    }
  }
}

# Full trust policy (Databricks account + self-assume) — used post-creation only.
data "aws_iam_policy_document" "databricks_cross_account_assume" {
  count = var.create_databricks_roles ? 1 : 0
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${var.databricks_account_id}:root"]
    }
    condition {
      test     = "StringEquals"
      variable = "sts:ExternalId"
      values   = [var.databricks_account_uuid]
    }
  }
  # Self-assume required by Databricks Unity Catalog storage credential validation
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${var.account_id}:role/${var.name_prefix}-databricks-cross-account-role"]
    }
  }
}

resource "aws_iam_role" "databricks_cross_account" {
  count              = var.create_databricks_roles ? 1 : 0
  name               = "${var.name_prefix}-databricks-cross-account-role"
  assume_role_policy = data.aws_iam_policy_document.databricks_cross_account_assume_initial[0].json
  tags               = var.common_tags

  lifecycle {
    # Prevent Terraform from reverting the trust policy to the initial version
    # after null_resource has updated it to include the self-assume statement.
    ignore_changes = [assume_role_policy]
  }
}

# Update trust policy to add self-assume after the role exists.
# AWS only validates principal ARNs on CreateRole; UpdateAssumeRolePolicy allows self-references.
resource "null_resource" "databricks_cross_account_self_assume" {
  count = var.create_databricks_roles ? 1 : 0

  depends_on = [aws_iam_role.databricks_cross_account]

  triggers = {
    role_arn    = aws_iam_role.databricks_cross_account[0].arn
    policy_hash = sha256(data.aws_iam_policy_document.databricks_cross_account_assume[0].json)
  }

  provisioner "local-exec" {
    # AWS IAM is eventually consistent: the self-referential role ARN is rejected as
    # "Invalid principal" for several minutes after CreateRole in us-east-1 and
    # sa-east-1. Wait 90s before first attempt, then retry every 60s up to 8 times.
    # First check if the trust policy already contains the self-assume (idempotency).
    command     = <<-EOF
      ROLE_NAME="${var.name_prefix}-databricks-cross-account-role"
      SELF_ARN="arn:aws:iam::${var.account_id}:role/$ROLE_NAME"
      POLICY_FILE=$(mktemp)
      cat > "$POLICY_FILE" << 'POLICY_EOF'
${data.aws_iam_policy_document.databricks_cross_account_assume[0].json}
POLICY_EOF

      # Idempotency: skip update if self-assume is already present
      EXISTING=$(aws iam get-role --role-name "$ROLE_NAME" \
                   --query 'Role.AssumeRolePolicyDocument' --output json 2>/dev/null || echo "{}")
      if echo "$EXISTING" | grep -qF "$SELF_ARN"; then
        echo "Self-assume already in trust policy — no update needed."
        rm -f "$POLICY_FILE"
        exit 0
      fi

      echo "Waiting 90s for IAM role ARN to propagate before adding self-assume trust policy ..."
      sleep 90
      for attempt in 1 2 3 4 5 6 7 8; do
        echo "Attempt $attempt: updating trust policy for $ROLE_NAME ..."
        if aws iam update-assume-role-policy \
            --role-name "$ROLE_NAME" \
            --policy-document "file://$POLICY_FILE"; then
          echo "Trust policy updated successfully on attempt $attempt."
          rm -f "$POLICY_FILE"
          exit 0
        fi
        echo "Failed (attempt $attempt). Retrying in 60s ..."
        sleep 60
      done
      rm -f "$POLICY_FILE"
      echo "ERROR: Failed to update trust policy after 8 attempts."
      exit 1
    EOF
    interpreter = ["/bin/bash", "-c"]
  }
}

resource "aws_iam_role_policy" "databricks_s3" {
  count = var.create_databricks_roles ? 1 : 0
  name  = "${var.name_prefix}-databricks-s3-access"
  role  = aws_iam_role.databricks_cross_account[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid    = "DatabricksS3"
      Effect = "Allow"
      Action = [
        "s3:GetObject", "s3:GetObjectVersion", "s3:PutObject", "s3:PutObjectAcl",
        "s3:DeleteObject", "s3:DeleteObjectVersion", "s3:ListBucket", "s3:ListBucketVersions",
        "s3:GetBucketLocation", "s3:GetBucketAcl", "s3:GetBucketVersioning",
        "s3:GetEncryptionConfiguration", "s3:GetLifecycleConfiguration", "s3:PutLifecycleConfiguration",
      ]
      Resource = [
        var.lakehouse_bucket_arn, "${var.lakehouse_bucket_arn}/*",
        var.raw_bucket_arn, "${var.raw_bucket_arn}/*",
        var.databricks_bucket_arn, "${var.databricks_bucket_arn}/*",
      ]
    }]
  })
}

resource "aws_iam_role_policy" "databricks_pass_cluster_role" {
  count = var.create_databricks_roles ? 1 : 0
  name  = "${var.name_prefix}-databricks-pass-cluster-role"
  role  = aws_iam_role.databricks_cross_account[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid      = "PassClusterRole"
      Effect   = "Allow"
      Action   = "iam:PassRole"
      Resource = aws_iam_role.databricks_cluster[0].arn
    }]
  })
}

resource "aws_iam_role_policy" "databricks_ec2_vpc_validation" {
  count = var.create_databricks_roles ? 1 : 0
  name  = "${var.name_prefix}-databricks-ec2-vpc-validation"
  role  = aws_iam_role.databricks_cross_account[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        # Read-only EC2 actions needed for VPC/network validation and workspace setup
        Sid    = "DatabricksEC2Describe"
        Effect = "Allow"
        Action = [
          "ec2:DescribeAvailabilityZones",
          "ec2:DescribeIamInstanceProfileAssociations",
          "ec2:DescribeInstanceStatus",
          "ec2:DescribeInstances",
          "ec2:DescribeInternetGateways",
          "ec2:DescribeNatGateways",
          "ec2:DescribeNetworkAcls",
          "ec2:DescribePrefixLists",
          "ec2:DescribeReservedInstancesOfferings",
          "ec2:DescribeRouteTables",
          "ec2:DescribeSecurityGroups",
          "ec2:DescribeSpotInstanceRequests",
          "ec2:DescribeSpotPriceHistory",
          "ec2:DescribeSubnets",
          "ec2:DescribeVolumes",
          "ec2:DescribeVpcAttribute",
          "ec2:DescribeVpcs",
        ]
        Resource = "*"
      },
      {
        # Security group rules management needed for Databricks network setup
        Sid    = "DatabricksSecurityGroupMgmt"
        Effect = "Allow"
        Action = [
          "ec2:AuthorizeSecurityGroupEgress",
          "ec2:AuthorizeSecurityGroupIngress",
          "ec2:RevokeSecurityGroupEgress",
          "ec2:RevokeSecurityGroupIngress",
        ]
        Resource = "arn:aws:ec2:${var.region}:${var.account_id}:security-group/*"
      },
    ]
  })
}

# ── Databricks Cluster Role ───────────────────────────────────────────────────
data "aws_iam_policy_document" "databricks_cluster_assume" {
  count = var.create_databricks_roles ? 1 : 0
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "databricks_cluster" {
  count              = var.create_databricks_roles ? 1 : 0
  name               = "${var.name_prefix}-databricks-cluster-role"
  assume_role_policy = data.aws_iam_policy_document.databricks_cluster_assume[0].json
  tags               = var.common_tags
}

resource "aws_iam_role_policy" "databricks_cluster" {
  count = var.create_databricks_roles ? 1 : 0
  name  = "${var.name_prefix}-databricks-cluster-permissions"
  role  = aws_iam_role.databricks_cluster[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3Access"
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket", "s3:GetBucketLocation", "s3:GetEncryptionConfiguration"]
        Resource = [
          var.raw_bucket_arn, "${var.raw_bucket_arn}/*",
          var.lakehouse_bucket_arn, "${var.lakehouse_bucket_arn}/*",
          var.databricks_bucket_arn, "${var.databricks_bucket_arn}/*",
        ]
      },
      {
        Sid    = "SecretsManagerAccess"
        Effect = "Allow"
        Action = ["secretsmanager:GetSecretValue", "secretsmanager:DescribeSecret"]
        Resource = "arn:aws:secretsmanager:${var.region}:${var.account_id}:secret:${var.name_prefix}-*"
      },
      {
        Sid    = "SSMAccess"
        Effect = "Allow"
        Action = ["ssm:GetParameter", "ssm:GetParameters", "ssm:GetParametersByPath"]
        Resource = [
          "arn:aws:ssm:${var.region}:${var.account_id}:parameter/etherscan-api-keys",
          "arn:aws:ssm:${var.region}:${var.account_id}:parameter/etherscan-api-keys/*",
          "arn:aws:ssm:${var.region}:${var.account_id}:parameter/web3-api-keys/*",
        ]
      }
    ]
  })
}

resource "aws_iam_instance_profile" "databricks_cluster" {
  count = var.create_databricks_roles ? 1 : 0
  name  = "${var.name_prefix}-databricks-cluster-profile"
  role  = aws_iam_role.databricks_cluster[0].name
  tags  = var.common_tags
}

# ── Lambda Execution Role ─────────────────────────────────────────────────────
resource "aws_iam_role" "lambda" {
  count = var.create_lambda_role ? 1 : 0
  name  = "${var.name_prefix}-gold-to-dynamodb-lambda-${var.environment}"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
  tags = var.common_tags
}

resource "aws_iam_role_policy" "lambda" {
  count = var.create_lambda_role ? 1 : 0
  name  = "${var.name_prefix}-gold-to-dynamodb-policy-${var.environment}"
  role  = aws_iam_role.lambda[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["dynamodb:BatchWriteItem", "dynamodb:PutItem"]
        Resource = var.lambda_dynamodb_table_arn
      },
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = "${var.lambda_s3_source_bucket_arn}/exports/*"
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}
