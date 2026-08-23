---
slug: aws-resources
title: AWS Resources
category: product
tldr: AWS inventory after the v0.5.0 cutover — S3, DynamoDB, Lambda, SSM, IAM incl. OIDC roles, CloudWatch and Terraform state.
summary: Single reference for every AWS resource this project touches — S3 buckets and path conventions, the DynamoDB single table and lock table, the two Lambdas and their triggers, SSM parameters, CloudWatch log groups, the IAM role set including the four GitHub OIDC deploy roles and the CI permissions boundary, and the Terraform state key layout. The capture-era residue (VPC, security groups, ECS/ECR shells, orphan roles, stale locks and orphan state keys) no longer exists; the only non-project entry left in the account boundary is dd-chain-capture's own capture/ecr state and KMS alias, pending transfer.
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
release_origin: v0.5.0
---

## Propósito

Canonical inventory of every AWS resource this project provisions or depends on, in
region **sa-east-1**. It is the lookup an engineer or agent consults before writing
infrastructure code, an IAM policy, or a runbook step.

Every resource below is Terraform-managed and live unless its status column says
otherwise. Terraform is the sole authority: resources are created, changed and destroyed
by an apply through the CI pipeline — the one exception is `prd/00_bootstrap`, which the
operator applies locally because it holds the credentials CI itself uses.

## Fluxo de uso

1. Identify the target environment (`dev`, `hml`, `prd`) and the resource type.
2. Look up the resource in the tables under **Referência** and read its status column.
3. Cross-reference the S3 path convention or the DynamoDB key schema as needed.
4. Check the Terraform state key before planning or applying anything.
5. Change it in Terraform and let CI apply — never by console or ad-hoc CLI.

## Trigger típico

Consulted whenever an exact resource name, ARN scope or state key is needed for a
deploy, a Terraform plan, an IAM change, or a live-infrastructure investigation.

## Diferencial

Environment prefixes differ across eras (`dm-`, `dm-dd-chain-explorer-prd-`, `-dev`,
`-hml`), and an agent that guesses a name writes to the wrong environment. This atom is
the single place where the live name, its owning stack and its state key are stated
together, so infrastructure code can be written without probing the account.

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

### Terraform stacks

| Stack | State key | Holds |
|---|---|---|
| `prd/00_bootstrap` | `prd/bootstrap` | the four GitHub OIDC roles + the CI permissions boundary — **operator-applied, never by CI, never destroyed** |
| `prd/01_tf_state` | local state | the state bucket and lock table — never destroyed |
| `prd/03_iam` | `prd/iam` | **empty** — its capture-era roles were destroyed; kept only for its bootstrap remote-state plumbing |
| `prd/04_peripherals` | `prd/peripherals` | S3 (raw, lakehouse, databricks, artifacts), DynamoDB, log group |
| `prd/06_lambda` | `prd/lambda` | both prd Lambdas, the layer, the ingestion schedule, Lambda log groups |
| `dev/01_peripherals` | `dev/peripherals` | S3 ingestion, DynamoDB, log group, `dm-databricks-dev-s3-role` |
| `dev/02_lambda` | `dev/lambda` | the dev export Lambda and its log group |
| `hml/04_peripherals` | `hml/peripherals` | the two hml buckets and `dm-databricks-hml-s3-role` |

### S3 buckets

| Bucket | Env | Status | Purpose |
|--------|-----|--------|---------|
| `dm-chain-explorer-raw-data` | prd | live, **empty — no object since 2026-05-23** | Raw landing zone: the integration boundary with dd-chain-capture |
| `dm-chain-explorer-lakehouse` | prd | live | Delta tables managed by Databricks (`checkpoints/`, `staging/`, `unity-catalog/`) |
| `dm-chain-explorer-databricks` | prd | live | Databricks workspace storage; holds the `exports/` prefix that triggers the export Lambda |
| `dm-chain-explorer-artifacts` | prd | **declared, not yet applied** | Content-addressed Lambda-layer store (`lambda-layers/dm-chain-utils/<sha256>.zip`; dev under a `dev/` prefix) |
| `dm-chain-explorer-dev-ingestion` | dev | live, empty | DEV landing zone |
| `dm-chain-explorer-hml-raw-data`, `dm-chain-explorer-hml-lakehouse` | hml | live, empty | The minimal hml lane; attached to Unity Catalog external locations |
| `dm-chain-explorer-terraform-state` | all | live, versioning enabled, bootstrapped by `prd/01_tf_state` | Remote Terraform state for every stack |

Path conventions:

```
# Raw delivery from dd-chain-capture (Kafka-Connect JSON)
s3://dm-chain-explorer-raw-data/raw/mainnet-{blocks-data,transactions-data,transactions-decoded}/year=YYYY/month=MM/day=DD/...

# Application logs from dd-chain-capture (Fluent-Bit NDJSON)
s3://dm-chain-explorer-raw-data/raw/app_logs/...

# Lambda batch delivery (contracts ingestion — dormant, schedule disabled)
s3://dm-chain-explorer-raw-data/raw/batch/{dataset}/year=YYYY/month=MM/day=DD/

# Gold exports (job_export_gold) — the export Lambda's trigger prefix
s3://dm-chain-explorer-databricks/exports/{table_name}/

# Databricks Auto Loader checkpoints
s3://dm-chain-explorer-lakehouse/checkpoints/{pipeline_id}/{table_name}/

# Lambda layer artifact (content-addressed)
s3://dm-chain-explorer-artifacts/lambda-layers/dm-chain-utils/<sha256>.zip
```

### DynamoDB

| Table | Env | Key schema | Status |
|-------|-----|-----------|--------|
| `dm-chain-explorer` | prd | PK `pk` (S), SK `sk` (S), TTL `ttl`, on-demand, PITR enabled | live, **0 items** |
| `dm-chain-explorer-dev` | dev | same | live, 0 items |
| `dm-chain-explorer-terraform-lock` | all | `LockID` (S), on-demand | live, **0 held locks** |

Entity types in use: `CONTRACT` (contracts-ingestion input, currently unseeded) and
`CONSUMPTION` (gold export output). The capture-era entity types are no longer written.

### Lambda functions

| Function | Env | Trigger | Status |
|----------|-----|---------|--------|
| `dm-dd-chain-explorer-prd-contracts-ingestion` | prd | EventBridge Scheduler, **DISABLED** | live and idle by declaration — the schedule is disabled in Terraform, so it burns no Etherscan quota |
| `dm-dd-chain-explorer-prd-gold-to-dynamodb` | prd | S3 PutObject on `dm-chain-explorer-databricks` `exports/gold_api_keys/*.json` | live, never invoked |
| `dm-chain-explorer-gold-to-dynamodb-dev` | dev | S3 PutObject on `dm-chain-explorer-dev-ingestion` `exports/` | live, idle |

Handler packages are built by `data "archive_file"` at plan time from
`apps/lambda/<fn>/src`. The `dm-chain-utils` layer is built in CI from the pinned lock
plus a path install of `utils/`, and consumed through `layer_s3_key`/`layer_sha256`
variables; the live functions still carry the last layer version published before that
rewire, which lands with the artifact-bucket apply.

### SSM Parameter Store

27 SecureString parameters on the AWS-managed SSM key, shared with dd-chain-capture:

| Path | Count | Consumed here |
|------|-------|---------------|
| `/etherscan-api-keys/api-key-{1..6}` | 6 | yes — contracts-ingestion Lambda |
| `/web3-api-keys/infura/api-key-{1..17}` | 17 | no — dd-chain-capture only |
| `/web3-api-keys/alchemy/api-key-{1..4}` | 4 | no — dd-chain-capture only |

The customer-managed KMS key `alias/dd-chain-capture-ssm` protects no parameter and
belongs to dd-chain-capture — cross-project residue pending ownership transfer.

### IAM

| Role / policy | Stack | Notes |
|------|-------|-------|
| `dm-chain-explorer-gha-deploy-{dev,hml,prd}` | `prd/00_bootstrap` | one per environment; trust pinned to `repo:<owner>/<repo>:environment:<env>`; prefix-scoped allows only |
| `dm-chain-explorer-gha-readonly-plan` | `prd/00_bootstrap` | trust pinned to `pull_request` + `refs/heads/{develop,main}`; no lock-table write (the plan path runs `-lock=false`) |
| `dm-chain-explorer-ci-boundary` | `prd/00_bootstrap` | permissions boundary carried by **every** project role, capping effective permissions regardless of inline grants |
| `dm-gha-self-mutation-deny` (inline, all four roles) | `prd/00_bootstrap` | explicit `Deny` on `iam:*` against `dm-chain-explorer-gha-*` and on `iam:CreateAccessKey`/`AttachUserPolicy`/`PutUserPolicy` |
| `dm-dd-chain-explorer-prd-contracts-ingestion-lambda`, `-eb-contracts-ingestion`, `-gold-to-dynamodb-lambda` | `prd/06_lambda` | Lambda execution and scheduler roles |
| `dm-chain-explorer-gold-to-dynamodb-lambda-dev` | `dev/02_lambda` | dev Lambda execution role |
| `dm-databricks-dev-s3-role` | `dev/01_peripherals` | **load-bearing** — the Unity Catalog storage credential for `dev`; imported into state, never delete |
| `dm-databricks-hml-s3-role` | `hml/04_peripherals` | the Unity Catalog storage credential for `hml`; grants only the two hml buckets |

The account-level GitHub OIDC identity provider exists (operator-created, outside
Terraform) and is referenced, not owned, by `00_bootstrap`. The legacy CI IAM user's
access key is `Inactive`; no static AWS key is used by anything.

Capture-era IAM — the ECS task and task-execution roles, the Databricks cross-account and
cluster roles, the firehose role, and the orphan legacy dev Lambda role — no longer
exists.

### CloudWatch log groups

| Group | Retention | Status |
|-------|-----------|--------|
| `/apps/dm-chain-explorer-prd` | 30 d | managed, empty |
| `/apps/dm-chain-explorer-dev` | 3 d | managed, empty |
| `/aws/lambda/dm-*` (the three live functions) | 30 d declared | declared in `prd/06_lambda` / `dev/02_lambda` with `import` blocks; retention becomes live with the deferred layer apply |

The ~39 CI-ephemeral `hml` log groups and the container-insights groups were deleted.

### Terraform state keys

```
s3://dm-chain-explorer-terraform-state/
  capture/ecr/terraform.tfstate            # cross-project: dd-chain-capture (ECR, Roles Anywhere, KMS) — pending transfer
  dev/lambda/terraform.tfstate
  dev/peripherals/terraform.tfstate
  hml/peripherals/terraform.tfstate
  prd/bootstrap/terraform.tfstate          # operator-applied OIDC roles + CI boundary
  prd/iam/terraform.tfstate                # empty
  prd/lambda/terraform.tfstate
  prd/peripherals/terraform.tfstate
```

Seven project keys plus the cross-project `capture/ecr` key. Every orphan and
zero-resource key of the capture era was removed; `prd/01_tf_state` keeps local state and
is never destroyed.

### Retirado do inventário

Capture-era and orphan resources that used to appear here **no longer exist in the
account**: the unmanaged `ChainExplorer-vpc` with its subnets, route table and internet
gateway; the 24 leaked `dm-hml-sg-*` security groups; the empty ECS cluster and every
`dm-*` task-definition revision; the HML IAM stack; the legacy dev `gold-to-dynamodb`
Lambda with its role and log group; the firehose role; and the two stale Terraform locks.
Do not reintroduce a reference to any of them.
