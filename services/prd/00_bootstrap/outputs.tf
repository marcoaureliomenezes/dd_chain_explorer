output "gha_deploy_dev_role_arn" {
  description = "OIDC deploy role for the dev GitHub environment"
  value       = aws_iam_role.gha_deploy_dev.arn
}

output "gha_deploy_hml_role_arn" {
  description = "OIDC deploy role for the hml GitHub environment"
  value       = aws_iam_role.gha_deploy_hml.arn
}

output "gha_deploy_prd_role_arn" {
  description = "OIDC deploy role for the production GitHub environment"
  value       = aws_iam_role.gha_deploy_prd.arn
}

output "gha_readonly_plan_role_arn" {
  description = "OIDC read-only plan role for plan_on_pr.yml and drift_detection.yml"
  value       = aws_iam_role.gha_readonly_plan.arn
}

output "ci_boundary_policy_arn" {
  description = "Permissions boundary attached to every IAM role this project's Terraform creates (T-A.2 HIGH #3)"
  value       = aws_iam_policy.ci_boundary.arn
}
