###############################################################################
# terraform_hml/main.tf
#
# Infraestrutura AWS persistente para o ambiente HML (homologação).
#
# Recursos criados:
#   - Bucket S3 para ingestão Kafka → S3 (usado pelos DABs HML)
#   - Tabela DynamoDB single-table para os streaming apps em HML
#   - IAM roles para as ECS tasks HML (task execution + task role)
#
# Recursos efêmeros (criados/destruídos por run de CI/CD, NÃO gerenciados aqui):
#   - ECS cluster dm-hml-ecs
#   - ECS task definitions
#   - Security groups por run
#
# Estado remoto: S3 (mesmo bucket de DEV e PRD).
#
# Uso:
#   make hml_tf_init
#   make hml_tf_apply
#   make hml_tf_destroy
###############################################################################

terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.36.0"
    }
  }

  backend "s3" {
    bucket         = "dm-chain-explorer-terraform-state"
    key            = "hml/terraform.tfstate"
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
