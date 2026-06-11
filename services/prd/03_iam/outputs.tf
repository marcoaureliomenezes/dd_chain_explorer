output "ecs_task_execution_role_arn" {
  value = aws_iam_role.ecs_task_execution.arn
}

output "ecs_task_role_arn" {
  value = aws_iam_role.ecs_task.arn
}

output "databricks_cross_account_role_arn" {
  value = aws_iam_role.databricks_cross_account.arn
}

output "databricks_cluster_instance_profile_arn" {
  value = aws_iam_instance_profile.databricks_cluster.arn
}

output "databricks_cluster_role_arn" {
  value = aws_iam_role.databricks_cluster.arn
}

# -----------------------------------------------------------------------
# GitHub Actions OIDC role ARNs (ADR-R6-3/R6-7) — consumed by the workflow
# `role-to-assume` cutover in T-R6-B3.
# -----------------------------------------------------------------------
output "gha_deploy_dev_role_arn" {
  description = "OIDC deploy role for the dev GitHub environment"
  value       = aws_iam_role.gha_deploy_dev.arn
}

output "gha_deploy_hml_role_arn" {
  description = "OIDC deploy role for the hml + hml-apps GitHub environments"
  value       = aws_iam_role.gha_deploy_hml.arn
}

output "gha_deploy_prd_role_arn" {
  description = "OIDC deploy role for the production GitHub environment"
  value       = aws_iam_role.gha_deploy_prd.arn
}

output "gha_readonly_plan_role_arn" {
  description = "OIDC read-only plan role for plan_on_pr.yml, drift_detection.yml, all-check-infra"
  value       = aws_iam_role.gha_readonly_plan.arn
}
