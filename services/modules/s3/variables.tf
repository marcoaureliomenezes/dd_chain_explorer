variable "environment" {
  description = "Deployment environment (dev/hml/prd)"
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

variable "bucket_name" {
  description = "S3 bucket name"
  type        = string
}

variable "versioning_enabled" {
  description = "Enable S3 bucket versioning"
  type        = bool
  default     = false
}

variable "prevent_destroy" {
  description = "Enable lifecycle prevent_destroy (for production buckets)"
  type        = bool
  default     = false
}

variable "ownership_controls" {
  description = "Object ownership: BucketOwnerEnforced or BucketOwnerPreferred"
  type        = string
  default     = "BucketOwnerEnforced"
}

variable "lifecycle_rules" {
  description = "List of lifecycle rules"
  type = list(object({
    id     = string
    prefix = string
    transitions = optional(list(object({
      days          = number
      storage_class = string
    })), [])
    expiration_days = optional(number, 0)
  }))
  default = []
}

variable "folder_prefixes" {
  description = "List of folder prefixes (placeholder objects) to create"
  type        = list(string)
  default     = []
}
