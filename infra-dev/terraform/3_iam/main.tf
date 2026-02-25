###############################################################################
# terraform_dev/3_iam/main.tf
#
# IAM role e policy para o Databricks acessar o bucket S3 de ingestão DEV.
#
# A role usa cross-account trust com a conta AWS do Databricks Free Edition.
# O ARN da role é referenciado em 1_databricks/ para criar a storage credential.
#
# Uso:
#   cd terraform_dev/3_iam
#   terraform init
#   terraform apply
###############################################################################

terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = local.common_tags
  }
}
