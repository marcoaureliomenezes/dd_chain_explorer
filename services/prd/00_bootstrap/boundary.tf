# =======================================================================
# Permissions boundary for every IAM role this project's Terraform creates
# (T-A.2 HIGH #3). A permissions boundary is the AWS-standard defence
# against the CreateRole -> PutRolePolicy -> PassRole escalation chain: it
# caps a role's EFFECTIVE permissions to the intersection of its identity
# policies and this boundary, regardless of what any later PutRolePolicy /
# AttachRolePolicy grants that role. It deliberately grants NO `iam:*`
# action at all — a role created under this boundary can never manage IAM,
# no matter what its own inline policy claims.
#
# Enforcement: policies.tf's `ProjectIamRoleCreate` statement requires
# `iam:PermissionsBoundary = aws_iam_policy.ci_boundary.arn` on every
# `iam:CreateRole` call the deploy roles make; `gha_self_mutation_deny`
# denies `iam:PutRolePermissionsBoundary`/`DeleteRolePermissionsBoundary`
# outright so the boundary can never be stripped post-creation.
# =======================================================================

data "aws_iam_policy_document" "ci_boundary" {
  # Merge the existing self-mutation Deny statements (policies.tf) — a
  # boundary-limited role inherits the same self-mutation guard as the
  # roles that created it. Safe to merge here: gha_self_mutation_deny does
  # NOT reference this document, so there is no dependency cycle.
  source_policy_documents = [data.aws_iam_policy_document.gha_self_mutation_deny.json]

  statement {
    sid       = "BoundaryProjectS3Buckets"
    effect    = "Allow"
    actions   = ["s3:*"]
    resources = local.s3_bucket_arns
  }

  statement {
    sid       = "BoundaryProjectDynamoDbTables"
    effect    = "Allow"
    actions   = ["dynamodb:*"]
    resources = local.dynamodb_table_arns
  }

  statement {
    sid       = "BoundaryProjectLambda"
    effect    = "Allow"
    actions   = ["lambda:*"]
    resources = concat(local.lambda_function_arns, local.lambda_layer_arns)
  }

  statement {
    sid       = "BoundaryProjectCloudWatchLogGroups"
    effect    = "Allow"
    actions   = ["logs:*"]
    resources = local.log_group_arns
  }

  statement {
    sid       = "BoundaryProjectEventBridgeRules"
    effect    = "Allow"
    actions   = ["events:*"]
    resources = local.events_rule_arns
  }

  statement {
    sid    = "BoundaryProjectSsmParameters"
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

  # Deliberately no statement grants any `iam:*`, `sts:*` or sensitive
  # network/account-level action — a boundary-limited role's ceiling stops
  # at this project's data-plane resources.
}

resource "aws_iam_policy" "ci_boundary" {
  name        = "dm-chain-explorer-ci-boundary"
  description = "Permissions boundary for every IAM role created by the dd-chain-explorer deploy roles (T-A.2 HIGH #3)"
  policy      = data.aws_iam_policy_document.ci_boundary.json
}
