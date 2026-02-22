###############################################################################
# terraform/8_elasticache/variables.tf
###############################################################################

variable "aws_region" {
  description = "Região AWS"
  type        = string
  default     = "sa-east-1"
}

variable "project" {
  description = "Nome do projeto"
  type        = string
  default     = "data-master"
}

variable "environment" {
  description = "Ambiente (prod, staging)"
  type        = string
  default     = "prod"
}

variable "vpc_id" {
  description = "ID da VPC onde o ElastiCache será criado"
  type        = string
}

variable "private_subnet_ids" {
  description = "IDs das subnets privadas para o subnet group do ElastiCache"
  type        = list(string)
}

variable "app_security_group_id" {
  description = "Security group dos containers ECS — autorizado a conectar no Redis"
  type        = string
}

variable "node_type" {
  description = "Tipo do nó ElastiCache (cache.t4g.micro para prod leve)"
  type        = string
  default     = "cache.t4g.micro"
}

variable "redis_version" {
  description = "Versão do Redis"
  type        = string
  default     = "7.1"
}

variable "auth_token" {
  description = "Auth token para ElastiCache (transit encryption). Mínimo 16 caracteres."
  type        = string
  sensitive   = true
  default     = null
}
