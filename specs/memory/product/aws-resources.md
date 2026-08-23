---
slug: aws-resources
title: AWS Resources
category: product
tldr: AWS inventory after capture retirement — S3, DynamoDB, Lambda, SSM, IAM, CloudWatch and Terraform state, each marked managed, orphan or residue.
summary: Single reference for every AWS resource this project touches — S3 buckets and path conventions, DynamoDB single table and lock table, the two Lambdas and their triggers, SSM parameters, CloudWatch log groups, IAM roles, the empty ECS/ECR shells, network residue, and the Terraform state key layout. Each row states whether the resource is Terraform-managed and live, live without state, declared without ever being applied, or residue slated for removal.
tags:
  - aws
  - infrastructure
  - s3
  - dynamodb
  - lambda
  - iam
  - ssm
  - terraform
last_updated: "2026-08-23"
release_origin: v0.4.0
---

## Propósito

Canonical inventory of every AWS resource this project provisions or depends on, in
region **sa-east-1**. It is the lookup an engineer or agent consults before writing
infrastructure code, an IAM policy, or a runbook step.

The inventory is written as *current truth*, including the uncomfortable parts: some
resources are Terraform-managed and live, some are live with no state behind them, some
are declared in code and were never applied, and some are residue left by the retired
capture layer. Every row says which.

Capture resources (Kinesis Data Streams, Kinesis Firehose, SQS queues, the five ECS
Fargate producer services) no longer exist — they were destroyed in AWS on 2026-06-22,
and the PRD Databricks workspace on 2026-04-11. Raw data now arrives from the external
dd-chain-capture project directly into S3; see [[capture-layer]].

## Fluxo de uso

1. Identify the target environment (`dev`, `hml`, `prd`) and the resource type.
2. Look up the resource in the tables under **Referência** and read its status column.
3. Cross-reference the S3 path convention or the DynamoDB key schema as needed.
4. Check the Terraform state key before planning or applying anything.
5. Never write code that depends on a row marked *residue*, *orphan* or *not applied*.

## Trigger típico

Consulted whenever an exact resource name, ARN scope or state key is needed for a
deploy, a Terraform plan, an IAM change, or a live-infrastructure investigation.

## Diferencial

Environment suffixes are inconsistent across eras (`-dev`, `-hml`, `dm-` and
`dm-dd-chain-explorer-prd-` prefixes), and the account still carries resources from a
retired architecture. Without this atom, an agent cannot tell a load-bearing resource
from residue, and risks either writing to the wrong environment or reviving dead
infrastructure by referencing it.

## Estado runtime tocado

Reference-only: this atom describes resources rather than reading or writing them. The
resources it lists collectively hold all persistent state of the platform — S3 objects,
DynamoDB items, Terraform state, and SSM parameters.

## Dependências

- Feeds [[medallion-pipelines]] — Databricks Auto Loader reads the S3 raw bucket
- Feeds [[serving-layer]] — gold exports land in S3 and the export Lambda writes DynamoDB
- Provisioned by [[cicd-pipeline]] — the Terraform stacks are applied from CI
- Receives deliveries described in [[capture-layer]]

## Referência

### S3 buckets

| Bucket | Env | Status | Purpose |
|--------|-----|--------|---------|
| `dm-chain-explorer-raw-data` | prd | managed (`prd/peripherals`), live, **currently empty — no object since 2026-05-23** | Raw landing zone: the integration boundary with dd-chain-capture |
| `dm-chain-explorer-lakehouse` | prd | managed, live | Delta tables managed by Databricks (`checkpoints/`, `staging/`, `unity-catalog/` prefixes only) |
| `dm-chain-explorer-databricks` | prd | managed, live | Databricks workspace storage; also holds `exports/` that trigger the export Lambda |
| `dm-chain-explorer-dev-ingestion` | dev | managed (`dev/peripherals`), live, empty | DEV landing zone |
| `dm-chain-explorer-terraform-state` | all | live, versioning enabled, bootstrapped by `prd/01_tf_state` (local state) | Remote Terraform state for every stack — including the cross-project `capture/ecr` key |
| `dm-chain-explorer-hml-raw`, `dm-chain-explorer-hml-lakehouse` | hml | **stale state** — declared in `hml/peripherals` state, do not exist live | Referenced by DABs bundles that therefore cannot run against hml |

Path conventions:

```
# Raw delivery from dd-chain-capture (Kafka-Connect JSON)
s3://dm-chain-explorer-raw-data/raw/mainnet-{blocks-data,transactions-data,transactions-decoded}/year=YYYY/month=MM/day=DD/...

# Application logs from dd-chain-capture (Fluent-Bit NDJSON)
s3://dm-chain-explorer-raw-data/raw/app_logs/...

# Lambda batch delivery (contracts ingestion)
s3://dm-chain-explorer-raw-data/raw/batch/{dataset}/year=YYYY/month=MM/day=DD/

# Gold exports (job_export_gold) — the export Lambda's trigger prefix
s3://dm-chain-explorer-databricks/exports/{table_name}/

# Databricks Auto Loader checkpoints
s3://dm-chain-explorer-lakehouse/checkpoints/{pipeline_id}/{table_name}/
```

### DynamoDB

| Table | Env | Key schema | Status |
|-------|-----|-----------|--------|
| `dm-chain-explorer` | prd | PK `pk` (S), SK `sk` (S), TTL `ttl`, on-demand, PITR enabled | managed, live, **0 items** |
| `dm-chain-explorer-dev` | dev | same | managed, live, 0 items |
| `dm-chain-explorer-terraform-lock` | all | `LockID` (S), on-demand | live; **two stale Apply locks held since 2026-04-22** on `prd/databricks-account` and `hml/peripherals` — the next locked plan/apply on those stacks will fail |

Entity types in use today: `CONTRACT` (contracts-ingestion input) and `CONSUMPTION`
(gold export output). `SEMAPHORE`, `COUNTER`, `BLOCK_CACHE`, `ABI` and `ABI_NEG` were
capture-era entities and are no longer written.

### Lambda functions

| Function | Env | Trigger | Status |
|----------|-----|---------|--------|
| `dm-dd-chain-explorer-prd-contracts-ingestion` | prd | EventBridge Scheduler `rate(1 hour)`, **ENABLED** | managed, live; every run processes 0 contracts because DynamoDB is empty — it burns Etherscan quota and log storage for nothing |
| `dm-dd-chain-explorer-prd-gold-to-dynamodb` | prd | S3 PutObject on `dm-chain-explorer-databricks` `exports/gold_api_keys/*.json` | managed, live, never invoked |
| `dm-chain-explorer-gold-to-dynamodb-dev` | dev | S3 PutObject on `dm-chain-explorer-dev-ingestion` `exports/` | managed, live, idle |
| `dd-chain-explorer-dev-gold-to-dynamodb` | — | none | **orphan** — legacy function plus its role and log group, outside every state |

Layer: `dm-dd-chain-explorer-prd-dm-chain-utils` (version 13) packages
`dm-chain-utils` for both prd functions.

### SSM Parameter Store

27 SecureString parameters on the AWS-managed SSM key, shared with dd-chain-capture:

| Path | Count | Consumed here |
|------|-------|---------------|
| `/etherscan-api-keys/api-key-{1..6}` | 6 | yes — contracts-ingestion Lambda |
| `/web3-api-keys/infura/api-key-{1..17}` | 17 | no — dd-chain-capture only |
| `/web3-api-keys/alchemy/api-key-{1..4}` | 4 | no — dd-chain-capture only |

A customer-managed KMS key `alias/dd-chain-capture-ssm` exists and currently protects
**no** parameter — cross-project residue with a fixed monthly cost.

### IAM roles

| Role | Status |
|------|--------|
| `dm-dd-chain-explorer-prd-contracts-ingestion-lambda`, `-eb-contracts-ingestion`, `-gold-to-dynamodb-lambda` | managed (`prd/lambda`), live |
| `dm-chain-explorer-databricks-cluster-role`, `-databricks-cross-account-role` | managed (`prd/iam`), live — Databricks S3 access |
| `dm-chain-explorer-ecs-task-role`, `-ecs-task-execution-role` (+ instance profile) | managed (`prd/iam`), live but **unused**; the task role still grants SQS, Kinesis and Firehose actions on name-pattern wildcards — residue slated for removal |
| `dm-chain-explorer-gold-to-dynamodb-lambda-dev` | managed (`dev/lambda`), live |
| `hml/iam` role set (19 resources incl. `-firehose-role-hml`) | live, unused since 2026-04 |
| `dm-chain-explorer-gha-{deploy-dev,deploy-hml,deploy-prd,readonly-plan}` | **declared in `prd/03_iam/oidc.tf`, never applied** — the reason CI cannot authenticate *(gap — see audit `20260823T145726Z-4db47555`)* |
| `dm-databricks-dev-s3-role`, `dm-hml-firehose-role`, `dd-chain-explorer-dev-gold-to-dynamodb-lambda` | **orphan** — live with no code and no state |
| `dd-chain-capture-scraper-role`, `dd-chain-capture-streaming-role` | cross-project (`capture/ecr` state), live |

The account-level GitHub OIDC identity provider exists (operator-created, outside
Terraform).

### ECS / ECR and network residue

| Resource | Status |
|----------|--------|
| ECS cluster `dm-chain-explorer-ecs-hml` | live, 0 services, 0 tasks — **empty shell**, no state behind it |
| `prd/07_ecs` (cluster + 2 ECR repos) | declared in code, never applied |
| ECR `dd-chain-capture-stream`, `dd-chain-capture-connect` | cross-project (`capture/ecr`), 0 images |
| ECS task-definition registry | ~60 ACTIVE revisions of the retired capture jobs; zero cost, zero use |
| VPC `ChainExplorer-vpc` (10.1.0.0/16) | live, unmanaged by any state, yet load-bearing: the CI secret `HML_VPC_ID` points at it |
| 24 × security group `dm-hml-sg-<run-id>` | leaked by CI teardown between 2026-03-22 and 2026-04-09 |

None of these represent capability. Do not write code that references them.

### CloudWatch log groups

| Group | Retention | Status |
|-------|-----------|--------|
| `/apps/dm-chain-explorer-prd` | 30 d | managed, empty |
| `/apps/dm-chain-explorer-dev` | 3 d | managed, empty |
| `/aws/lambda/dm-dd-chain-explorer-prd-*` | none | Lambda-created, outside Terraform |
| `/aws/lambda/hml-*-<run-id>` (~39 groups) | none | orphan, CI-ephemeral |

### Terraform state keys

```
s3://dm-chain-explorer-terraform-state/
  capture/ecr/terraform.tfstate            # cross-project: dd-chain-capture (ECR, Roles Anywhere, KMS)
  dev/lambda/terraform.tfstate
  dev/peripherals/terraform.tfstate        # S3 + DynamoDB + CloudWatch
  hml/{vpc,peripherals,iam,ecs,databricks,databricks-workspace}/terraform.tfstate
  prd/vpc/terraform.tfstate                # empty
  prd/iam/terraform.tfstate                # 12 resources live; OIDC roles declared, not applied
  prd/peripherals/terraform.tfstate        # S3 + DynamoDB + CloudWatch
  prd/lambda/terraform.tfstate             # both prd Lambdas + schedule
  prd/{databricks-account,databricks-workspace,ecs}/terraform.tfstate   # empty
```

`services/prd/05_databricks` declares resources against a backend key that was never
created — dead code. `services/prd/01_tf_state` bootstraps the bucket and lock table
from local state and is never destroyed.
