---
slug: tech-stack
title: Tech Stack
category: core
tldr: Python 3.12 Lambdas, Databricks Free Edition (DLT, Auto Loader, Lakeview), Terraform on S3 state, GitHub Actions CI, S3/DynamoDB/SSM on AWS.
summary: Technology reference for the three surfaces this repository owns — Terraform infrastructure, the GitHub Actions CI pipeline, and the Databricks artifacts plus two Python 3.12 Lambdas. Covers the shared dm-chain-utils library and how it is path-installed into the Lambda layer, the live AWS service surface, the single Free-Edition Databricks workspace, pinned IaC and provider versions, the CI toolchain under OIDC with its ruff/mypy/pytest/pip-audit gates, the single version axis, and the external APIs consumed.
tags:
  - tech-stack
  - python
  - aws
  - databricks
  - terraform
  - github-actions
last_updated: "2026-08-23"
release_origin: v0.5.0
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
| `boto3` | `==` pinned in the compiled lock | S3, DynamoDB, SSM |
| `requests` | `==` pinned in the compiled lock | Etherscan API |
| `dm-chain-utils` | local path `./utils` | Lambda layer (`dm_dynamodb`, `dm_etherscan`, `dm_parameter_store`) |

Every third-party requirement is `==`-pinned in a compiled, hash-checked lock file
(`pip install --require-hashes`). There is **no public-index pin of the library**: the
layer installs it from the repository path (`pip install ./utils --no-deps`), which is
what closes dependency confusion — no attacker-controlled name on a public index can
shadow it.

### Shared library: dm-chain-utils

Source at `utils/`, version equal to the release id, shipped as a Lambda layer built in
CI and stored content-addressed in S3.

| Module | Class | Purpose |
|--------|-------|---------|
| `dm_dynamodb` | `DMDynamoDB` | Single-table DynamoDB CRUD + conditional put + query |
| `dm_etherscan` | `EtherscanClient` | Etherscan API v2 — ABI retrieval, 4-byte signatures, block lookups |
| `dm_parameter_store` | `ParameterStoreClient` | SSM Parameter Store wrapper |

The library is exactly these three modules. The capture-era handlers (Kinesis, SQS,
Firehose, the Web3 client, the buffered CloudWatch logger, the API-key semaphore) were
deleted with the capture layer and must not be reintroduced.

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
| **IAM** | Lambda execution roles, the two Unity-Catalog storage-credential roles, and the four GitHub OIDC deploy roles under a permissions boundary | Least-privilege data-plane and CI access |

There is **no VPC and no container compute** in this project: nothing it runs needs a
network of its own.

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
| Authentication | PAT profile for `dev`/`hml` work; Databricks credentials in GitHub Secrets for CI | bundles `run_as` the workspace service principal; the host is a variable on every target |

### Infrastructure as Code

| Component | Version |
|-----------|---------|
| Terraform | single-sourced pin, matched by an exact `required_version` in every stack |
| AWS provider | pinned; a `.terraform.lock.hcl` is committed for every root stack |
| Databricks provider | pinned via `required_providers` |
| State backend | S3 `dm-chain-explorer-terraform-state` + DynamoDB lock table |

| Module | Path | Purpose |
|--------|------|---------|
| `cloudwatch_logs` | `services/modules/cloudwatch_logs/` | Log groups |
| `dynamodb` | `services/modules/dynamodb/` | Single-table DynamoDB with TTL + PITR |
| `lambda` | `services/modules/lambda/` | Functions, layers, S3 event triggers |
| `s3` | `services/modules/s3/` | Buckets with encryption, versioning, lifecycle |

Four modules, each declaring `required_providers`. The capture-era `kinesis`, `sqs`,
`ecs`, `vpc` and `iam` modules were deleted.

### CI/CD

| Component | Technology |
|-----------|-----------|
| Platform | GitHub Actions — 7 workflows (deploy apps, deploy infra, destroy infra, destroy all, drift detection, plan on PR, OpenSSF Scorecard) |
| Default branch | `main`, protected, with 9 required status checks |
| CI scripts | Bash helpers + `changed_stacks.py` + `stack_map.json` + `publish_oidc_vars.sh` under `scripts/ci/` |
| Terraform in CI | `terraform_wrapper: false` to preserve exit codes; the read-only plan path runs `-lock=false` |
| Quality gate | `ruff format --check`, `ruff check`, `mypy`, `pytest`, `pip-audit` |
| Workflow lint gate | `actionlint` (pinned installer + checksum) and `zizmor` must be clean |
| Terraform hygiene gate | `terraform fmt -check -recursive` + `terraform validate` in `plan_on_pr.yml` |
| AWS auth in CI | GitHub OIDC only — `role-to-assume` from `vars.AWS_DEPLOY_ROLE_{DEV,HML,PRD,READONLY}`, job-scoped `id-token: write`, a fail-fast preflight on an empty variable, and no static key anywhere |
| Supply chain | every action SHA-pinned under an allowlist, runner hardening on every job, `persist-credentials: false`, Dependabot enabled |

`scripts/ci/stack_map.json` is the declared single source for stack names, stack→module
mappings, upstream dependencies and `bootstrap_plannable` flags, consumed by both
`plan_on_pr.yml` change detection and the deploy gate.

### Development tools

| Tool | Purpose |
|------|---------|
| `ruff` | Format check + lint, enforced in CI |
| `mypy` | Static typing, enforced in CI |
| `pytest` | All four suites, `-p no:cacheprovider` |
| `make` | Thin wrappers over the scripts CI runs — no target exists that CI does not |
| `databricks bundle` | DABs validate / deploy / run |
| `aws` CLI | Read-only inspection of live infrastructure and Terraform state |

## Restrições e proibições

- No capture technology in this stack — no Kinesis, no Kinesis Firehose, no SQS, no ECS
  producer services. Do not reintroduce them; the S3 bucket is the boundary.
- Databricks Free Edition has serverless compute only: no job clusters, no instance
  pools, no `prod` deployment target.
- API keys are read from SSM at runtime and never committed, printed or logged.
- Terraform state is remote and shared — never *apply* with `-lock=false` (the read-only
  plan path is the sole, deliberate exception).
- Infrastructure changes reach AWS only through the CI pipeline applying Terraform, never
  through a console click or an ad-hoc CLI mutation.
- No binary artifact is tracked in git; the Lambda layer is built in CI and stored in S3.

## Referência

### Version axis

**One axis, the SDD release id.** The root `VERSION`, every `apps/dabs/*/VERSION`, the
`dm-chain-utils` distribution version, the git tag and the release directory all carry the
same `major.minor.patch`. A second axis is never introduced.

### Cross-project facts

- The `capture/ecr` Terraform state of **dd-chain-capture** (ECR repositories, IAM Roles
  Anywhere trust anchor and profiles, KMS key) is stored in this repository's state
  bucket `dm-chain-explorer-terraform-state`, with no source code here.
- SSM is a shared secret plane with dd-chain-capture; this repository consumes only the
  Etherscan keys.
- Cost after capture retirement: approximately **US$ 1–5 per month**.
