output "cluster_id" {
  value = module.ecs.cluster_id
}

output "cluster_arn" {
  value = module.ecs.cluster_arn
}

output "cluster_name" {
  value = module.ecs.cluster_name
}

output "cloudwatch_log_group_name" {
  value = module.ecs.cloudwatch_log_group_name
}

output "ecr_repository_urls" {
  value = module.ecs.ecr_repository_urls
}
