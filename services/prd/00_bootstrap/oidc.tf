# =======================================================================
# GitHub Actions OIDC trust — the sole reference to the operator-created
# identity provider. This stack never creates the provider (chicken-and-egg:
# CI cannot terraform its own identity provider while authenticating as it).
# =======================================================================

data "aws_iam_openid_connect_provider" "github" {
  count = var.github_oidc_provider_arn == "" ? 1 : 0
  url   = "https://token.actions.githubusercontent.com"
}

locals {
  github_oidc_provider_arn = var.github_oidc_provider_arn != "" ? var.github_oidc_provider_arn : data.aws_iam_openid_connect_provider.github[0].arn
  github_sub_prefix        = "repo:${var.github_org}/${var.github_repo}"
}

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

# hml deploy role — trusts the `hml` GitHub environment only (no `hml-apps`
# — that phantom environment reference is removed by A5/T-A.10).
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
      values   = ["${local.github_sub_prefix}:environment:hml"]
    }
  }
}

# prd deploy role — trusts the `production` GitHub environment.
# NOTE: the GitHub environment is named `production` (NOT `prd`) — bound
# as-is, no rename (renaming would drop required_reviewers settings).
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

# read-only plan role — trusts pull_request runs (plan_on_pr.yml, PRs into
# either long-lived branch resolve to the same `pull_request` sub claim)
# AND both long-lived branch refs directly (drift_detection.yml on `main`;
# pre-gate plan jobs dispatched from `develop`). No GitHub environment.
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
        "${local.github_sub_prefix}:ref:refs/heads/${var.github_deploy_branch}",
        "${local.github_sub_prefix}:ref:refs/heads/${var.github_default_branch}",
      ]
    }
  }
}
