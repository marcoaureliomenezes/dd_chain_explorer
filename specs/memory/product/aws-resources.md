---
slug: aws-resources
title: AWS Resources
category: product
tldr: AWS resource inventory (S3, Kinesis, Firehose, SQS, DynamoDB, Lambda, ECS/ECR, CloudWatch, IAM) for DD Chain Explorer across DEV/HML/PRD.
summary: Documents every named AWS resource used by DD Chain Explorer — account 016098071081, region sa-east-1 — including S3 path conventions, Kinesis/Firehose stream topology, SQS queue parameters, DynamoDB single-table schema, Lambda function configuration, ECS/ECR resources, CloudWatch log groups, IAM roles, and Terraform state paths. State reflects post pipeline-restart-r1 (validated 2026-05-23).
tags:
  - aws
  - infrastructure
  - s3
  - kinesis
  - firehose
  - sqs
  - dynamodb
  - lambda
  - ecs
  - iam
  - terraform
agent_tier: self-pull
token_estimate: 1200
last_updated: "2026-06-09"
release_origin: legacy-memory-promotion
---

## Propósito

Canonical inventory of every AWS resource provisioned for DD Chain Explorer. Account **016098071081**, region **sa-east-1**. State reflects post `pipeline-restart-r1` (provisioned and validated 2026-05-23).

This atom is the single reference for resource names, environments, and configuration parameters. It covers S3, Kinesis, Firehose, SQS, DynamoDB, Lambda, ECS/ECR, CloudWatch, IAM, and Terraform state paths.

Agents and engineers use this atom to resolve the exact resource name for any environment (DEV / HML / PRD) before writing infrastructure code or runbook steps.

## Fluxo de uso

1. Identify the target environment (DEV / HML / PRD) and resource type.
2. Look up the resource name in the relevant section table below.
3. Cross-reference path conventions (S3 paths, DynamoDB key schema) as needed.
4. Validate IAM permissions via the ECS Task Role row before adding new data-plane operations.
5. Verify Terraform state path when applying infrastructure changes.

## Trigger típico

Referenced whenever an engineer needs the exact resource name for a deploy, a runbook, an IAM policy update, or a Terraform plan in any environment.

## Diferencial

Without a single canonical resource inventory, environment-specific suffixes (`-dev`, `-hml`, no suffix for PRD) are error-prone to remember. This atom prevents misrouted writes to production S3 buckets or wrong SQS queues by providing a lookup table that agents can read before any infrastructure operation.

## Estado runtime tocado

This atom is reference-only — it describes resources rather than reading or writing them. The resources it documents collectively own all runtime state of the platform.

## Dependências

- Consumed by `capture-layer` (ECS jobs use DynamoDB, SQS, Kinesis, Firehose, SSM, S3)
- Consumed by `medallion-pipelines` (Databricks reads S3, writes to lakehouse bucket)
- Consumed by `serving-layer` (Lambda reads S3 exports, writes DynamoDB; dashboards read Gold tables)

---

## S3 Buckets

| Bucket Name | Environment | Purpose |
|-------------|-------------|---------|
| `dm-chain-explorer-terraform-state` | All | Terraform remote state backend (versioned + lock) |
| `dm-chain-explorer-raw-data` | PRD | Raw NDJSON delivery from all Firehose streams. Provisioned 2026-05-23. |
| `dm-chain-explorer-lakehouse` | PRD | Delta tables managed by Databricks (checkpoints, staging, unity-catalog prefixes only — no medallion layer prefixes). Provisioned 2026-05-23. |
| `dm-chain-explorer-databricks` | PRD | Databricks workspace storage |
| `dm-chain-explorer-dev-ingestion` | DEV | Raw NDJSON delivery (DEV Firehose streams) |
| `dm-chain-explorer-hml-raw` | HML | Raw NDJSON delivery (HML Firehose streams) |
| `dm-chain-explorer-hml-lakehouse` | HML | Delta tables (HML Databricks) |
| `dm-chain-explorer-hml-databricks` | HML | Databricks workspace storage (HML) |

> **Lakehouse bucket path convention (post R1):** No medallion-layer folder prefixes (`bronze/`, `silver/`, `gold/` were removed in T-R1-18). Only `checkpoints/`, `staging/`, `unity-catalog/` prefixes exist.

### S3 Path Convention

```
# Firehose streaming delivery
s3://{bucket}/raw/{stream-name}/year=YYYY/month=MM/day=DD/hour=HH/

# Lambda batch delivery
s3://{bucket}/raw/batch/{dataset}/year=YYYY/month=MM/day=DD/

# Gold exports (job_export_gold)
s3://{bucket}/exports/{table_name}/

# Databricks checkpoints (Auto Loader)
s3://{databricks-bucket}/checkpoints/{pipeline_id}/{table_name}/
```

---

## Kinesis Data Streams

| Stream Name | Env | Mode | Shards | Producer | Consumer |
|-------------|-----|------|--------|----------|----------|
| `mainnet-transactions-data-dev` | DEV | PROVISIONED | 1 | Job 4 (×6) | Job 5 (×3) |
| `mainnet-transactions-data-hml` | HML | PROVISIONED | 1 | Job 4 (×6) | Job 5 (×3) |
| `mainnet-transactions-data` | PRD | PROVISIONED | 1 | Job 4 (×6) | Job 5 (×3) |

Managed by Terraform `04_peripherals`. Only one Kinesis stream exists (raw transactions). Blocks and decoded transactions use Firehose Direct Put.

---

## Kinesis Firehose Delivery Streams

| Stream Name | Env | Source | S3 Destination |
|-------------|-----|--------|----------------|
| `firehose-mainnet-blocks-data-dev` | DEV | Direct Put (Job 3) | `dm-chain-explorer-dev-ingestion/raw/mainnet-blocks-data/` |
| `firehose-mainnet-transactions-data-dev` | DEV | Kinesis-source | `dm-chain-explorer-dev-ingestion/raw/mainnet-transactions-data/` |
| `firehose-mainnet-transactions-decoded-dev` | DEV | Direct Put (Job 5) | `dm-chain-explorer-dev-ingestion/raw/mainnet-transactions-decoded/` |
| `firehose-app-logs-dev` | DEV | CloudWatch Logs | `dm-chain-explorer-dev-ingestion/raw/app_logs/` |
| `firehose-app-logs-hml` | HML | CloudWatch Logs | `dm-chain-explorer-hml-raw/raw/app_logs/` |

PRD equivalents (managed by Terraform, no `-dev` suffix): same structure, pointing to `dm-chain-explorer-raw-data`.

**Firehose config:** Buffer 1 MB OR 60 s. Format: NDJSON. Partitioning: `year=YYYY/month=MM/day=DD/hour=HH/`.

---

## SQS Queues

| Queue Name | Env | Producer | Consumer | DLQ | Visibility Timeout |
|------------|-----|----------|----------|-----|--------------------|
| `mainnet-mined-blocks-events-dev` | DEV | Job 1, Job 2 | Job 2, Job 3 | `...-dlq-dev` | 30s |
| `mainnet-mined-blocks-events-hml` | HML | Job 1, Job 2 | Job 2, Job 3 | `...-dlq-hml` | 30s |
| `mainnet-mined-blocks-events` | PRD | Job 1, Job 2 | Job 2, Job 3 | `...-dlq` | 30s |
| `mainnet-block-txs-hash-id-dev` | DEV | Job 3 | Job 4 (×6) | `...-dlq-dev` | 30s |
| `mainnet-block-txs-hash-id-hml` | HML | Job 3 | Job 4 (×6) | `...-dlq-hml` | 30s |
| `mainnet-block-txs-hash-id` | PRD | Job 3 | Job 4 (×6) | `...-dlq` | 30s |

Config: long-polling (20s), max receive count = 3 before DLQ. PRD queues provisioned 2026-05-23.

---

## DynamoDB Tables

| Table Name | Env | Key Schema | Billing | Purpose |
|------------|-----|-----------|---------|---------|
| `dm-chain-explorer-dev` | DEV | PK=`pk` (S), SK=`sk` (S), TTL=`ttl` | On-demand | All entities: SEMAPHORE, COUNTER, BLOCK_CACHE, ABI, ABI_NEG, CONTRACT, CONSUMPTION |
| `dm-chain-explorer-hml` | HML | Same | On-demand | Same entities for HML integration tests |
| `dm-chain-explorer` | PRD | Same | On-demand | Production single-table |
| `dm-chain-explorer-terraform-lock` | All | LockID (S) | On-demand | Terraform state locking |

---

## Lambda Functions

| Function Name | Env | Runtime | Trigger | Purpose |
|---------------|-----|---------|---------|---------|
| `dm-chain-explorer-gold-to-dynamodb-dev` | DEV | Python 3.12 | S3 PutObject (`exports/`) | Reads Gold JSON export → writes CONSUMPTION entities to DynamoDB |
| `dm-chain-explorer-contracts-ingestion-dev` | DEV | Python 3.12 | EventBridge Scheduler (hourly) | Reads CONTRACT entities from DynamoDB → Etherscan API → writes batch JSON to S3 |
| `dm-chain-explorer-gold-to-dynamodb` | PRD | Python 3.12 | S3 PutObject | Same as DEV, PRD bucket. Provisioned 2026-05-23. |
| `dm-chain-explorer-contracts-ingestion` | PRD | Python 3.12 | EventBridge Scheduler (hourly) | Same as DEV, PRD resources. Provisioned 2026-05-23. |

**Lambda Layer:** `dm-chain-utils==0.2.9` installed as a Lambda layer (shared between both functions). Pinned in R1.

**CloudWatch log ARN (post R1):** `arn:aws:logs:${region}:${account_id}:log-group:/aws/lambda/${name_prefix}-*` — scoped, no wildcard resource.

---

## ECS / ECR

| Resource | Name | Notes |
|----------|------|-------|
| ECS Cluster (HML) | `dm-chain-explorer-ecs-hml` | Ephemeral — created per CI/CD run |
| ECS Cluster (PRD) | `dm-chain-explorer-ecs` | Managed by `07_ecs` Terraform module |
| ECR Repository | `onchain-stream-txs` | Docker image for all 5 streaming jobs. `dm-chain-utils==0.2.9` pinned in requirements.txt. |
| ECS Services (PRD) | 5 services (jobs 1–5) | Job 4: 6 tasks; Job 5: 3 tasks |

---

## CloudWatch Logs

| Log Group | Source | Firehose Subscription |
|-----------|--------|-----------------------|
| `/apps/dm-chain-explorer-dev` | Docker streaming jobs (DEV) | `firehose-app-logs-dev` |
| `/apps/dm-chain-explorer-hml` | ECS tasks (HML) | `firehose-app-logs-hml` |
| `/apps/dm-chain-explorer` | ECS tasks (PRD) | `firehose-app-logs` |

---

## IAM Key Roles (PRD)

> **Post R1 security state:** All wildcard ARNs (`*:*`) replaced with `${region}:${account_id}`-scoped ARNs. ECS task role has no `dynamodb:Scan`. Databricks cluster role has no SSM access. Lambda CloudWatch ARN scoped to log-group prefix. All changes applied to `services/prd/03_iam/iam.tf` (commit `60c71c7`).

| Role | Name | Usage |
|------|------|-------|
| ECS Task Execution | `dm-ecs-task-execution-role` | ECS task pull from ECR + CloudWatch logs. No data-plane permissions. |
| ECS Task Role | `dm-chain-explorer-ecs-task-role` (policy: `dm-ecs-task-permissions`) | Container runtime access: DynamoDB (GetItem/PutItem/UpdateItem/DeleteItem only), SQS, Kinesis, Firehose, S3, SSM. No Scan. No wildcard ARNs. Provisioned in `services/prd/03_iam/iam.tf`. |
| Databricks Cross-Account | `dm-databricks-cross-account-role` | Databricks workspace cross-account access (AWS-managed trust policy). |
| Databricks Cluster | `dm-databricks-cluster-role` | Databricks cluster S3 access (External Location). No SSM access (removed in R1). |
| Lambda Execution | `dm-lambda-role` | Lambda: S3, DynamoDB, SSM, EventBridge. CloudWatch log ARN scoped to `/aws/lambda/${name_prefix}-*`. |

---

## Terraform State Paths

```
s3://dm-chain-explorer-terraform-state/
  dev/
    peripherals/terraform.tfstate    # S3, Kinesis, SQS, Firehose, DynamoDB, CloudWatch
    lambda/terraform.tfstate         # gold_to_dynamodb Lambda (DEV)
  hml/
    vpc/terraform.tfstate            # (ephemeral, created per CI run)
    peripherals/terraform.tfstate
    iam/terraform.tfstate
    ecs/terraform.tfstate
    databricks-workspace/terraform.tfstate
  prd/
    vpc/terraform.tfstate
    iam/terraform.tfstate            # applied 2026-05-23 (post IAM fix, 2 changed)
    peripherals/terraform.tfstate    # applied 2026-05-23 (40 added fresh)
    databricks-account/terraform.tfstate
    databricks-workspace/terraform.tfstate
    lambda/terraform.tfstate         # applied 2026-05-23 (12 added fresh)
    ecs/terraform.tfstate
```
