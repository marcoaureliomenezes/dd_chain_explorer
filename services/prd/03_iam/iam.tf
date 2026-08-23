# -----------------------------------------------------------------------
# T-A.2 rev2 HIGH — permissions-boundary retrofit. Every project
# `aws_iam_role` in this account carries the boundary `prd/00_bootstrap`
# exports, capping its effective permissions regardless of what its own
# inline policy grants. Read via `terraform_remote_state` (literal backend
# config, mirroring dev/02_lambda and prd/06_lambda's existing remote-state
# data sources), not a variable — keeps the CI `-var` surface unchanged.
#
# NOTE — currently unconsumed. See the T-B.3 removal note below: this stack
# has no `aws_iam_role` left to carry the boundary. Kept so a future
# project-relevant PRD IAM role does not have to reintroduce the
# remote-state plumbing.
# -----------------------------------------------------------------------
data "terraform_remote_state" "bootstrap" {
  backend = "s3"
  config = {
    bucket = "dm-chain-explorer-terraform-state"
    key    = "prd/bootstrap/terraform.tfstate"
    region = "sa-east-1"
  }
}

# -----------------------------------------------------------------------
# T-B.3 (security rev3 HIGH, 2026-08-23) — removed the ECS task role,
# task-execution role and their inline/managed policies
# (`AmazonECSTaskExecutionRolePolicy`, `secretsmanager:GetSecretValue`,
# `kms:Decrypt`, `/ecs/dm-chain-explorer*` log-group grants). Both roles
# served the capture-era ECS Fargate producers, destroyed 2026-06-22
# (DRIFT-13/B1); the ECS cluster itself (`dm-chain-explorer-ecs-hml`) is
# already a live-but-unmanaged empty shell per [[aws-resources]]. Neither
# of the 2 project Lambdas nor the DABs bundles nor CI assume these roles
# — Lambda execution roles live in `prd/06_lambda`/`dev/02_lambda`.
#
# After this removal, `03_iam` declares no `aws_iam_role` at all — an
# `apply` here now destroys both live roles and leaves the stack's state
# key (`prd/iam/terraform.tfstate`) empty. See the release report for the
# follow-up recommendation to retire the stack (dir + state key) entirely.
# -----------------------------------------------------------------------
