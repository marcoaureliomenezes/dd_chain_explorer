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
