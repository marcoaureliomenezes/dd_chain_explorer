---
slug: tech-stack
title: Tech Stack
category: core
tldr: Python 3.12 + PySpark on Databricks serverless jobs, Terraform 1.10 (S3-native locking) with aws / databricks ~>1.133 / github ~>6.6 providers, ECS Fargate Spot + ECR + EventBridge Scheduler, all in us-east-1 with SSE-S3; GitHub Actions under OIDC and a GitHub App.
summary: Technology reference for the three repositories after release v0.7.0's rulings. Languages and pins, the Terraform toolchain (1.10.5 in CI, required_version ~> 1.10, use_lockfile, committed lock files), provider versions, the AWS surface in us-east-1 (S3, ECR, ECS Fargate Spot, EventBridge Scheduler, IAM, CloudWatch Logs), the Databricks surface (Premium account, SERVERLESS workspaces, Unity Catalog with file events, serverless jobs STANDARD, a dev-only serverless SQL warehouse), the CI toolchain, and the prohibitions — no DLT, Lambda, DynamoDB, KMS CMK, Kinesis or sa-east-1.
tags:
  - tech-stack
  - python
  - pyspark
  - aws
  - databricks
  - terraform
  - github-actions
last_updated: "2026-09-23"
release_origin: v0.7.0
---

## Visão geral

**Status 2026-09-23.** DECIDED stack, written on the `feature/0.7.0` branches; the us-east-1
runtime is not applied yet ([[architecture]] §Estado runtime). Verify every version here
before generating code.

## Linguagens

| Component | Version | Where |
|---|---|---|
| Python | 3.12 | capture images (`python:3.12-slim`), bundle tasks, `dm_market_parsers`, CI scripts, tests |
| PySpark | serverless environment client `2` | the three `job_market_data` tasks; no library installed on compute |
| SQL | Databricks SQL | `CREATE TABLE … LOCATION`, MERGE, gold overwrites |
| HCL | Terraform 1.10.5 in CI; `required_version = "~> 1.10"` (bootstrap `>= 1.10.0`) | every stack |
| Bash | — | `scripts/ci/`, `scripts/seed/trust_seed.sh` |

## Dependências aprovadas

| Provider | Pin | Stacks |
|---|---|---|
| `hashicorp/aws` | `>= 5.0` (bootstrap `>= 4.60.0`) | every AWS-touching stack |
| `databricks/databricks` | `~> 1.133` (SERVERLESS `compute_mode`, `enable_file_events`) | `account/databricks`, `*/05_workspace`, `*/04_unity_catalog` |
| `integrations/github` | `~> 6.6`, `app_auth` | `*/06_github` |
| `hashicorp/time` | `~> 0.12` | `*/04_unity_catalog` (IAM propagation wait) |

- Every root stack commits its `.terraform.lock.hcl`. Modules: `s3`, `cloudwatch_logs`,
  `databricks_workspace`, `unity_catalog`.
- Explorer: pure-Python `dm_market_parsers` (no third-party runtime deps); dev tooling from
  a hash-pinned `requirements-dev.txt`; tests run without `pyspark`.
- Capture: one landing library `dm_capture_landing` shared by the three images.

## Runtimes e ferramentas

### AWS — us-east-1 only

| Service | Use |
|---|---|
| S3 | `dm-chain-explorer-{dev,prd}-{raw,lakehouse}`, state `dm-chain-explorer-tfstate-use1`; SSE-S3, Block Public Access, versioned state |
| ECR | three capture repos, MUTABLE, scan on push; lifecycle: untagged expire after 1 day, keep the 10 most recent |
| ECS Fargate / Fargate Spot | capture tasks, default capacity FARGATE_SPOT, default VPC, egress-only SG |
| EventBridge Scheduler | seven capture schedules, DISABLED |
| IAM | OIDC deploy/read-only/capture-publish roles under a permissions boundary; per-image task roles; UC roles `dm-chain-explorer-<env>-uc`; MFA-gated dev raw writer |
| CloudWatch Logs | capture task log group, 14-day retention |

### Databricks

| Component | Configuration |
|---|---|
| Account | Premium on AWS, card-billed; Terraform auth by the account SP `dm-chain-explorer-terraform` (OAuth M2M) |
| Metastore | one, `dm-chain-explorer-use1`, us-east-1 |
| Workspaces | `dm-chain-explorer-{dev,prd}`, `compute_mode = SERVERLESS` — no VPC, no NAT, no clusters |
| Unity Catalog | file events on both external locations (managed SNS/SQS `csms-*`); external tables only |
| Jobs | serverless, `performance_target: STANDARD`, `max_concurrent_runs: 1`, queue on |
| SQL warehouse | dev only: serverless PRO, 2X-Small, auto-stop 1 min, 1 cluster |
| Bundles | Databricks CLI via `databricks/setup-cli` v1.13.0 (SHA-pinned); `artifact_path` on the UC volume |

### CI/CD

| Component | Technology |
|---|---|
| Platform | GitHub Actions in all three repos; every action SHA-pinned, runner hardening, `persist-credentials: false` |
| AWS auth | GitHub OIDC only, job-scoped `id-token: write` |
| Cross-repo auth | GitHub App `dm-chain-explorer-ci` — `actions/create-github-app-token`, one-hour token per job, scoped to one repo and the permissions it needs |
| Quality gate | `ruff format --check`, `ruff check`, `mypy`, `pytest -p no:cacheprovider`, `pip-audit`, `actionlint`, `zizmor`; `terraform fmt -check` + `validate` |

## Restrições e proibições

- us-east-1 only; no `sa-east-1` literal outside `docs/legacy` (AC-25).
- No DLT, no `dlt` import, no `pipelines:` resource; no Lambda, DynamoDB, KMS CMK
  (`aws_kms_key`, `aws:kms`), Kinesis, SQS producer, Web3 client.
- State locking by `use_lockfile` only — no `dynamodb_table` backend line.
- No static AWS key, no PAT; secret values are typed once into the seed or written by
  Terraform, never copied or echoed.
- Infrastructure changes reach the cloud only through CI applying Terraform, except the
  trust seed.

## Referência

### Version axis

One axis, the SDD release id (`0.7.0`): root `VERSION`, bundle `VERSION`, tags and the
release directory carry the same `major.minor.patch`.

### Naming

`dm-chain-explorer-<env>-<purpose>` for buckets, workspaces, SPs and UC roles; ECR
`dm-chain-explorer-capture/<image>`; GitHub environments `dev` and `production`.
