# =======================================================================
# Least-privilege permission policies for the 4 `gha` roles (D14, DRIFT-08,
# SEC-H-02). Every statement is explicit — no managed-policy attachment, no
# `iam:*` on `"*"`. Every Allow statement's `resources` list is built only
# from locals.tf's project-prefix globs, the state bucket/lock table, or the
# artifacts bucket — proven negatively by T-A.3b's `terraform show -json`
# assertion.
# =======================================================================

# -----------------------------------------------------------------------
# Explicit self-mutation Deny — attached to ALL FOUR roles. IAM evaluates
# an explicit Deny before any Allow, so this closes the self-escalation gap
# even though the IAM-role Allow statement below textually overlaps
# `dm-chain-explorer-gha-*` (it does, by design — see locals.iam_role_arns).
# -----------------------------------------------------------------------
data "aws_iam_policy_document" "gha_self_mutation_deny" {
  statement {
    sid       = "DenySelfMutationOfGhaRoles"
    effect    = "Deny"
    actions   = ["iam:*"]
    resources = ["arn:aws:iam::*:role/dm-chain-explorer-gha-*"]
  }

  statement {
    sid    = "DenyUserCredentialEscalation"
    effect = "Deny"
    actions = [
      "iam:CreateAccessKey",
      "iam:AttachUserPolicy",
      "iam:PutUserPolicy",
    ]
    # These actions target IAM *users*, not roles — there is no project-
    # scoped resource ARN to narrow to; a public-repo static-key user is
    # exactly what OIDC replaces, so this Deny is unconditional.
    resources = ["*"]
  }
}

# -----------------------------------------------------------------------
# Deploy permissions — shared by the three deploy roles (dev/hml/prd). All
# three run in the same AWS account; scoping is by project resource-name
# prefix (locals.tf), not by account, matching the existing single-account
# layout. Full lock-table read/write — deploy applies take the lock.
# -----------------------------------------------------------------------
data "aws_iam_policy_document" "gha_deploy_permissions" {
  statement {
    sid    = "TerraformStateBucket"
    effect = "Allow"
    actions = [
      "s3:ListBucket",
      "s3:GetBucketLocation",
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
    ]
    resources = [local.tf_state_bucket_arn, local.tf_state_objects_arn]
  }

  statement {
    sid    = "TerraformStateLock"
    effect = "Allow"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:DeleteItem",
      "dynamodb:DescribeTable",
    ]
    resources = [local.tf_lock_table_arn]
  }

  statement {
    sid    = "ArtifactsBucketRead"
    effect = "Allow"
    actions = [
      "s3:ListBucket",
      "s3:GetBucketLocation",
      "s3:GetObject",
    ]
    resources = [local.artifacts_bucket_arn, "${local.artifacts_bucket_arn}/*"]
  }

  statement {
    sid       = "ProjectS3Buckets"
    effect    = "Allow"
    actions   = ["s3:*"]
    resources = local.s3_bucket_arns
  }

  statement {
    sid       = "ProjectDynamoDbTables"
    effect    = "Allow"
    actions   = ["dynamodb:*"]
    resources = local.dynamodb_table_arns
  }

  statement {
    sid       = "ProjectLambdaFunctions"
    effect    = "Allow"
    actions   = ["lambda:*"]
    resources = local.lambda_function_arns
  }

  statement {
    sid       = "ProjectLambdaLayers"
    effect    = "Allow"
    actions   = ["lambda:*"]
    resources = local.lambda_layer_arns
  }

  statement {
    sid       = "ProjectCloudWatchLogGroups"
    effect    = "Allow"
    actions   = ["logs:*"]
    resources = local.log_group_arns
  }

  statement {
    sid       = "ProjectEventBridgeRules"
    effect    = "Allow"
    actions   = ["events:*"]
    resources = local.events_rule_arns
  }

  statement {
    sid = "ProjectIamRoleManagement"
    # Excludes gha-* roles via the explicit Deny above.
    effect = "Allow"
    actions = [
      "iam:GetRole",
      "iam:GetRolePolicy",
      "iam:ListRolePolicies",
      "iam:ListAttachedRolePolicies",
      "iam:ListInstanceProfilesForRole",
      "iam:CreateRole",
      "iam:DeleteRole",
      "iam:TagRole",
      "iam:UntagRole",
      "iam:PutRolePolicy",
      "iam:DeleteRolePolicy",
      "iam:AttachRolePolicy",
      "iam:DetachRolePolicy",
      "iam:CreateInstanceProfile",
      "iam:DeleteInstanceProfile",
      "iam:AddRoleToInstanceProfile",
      "iam:RemoveRoleFromInstanceProfile",
      "iam:GetInstanceProfile",
    ]
    resources = concat(local.iam_role_arns, local.iam_instance_profile_arns)
  }

  statement {
    sid       = "ProjectIamPassRole"
    effect    = "Allow"
    actions   = ["iam:PassRole"]
    resources = local.iam_role_arns
  }

  statement {
    sid    = "ProjectSsmParameters"
    effect = "Allow"
    actions = [
      "ssm:GetParameter",
      "ssm:GetParameters",
      "ssm:GetParametersByPath",
      "ssm:DescribeParameters",
      "ssm:PutParameter",
      "ssm:DeleteParameter",
      "ssm:AddTagsToResource",
      "ssm:ListTagsForResource",
    ]
    resources = local.ssm_parameter_arns
  }
}

# -----------------------------------------------------------------------
# Read-only plan permissions — no lock-table access at all (the read-only
# plan path runs `terraform plan -lock=false`, F-04); state-bucket read
# only; the artifacts bucket gets scoped write for the layer-build upload
# that plan_on_pr performs (K6), nothing else does.
# -----------------------------------------------------------------------
data "aws_iam_policy_document" "gha_readonly_plan_permissions" {
  statement {
    sid    = "TerraformStateBucketRead"
    effect = "Allow"
    actions = [
      "s3:ListBucket",
      "s3:GetBucketLocation",
      "s3:GetObject",
    ]
    resources = [local.tf_state_bucket_arn, local.tf_state_objects_arn]
  }

  statement {
    sid    = "ArtifactsBucketLayerUpload"
    effect = "Allow"
    actions = [
      "s3:ListBucket",
      "s3:GetBucketLocation",
    ]
    resources = [local.artifacts_bucket_arn]
  }

  statement {
    sid    = "ArtifactsBucketLayerUploadObjects"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
    ]
    resources = [local.artifacts_layer_prefix_rw]
  }

  statement {
    sid    = "ProjectReadOnly"
    effect = "Allow"
    actions = [
      "s3:GetBucket*",
      "s3:ListBucket",
      "s3:GetObject",
      "dynamodb:DescribeTable",
      "dynamodb:ListTagsOfResource",
      "lambda:GetFunction",
      "lambda:GetFunctionConfiguration",
      "lambda:ListVersionsByFunction",
      "lambda:GetLayerVersion",
      "lambda:ListLayerVersions",
      "lambda:GetPolicy",
      "lambda:ListEventSourceMappings",
      "lambda:ListTags",
      "logs:DescribeLogGroups",
      "logs:DescribeLogStreams",
      "logs:ListTagsForResource",
      "events:DescribeRule",
      "events:ListTargetsByRule",
      "events:ListTagsForResource",
      "iam:GetRole",
      "iam:GetRolePolicy",
      "iam:ListRolePolicies",
      "iam:ListAttachedRolePolicies",
      "iam:GetInstanceProfile",
      "ssm:DescribeParameters",
      "ssm:GetParameter",
      "ssm:GetParameters",
      "ssm:GetParametersByPath",
    ]
    resources = concat(
      local.s3_bucket_arns,
      local.dynamodb_table_arns,
      local.lambda_function_arns,
      local.lambda_layer_arns,
      local.log_group_arns,
      local.events_rule_arns,
      local.iam_role_arns,
      local.iam_instance_profile_arns,
      local.ssm_parameter_arns,
    )
  }
}
