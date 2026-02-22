locals {
  common_tags = {
    "owner"       = "marco-menezes"
    "managed-by"  = "terraform"
    "cost-center" = "data-platform"
    "environment" = var.environment
    "project"     = "dd-chain-explorer"
  }
}
