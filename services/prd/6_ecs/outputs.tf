output "ecs_cluster_name" {
  value = aws_ecs_cluster.dm.name
}

output "ecs_cluster_arn" {
  value = aws_ecs_cluster.dm.arn
}
