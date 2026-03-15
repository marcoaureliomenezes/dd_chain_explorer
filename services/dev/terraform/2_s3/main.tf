###############################################################################
# terraform_dev/2_s3/main.tf
#
# Bucket S3 para ingestão de dados Kafka → Databricks (DEV).
#
# Uso:
#   cd terraform_dev/2_s3
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
