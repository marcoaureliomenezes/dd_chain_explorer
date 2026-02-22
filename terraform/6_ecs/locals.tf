locals {
  common_tags = {
    "owner"       = "marco-menezes"
    "managed-by"  = "terraform"
    "cost-center" = "data-platform"
    "environment" = var.environment
    "project"     = "dd-chain-explorer"
  }

  # Common environment variables for all stream apps
  common_stream_env = [
    {
      name  = "KAFKA_BOOTSTRAP_SERVERS"
      value = data.terraform_remote_state.msk.outputs.msk_bootstrap_brokers_iam
    },
    {
      name  = "MSK_IAM_AUTH"
      value = "true"
    },
    {
      name  = "AWS_REGION"
      value = var.region
    },
    {
      name  = "DYNAMODB_SEMAPHORE_TABLE"
      value = data.terraform_remote_state.dynamodb.outputs.api_key_semaphore_table_name
    },
    {
      name  = "DYNAMODB_CONSUMPTION_TABLE"
      value = data.terraform_remote_state.dynamodb.outputs.api_key_consumption_table_name
    },
    {
      name  = "APP_ENV"
      value = "prod"
    },
  ]
}
