###############################################################################
# modules/sqs/variables.tf
#
# Input variables for SQS Queues + Dead Letter Queues module.
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

variable "queues" {
  description = <<-EOT
    Map of SQS queues to create.
    Key   = logical name (used for resource naming).
    Value = object with queue configuration.
  EOT
  type = map(object({
    visibility_timeout_seconds = optional(number, 30)
    message_retention_seconds  = optional(number, 345600) # 4 days
    max_message_size           = optional(number, 262144)  # 256 KB
    receive_wait_time_seconds  = optional(number, 20)      # long polling
    delay_seconds              = optional(number, 0)
    dlq_enabled                = optional(bool, true)
    dlq_max_receive_count      = optional(number, 3)       # retries before DLQ
  }))
}

variable "ip_allowlist" {
  description = "List of CIDR blocks allowed to send/receive messages (for DEV IP restriction). Empty = no restriction."
  type        = list(string)
  default     = []
}
