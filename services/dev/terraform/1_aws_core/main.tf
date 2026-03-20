###############################################################################
# terraform_dev/main.tf
#
# Infraestrutura AWS para o ambiente DEV (Databricks Free Edition).
#
# Recursos criados:
#   - Bucket S3 para ingestão de dados (external location no Databricks)
#   - IAM user + policy para o Databricks Free Edition acessar o S3
#
# O Databricks Free Edition não tem API de gerenciamento. Todos os recursos
# do Databricks (clusters, jobs, DLTs) são gerenciados via DABs ou UI.
# Terraform é usado SOMENTE para infraestrutura AWS.
#
# Autenticação AWS:
#   AWS CLI (perfil padrão ou env vars AWS_ACCESS_KEY_ID/SECRET)
#
# Estado remoto: S3 (mesmo bucket de HML e PRD)
#
# Uso:
#   make dev_tf_init
#   make dev_tf_apply
#   make dev_tf_destroy
###############################################################################

terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }

  backend "s3" {
    bucket         = "dm-chain-explorer-terraform-state"
    key            = "dev/terraform.tfstate"
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
