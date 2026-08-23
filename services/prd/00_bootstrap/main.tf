# =======================================================================
# prd/00_bootstrap — operator-applied OIDC bootstrap stack (D14).
#
# Same posture as prd/01_tf_state: applied locally by the coordinator with
# operator credentials, NEVER by CI, NEVER destroyed by an automated path.
# It holds the GitHub OIDC provider reference and the four `gha` roles that
# every CI workflow assumes. Moving these out of a CI-applied stack (they
# used to live in prd/03_iam, see ADR/DRIFT-01, DRIFT-08) breaks the
# bootstrap paradox: CI cannot authenticate until the roles it needs exist,
# and CI can never be trusted to create the identity it authenticates as.
# =======================================================================

terraform {
  required_version = ">= 1.3.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 4.60.0"
    }
  }

  backend "s3" {
    bucket         = "dm-chain-explorer-terraform-state"
    key            = "prd/bootstrap/terraform.tfstate"
    region         = "sa-east-1"
    dynamodb_table = "dm-chain-explorer-terraform-lock"
    encrypt        = true
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = local.common_tags
  }
}

data "aws_caller_identity" "current" {}
