locals {
  common_tags = {
    "owner"           = "marco-menezes"
    "managed-by"      = "terraform"
    "cost-center"     = "dd-chain-explorer"
    "environment"     = var.environment
    "project"         = "dd-chain-explorer"
    "project_version" = var.project_version
  }
}
