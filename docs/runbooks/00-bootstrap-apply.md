# Runbook — one-time apply of `services/prd/00_bootstrap`

**Owner:** the operator, with their own AWS credentials. This is the **only**
Terraform stack CI may never apply (O-1) — everything else in `services/**` is
applied by GitHub Actions through OIDC roles this stack itself creates.

## What this stack is

`services/prd/00_bootstrap` declares the GitHub OIDC provider reference and the
four CI roles CI assumes for every other apply:

- `dm-chain-explorer-gha-deploy-dev`
- `dm-chain-explorer-gha-deploy-hml`
- `dm-chain-explorer-gha-deploy-prd`
- `dm-chain-explorer-gha-readonly-plan`

Each role's `Allow` statements are scoped to this project's resource prefixes,
the shared state bucket + lock table, and (readonly role excluded) an explicit
`Deny` on `iam:*` against `dm-chain-explorer-gha-*` role ARNs and on
`iam:CreateAccessKey`/`AttachUserPolicy`/`PutUserPolicy` — the roles can never
grant themselves more privilege or mint new IAM users.

## Why it cannot be CI-applied

CI authenticates as one of these four roles. A role cannot be trusted to create
or modify the very roles that authorize it — that is a privilege-escalation
path, not a convenience. The bootstrap chicken-and-egg is broken by a human
applying it once, out-of-band, with their own credentials.

## Preconditions

1. `services/prd/00_bootstrap/**` has an **APPROVED** security-reviewer verdict
   on the IAM policy delta (T-A.2) naming this stack's commit sha.
2. `.terraform.lock.hcl` is committed for this stack (T-B.5) — applies never
   run against an unpinned provider version.
3. No other apply or plan is in flight (`gh run list --status in_progress`
   should be empty) — this stack shares the state bucket + lock table with
   every other stack.

## Steps

```bash
# 1. Confirm the preconditions above, then:
make prd_bootstrap_apply
# — this runs `terraform init` + `terraform apply` (interactive: review the
#   plan, type "yes") in services/prd/00_bootstrap, using YOUR OWN AWS
#   credentials (never a CI role — this is the one stack CI cannot touch).

# 2. Prove least privilege, before publishing the role ARNs anywhere:
aws iam list-roles --query "Roles[?starts_with(RoleName,'dm-chain-explorer-gha-')].RoleName"
aws iam list-attached-role-policies --role-name dm-chain-explorer-gha-deploy-prd
aws iam get-role-policy --role-name dm-chain-explorer-gha-deploy-prd --policy-name <inline-policy-name>
```

## After the apply

Publishing the four role ARNs as GitHub repository variables
(`AWS_DEPLOY_ROLE_{DEV,HML,PRD,READONLY}`) and deleting the legacy static
credentials is `scripts/ci/publish_oidc_vars.sh` (T-A.4) — a separate,
also-operator-run step, not part of this runbook.

## Rollback

`terraform destroy` in `services/prd/00_bootstrap` only after confirming no
workflow currently depends on the four roles (every other stack's apply would
start failing at the OIDC `configure-aws-credentials` step). There is no
partial-rollback path — this stack is applied and destroyed as a unit.
