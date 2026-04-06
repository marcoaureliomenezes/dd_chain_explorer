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
# Access: Kinesis, SQS, CloudWatch Logs, DynamoDB, S3, SSM
# -----------------------------------------------------------------------
resource "aws_iam_role" "ecs_task" {
  name               = "dm-chain-explorer-ecs-task-role"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_execution_assume.json
  tags               = local.common_tags
}

data "aws_iam_policy_document" "ecs_task_permissions" {
  # Kinesis Data Streams: produce and consume records
  statement {
    sid = "KinesisAccess"
    actions = [
      "kinesis:PutRecord",
      "kinesis:PutRecords",
      "kinesis:GetRecords",
      "kinesis:GetShardIterator",
      "kinesis:DescribeStream",
      "kinesis:DescribeStreamSummary",
      "kinesis:ListShards",
    ]
    resources = ["arn:aws:kinesis:*:*:stream/mainnet-*-prd"]
  }

  # Firehose Direct Put: write blocks and decoded txs directly to delivery streams
  statement {
    sid = "FirehoseAccess"
    actions = [
      "firehose:PutRecord",
      "firehose:PutRecordBatch",
    ]
    resources = ["arn:aws:firehose:*:*:deliverystream/firehose-mainnet-*-prd"]
  }

  # SQS: send and receive messages between streaming jobs
  statement {
    sid = "SQSAccess"
    actions = [
      "sqs:SendMessage",
      "sqs:SendMessageBatch",
      "sqs:ReceiveMessage",
      "sqs:DeleteMessage",
      "sqs:DeleteMessageBatch",
      "sqs:GetQueueUrl",
      "sqs:GetQueueAttributes",
    ]
    resources = ["arn:aws:sqs:*:*:mainnet-*-prd"]
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
    resources = ["arn:aws:ssm:*:*:parameter/web3-api-keys/*", "arn:aws:ssm:*:*:parameter/etherscan-api-keys/*"]
  }

  # DynamoDB: read/write to the single-table (dm-chain-explorer)
  statement {
    sid = "DynamoDBAccess"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:UpdateItem",
      "dynamodb:DeleteItem",
      "dynamodb:Query",
      "dynamodb:BatchWriteItem",
      "dynamodb:BatchGetItem",
      "dynamodb:Scan",
      "dynamodb:DescribeTable",
    ]
    resources = ["arn:aws:dynamodb:*:*:table/dm-chain-explorer"]
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

# Initial trust policy — Databricks account root only.
# The self-assume statement is added AFTER role creation via null_resource below
# to avoid AWS's "invalid principal" error on CreateRole (chicken-and-egg).
data "aws_iam_policy_document" "databricks_cross_account_assume_initial" {
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
# Self-assume is required by Databricks Unity Catalog storage credential validation.
data "aws_iam_policy_document" "databricks_cross_account_assume" {
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
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/dm-chain-explorer-databricks-cross-account-role"]
    }
  }
}

resource "aws_iam_role" "databricks_cross_account" {
  name               = "dm-chain-explorer-databricks-cross-account-role"
  assume_role_policy = data.aws_iam_policy_document.databricks_cross_account_assume_initial.json
  tags               = local.common_tags

  lifecycle {
    # Prevent Terraform from reverting the trust policy after null_resource updates it.
    ignore_changes = [assume_role_policy]
  }
}

# Updates the trust policy to add self-assume after the role exists.
# AWS only validates principal ARNs on CreateRole; UpdateAssumeRolePolicy allows self-references.
# AWS IAM in sa-east-1 takes several minutes to propagate a new role ARN as a valid principal.
resource "null_resource" "databricks_cross_account_self_assume" {
  depends_on = [aws_iam_role.databricks_cross_account]

  triggers = {
    role_arn    = aws_iam_role.databricks_cross_account.arn
    policy_hash = sha256(data.aws_iam_policy_document.databricks_cross_account_assume.json)
  }

  provisioner "local-exec" {
    command     = <<-EOF
      ROLE_NAME="dm-chain-explorer-databricks-cross-account-role"
      ACCOUNT_ID="${data.aws_caller_identity.current.account_id}"
      SELF_ARN="arn:aws:iam::$ACCOUNT_ID:role/$ROLE_NAME"
      POLICY_FILE=$(mktemp)
      cat > "$POLICY_FILE" << 'POLICY_EOF'
${data.aws_iam_policy_document.databricks_cross_account_assume.json}
POLICY_EOF

      # Idempotency: skip update only if BOTH the self-assume ARN and the correct
      # ExternalId are already present (prevents stale ExternalId from blocking validation).
      EXPECTED_EXT_ID="${var.databricks_account_uuid}"
      EXISTING=$(aws iam get-role --role-name "$ROLE_NAME" \
                   --query 'Role.AssumeRolePolicyDocument' --output json 2>/dev/null || echo "{}")
      EXISTING_EXT_ID=$(echo "$EXISTING" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for stmt in data.get('Statement', []):
    cond = stmt.get('Condition', {}).get('StringEquals', {})
    if 'sts:ExternalId' in cond:
        print(cond['sts:ExternalId']); break
" 2>/dev/null || true)
      HAS_SELF=$(echo "$EXISTING" | grep -cF "$SELF_ARN" 2>/dev/null || echo "0")
      if [[ "$HAS_SELF" -gt "0" && "$EXISTING_EXT_ID" == "$EXPECTED_EXT_ID" ]]; then
        echo "Trust policy already has correct ExternalId ($EXISTING_EXT_ID) and self-assume — no update needed."
        rm -f "$POLICY_FILE"
        exit 0
      fi
      echo "Trust policy needs update: HAS_SELF=$HAS_SELF, EXISTING_EXT_ID=$EXISTING_EXT_ID, EXPECTED_EXT_ID=$EXPECTED_EXT_ID"

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

data "aws_iam_policy_document" "databricks_s3_access" {
  statement {
    sid = "DatabricksS3Lakehouse"
    actions = [
      # Object operations
      "s3:GetObject",
      "s3:GetObjectVersion",
      "s3:PutObject",
      "s3:PutObjectAcl",
      "s3:DeleteObject",
      "s3:DeleteObjectVersion",
      # Bucket operations
      "s3:ListBucket",
      "s3:ListBucketVersions",
      "s3:GetBucketLocation",
      "s3:GetBucketAcl",
      "s3:GetBucketVersioning",
      "s3:GetEncryptionConfiguration",
      "s3:GetLifecycleConfiguration",
      "s3:PutLifecycleConfiguration",
    ]
    resources = [
      local.lakehouse_bucket_arn,
      "${local.lakehouse_bucket_arn}/*",
      local.raw_bucket_arn,
      "${local.raw_bucket_arn}/*",
      local.databricks_bucket_arn,
      "${local.databricks_bucket_arn}/*",
    ]
  }
}

resource "aws_iam_role_policy" "databricks_s3" {
  name   = "dm-databricks-s3-access"
  role   = aws_iam_role.databricks_cross_account.id
  policy = data.aws_iam_policy_document.databricks_s3_access.json
}

# -----------------------------------------------------------------------
# Databricks cross-account EC2 permissions (required for workspace validation)
# https://docs.databricks.com/administration-guide/account-settings-e2/credentials.html
# -----------------------------------------------------------------------
data "aws_iam_policy_document" "databricks_cross_account_ec2" {
  statement {
    sid = "DatabricksEC2"
    actions = [
      "ec2:AssignPrivateIpAddresses",
      "ec2:AllocateAddress",
      "ec2:AssociateIamInstanceProfile",
      "ec2:AttachVolume",
      "ec2:AuthorizeSecurityGroupEgress",
      "ec2:AuthorizeSecurityGroupIngress",
      "ec2:CancelSpotInstanceRequests",
      "ec2:CreateDhcpOptions",
      "ec2:CreateFleet",
      "ec2:CreateInternetGateway",
      "ec2:CreateLaunchTemplate",
      "ec2:CreateLaunchTemplateVersion",
      "ec2:CreateNatGateway",
      "ec2:CreateNetworkAcl",
      "ec2:CreateNetworkAclEntry",
      "ec2:CreateNetworkInterface",
      "ec2:CreateNetworkInterfacePermission",
      "ec2:CreatePlacementGroup",
      "ec2:CreateRoute",
      "ec2:CreateRouteTable",
      "ec2:CreateSecurityGroup",
      "ec2:CreateSubnet",
      "ec2:CreateTags",
      "ec2:CreateVolume",
      "ec2:CreateVpc",
      "ec2:CreateVpcEndpoint",
      "ec2:DeleteDhcpOptions",
      "ec2:DeleteFleets",
      "ec2:DeleteInternetGateway",
      "ec2:DeleteLaunchTemplate",
      "ec2:DeleteLaunchTemplateVersions",
      "ec2:DeleteNatGateway",
      "ec2:DeleteNetworkAcl",
      "ec2:DeleteNetworkAclEntry",
      "ec2:DeleteNetworkInterface",
      "ec2:DeleteNetworkInterfacePermission",
      "ec2:DeletePlacementGroup",
      "ec2:DeleteRoute",
      "ec2:DeleteRouteTable",
      "ec2:DeleteSecurityGroup",
      "ec2:DeleteSubnet",
      "ec2:DeleteTags",
      "ec2:DeleteVolume",
      "ec2:DeleteVpc",
      "ec2:DeleteVpcEndpoints",
      "ec2:DescribeAvailabilityZones",
      "ec2:DescribeDhcpOptions",
      "ec2:DescribeFleetHistory",
      "ec2:DescribeFleetInstances",
      "ec2:DescribeFleets",
      "ec2:DescribeIamInstanceProfileAssociations",
      "ec2:DescribeInstanceStatus",
      "ec2:DescribeInstances",
      "ec2:DescribeInternetGateways",
      "ec2:DescribeLaunchTemplates",
      "ec2:DescribeLaunchTemplateVersions",
      "ec2:DescribeNatGateways",
      "ec2:DescribeNetworkAcls",
      "ec2:DescribeNetworkInterfaces",
      "ec2:DescribePlacementGroups",
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
      "ec2:DetachInternetGateway",
      "ec2:DetachVolume",
      "ec2:DisassociateIamInstanceProfile",
      "ec2:DisassociateRouteTable",
      "ec2:GetLaunchTemplateData",
      "ec2:GetSpotPlacementScores",
      "ec2:ModifyFleet",
      "ec2:ModifyInstanceAttribute",
      "ec2:ModifyLaunchTemplate",
      "ec2:ModifyNetworkInterfaceAttribute",
      "ec2:ModifyVolume",
      "ec2:ModifyVpcAttribute",
      "ec2:ReplaceIamInstanceProfileAssociation",
      "ec2:RequestSpotInstances",
      "ec2:ReleaseAddress",
      "ec2:RevokeSecurityGroupEgress",
      "ec2:RevokeSecurityGroupIngress",
      "ec2:RunInstances",
      "ec2:TerminateInstances",
    ]
    resources = ["*"]
  }

  statement {
    sid = "DatabricksIAMPassRole"
    actions = [
      "iam:CreateServiceLinkedRole",
      "iam:PutRolePolicy",
    ]
    resources = ["arn:aws:iam::*:role/aws-service-role/spot.amazonaws.com/AWSServiceRoleForEC2Spot"]
    condition {
      test     = "StringLike"
      variable = "iam:AWSServiceName"
      values   = ["spot.amazonaws.com"]
    }
  }

  # PassRole: permite que Databricks atribua o instance profile (cluster role) a instâncias EC2
  statement {
    sid       = "PassRoleForClusterProfile"
    actions   = ["iam:PassRole"]
    resources = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/dm-chain-explorer-databricks-cluster-role"]
  }
}

resource "aws_iam_role_policy" "databricks_cross_account_ec2" {
  name   = "dm-databricks-ec2-access"
  role   = aws_iam_role.databricks_cross_account.id
  policy = data.aws_iam_policy_document.databricks_cross_account_ec2.json
}

# -----------------------------------------------------------------------
# Databricks Cluster Instance Profile
# Used by Databricks cluster nodes (EC2) to access MSK, S3, SSM
# -----------------------------------------------------------------------
data "aws_iam_policy_document" "databricks_cluster_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "databricks_cluster" {
  name               = "dm-chain-explorer-databricks-cluster-role"
  assume_role_policy = data.aws_iam_policy_document.databricks_cluster_assume.json
  tags               = local.common_tags
}

data "aws_iam_policy_document" "databricks_cluster_permissions" {
  # S3: read/write to raw, lakehouse, and Databricks buckets
  statement {
    sid = "S3Access"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:ListBucket",
      "s3:GetBucketLocation",
      "s3:GetEncryptionConfiguration",
    ]
    resources = [
      local.raw_bucket_arn,
      "${local.raw_bucket_arn}/*",
      local.lakehouse_bucket_arn,
      "${local.lakehouse_bucket_arn}/*",
      local.databricks_bucket_arn,
      "${local.databricks_bucket_arn}/*",
    ]
  }

  # S3: Auto Loader reads from raw/ (Firehose delivery)
  # (S3 access already covered by S3Access statement above)

  # Secrets Manager: read API keys
  statement {
    sid = "SecretsManagerAccess"
    actions = [
      "secretsmanager:GetSecretValue",
      "secretsmanager:DescribeSecret",
    ]
    resources = ["arn:aws:secretsmanager:${var.region}:${data.aws_caller_identity.current.account_id}:secret:dm-chain-explorer-*"]
  }

  # SSM Parameter Store: read API keys
  statement {
    sid = "SSMAccess"
    actions = [
      "ssm:GetParameter",
      "ssm:GetParameters",
      "ssm:GetParametersByPath",
    ]
    resources = [
      "arn:aws:ssm:${var.region}:${data.aws_caller_identity.current.account_id}:parameter/etherscan-api-keys/*",
      "arn:aws:ssm:${var.region}:${data.aws_caller_identity.current.account_id}:parameter/web3-api-keys/*",
    ]
  }
}

resource "aws_iam_role_policy" "databricks_cluster" {
  name   = "dm-databricks-cluster-permissions"
  role   = aws_iam_role.databricks_cluster.id
  policy = data.aws_iam_policy_document.databricks_cluster_permissions.json
}

resource "aws_iam_instance_profile" "databricks_cluster" {
  name = "dm-chain-explorer-databricks-cluster-profile"
  role = aws_iam_role.databricks_cluster.name
  tags = local.common_tags
}
