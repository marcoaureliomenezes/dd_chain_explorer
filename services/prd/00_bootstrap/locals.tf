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

  # The PRD legacy eponymous resources are named exactly the project name with
  # no env suffix (predating the prefix convention): exact ARNs appended, never
  # a widened prefix — T-A.2 HIGH #1 keeps the hyphenated prefixes. Renaming
  # these productive resources is deferred to the infra-repo migration.
  dynamodb_table_arns = concat(
    [
      for p in var.project_name_prefixes :
      "arn:aws:dynamodb:${var.region}:${local.account_id}:table/${p}*"
    ],
    ["arn:aws:dynamodb:${var.region}:${local.account_id}:table/dm-chain-explorer"],
  )

  lambda_function_arns = [
    for p in var.project_name_prefixes :
    "arn:aws:lambda:${var.region}:${local.account_id}:function:${p}*"
  ]

  lambda_layer_arns = [
    for p in var.project_name_prefixes :
    "arn:aws:lambda:${var.region}:${local.account_id}:layer:${p}*"
  ]

  log_group_arns = concat(
    flatten([
      for p in var.project_name_prefixes : [
        "arn:aws:logs:${var.region}:${local.account_id}:log-group:/aws/lambda/${p}*",
        "arn:aws:logs:${var.region}:${local.account_id}:log-group:/aws/lambda/${p}*:*",
        "arn:aws:logs:${var.region}:${local.account_id}:log-group:/apps/${p}*",
        "arn:aws:logs:${var.region}:${local.account_id}:log-group:/apps/${p}*:*",
      ]
    ]),
    [
      "arn:aws:logs:${var.region}:${local.account_id}:log-group:/apps/dm-chain-explorer",
      "arn:aws:logs:${var.region}:${local.account_id}:log-group:/apps/dm-chain-explorer:*",
    ],
  )

  # logs:DescribeLogGroups is a list API: IAM evaluates it against
  # log-group:* in the account/region, so specific log-group ARNs never match.
  log_groups_describe_arn = "arn:aws:logs:${var.region}:${local.account_id}:log-group:*"

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

  # Unity Catalog storage-credential roles — the only roles the boundary lets
  # assume themselves (Databricks requires self-assumption).
  uc_storage_role_arns = [
    "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/dm-databricks-*-s3-role",
  ]

  iam_instance_profile_arns = [
    for p in var.project_name_prefixes :
    "arn:aws:iam::${local.account_id}:instance-profile/${p}*"
  ]

  # Customer-managed IAM policies this project declares (e.g.
  # dm-databricks-dev-s3-policy, dm-databricks-hml-s3-policy) — a distinct
  # ARN namespace (arn:aws:iam::<acct>:policy/...) from roles.
  iam_policy_arns = [
    for p in var.project_name_prefixes :
    "arn:aws:iam::${local.account_id}:policy/${p}*"
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
