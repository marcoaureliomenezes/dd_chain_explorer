# GitHub CI/CD – dd_chain_explorer

This document describes the GitFlow strategy, GitHub Actions workflows, required secrets, and branch protection rules for the `dd_chain_explorer` project.

---

## GitFlow

```
main
 └── release/x.y.z     ← RC branch; merged into main + develop after release
       └── develop      ← integration branch; all feature/fix PRs target here
             ├── feature/<short-description>
             ├── fix/<short-description>
             └── chore/<short-description>
```

| Branch pattern | Purpose | Direct push |
|---|---|---|
| `main` | Production-ready code only | ❌ PRs only |
| `develop` | Integration of finished features | ❌ PRs only |
| `release/*` | Release candidates | ❌ PRs only |
| `feature/*` | New features | ✅ author only |
| `fix/*` | Bug fixes | ✅ author only |
| `chore/*` | Maintenance / deps | ✅ author only |
| `infra/*` | Infrastructure changes | ✅ author only |

### Commit message convention

```
<type>(<scope>): <short summary>

feat(stream): add broker pre-warm on producer init
fix(batch): handle empty Etherscan response
chore(deps): bump confluent-kafka to 2.5.0
infra(ecs): add ECR repositories to Terraform
ci(deploy): migrate DockerHub → ECR
docs(readme): update GitFlow section
```

---

## Workflows

| Workflow | File | Trigger |
|---|---|---|
| **CI – dm-chain-utils** | `ci_lib.yml` | push/PR on `utils/**` |
| **Deploy Apps** | `deploy_apps.yml` | push to `main` on `docker/**` or `utils/**` |
| **CI – Terraform Plan** | `ci_terraform_plan.yml` | PR on `services/prd/terraform/**` |

### `ci_lib.yml` jobs

1. **test** — `pytest tests/unit/ -v --tb=short`
2. **build** — `python -m build --wheel` → upload artifact `dm-chain-utils-wheel`

### `deploy_apps.yml` jobs

1. **lint-and-test** — pytest unit tests + Docker Compose validation (gate for all builds)
2. **detect-changes** — determines which images to build based on changed paths
3. **build-push-stream** — builds `onchain-stream-txs` image, pushes to ECR, updates ECS streaming services
4. **build-push-batch** — builds `onchain-batch-txs` image, pushes to ECR, registers new batch task definition

### `ci_terraform_plan.yml` jobs

1. **detect-modules** — detects which Terraform modules changed in the PR
2. **terraform-plan** (matrix) — `terraform init` + `validate` + `plan` per changed module; posts plan as PR comment

---

## Required GitHub Secrets

Run `scripts/setup_github_secrets.sh` to configure all secrets via the `gh` CLI.

| Secret | Description | Source |
|---|---|---|
| `AWS_ACCESS_KEY_ID` | IAM user access key ID for CI | AWS IAM console |
| `AWS_SECRET_ACCESS_KEY` | IAM user secret access key for CI | AWS IAM console |
| `DATABRICKS_PROD_HOST` | Databricks workspace URL | Databricks workspace settings |
| `DATABRICKS_PROD_TOKEN` | Databricks personal access token | Databricks user settings |
| `MSK_BOOTSTRAP_SERVERS` | MSK cluster bootstrap broker string | AWS MSK console |

> **Removed secrets** (no longer needed after ECR migration):
> - `DOCKERHUB_USERNAME`
> - `DOCKERHUB_TOKEN`

---

## Branch Protection Rules

Configure these rules on `main` and `develop` via **Settings → Branches → Add rule**:

### `main`
- ✅ Require a pull request before merging
- ✅ Require approvals: **1**
- ✅ Dismiss stale pull request approvals when new commits are pushed
- ✅ Require status checks to pass before merging:
  - `Compose lint & unit tests`
- ✅ Require branches to be up to date before merging
- ✅ Do not allow bypassing the above settings

### `develop`
- ✅ Require a pull request before merging
- ✅ Require status checks to pass before merging:
  - `Compose lint & unit tests` (when `docker/**` or `utils/**` change)
  - `Plan – <module>` (when `services/prd/terraform/**` change)
- ✅ Allow force pushes: **disabled**

---

## Local Setup

```bash
# Install library for local development
pip install -e "dd_chain_explorer/utils/[dev]"

# Run unit tests
pytest dd_chain_explorer/utils/tests/unit/ -v

# Validate compose files
docker compose -f dd_chain_explorer/services/dev/compose/app_services.yml config
docker compose -f dd_chain_explorer/services/dev/compose/batch_services.yml config

# Build stream image locally (from dd_chain_explorer root)
cd dd_chain_explorer
docker build -f docker/onchain-stream-txs/Dockerfile -t onchain-stream-txs:dev .
```
