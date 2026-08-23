# =======================================================================
# The 4 IAM roles for federated CI auth (D14). No managed-policy
# attachment anywhere in this stack — every permission is an explicit
# inline statement list (policies.tf), least-privilege and prefix-scoped.
# =======================================================================

resource "aws_iam_role" "gha_deploy_dev" {
  name               = "dm-chain-explorer-gha-deploy-dev"
  assume_role_policy = data.aws_iam_policy_document.gha_deploy_dev_assume.json
  tags               = local.common_tags
}

resource "aws_iam_role_policy" "gha_deploy_dev_deny" {
  name   = "dm-gha-self-mutation-deny"
  role   = aws_iam_role.gha_deploy_dev.id
  policy = data.aws_iam_policy_document.gha_self_mutation_deny.json
}

resource "aws_iam_role_policy" "gha_deploy_dev_allow" {
  name   = "dm-gha-deploy-permissions"
  role   = aws_iam_role.gha_deploy_dev.id
  policy = data.aws_iam_policy_document.gha_deploy_permissions.json
}

resource "aws_iam_role" "gha_deploy_hml" {
  name               = "dm-chain-explorer-gha-deploy-hml"
  assume_role_policy = data.aws_iam_policy_document.gha_deploy_hml_assume.json
  tags               = local.common_tags
}

resource "aws_iam_role_policy" "gha_deploy_hml_deny" {
  name   = "dm-gha-self-mutation-deny"
  role   = aws_iam_role.gha_deploy_hml.id
  policy = data.aws_iam_policy_document.gha_self_mutation_deny.json
}

resource "aws_iam_role_policy" "gha_deploy_hml_allow" {
  name   = "dm-gha-deploy-permissions"
  role   = aws_iam_role.gha_deploy_hml.id
  policy = data.aws_iam_policy_document.gha_deploy_permissions.json
}

resource "aws_iam_role" "gha_deploy_prd" {
  name               = "dm-chain-explorer-gha-deploy-prd"
  assume_role_policy = data.aws_iam_policy_document.gha_deploy_prd_assume.json
  tags               = local.common_tags
}

resource "aws_iam_role_policy" "gha_deploy_prd_deny" {
  name   = "dm-gha-self-mutation-deny"
  role   = aws_iam_role.gha_deploy_prd.id
  policy = data.aws_iam_policy_document.gha_self_mutation_deny.json
}

resource "aws_iam_role_policy" "gha_deploy_prd_allow" {
  name   = "dm-gha-deploy-permissions"
  role   = aws_iam_role.gha_deploy_prd.id
  policy = data.aws_iam_policy_document.gha_deploy_permissions.json
}

resource "aws_iam_role" "gha_readonly_plan" {
  name               = "dm-chain-explorer-gha-readonly-plan"
  assume_role_policy = data.aws_iam_policy_document.gha_readonly_plan_assume.json
  tags               = local.common_tags
}

resource "aws_iam_role_policy" "gha_readonly_plan_deny" {
  name   = "dm-gha-self-mutation-deny"
  role   = aws_iam_role.gha_readonly_plan.id
  policy = data.aws_iam_policy_document.gha_self_mutation_deny.json
}

resource "aws_iam_role_policy" "gha_readonly_plan_allow" {
  name   = "dm-gha-readonly-plan-permissions"
  role   = aws_iam_role.gha_readonly_plan.id
  policy = data.aws_iam_policy_document.gha_readonly_plan_permissions.json
}
