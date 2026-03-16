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
  description = "Ambiente (prd, staging)"
  type        = string
  default     = "prd"
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
