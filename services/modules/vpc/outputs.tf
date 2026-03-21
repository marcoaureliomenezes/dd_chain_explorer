output "vpc_id" {
  value = aws_vpc.main.id
}

output "public_subnet_id" {
  value = aws_subnet.public_1.id
}

output "private_subnet_ids" {
  value = var.enable_private_subnets ? [aws_subnet.private_1[0].id, aws_subnet.private_2[0].id] : []
}

output "sg_ecs_tasks_id" {
  value = aws_security_group.ecs_tasks.id
}

output "route_table_public_id" {
  value = aws_route_table.public.id
}

output "route_table_private_id" {
  value = var.enable_private_subnets ? aws_route_table.private[0].id : null
}

output "s3_vpc_endpoint_id" {
  value = var.enable_s3_endpoint ? aws_vpc_endpoint.s3[0].id : null
}

output "vpc_cidr" {
  value = aws_vpc.main.cidr_block
}
