# -----------------------------------------------------------------------
# NOTE — the GitHub Actions OIDC provider reference and the four gha_* roles
# (oidc.tf) moved to services/prd/00_bootstrap (T-B.3a, D14): 03_iam has one
# applier and that stack owns their apply going forward. Their outputs live
# there now.
#
# NOTE (T-B.3, security rev3 HIGH) — the ECS task/task-execution role
# outputs were removed with the roles themselves (see iam.tf). This stack
# currently has no outputs.
# -----------------------------------------------------------------------
