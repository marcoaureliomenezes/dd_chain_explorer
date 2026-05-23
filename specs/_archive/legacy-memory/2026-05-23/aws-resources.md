# AWS Resources — DD Chain Explorer

> **Source:** AWS CLI + Terraform state (S3 backend) — scraped 2026-04.  
> **Account:** 016098071081 | **Region:** sa-east-1

---

## S3 Buckets

| Bucket Name | Environment | Purpose |
|---|---|---|
| `dm-chain-explorer-terraform-state` | All | Terraform remote state backend (versioned) |
| `dm-chain-explorer-raw-data` | PRD | Raw NDJSON delivery from all Firehose streams |
| `dm-chain-explorer-lakehouse` | PRD | Delta tables managed by Databricks (bronze/silver/gold prefixes) |
| `dm-chain-explorer-databricks` | PRD | Databricks workspace storage (checkpoints, staging, unity-catalog) |
| `dm-chain-explorer-dev-ingestion` | DEV | Raw NDJSON delivery (DEV Firehose streams) |
| `dm-chain-explorer-hml-raw` | HML | Raw NDJSON delivery (HML Firehose streams) |
| `dm-chain-explorer-hml-lakehouse` | HML | Delta tables (HML Databricks) |
| `dm-chain-explorer-hml-databricks` | HML | Databricks workspace storage (HML) |

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
|---|---|---|---|---|---|
| `mainnet-transactions-data-dev` | DEV | PROVISIONED | 1 | Job 4 (×6) | Job 5 (×3) |
| `mainnet-transactions-data-hml` | HML | PROVISIONED | 1 | Job 4 (×6) | Job 5 (×3) |
| `mainnet-transactions-data` | PRD | PROVISIONED | 1 | Job 4 (×6) | Job 5 (×3) |

**Note:** PRD stream managed by Terraform `04_peripherals`. Only one Kinesis stream exists (raw transactions). Blocks and decoded txs use Firehose Direct Put.

---

## Kinesis Firehose Delivery Streams

| Stream Name | Env | Source | S3 Destination |
|---|---|---|---|
| `firehose-mainnet-blocks-data-dev` | DEV | Direct Put (Job 3) | `dm-chain-explorer-dev-ingestion/raw/mainnet-blocks-data/` |
| `firehose-mainnet-transactions-data-dev` | DEV | Kinesis-source | `dm-chain-explorer-dev-ingestion/raw/mainnet-transactions-data/` |
| `firehose-mainnet-transactions-decoded-dev` | DEV | Direct Put (Job 5) | `dm-chain-explorer-dev-ingestion/raw/mainnet-transactions-decoded/` |
| `firehose-app-logs-dev` | DEV | CloudWatch Logs | `dm-chain-explorer-dev-ingestion/raw/app_logs/` |
| `firehose-app-logs-hml` | HML | CloudWatch Logs | `dm-chain-explorer-hml-raw/raw/app_logs/` |

**PRD equivalents** (managed by Terraform, suffixed without `-dev`): same structure, pointing to `dm-chain-explorer-raw-data`.

### Firehose Configuration

- **Buffer:** 1 MB OR 60 seconds (whichever comes first)
- **Format:** NDJSON (no compression prefix — gzip applied by CloudWatch Logs source)
- **Partitioning:** `year=YYYY/month=MM/day=DD/hour=HH/` (dynamic partitioning)

---

## SQS Queues

| Queue Name | Env | Producer | Consumer | DLQ | Visibility Timeout |
|---|---|---|---|---|---|
| `mainnet-mined-blocks-events-dev` | DEV | Job 1, Job 2 | Job 2, Job 3 | `...-dlq-dev` | 30s |
| `mainnet-mined-blocks-events-hml` | HML | Job 1, Job 2 | Job 2, Job 3 | `...-dlq-hml` | 30s |
| `mainnet-mined-blocks-events` | PRD | Job 1, Job 2 | Job 2, Job 3 | `...-dlq` | 30s |
| `mainnet-block-txs-hash-id-dev` | DEV | Job 3 | Job 4 (×6) | `...-dlq-dev` | 30s |
| `mainnet-block-txs-hash-id-hml` | HML | Job 3 | Job 4 (×6) | `...-dlq-hml` | 30s |
| `mainnet-block-txs-hash-id` | PRD | Job 3 | Job 4 (×6) | `...-dlq` | 30s |

**Configuration:** Long-polling (20s), max receive count = 3 before DLQ.

---

## DynamoDB Tables

| Table Name | Env | Key Schema | Billing | Purpose |
|---|---|---|---|---|
| `dm-chain-explorer-dev` | DEV | PK=`pk` (S), SK=`sk` (S), TTL=`ttl` | On-demand | All entities: SEMAPHORE, COUNTER, BLOCK_CACHE, ABI, ABI_NEG, CONTRACT, CONSUMPTION |
| `dm-chain-explorer-hml` | HML | Same | On-demand | Same entities for HML integration tests |
| `dm-chain-explorer` | PRD | Same | On-demand | Production single-table |
| `dm-chain-explorer-terraform-lock` | All | LockID (S) | On-demand | Terraform state locking |

---

## Lambda Functions

| Function Name | Env | Runtime | Trigger | Purpose |
|---|---|---|---|---|
| `dm-chain-explorer-gold-to-dynamodb-dev` | DEV | Python 3.12 | S3 PutObject (`exports/`) | Reads Gold JSON export → writes CONSUMPTION entities to DynamoDB |
| `dm-chain-explorer-contracts-ingestion-dev` | DEV | Python 3.12 | EventBridge Scheduler (hourly) | Reads CONTRACT entities from DynamoDB → Etherscan API → writes batch JSON to S3 |
| `dm-chain-explorer-gold-to-dynamodb` | PRD | Python 3.12 | S3 PutObject | Same as DEV, PRD bucket |
| `dm-chain-explorer-contracts-ingestion` | PRD | Python 3.12 | EventBridge Scheduler (hourly) | Same as DEV, PRD resources |

**Lambda Layer:** `dm-chain-utils` installed as a Lambda layer (shared between both functions).

---

## ECS / ECR

| Resource | Name | Notes |
|---|---|---|
| ECS Cluster (HML) | `dm-chain-explorer-ecs-hml` | Ephemeral — created per CI/CD run |
| ECS Cluster (PRD) | `dm-chain-explorer-ecs` | Managed by `07_ecs` Terraform module |
| ECR Repository | `onchain-stream-txs` | Docker image for all 5 streaming jobs |
| ECS Services (PRD) | 5 services (jobs 1–5) | Job 4 runs with 6 tasks, Job 5 with 3 tasks |

---

## CloudWatch Logs

| Log Group | Source | Firehose Subscription |
|---|---|---|
| `/apps/dm-chain-explorer-dev` | Docker streaming jobs (DEV) | `firehose-app-logs-dev` |
| `/apps/dm-chain-explorer-hml` | ECS tasks (HML) | `firehose-app-logs-hml` |
| `/apps/dm-chain-explorer` | ECS tasks (PRD) | `firehose-app-logs` |

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
    iam/terraform.tfstate
    peripherals/terraform.tfstate
    databricks-account/terraform.tfstate
    databricks-workspace/terraform.tfstate
    lambda/terraform.tfstate
    ecs/terraform.tfstate
```

---

## IAM Key Roles (PRD)

| Role | Usage |
|---|---|
| `dm-ecs-task-execution-role` | ECS task pull from ECR + CloudWatch |
| `dm-ecs-task-role` | ECS container accesses Kinesis, SQS, S3, DynamoDB, SSM |
| `dm-databricks-cross-account-role` | Databricks workspace cross-account access |
| `dm-databricks-cluster-role` | Databricks cluster S3 access (External Location) |
| `dm-lambda-role` | Lambda execution (S3, DynamoDB, SSM, EventBridge) |
