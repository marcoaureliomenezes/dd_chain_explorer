output "vpc_id" {
  value = module.vpc.vpc_id
}

output "public_subnet_id" {
  value = module.vpc.public_subnet_id
}

output "private_subnet_ids" {
  value = module.vpc.private_subnet_ids
}

output "sg_ecs_tasks_id" {
  value = module.vpc.sg_ecs_tasks_id
}

output "vpc_cidr" {
  value = module.vpc.vpc_cidr
}

output "route_table_public_id" {
  value = module.vpc.route_table_public_id
}

output "route_table_private_id" {
  value = module.vpc.route_table_private_id
}
