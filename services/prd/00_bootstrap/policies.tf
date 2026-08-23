# =======================================================================
# Least-privilege permission policies for the 4 `gha` roles (D14, DRIFT-08,
# SEC-H-02). Every statement is explicit — no managed-policy attachment, no
# `iam:*` on `"*"`. Every Allow statement's `resources` list is built only
# from locals.tf's project-prefix globs, the state bucket/lock table, or the
# artifacts bucket — proven negatively by T-A.3b's `terraform show -json`
# assertion.
#
# Hardened per the T-A.2 security verdict (2026-08-23T164159Z, REJECTED —
# 3 HIGH): the broad `s3:*`/`dynamodb:*`/`iam:*` Allow statements below are
# deliberately wide (glob resource scoping, not a per-action allowlist) —
# what closes each HIGH is an explicit Deny that survives regardless of how
# wide the Allow ever grows (state-backend destructive actions, project
# bucket public-exposure actions), plus a permissions boundary + condition
# keys on the one action pair (iam:CreateRole + iam:PassRole) that is a
# reproducible path to account admin if left unconditioned.
# =======================================================================

# -----------------------------------------------------------------------
# Explicit Deny statements — attached to ALL FOUR roles via
# gha_self_mutation_deny (iam.tf). IAM evaluates an explicit Deny before
# any Allow, so every statement here closes a gap regardless of how the
# Allow statements below are written or later widened.
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

  # T-A.2 HIGH #2 — the broad ProjectS3Buckets/ProjectDynamoDbTables Allow
  # statements below textually cover the terraform state bucket, the lock
  # table and the artifacts bucket (they all match a `dm-chain-explorer-*`
  # or `dm-*` prefix). This Deny keeps every destructive/config action on
  # the state backend off-limits no matter how the Allow grants widen.
  statement {
    sid    = "DenyStateBackendDestructiveActions"
    effect = "Deny"
    actions = [
      "s3:DeleteBucket",
      "s3:PutBucketVersioning",
      "s3:DeleteObjectVersion",
      "s3:PutBucketPolicy",
      "s3:DeleteBucketPolicy",
      "s3:PutBucketAcl",
      "s3:PutBucketPublicAccessBlock",
      "s3:PutEncryptionConfiguration",
      "s3:PutLifecycleConfiguration",
      "s3:PutBucketLogging",
      "s3:PutBucketOwnershipControls",
    ]
    resources = [
      local.tf_state_bucket_arn,
      local.tf_state_objects_arn,
      local.artifacts_bucket_arn,
      "${local.artifacts_bucket_arn}/*",
    ]
  }

  statement {
    sid    = "DenyStateLockTableDestructiveActions"
    effect = "Deny"
    actions = [
      "dynamodb:DeleteTable",
      "dynamodb:UpdateTable",
    ]
    resources = [local.tf_lock_table_arn]
  }

  # T-A.2 HIGH #2 (bucket-public half) — the same broad ProjectS3Buckets
  # Allow would otherwise let a deploy role make a data-lake bucket public.
  statement {
    sid    = "DenyProjectBucketPublicExposure"
    effect = "Deny"
    actions = [
      "s3:PutBucketAcl",
      "s3:PutBucketPublicAccessBlock",
      "s3:PutBucketPolicy",
      "s3:DeleteBucketPolicy",
      "s3:PutObjectAcl",
    ]
    resources = local.s3_bucket_arns
  }

  # T-A.2 rev2 HIGH — a permissions boundary (below) is enforced at
  # iam:CreateRole time via the iam:PermissionsBoundary condition. This Deny
  # keeps the boundary from ever being STRIPPED from a role
  # (iam:DeleteRolePermissionsBoundary). It deliberately does NOT deny
  # iam:PutRolePermissionsBoundary: the boundary-conditioned Allow below
  # (ProjectIamRoleSetBoundary, gha_deploy_permissions) is the only way to
  # SET it, and is the sole retrofit path onto the 8 project roles that
  # predate this stack — a wider Deny here would make that retrofit apply
  # fail with AccessDenied.
  statement {
    sid       = "DenyRolePermissionsBoundaryTampering"
    effect    = "Deny"
    actions   = ["iam:DeleteRolePermissionsBoundary"]
    resources = local.iam_role_arns
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

  # T-A.2 HIGH #3 — iam:CreateRole is split into its own conditioned
  # statement: every role this project's Terraform creates MUST carry the
  # ci_boundary permissions boundary (boundary.tf), which caps its
  # effective permissions regardless of what any later PutRolePolicy /
  # AttachRolePolicy grants that role. This is the standard AWS mitigation
  # for the CreateRole -> PutRolePolicy -> PassRole escalation chain.
  statement {
    sid       = "ProjectIamRoleCreate"
    effect    = "Allow"
    actions   = ["iam:CreateRole"]
    resources = local.iam_role_arns
    condition {
      test     = "StringEquals"
      variable = "iam:PermissionsBoundary"
      values   = [aws_iam_policy.ci_boundary.arn]
    }
  }

  # T-A.2 rev2 HIGH — the retrofit path: iam:PermissionsBoundary IS a
  # supported condition key for PutRolePermissionsBoundary (unlike
  # PutRolePolicy/AttachRolePolicy, where it never matches). This lets a
  # deploy role SET only ci_boundary on any of the 8 pre-existing project
  # roles (below); iam:DeleteRolePermissionsBoundary stays denied above, so
  # stripping the boundary once set remains impossible.
  statement {
    sid       = "ProjectIamRoleSetBoundary"
    effect    = "Allow"
    actions   = ["iam:PutRolePermissionsBoundary"]
    resources = local.iam_role_arns
    condition {
      test     = "StringEquals"
      variable = "iam:PermissionsBoundary"
      values   = [aws_iam_policy.ci_boundary.arn]
    }
  }

  statement {
    sid = "ProjectIamRoleManagement"
    # Excludes gha-* roles via the explicit Deny above. iam:CreateRole is
    # NOT here — see ProjectIamRoleCreate (boundary-conditioned).
    effect = "Allow"
    actions = [
      "iam:GetRole",
      "iam:GetRolePolicy",
      "iam:ListRolePolicies",
      "iam:ListAttachedRolePolicies",
      "iam:ListInstanceProfilesForRole",
      "iam:DeleteRole",
      "iam:TagRole",
      "iam:UntagRole",
      "iam:PutRolePolicy",
      "iam:DeleteRolePolicy",
      "iam:AttachRolePolicy",
      "iam:DetachRolePolicy",
      "iam:UpdateAssumeRolePolicy",
      "iam:CreateInstanceProfile",
      "iam:DeleteInstanceProfile",
      "iam:AddRoleToInstanceProfile",
      "iam:RemoveRoleFromInstanceProfile",
      "iam:GetInstanceProfile",
    ]
    resources = concat(local.iam_role_arns, local.iam_instance_profile_arns)
  }

  # Customer-managed policies this project declares (e.g.
  # dm-databricks-dev-s3-policy, dm-databricks-hml-s3-policy) — a distinct
  # ARN namespace from roles.
  statement {
    sid    = "ProjectIamCustomPolicies"
    effect = "Allow"
    actions = [
      "iam:CreatePolicy",
      "iam:DeletePolicy",
      "iam:GetPolicy",
      "iam:GetPolicyVersion",
      "iam:CreatePolicyVersion",
      "iam:DeletePolicyVersion",
      "iam:ListPolicyVersions",
      "iam:TagPolicy",
      "iam:UntagPolicy",
    ]
    resources = local.iam_policy_arns
  }

  # T-A.2 HIGH #3 — iam:PassRole is gated to only the AWS services this
  # project actually passes a role to (Lambda execution roles, EventBridge
  # rule targets). Without iam:PassedToService, a role created via
  # ProjectIamRoleCreate above could be passed to an attacker-chosen
  # consumer service.
  statement {
    sid       = "ProjectIamPassRole"
    effect    = "Allow"
    actions   = ["iam:PassRole"]
    resources = local.iam_role_arns
    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values   = ["lambda.amazonaws.com", "events.amazonaws.com"]
    }
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

  # T-R.2 F-05 — read-only, deliberately no s3:PutObject: the read-only plan
  # role never uploads. Only the deploy roles' policies (gha_deploy_permissions)
  # write layer artifacts, from deploy_all_dm_applications.yml's build-layer
  # job — the sole legitimate uploader, resolve_layer.sh only ever reads.
  statement {
    sid    = "ArtifactsBucketLayerReadObjects"
    effect = "Allow"
    actions = [
      "s3:GetObject",
    ]
    resources = [local.artifacts_layer_prefix_rw]
  }

  # T-A.2 MEDIUM #1 — deliberately NO s3:GetObject on local.s3_bucket_arns:
  # `terraform plan` needs bucket/list metadata, never object bodies, and a
  # PR-triggered role reading raw-data/lakehouse object contents is pure
  # surplus (OWASP A01/A02). Kept as GetBucket*/ListBucket only.
  statement {
    sid    = "ProjectReadOnly"
    effect = "Allow"
    actions = [
      "s3:GetBucket*",
      "s3:ListBucket",
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
