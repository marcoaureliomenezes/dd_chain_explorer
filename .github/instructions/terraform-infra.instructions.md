---
applyTo: "services/**/*.tf,services/**/variables.tf,services/**/outputs.tf,.github/workflows/*.yml,scripts/ci/*.sh"
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
- **State drift** — Terraform doesn't know about the resource; next `apply` may duplicate or conflict
- **Schema conflicts** — e.g., DynamoDB PK/SK case, SQS names, IAM role names
- **Race conditions** — provision/teardown order is not guaranteed outside Terraform
- **Orphaned resources** — `terraform destroy` leaves CLI-created resources running, incurring cost
- **Lost control** — no single source of truth for what exists in each environment

## Mandatory Pipeline Order

**Every environment must have its persistent Terraform infrastructure applied BEFORE deploying applications:**

```
deploy_cloud_infra.yml (env=hml)  ──► deploy_all_dm_applications.yml
deploy_cloud_infra.yml (env=prd)  ──► deploy_all_dm_applications.yml
deploy_cloud_infra.yml (env=DEV)  ──► (dev local Docker Compose or Cloud AWS apps)
```

Never attempt to deploy applications into an environment where infrastructure has not been applied.

## Exceptions — AWS CLI IS allowed for

- **Reading/querying** existing resources (`aws sqs get-queue-url`, `aws ecs list-tasks`, `aws iam get-role`, `aws cloudwatch get-metric-statistics`, etc.)
- **Ephemeral CI-only Security Groups** — created per integration-test run (`dm-hml-sg-${GITHUB_RUN_ID}`), deleted in teardown; have no Terraform state impact
- **Ephemeral CI-only Lambda functions/layers** — HML test functions (`hml-contracts-ingestion-${RUN_ID}`, `hml-gold-to-dynamodb-${RUN_ID}`) are test artifacts, not persistent infra
- **Ephemeral CI-only ECS task definitions** — registered/deregistered per run; ECS CLUSTER is Terraform-managed
- **S3 bucket emptying** before destroy (`scripts/empty_s3_bucket.sh`) — required because non-empty buckets cannot be deleted by Terraform
- **ECR image cleanup** before destroy

## Explicitly Forbidden — Never Create These via AWS CLI or workflow inline code

```
aws ecs create-cluster       ← use services/hml/07_ecs or services/prd/07_ecs
aws ecs delete-cluster       ← use terraform destroy
aws sqs create-queue         ← use services/*/04_peripherals/main.tf (module.sqs)
aws dynamodb create-table    ← use services/*/04_peripherals/main.tf (module.dynamodb)
aws ecr create-repository    ← use services/*/07_ecs/main.tf (module.ecs.ecr_repositories)
aws kinesis create-stream    ← use services/*/04_peripherals/main.tf (module.kinesis)
aws iam create-role          ← use services/*/03_iam/main.tf
aws ec2 create-vpc           ← use services/*/02_vpc/main.tf
```

## Import Rule — Mandatory for Out-of-Band Resources

If a resource was accidentally created outside Terraform, it MUST be imported immediately:

```bash
cd services/<env>/<module>
terraform init
terraform import <resource_address> <resource_id>
# Verify: terraform plan must show zero changes after import
git add .terraform.lock.hcl
git commit -m "terraform: import <resource> into <env>/<module> state"
```

Do not leave manually-created resources unimported. They will be duplicated or drift on the next `apply`.

## Remote State Backend — Shared, Never Destroy

All Terraform modules use the same remote S3 backend:

| Setting | Value |
|---------|-------|
| Bucket  | `dm-chain-explorer-terraform-state` |
| Region  | `sa-east-1` |
| Lock table | `dm-chain-explorer-terraform-lock` (DynamoDB) |
| Encryption | enabled |

**Never run `terraform destroy` in `services/prd/01_tf_state/`** — destroying it would orphan every other state file.

## Terraform State Keys by Environment

| Env | Module | State S3 Key |
|-----|--------|-------------|
| PRD | 02_vpc | `prd/vpc/terraform.tfstate` |
| PRD | 03_iam | `prd/iam/terraform.tfstate` |
| PRD | 04_peripherals | `prd/peripherals/terraform.tfstate` |
| PRD | 05a_databricks_account | `prd/databricks-account/terraform.tfstate` |
| PRD | 05b_databricks_workspace | `prd/databricks-workspace/terraform.tfstate` |
| PRD | 06_lambda | `prd/lambda/terraform.tfstate` |
| PRD | 07_ecs | `prd/ecs/terraform.tfstate` |
| HML | 02_vpc | `hml/vpc/terraform.tfstate` |
| HML | 03_iam | `hml/iam/terraform.tfstate` |
| HML | 04_peripherals | `hml/peripherals/terraform.tfstate` |
| HML | 07_ecs | `hml/ecs/terraform.tfstate` |
| DEV | 01_peripherals | `dev/peripherals/terraform.tfstate` |
| DEV | 02_lambda | `dev/lambda/terraform.tfstate` |

## Resource Ownership by Environment

| Resource | DEV | HML | PRD | Managed By |
|----------|-----|-----|-----|-----------|
| VPC + Subnets | — | `02_vpc` | `02_vpc` | Terraform |
| IAM roles (ECS, Lambda) | — | `03_iam` | `03_iam` | Terraform |
| S3 buckets | `01_peripherals` | `04_peripherals` | `04_peripherals` | Terraform |
| DynamoDB table | `01_peripherals` | `04_peripherals` | `04_peripherals` | Terraform |
| Kinesis streams + Firehose | `01_peripherals` | `04_peripherals` | `04_peripherals` | Terraform |
| SQS queues | `01_peripherals` | `04_peripherals` | `04_peripherals` | Terraform |
| CloudWatch log groups | `01_peripherals` | `04_peripherals` | `04_peripherals` | Terraform |
| ECS cluster | — | `07_ecs` | `07_ecs` | Terraform |
| ECR repositories | — | `07_ecs` | `07_ecs` | Terraform |
| Lambda functions | `02_lambda` | ephemeral per CI run | `06_lambda` | Terraform (PRD/DEV), CLI (HML test) |
| Security Group (HML) | — | ephemeral per CI run | — | AWS CLI (intentional, per-run SG) |
| ECS task definitions (HML) | — | ephemeral per CI run | — | AWS CLI (intentional, per-run) |

## HML Cost Control Strategy

HML Kinesis streams are **destroyed after each pipeline run** (targeted Terraform destroy in `all-hml-teardown`) and **re-created at the start of the next run** (idempotent `all-hml-infra-apply`). This eliminates idle Kinesis costs while maintaining full state control.

The HML ECS cluster is **persistent** (Terraform-managed, always active). ECS tasks are stopped after tests but the cluster remains, avoiding re-creation overhead and ECS task definition orphaning.

## HML Cluster Name

The HML ECS cluster is named `dm-chain-explorer-ecs-hml` (set by `services/hml/07_ecs/main.tf`).
The workflow env var `HML_ECS_CLUSTER` must always equal `dm-chain-explorer-ecs-hml`.

## Destroy Order (reverse dependency)

When destroying infrastructure, always follow reverse dependency order:

| Env | Layer order (outermost first) |
|-----|-------------------------------|
| PRD | `06_lambda` + `07_ecs` → `05b_databricks_workspace` → `05a_databricks_account` → `04_peripherals` → `03_iam` → `02_vpc` |
| HML | `05_databricks` + `07_ecs` → `04_peripherals` → `03_iam` → `02_vpc` |
| DEV | `02_lambda` → `01_peripherals` |

Always empty S3 buckets before `terraform destroy` on any module that owns them.
