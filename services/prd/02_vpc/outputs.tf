output "vpc_id" {
  value = aws_vpc.main.id
}

# Subnet pública única — onde as tasks ECS serão colocadas (assign_public_ip = true)
output "public_subnet_id" {
  value = aws_subnet.public_1.id
}

# 2 subnets privadas — Databricks workspace (is_no_public_ip_enabled)
output "private_subnet_ids" {
  value = [aws_subnet.private_1.id, aws_subnet.private_2.id]
}

output "sg_ecs_tasks_id" {
  value = aws_security_group.ecs_tasks.id
}

output "route_table_public_id" {
  value = aws_route_table.public.id
}

output "route_table_private_id" {
  value = aws_route_table.private.id
}

output "s3_vpc_endpoint_id" {
  value = aws_vpc_endpoint.s3.id
}
