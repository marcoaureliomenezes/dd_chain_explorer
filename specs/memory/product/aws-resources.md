---
slug: aws-resources
title: AWS Resources
category: product
tldr: Target inventory in us-east-1 (buckets dm-chain-explorer-{dev,prd}-{raw,lakehouse}, state dm-chain-explorer-tfstate-use1, ECR ×3, Fargate capture runtime, IAM) plus the live sa-east-1 teardown status — dev lane and capture/ecr destroyed, prd stacks pending PR #11.
summary: Single reference for every AWS object the platform owns. Part one is the us-east-1 target of release v0.7.0 (R29-R34) — Terraform stacks and state keys on dm-chain-explorer-tfstate-use1 with S3-native locking, four data buckets with SSE-S3, ECR, the dev capture runtime, IAM (OIDC roles, capture publish, task roles, UC roles, MFA-gated writer, permissions boundary). Part two is the sa-east-1 teardown as of 2026-09-23 — what run 35817189275 destroyed, and what still exists (prd/04_peripherals, prd/06_lambda, the old state bucket and lock table, the bootstrap roles and their state).
tags:
  - aws
  - infrastructure
  - s3
  - ecr
  - ecs
  - iam
  - terraform
  - us-east-1
last_updated: "2026-09-23"
release_origin: v0.7.0
---

## Propósito

**Status 2026-09-23.** us-east-1: DECIDED, coded on infra `feature/0.7.0-us-east-1`
(PR-β), **nothing applied**. sa-east-1: teardown in progress — see §Referência.

The one list of AWS objects, their owning stack and their live state. Anything not listed
here, or owned by no stack, is a defect.

## Fluxo de uso

1. Seed S1 (operator, MFA): `prd/01_tf_state` creates the state bucket (local state),
   `prd/00_bootstrap` migrates to it and applies, OIDC variables are published, account
   Block Public Access is set, then the sa-east-1 state bucket and lock table are deleted.
2. Every other stack applies through the lanes ([[cicd-pipeline]]).

## Trigger típico

Consulted before adding, renaming, granting or destroying any AWS object.

## Diferencial

One region, one state bucket, no DynamoDB, no KMS: fewer objects, no lock table to go stale,
SSE-S3 everywhere (R30, R33).

## Estado runtime tocado

### Stacks and state keys (us-east-1, `s3://dm-chain-explorer-tfstate-use1/`, `use_lockfile`)

| Stack | Key | Owns | Applied by |
|---|---|---|---|
| `prd/01_tf_state` | local | state bucket | operator (S1) |
| `prd/00_bootstrap` | `prd/bootstrap/` | OIDC roles, boundary, operator debug role | operator (S1) |
| `prd/04_peripherals` | `prd/peripherals/` | ECR ×3, `dm-chain-explorer-prd-{raw,lakehouse}` | prd lane (gated) |
| `dev/01_peripherals` | `dev/peripherals/` | `dm-chain-explorer-dev-{raw,lakehouse}`, MFA-gated writer role | dev lane |
| `dev/03_capture` | `dev/capture/` | ECS cluster, SG, task roles/defs, log group, 7 schedules DISABLED | dev lane |
| `{env}/04_unity_catalog` | `{env}/unity-catalog/` | UC IAM role `dm-chain-explorer-<env>-uc` (+ UC objects, [[data-catalog]]) | lanes |

`account/databricks`, `{env}/05_workspace`, `{env}/06_github` hold no AWS object.

### S3 (SSE-S3 `AES256`, Block Public Access)

| Bucket | Purpose |
|---|---|
| `dm-chain-explorer-{dev,prd}-raw` | raw landing; Intelligent-Tiering day 0; **no expiration** |
| `dm-chain-explorer-{dev,prd}-lakehouse` | external Delta tables, catalog `storage_root` |
| `dm-chain-explorer-tfstate-use1` | Terraform state, versioned |

### IAM

| Role | Stack | Scope |
|---|---|---|
| `dm-chain-explorer-gha-deploy-{dev,prd}` | bootstrap | OIDC `environment:<env>`, prefix-scoped, boundary, self-mutation deny |
| `dm-chain-explorer-gha-readonly-plan` | bootstrap | OIDC PR + `develop`/`main` refs |
| `dm-chain-explorer-gha-capture-publish` | bootstrap | OIDC from capture `dev`/`production`; ECR push/pull on the three repos only |
| capture task roles (one per image) | `dev/03_capture` | `s3:PutObject` on `raw/<source>/*` |
| capture dev writer | `dev/01_peripherals` | MFA-gated assume; `PutObject raw/*`, no delete |
| `dm-chain-explorer-<env>-uc` | `{env}/04_unity_catalog` | UCMasterRole + self + ExternalId trust; raw read, lakehouse RW, `csms-*` SNS/SQS for file events |
| `dm-chain-explorer-ci-boundary` | bootstrap | permissions boundary on every project role |

## Dependências

- **[[cicd-pipeline]]**, **[[capture-layer]]**, **[[data-catalog]]**, **[[environments]]**

## Referência

### sa-east-1 teardown — status 2026-09-23 (LIVE facts)

| Object | Status |
|---|---|
| `capture/ecr` state (ECR stream/connect, KMS key + alias, Roles Anywhere) | **destroyed** whole, 11 resources, retire job of run `35817189275`; the KMS key sits in its 7-day pending deletion |
| sa-east-1 buckets (`dm-chain-explorer-{dev-ingestion,dev-raw-data,raw-data,lakehouse,databricks,artifacts}`) | emptied by retire (all were already empty) |
| `dev/01_peripherals`, `dev/02_lambda`, `dev/03_capture` | **destroyed** by the dev lane of run `35817189275` (45 resources) |
| `prd/04_peripherals` (prd buckets, emptied ECR ×3, DynamoDB), `prd/06_lambda` (Lambdas, layer, schedule) | **still live** — the prd lane was skipped by a skip-inheritance bug; fix infra PR #11 open |
| state bucket `dm-chain-explorer-terraform-state` + lock table | live until seed S1 migrates `prd/bootstrap` and deletes them |
| Free Edition UC objects | abandoned with that organization (R27) |
| 27 SSM parameters `/etherscan-api-keys/*`, `/web3-api-keys/*` | owned by no stack; not verified in this pass — AC-26 probes decide |

Proof of completion is AC-23/AC-26 (tagging API empty in sa-east-1, every destroy citing a
run id).

### Retirado do inventário

DynamoDB tables (`dm-chain-explorer[-dev]`, lock table), both Lambdas and their layer,
the EventBridge contracts schedule, the artifacts bucket, `gha-artifacts-publish`, every
KMS key, `hml` and every capture-era VPC/ECS residue. Do not reintroduce them.
