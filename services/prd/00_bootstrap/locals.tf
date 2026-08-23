locals {
  common_tags = {
    "owner"           = "marco-menezes"
    "managed-by"      = "terraform"
    "cost-center"     = "dd-chain-explorer"
    "environment"     = var.environment
    "project"         = "dd-chain-explorer"
    "project_version" = var.project_version
  }

  account_id = data.aws_caller_identity.current.account_id

  # ARN globs for every project resource type, one per declared name prefix
  # (var.project_name_prefixes). Every Allow statement in policies.tf draws
  # its `resources` list only from these plus the state bucket / lock table
  # / artifacts bucket — never "*". Proven negatively by T-A.3b.
  s3_bucket_arns = flatten([
    for p in var.project_name_prefixes : [
      "arn:aws:s3:::${p}*",
      "arn:aws:s3:::${p}*/*",
    ]
  ])

  dynamodb_table_arns = [
    for p in var.project_name_prefixes :
    "arn:aws:dynamodb:${var.region}:${local.account_id}:table/${p}*"
  ]

  lambda_function_arns = [
    for p in var.project_name_prefixes :
    "arn:aws:lambda:${var.region}:${local.account_id}:function:${p}*"
  ]

  lambda_layer_arns = [
    for p in var.project_name_prefixes :
    "arn:aws:lambda:${var.region}:${local.account_id}:layer:${p}*"
  ]

  log_group_arns = flatten([
    for p in var.project_name_prefixes : [
      "arn:aws:logs:${var.region}:${local.account_id}:log-group:/aws/lambda/${p}*",
      "arn:aws:logs:${var.region}:${local.account_id}:log-group:/aws/lambda/${p}*:*",
      "arn:aws:logs:${var.region}:${local.account_id}:log-group:/apps/${p}*",
      "arn:aws:logs:${var.region}:${local.account_id}:log-group:/apps/${p}*:*",
    ]
  ])

  events_rule_arns = [
    for p in var.project_name_prefixes :
    "arn:aws:events:${var.region}:${local.account_id}:rule/${p}*"
  ]

  # Every project IAM role EXCEPT the gha-* roles themselves — the explicit
  # Deny statement (policies.tf) closes the self-mutation gap regardless of
  # this Allow's textual overlap with "dm-chain-explorer-gha-*".
  iam_role_arns = [
    for p in var.project_name_prefixes :
    "arn:aws:iam::${local.account_id}:role/${p}*"
  ]

  iam_instance_profile_arns = [
    for p in var.project_name_prefixes :
    "arn:aws:iam::${local.account_id}:instance-profile/${p}*"
  ]

  ssm_parameter_arns = [
    for p in var.project_ssm_path_prefixes :
    "arn:aws:ssm:${var.region}:${local.account_id}:parameter${p}*"
  ]

  artifacts_bucket_arn      = "arn:aws:s3:::${var.artifacts_bucket}"
  artifacts_layer_prefix_rw = "arn:aws:s3:::${var.artifacts_bucket}/lambda-layers/*"

  tf_state_bucket_arn  = "arn:aws:s3:::${var.tf_state_bucket}"
  tf_state_objects_arn = "arn:aws:s3:::${var.tf_state_bucket}/*"
  tf_lock_table_arn    = "arn:aws:dynamodb:${var.region}:${local.account_id}:table/${var.tf_state_lock_table}"
}
