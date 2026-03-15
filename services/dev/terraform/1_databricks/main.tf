###############################################################################
# terraform_dev/1_databricks/main.tf
#
# Configuração do Databricks para acesso ao S3 DEV via Unity Catalog.
#
# Recursos criados:
#   - databricks_storage_credential: usa a IAM role criada em 3_iam/
#   - databricks_external_location: aponta para o bucket S3 de ingestão DEV
#
# Pré-requisitos:
#   1. terraform_dev/2_s3 aplicado (bucket criado)
#   2. terraform_dev/3_iam aplicado (IAM role criada)
#
# Autenticação Databricks (Service Principal):
#   export TF_VAR_databricks_client_id=<client_id>
#   export TF_VAR_databricks_client_secret=<client_secret>
#
# Uso:
#   cd terraform_dev/1_databricks
#   terraform init
#   terraform apply
###############################################################################

terraform {
  required_version = ">= 1.5"

  required_providers {
    databricks = {
      source  = "databricks/databricks"
      version = ">= 1.38"
    }
  }
}

provider "databricks" {
  host  = var.databricks_host
  token = var.databricks_token != "" ? var.databricks_token : null

  client_id     = var.databricks_client_id != "" ? var.databricks_client_id : null
  client_secret = var.databricks_client_secret != "" ? var.databricks_client_secret : null
}
