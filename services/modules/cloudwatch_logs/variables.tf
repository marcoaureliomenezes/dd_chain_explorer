###############################################################################
# modules/cloudwatch_logs/variables.tf
#
# Input variables for the CloudWatch Log Group module.
###############################################################################

variable "environment" {
  description = "Environment name (dev, hml, prd)"
  type        = string
}

variable "common_tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
  default     = {}
}

# ---------------------------------------------------------------------------
# CloudWatch Log Group
# ---------------------------------------------------------------------------

variable "log_group_name" {
  description = "Name of the CloudWatch Log Group"
  type        = string
  default     = "/apps/dm-chain-explorer"
}

variable "retention_in_days" {
  description = "Number of days to retain log events (0 = never expire)"
  type        = number
  default     = 30
}
