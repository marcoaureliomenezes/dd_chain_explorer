###############################################################################
# terraform_hml/locals.tf
###############################################################################

locals {
  name_prefix = "dd-chain-explorer-${var.environment}"

  common_tags = {
    "owner"       = "marco-menezes"
    "managed-by"  = "terraform"
    "cost-center" = "dd-chain-explorer"
    "environment" = var.environment
    "project"     = "dd-chain-explorer"
  }
}
