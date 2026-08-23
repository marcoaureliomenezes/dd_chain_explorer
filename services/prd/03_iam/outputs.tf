output "ecs_task_execution_role_arn" {
  value = aws_iam_role.ecs_task_execution.arn
}

output "ecs_task_role_arn" {
  value = aws_iam_role.ecs_task.arn
}

# -----------------------------------------------------------------------
# NOTE — the GitHub Actions OIDC provider reference and the four gha_* roles
# (oidc.tf) moved to services/prd/00_bootstrap (T-B.3a, D14): 03_iam has one
# applier and that stack owns their apply going forward. Their outputs live
# there now.
# -----------------------------------------------------------------------
