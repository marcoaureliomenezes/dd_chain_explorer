---
slug: tech-stack
title: Tech Stack
category: core
tldr: Python 3.12 Lambdas, Databricks Free Edition (DLT, Auto Loader, Lakeview), Terraform on S3 state, GitHub Actions CI, S3/DynamoDB/SSM on AWS.
summary: Technology reference for the three surfaces this repository owns — Terraform infrastructure, the GitHub Actions CI pipeline, and the Databricks artifacts plus two Python 3.12 Lambdas. Covers the shared dm-chain-utils library, the live AWS service surface after capture retirement, the single Free-Edition Databricks workspace, IaC and provider versions, the CI toolchain and its OIDC authentication gap, the two version axes, and the external APIs consumed.
tags:
  - tech-stack
  - python
  - aws
  - databricks
  - terraform
  - github-actions
last_updated: "2026-08-23"
release_origin: v0.4.0
---

## Visão geral

Every agent must verify version compatibility against this file before generating code.
The stack spans three surfaces: Terraform infrastructure (`services/`), the GitHub
Actions control plane (`.github/workflows/` + `scripts/ci/`), and the data-processing
artifacts (`apps/dabs/` for Databricks, `apps/lambda/` for AWS Lambda). Blockchain
capture technology is **not** part of this stack — it belongs to the external
dd-chain-capture project, which meets this one at the S3 raw bucket.

## Linguagens

| Component | Version | Notes |
|-----------|---------|-------|
| Python | 3.12 | Lambdas, `dm-chain-utils`, DABs batch jobs |
| PySpark | >= 3.5 | DLT pipelines and batch jobs on Databricks |
| HCL (Terraform) | >= 1.5 | All infrastructure |
| Bash | — | `scripts/ci/` helpers and integration tests |
| SQL | — | DLT transformations, Lakeview dashboard queries |

## Dependências aprovadas

### Lambda functions (`apps/lambda`)

| Package | Version | Usage |
|---------|---------|-------|
| `boto3` | >= 1.26.0 | S3, DynamoDB, SSM |
| `requests` | >= 2.28.0 | Etherscan API |
| `dm-chain-utils` | >= 0.2.9 | Lambda layer (`dm_dynamodb`, `dm_etherscan`, `dm_parameter_store`) |

### Shared library: dm-chain-utils

Source at `utils/`, version synced with the root `VERSION` file, shipped as a Lambda
layer.

| Module | Class | Purpose | Live caller here |
|--------|-------|---------|------------------|
| `dm_dynamodb` | `DMDynamoDB` | Single-table DynamoDB CRUD + conditional put + query | yes |
| `dm_etherscan` | `EtherscanClient` | Etherscan API v2 — ABI retrieval, 4-byte signatures, block lookups | yes |
| `dm_parameter_store` | `ParameterStoreClient` | SSM Parameter Store wrapper | yes |
| `dm_kinesis` | `KinesisHandler` | Kinesis producer/consumer | no — capture-era export, retained in the library |
| `dm_sqs` | `SQSHandler` | SQS producer/consumer | no — capture-era export, retained in the library |
| `dm_firehose` | `FirehoseHandler` | Firehose Direct Put delivery | no — capture-era export, retained in the library |
| `dm_cloudwatch_logger` | `CloudWatchLoggingHandler` | Buffered structured JSON logging | no |
| `dm_web3_client` | `Web3Handler` | Web3.py block/transaction extraction | no |
| `api_keys_manager` | `APIKeysManager` | DynamoDB semaphore for API-key rotation | no |

### External APIs

| API | Authentication | Usage | Key storage |
|-----|---------------|-------|------------|
| Etherscan API v2 | API key | Contract ABI retrieval and contract transactions (contracts-ingestion Lambda) | SSM `/etherscan-api-keys/api-key-{1..6}` |
| Ethereum RPC (Infura / Alchemy) | API key per provider | Consumed by dd-chain-capture, not by this repo | SSM `/web3-api-keys/infura/*`, `/web3-api-keys/alchemy/*` — shared secret plane |

## Runtimes e ferramentas

### AWS surface

| Service | Configuration | Usage |
|---------|--------------|-------|
| **S3** | `dm-chain-explorer-raw-data`, `-lakehouse`, `-databricks`, `-dev-ingestion`, `-terraform-state` | Raw landing zone (integration boundary), Delta storage, gold exports, remote state |
| **DynamoDB** | Single table `dm-chain-explorer[-dev]`, on-demand, PITR on prd | CONTRACT and CONSUMPTION entities; `dm-chain-explorer-terraform-lock` for state locking |
| **Lambda** | 2 functions, Python 3.12, `dm-chain-utils` layer | `contracts-ingestion`, `gold-to-dynamodb` |
| **EventBridge Scheduler** | `rate(1 hour)` | Triggers contracts ingestion |
| **CloudWatch Logs** | Log groups per app/function | Lambda and application logs |
| **SSM Parameter Store** | 27 SecureString parameters | Web3 and Etherscan API keys |
| **IAM** | Roles for Lambda, Databricks cross-account and cluster access | Least-privilege data-plane access |
| **VPC (prd)** | 10.0.0.0/16, 1 public + 2 private subnets | Declared for Databricks; no compute currently attached |

Region: **sa-east-1** (São Paulo). Naming convention: `dm-{env}-` or
`dm-dd-chain-explorer-{env}-`; `dev` = development, `hml` = homologation, no suffix or
`prd` = production.

### Databricks

| Component | Configuration | Notes |
|-----------|--------------|-------|
| Workspace | **one, Free Edition** | Serverless compute only; there is no production workspace |
| Targets / catalogs | `dev` (assets prefixed `[dev]`) and `hml` (unprefixed) | The `prod` target is not deployable and is guarded |
| Unity Catalog | 29 objects in `dev` — 12 streaming tables + 17 materialized views | See [[data-catalog]] |
| DLT | `dm-ethereum` (24 tables, 11 expectations), `dm-app-logs` (5 tables) | Triggered mode; triggers currently PAUSED |
| Auto Loader | `cloudFiles`, JSON | Reads `raw/mainnet-*/` from the S3 raw bucket |
| Lakeview dashboards | 4 ACTIVE | Network Overview, Gas Analytics, Hot Contracts, API Health |
| SQL Warehouse | Serverless | Dashboard queries |
| Authentication | PAT profile for `dev`/`hml` work; PAT in GitHub Secrets for CI | No OAuth M2M service principal is in use |

### Infrastructure as Code

| Component | Version |
|-----------|---------|
| Terraform | >= 1.5 (CI pins 1.7.0; local applies used 1.13–1.15 — version drift across states) |
| AWS provider | `hashicorp/aws >= 5.0` (no `.terraform.lock.hcl` committed) |
| Databricks provider | `databricks/databricks` (latest compatible) |
| State backend | S3 `dm-chain-explorer-terraform-state` + DynamoDB lock table |

| Module | Path | Purpose |
|--------|------|---------|
| `cloudwatch_logs` | `services/modules/cloudwatch_logs/` | Log groups (the Firehose branch is disabled everywhere) |
| `dynamodb` | `services/modules/dynamodb/` | Single-table DynamoDB with TTL + PITR |
| `ecs` | `services/modules/ecs/` | Cluster + ECR — an empty shell since capture retirement |
| `iam` | `services/modules/iam/` | Roles and policies for Lambda, Databricks, ECS |
| `lambda` | `services/modules/lambda/` | Functions, layers, S3 event triggers |
| `s3` | `services/modules/s3/` | Buckets with encryption, versioning, lifecycle |
| `vpc` | `services/modules/vpc/` | VPC, subnets, IGW, SG, S3 VPC endpoint |

The `kinesis` and `sqs` modules were deleted with the capture layer.

### CI/CD

| Component | Technology |
|-----------|-----------|
| Platform | GitHub Actions — 7 workflows (deploy apps, deploy infra, destroy infra, destroy all, auto-bump version, drift detection, plan on PR) present on `develop` and feature branches |
| Default branch | `master`; last CI run 2026-04-11 |
| CI scripts | 18 Bash helpers + `changed_stacks.py` + `stack_map.json` under `scripts/ci/` |
| Integration tests | 5 Bash scripts under `scripts/` |
| Terraform in CI | `terraform_wrapper: false` to preserve exit codes |
| Workflow lint gate | `actionlint` must exit 0 on every workflow |
| Terraform hygiene gate | `terraform fmt -check -recursive` + `terraform validate` in `plan_on_pr.yml` |
| AWS auth in CI (intended) | GitHub OIDC `role-to-assume` via `vars.AWS_DEPLOY_ROLE_{DEV,HML,PRD,READONLY}` with `permissions: id-token: write`; no static keys referenced by any workflow |

**Gap — CI cannot authenticate to AWS today.** The OIDC roles declared in
`services/prd/03_iam/oidc.tf` were never applied and the `vars.AWS_DEPLOY_ROLE_*`
repository variables do not exist, so every `configure-aws-credentials` step fails
*(gap — see audit `20260823T145726Z-4db47555`)*. The design above describes the intent,
not the running state.

`scripts/ci/stack_map.json` is the declared single source for stack names, stack→module
mappings, upstream dependencies and `bootstrap_plannable` flags, consumed by both
`plan_on_pr.yml` change detection and the deploy gate.

### Development tools

| Tool | Purpose |
|------|---------|
| `make` | Developer shortcuts |
| `databricks bundle` | DABs validate / deploy / run |
| `aws` CLI | Read-only inspection of live infrastructure and Terraform state |

## Restrições e proibições

- No capture technology in this stack — no Kinesis, no Kinesis Firehose, no SQS, no ECS
  producer services. Do not reintroduce them; the S3 bucket is the boundary.
- Databricks Free Edition has serverless compute only: no job clusters, no instance
  pools, no `prod` deployment target.
- API keys are read from SSM at runtime and never committed, printed or logged.
- Terraform state is remote and shared — never apply with `-lock=false`.

## Referência

### Version axes

Two independent version axes coexist and must not be conflated:

| Axis | Where | Current |
|------|-------|---------|
| Artifact version | root `VERSION`, `dm-chain-utils` distribution, CI artifact tags `v0.2.9-*` | `0.2.9` |
| SDD release id | `specs/releases/` | `v0.3.0` shipped; `v0.4.0` closing |

### Cross-project facts

- The `capture/ecr` Terraform state of **dd-chain-capture** (ECR repositories, IAM Roles
  Anywhere trust anchor and profiles, KMS key) is stored in this repository's state
  bucket `dm-chain-explorer-terraform-state`, with no source code here.
- SSM is a shared secret plane with dd-chain-capture; this repository consumes only the
  Etherscan keys.
- Cost after capture retirement: approximately **US$ 1–5 per month**.
