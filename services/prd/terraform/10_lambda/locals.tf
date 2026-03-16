locals {
  name_prefix = "dm-${var.project}-${var.environment}"

  common_tags = {
    "owner"       = "marco-menezes"
    "managed-by"  = "terraform"
    "cost-center" = var.project
    "environment" = var.environment
    "project"     = var.project
  }
}
