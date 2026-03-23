---
applyTo: "services/**/*.tf,services/**/variables.tf,services/**/outputs.tf,.github/workflows/*.yml"
---

# Terraform Infrastructure Management Rules

## Golden Rule: Terraform Only

**Never use AWS CLI (`aws` commands) to create, modify, or destroy cloud infrastructure resources.**

All persistent infrastructure resources must be declared in Terraform and managed via:
- `terraform plan` → review changes
- `terraform apply` → create/update resources
- `terraform destroy` → remove resources
- GitHub Actions workflows `deploy_cloud_infra.yml` / `destroy_cloud_infra.yml`

## Why This Rule Exists

Using AWS CLI to create resources outside Terraform causes:
- State drift (Terraform doesn't know about CLI-created resources)
- Schema conflicts (e.g., DynamoDB PK/SK uppercase vs lowercase)
- Race conditions in CI/CD (provision/teardown order not guaranteed)
- Resources left orphaned after `terraform destroy`

## Exceptions — AWS CLI is allowed for

- **Reading/querying** existing resources (e.g., `aws sqs get-queue-url`, `aws ecs list-tasks`, `aws cloudwatch get-metric-statistics`)
- **Ephemeral CI-only resources** that are not persistent infrastructure: ECS cluster created per integration-test run, Security Groups per CI run
- **S3 bucket emptying** before destroy (required — non-empty buckets cannot be deleted by Terraform)
- **ECR image cleanup** before destroy

## Remote State Backend — Never Destroy

All Terraform modules use the remote S3 backend:
- **Bucket**: `dm-chain-explorer-terraform-state`
- **Region**: `sa-east-1`
- **Lock table**: `dm-chain-explorer-terraform-lock` (DynamoDB)
- **Defined in**: `services/prd/01_tf_state/` (local state — must be preserved)

**Never run `terraform destroy` in `services/prd/01_tf_state/`** — destroying it would orphan all other state files.

## Destroy Order (reverse dependency)

When destroying infrastructure, always follow reverse dependency order:

| Env | Layer order (outermost first) |
|-----|-------------------------------|
| PRD | `06_lambda` + `07_ecs` → `05b_databricks_workspace` → `05a_databricks_account` → `04_peripherals` → `03_iam` → `02_vpc` |
| HML | `05_databricks` + `07_ecs` → `04_peripherals` → `03_iam` → `02_vpc` |
| DEV | `02_lambda` → `01_peripherals` |

Always empty S3 buckets before `terraform destroy` on any module that owns them.
