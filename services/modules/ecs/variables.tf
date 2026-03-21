variable "environment" {
  description = "Deployment environment (hml/prd)"
  type        = string
}

variable "region" {
  description = "AWS region"
  type        = string
  default     = "sa-east-1"
}

variable "common_tags" {
  description = "Common resource tags"
  type        = map(string)
  default     = {}
}

variable "name_prefix" {
  description = "Resource name prefix"
  type        = string
  default     = "dm-chain-explorer"
}

variable "cluster_name" {
  description = "ECS cluster name"
  type        = string
}

variable "container_insights" {
  description = "Enable ECS Container Insights"
  type        = bool
  default     = true
}

variable "capacity_providers" {
  description = "List of capacity providers for the cluster"
  type        = list(string)
  default     = ["FARGATE", "FARGATE_SPOT"]
}

variable "default_capacity_provider" {
  description = "Default capacity provider strategy"
  type        = string
  default     = "FARGATE_SPOT"
}

variable "cloudwatch_log_group_name" {
  description = "CloudWatch log group name for ECS tasks"
  type        = string
}

variable "cloudwatch_log_retention_days" {
  description = "Retention period for ECS CloudWatch logs"
  type        = number
  default     = 7
}

variable "vpc_id" {
  description = "VPC ID for Cloud Map DNS namespace"
  type        = string
}

variable "ecr_repositories" {
  description = "Map of ECR repositories to create (name => config)"
  type = map(object({
    image_tag_mutability = optional(string, "MUTABLE")
    scan_on_push         = optional(bool, true)
    force_delete         = optional(bool, true)
  }))
  default = {}
}
