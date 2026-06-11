# =======================================================================
# GitHub Actions OIDC role-assumption (ADR-R6-3 / R6-6 / R6-7)
# -----------------------------------------------------------------------
# 4 IAM roles for federated CI auth, replacing long-lived static AWS keys
# (SEC-H-02 / SEC-M-05, CWE-798). ALL roles live in this account-level prd
# IAM stack — dev has no IAM stack by design (ADR-R6-6).
#
#   - dm-chain-explorer-gha-deploy-dev     (trusts environment:dev)
#   - dm-chain-explorer-gha-deploy-hml     (trusts environment:hml + hml-apps)
#   - dm-chain-explorer-gha-deploy-prd     (trusts environment:production)
#   - dm-chain-explorer-gha-readonly-plan  (trusts pull_request + default-branch ref)
#
# The GitHub OIDC identity provider itself is created ONCE by the operator
# (OP-R6-2, chicken-and-egg: CI cannot terraform its own identity provider
# while still authenticating with the keys being retired). This terraform
# only REFERENCES it — via data source by default, or via an explicit ARN
# override variable. It does NOT create the provider.
# =======================================================================

# Resolve the operator-created OIDC provider. Default path: look it up by URL.
# Override path: pass var.github_oidc_provider_arn to skip the data lookup
# (e.g. during a plan before the provider data source is queryable in CI).
data "aws_iam_openid_connect_provider" "github" {
  count = var.github_oidc_provider_arn == "" ? 1 : 0
  url   = "https://token.actions.githubusercontent.com"
}

locals {
  github_oidc_provider_arn = var.github_oidc_provider_arn != "" ? var.github_oidc_provider_arn : data.aws_iam_openid_connect_provider.github[0].arn

  # repo:<org>/<repo> prefix used in every OIDC `sub` claim condition.
  github_sub_prefix = "repo:${var.github_org}/${var.github_repo}"
}

# -----------------------------------------------------------------------
# Reusable trust-policy builder per role.
# Each statement federates the GitHub OIDC provider, pins the audience to
# sts.amazonaws.com, and constrains the `sub` claim to the exact GitHub
# environment(s) / ref(s) in the ADR-R6-7 trust matrix.
# -----------------------------------------------------------------------

# dev deploy role — trusts only the `dev` GitHub environment.
data "aws_iam_policy_document" "gha_deploy_dev_assume" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    effect  = "Allow"
    principals {
      type        = "Federated"
      identifiers = [local.github_oidc_provider_arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["${local.github_sub_prefix}:environment:dev"]
    }
  }
}

# hml deploy role — trusts BOTH the `hml` and `hml-apps` GitHub environments
# (the 9 mutating dm-applications jobs gain environment:hml-apps in T-R6-B3).
data "aws_iam_policy_document" "gha_deploy_hml_assume" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    effect  = "Allow"
    principals {
      type        = "Federated"
      identifiers = [local.github_oidc_provider_arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values = [
        "${local.github_sub_prefix}:environment:hml",
        "${local.github_sub_prefix}:environment:hml-apps",
      ]
    }
  }
}

# prd deploy role — trusts the `production` GitHub environment.
# NOTE: the GitHub environment is named `production` (NOT `prd`) — bound as-is,
# no rename (renaming would move required_reviewers settings). ADR-R6-7.
data "aws_iam_policy_document" "gha_deploy_prd_assume" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    effect  = "Allow"
    principals {
      type        = "Federated"
      identifiers = [local.github_oidc_provider_arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["${local.github_sub_prefix}:environment:production"]
    }
  }
}

# read-only plan role — trusts pull_request runs (plan_on_pr.yml) AND the
# default-branch ref (drift_detection.yml, all-check-infra). No environment.
data "aws_iam_policy_document" "gha_readonly_plan_assume" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    effect  = "Allow"
    principals {
      type        = "Federated"
      identifiers = [local.github_oidc_provider_arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values = [
        "${local.github_sub_prefix}:pull_request",
        "${local.github_sub_prefix}:ref:refs/heads/${var.github_default_branch}",
        # Deploy pre-gate plan jobs (prd-plan/hml-plan) dispatch from develop
        # (branch_guard.sh:6). The READONLY plan role must trust develop so
        # AssumeRoleWithWebIdentity succeeds at the first live pre-gate plan run
        # (F-QA-A1R-1). master remains trusted for drift/all-check-infra runs.
        "${local.github_sub_prefix}:ref:refs/heads/${var.github_deploy_branch}",
      ]
    }
  }
}

# -----------------------------------------------------------------------
# The 3 deploy roles. Deploy permissions are env-scoped to the resources
# each pipeline manages (least privilege per ADR-R6-7). For the bootstrap
# release the deploy roles attach AWS managed PowerUserAccess plus an
# inline statement granting the IAM + state-backend actions terraform needs
# to manage this account's stacks; tightening to per-resource ARNs is a
# follow-up tracked in the backlog epic (WS-D).
# -----------------------------------------------------------------------

# Inline policy granting the IAM management + state-backend access that
# `terraform apply` requires but that PowerUserAccess deliberately omits.
data "aws_iam_policy_document" "gha_deploy_iam_and_state" {
  # IAM role/policy management — terraform manages this very IAM stack.
  statement {
    sid = "IamManagement"
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
      "iam:UpdateAssumeRolePolicy",
      "iam:PassRole",
      "iam:CreateInstanceProfile",
      "iam:DeleteInstanceProfile",
      "iam:AddRoleToInstanceProfile",
      "iam:RemoveRoleFromInstanceProfile",
      "iam:GetInstanceProfile",
      "iam:GetOpenIDConnectProvider",
    ]
    resources = ["*"]
  }

  # Terraform S3 remote-state backend: read + write the state objects.
  statement {
    sid = "TerraformStateBucket"
    actions = [
      "s3:ListBucket",
      "s3:GetBucketLocation",
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
    ]
    resources = [
      "arn:aws:s3:::${var.tf_state_bucket}",
      "arn:aws:s3:::${var.tf_state_bucket}/*",
    ]
  }

  # Terraform DynamoDB state lock table.
  statement {
    sid = "TerraformStateLock"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:DeleteItem",
      "dynamodb:DescribeTable",
    ]
    resources = [
      "arn:aws:dynamodb:${var.region}:${data.aws_caller_identity.current.account_id}:table/${var.tf_state_lock_table}",
    ]
  }
}

resource "aws_iam_role" "gha_deploy_dev" {
  name               = "dm-chain-explorer-gha-deploy-dev"
  assume_role_policy = data.aws_iam_policy_document.gha_deploy_dev_assume.json
  tags               = local.common_tags
}

resource "aws_iam_role_policy_attachment" "gha_deploy_dev_poweruser" {
  role       = aws_iam_role.gha_deploy_dev.name
  policy_arn = "arn:aws:iam::aws:policy/PowerUserAccess"
}

resource "aws_iam_role_policy" "gha_deploy_dev_iam_and_state" {
  name   = "dm-gha-deploy-iam-and-state"
  role   = aws_iam_role.gha_deploy_dev.id
  policy = data.aws_iam_policy_document.gha_deploy_iam_and_state.json
}

resource "aws_iam_role" "gha_deploy_hml" {
  name               = "dm-chain-explorer-gha-deploy-hml"
  assume_role_policy = data.aws_iam_policy_document.gha_deploy_hml_assume.json
  tags               = local.common_tags
}

resource "aws_iam_role_policy_attachment" "gha_deploy_hml_poweruser" {
  role       = aws_iam_role.gha_deploy_hml.name
  policy_arn = "arn:aws:iam::aws:policy/PowerUserAccess"
}

resource "aws_iam_role_policy" "gha_deploy_hml_iam_and_state" {
  name   = "dm-gha-deploy-iam-and-state"
  role   = aws_iam_role.gha_deploy_hml.id
  policy = data.aws_iam_policy_document.gha_deploy_iam_and_state.json
}

resource "aws_iam_role" "gha_deploy_prd" {
  name               = "dm-chain-explorer-gha-deploy-prd"
  assume_role_policy = data.aws_iam_policy_document.gha_deploy_prd_assume.json
  tags               = local.common_tags
}

resource "aws_iam_role_policy_attachment" "gha_deploy_prd_poweruser" {
  role       = aws_iam_role.gha_deploy_prd.name
  policy_arn = "arn:aws:iam::aws:policy/PowerUserAccess"
}

resource "aws_iam_role_policy" "gha_deploy_prd_iam_and_state" {
  name   = "dm-gha-deploy-iam-and-state"
  role   = aws_iam_role.gha_deploy_prd.id
  policy = data.aws_iam_policy_document.gha_deploy_iam_and_state.json
}

# -----------------------------------------------------------------------
# read-only plan role — used by plan_on_pr.yml, drift_detection.yml, and
# all-check-infra. ReadOnlyAccess-equivalent (AWS managed ReadOnlyAccess)
# plus state-bucket read + lock-table read so `terraform plan` can fetch
# remote state. NO mutating actions.
# -----------------------------------------------------------------------
data "aws_iam_policy_document" "gha_readonly_state" {
  statement {
    sid = "TerraformStateRead"
    actions = [
      "s3:ListBucket",
      "s3:GetBucketLocation",
      "s3:GetObject",
    ]
    resources = [
      "arn:aws:s3:::${var.tf_state_bucket}",
      "arn:aws:s3:::${var.tf_state_bucket}/*",
    ]
  }

  # Lock table read only — plan acquires/inspects the lock without mutating.
  statement {
    sid = "TerraformLockRead"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:DescribeTable",
    ]
    resources = [
      "arn:aws:dynamodb:${var.region}:${data.aws_caller_identity.current.account_id}:table/${var.tf_state_lock_table}",
    ]
  }
}

resource "aws_iam_role" "gha_readonly_plan" {
  name               = "dm-chain-explorer-gha-readonly-plan"
  assume_role_policy = data.aws_iam_policy_document.gha_readonly_plan_assume.json
  tags               = local.common_tags
}

resource "aws_iam_role_policy_attachment" "gha_readonly_plan_readonly" {
  role       = aws_iam_role.gha_readonly_plan.name
  policy_arn = "arn:aws:iam::aws:policy/ReadOnlyAccess"
}

resource "aws_iam_role_policy" "gha_readonly_plan_state" {
  name   = "dm-gha-readonly-state-access"
  role   = aws_iam_role.gha_readonly_plan.id
  policy = data.aws_iam_policy_document.gha_readonly_state.json
}
