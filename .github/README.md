# GitHub CI/CD – dd_chain_explorer

This document describes the GitFlow strategy, GitHub Actions workflows, required secrets, and branch protection rules for the `dd_chain_explorer` project.

---

## GitFlow

```
master  (protected — no direct push)
  └── release/<scope>-v<ver>   ← auto-created by CI after HML test passes
        └── develop             ← protected; all PRs target here
              ├── feature/<short-description>
              └── hotfix/<short-description>
```

| Branch pattern | Purpose | Direct push | PR targets |
|---|---|---|---|
| `master` | Production state | ❌ PRs only | — |
| `develop` | Integration branch | ❌ PRs only | — |
| `release/*` | Auto-created by CI after HML pass | ❌ PRs only | — |
| `feature/*` | New features | ✅ author | `develop` |
| `hotfix/*` | Urgent bug fixes | ✅ author | `develop` |

> **Rule**: PRs may only target `develop`. Merging `release/*` → `master` is done by CI after prod deploy approval.

### Commit message convention

```
<type>(<scope>): <short summary>

feat(stream): add broker pre-warm on producer init
fix(batch): handle empty Etherscan response
chore(deps): bump confluent-kafka to 2.5.0
infra(ecs): add ECR repositories to Terraform
ci(deploy): redesign streaming pipeline with HML stage
docs(readme): update GitFlow section
```

---

## Workflows

All deploy workflows are `workflow_dispatch` only and enforce execution from the `develop` branch via a `branch-guard` job.

| Workflow | File | Trigger | Scope |
|---|---|---|---|
| **Deploy Streaming Apps** | `deploy_streaming_apps.yml` | Manual (`develop`) | `docker/onchain-stream-txs/` → ECR → ECS |
| **Deploy Batch Apps** | `deploy_batch_apps.yml` | Manual (`develop`) | `docker/onchain-batch-txs/` → ECR → ECS task def |
| **Deploy Databricks (DABs)** | `deploy_databricks.yml` | Manual (`develop`) | `dabs/` → Databricks HML → Databricks PROD |
| **Deploy Lib Utils** | `deploy_lib_utils.yml` | Manual (`develop`) | `utils/` → PyPI |
| **Deploy Cloud Infra DEV** | `deploy_cloud_infra_dev.yml` | Manual (`develop`) | `services/dev/terraform/1_aws_core/` → AWS DEV |
| **Deploy Cloud Infra PRD** | `deploy_cloud_infra_prd.yml` | Manual (`develop`) | `services/hml/1_aws_core/` + `services/prd/` → AWS HML + PRD |

---

## Pipeline Flow — Deploy Streaming Apps

```
develop branch
  │
  ├─ branch-guard         enforce develop
  ├─ lint-and-test         pytest + compose validate
  ├─ check-idempotency     skip if SHA already deployed
  ├─ build-rc              ECR :rc-{sha}  (HML only, not prod)
  │
  ├─ hml-provision         spin up: ECS cluster + Kafka (KRaft) + Schema Registry + SG
  ├─ hml-integration-test  run RC image × 10 min, poll CloudWatch for ERRORs
  ├─ hml-teardown          always: stop tasks, delete cluster, SG, DynamoDB HML table
  │
  ├─ create-release-branch  release/onchain-stream-v{version}
  │
  └─ prod-deploy           ← requires GitHub Environment approval
       ├─ promote :rc-{sha} → :{sha} + :latest  in ECR
       ├─ register new ECS task definitions
       └─ aws ecs wait services-stable
```

---

## Secrets

### Existing

| Secret | Used by |
|---|---|
| `AWS_ACCESS_KEY_ID` | all |
| `AWS_SECRET_ACCESS_KEY` | all |
| `DATABRICKS_ACCOUNT_ID` | deploy_cloud_infrastructure |
| `DATABRICKS_CLIENT_ID` | deploy_cloud_infrastructure |
| `DATABRICKS_CLIENT_SECRET` | deploy_cloud_infrastructure |
| `DATABRICKS_HML_HOST` | deploy_databricks |
| `DATABRICKS_HML_TOKEN` | deploy_databricks |

### New (required for HML pipelines — CICD-17)

| Secret | Used by | Description |
|---|---|---|
| `HML_VPC_ID` | deploy_streaming_apps, deploy_batch_apps | VPC ID for ephemeral HML SG |
| `HML_SUBNET_ID` | deploy_streaming_apps, deploy_batch_apps | Public subnet for Fargate tasks |
| `ECS_TASK_EXECUTION_ROLE_ARN` | deploy_streaming_apps, deploy_batch_apps | ECS execution role (ECR pull, CW logs) |
| `ECS_TASK_ROLE_ARN` | deploy_streaming_apps, deploy_batch_apps | ECS task role (DynamoDB access) |

---

## GitHub Environments

| Environment | Used by | Behaviour |
|---|---|---|
| `production` | deploy_streaming_apps, deploy_databricks, deploy_cloud_infra_prd, deploy_lambda_functions | Manual approval required before prod stage |
| `hml` | deploy_cloud_infra_prd | Auto-approve for HML Terraform apply |
| `dev` | deploy_cloud_infra_dev | Auto-approve for DEV Terraform apply |
| `release` | deploy_lib_utils | OIDC trusted publisher for PyPI |

> Create these in **Settings → Environments** before running the pipelines.

---

## Branch Protection Rules (CICD-15 — pending)

Configure in **Settings → Branches**:

- `master`: require PR, 1 approving review, no direct push
- `develop`: require PR, 1 approving review, no direct push, require status checks (`lint-and-test`)
