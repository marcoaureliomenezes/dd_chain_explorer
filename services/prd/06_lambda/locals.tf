locals {
  name_prefix = "dm-${var.project}-${var.environment}"

  common_tags = {
    "owner"       = "marco-menezes"
    "managed-by"  = "terraform"
    "cost-center" = "dd-chain-explorer"
    "environment" = var.environment
    "project"     = "dd-chain-explorer"

  }
}
