###############################################################################
# terraform/9_dynamodb/locals.tf
###############################################################################

locals {
  name_prefix = "${var.project}-${var.environment}"
  common_tags = {
    Project     = var.project
    Environment = var.environment
    ManagedBy   = "terraform"
    CostCenter  = "dd-chain-explorer"
  }
}
