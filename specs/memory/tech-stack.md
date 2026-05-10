# Tech Stack — DD Chain Explorer

> Canonical technology inventory. All AI agents must verify version compatibility against this file before generating code.

---

## Application Layer

### Python Runtime

| Component | Version | Notes |
|-----------|---------|-------|
| Python | 3.12 | All services (streaming, Lambda, utils, DABs batch) |
| PySpark | >= 3.5 | DLT pipelines and batch jobs on Databricks |

### Streaming Application (Docker)

| Package | Version | Usage |
|---------|---------|-------|
| `web3` | >= 7.8.0 | Ethereum RPC calls (get_block, get_transaction) |
| `boto3` | >= 1.26.0 | AWS SDK (Kinesis, Firehose, SQS, DynamoDB, SSM, CloudWatch) |
| `hexbytes` | >= 1.3.0 | HexBytes → hex string conversion for Ethereum data |
| `eth-abi` | >= 2.0.0 | ABI decoding of transaction input calldata |
| `requests` | >= 2.28.0 | Etherscan API, 4byte.directory HTTP calls |
| `aiohttp` | latest | Async HTTP (used in transaction crawler) |
| `dm-chain-utils` | >= 0.2.9 | Shared internal library (see below) |

### Lambda Functions

| Package | Version | Usage |
|---------|---------|-------|
| `boto3` | >= 1.26.0 | S3, DynamoDB, SSM |
| `requests` | >= 2.28.0 | Etherscan API |
| `dm-chain-utils` | >= 0.2.9 | Lambda layer (dm_dynamodb, dm_etherscan, dm_parameter_store) |

---

## Shared Library: dm-chain-utils

Published to PyPI as `dm-chain-utils`. Source at `utils/`. Version synced with root `VERSION` file.

| Module | Class | Purpose |
|--------|-------|---------|
| `dm_dynamodb` | `DMDynamoDB` | Single-table wrapper for DynamoDB CRUD + conditional put + query |
| `dm_kinesis` | `KinesisHandler` | Kinesis producer (put_record, put_records) and consumer (generator) |
| `dm_sqs` | `SQSHandler` | SQS producer/consumer with batch support |
| `dm_firehose` | `FirehoseHandler` | Firehose Direct Put delivery (single + batch) |
| `dm_cloudwatch_logger` | `CloudWatchLoggingHandler` | Structured JSON logging to CloudWatch Logs with buffered batch delivery |
| `dm_web3_client` | `Web3Handler` | Web3.py wrapper for block and transaction extraction |
| `dm_etherscan` | `EtherscanClient` | Etherscan API v2 with ABI retrieval, 4-byte signatures, block lookups |
| `api_keys_manager` | `APIKeysManager` | Distributed semaphore via DynamoDB for API key rotation across replicas |
| `dm_parameter_store` | `ParameterStoreClient` | AWS SSM Parameter Store wrapper (get, put, list, path-based scan) |

---

## AWS Infrastructure

| Service | Configuration | Usage |
|---------|--------------|-------|
| **ECS Fargate** | 5 task definitions (1+1+1+6+3 replicas) | Streaming Docker jobs |
| **ECR** | `onchain-stream-txs` repository | Docker image registry |
| **Kinesis Data Streams** | PROVISIONED, 1 shard | `mainnet-transactions-data` — raw transactions |
| **Kinesis Firehose** | 4 Direct Put + 4 Kinesis-source streams | S3 hourly delivery with partitioning |
| **SQS** | 2 queues + 2 DLQs | Inter-job coordination (mined-blocks-events, block-txs-hash-id) |
| **DynamoDB** | Single-table `dm-chain-explorer`, on-demand | BLOCK_CACHE, SEMAPHORE, COUNTER, ABI, ABI_NEG, CONTRACT, CONSUMPTION |
| **S3** | 3 buckets: raw-data, lakehouse, databricks | Raw NDJSON ingestion, Delta tables, Databricks storage |
| **Lambda** | 2 functions | contracts_ingestion, gold_to_dynamodb |
| **EventBridge Scheduler** | Hourly rule | Triggers contracts_ingestion Lambda |
| **CloudWatch Logs** | Log groups per service | Application JSON logs → Firehose → S3 |
| **VPC (PRD)** | 10.0.0.0/16, 1 public + 2 private subnets | ECS in public subnet, Databricks in private |
| **SSM Parameter Store** | `/etherscan-api-keys` path | API key storage at runtime |

### AWS Region

All production resources: **sa-east-1** (São Paulo).

### Naming Convention

All resources prefixed `dm-{env}-` or `dm-dd-chain-explorer-{env}-`.

| env value | Environment |
|-----------|-------------|
| `dev` | Development |
| `hml` | Staging/Homologation |
| (none) | Production |

---

## Databricks

| Component | Version | Notes |
|-----------|---------|-------|
| Runtime | DBR 15.x LTS | DLT pipelines and cluster nodes |
| Unity Catalog | — | Enforced in PRD; DEV/HML use Free Edition |
| DLT (Delta Live Tables) | — | Continuous/triggered mode for pipeline updates |
| Auto Loader | `cloudFiles` | S3 JSON and binaryFile (CloudWatch Logs) ingestion |
| SQL Warehouses | Serverless | Dashboard queries, Genie, integration tests |
| Lakeview Dashboards | — | 4 dashboards for operational analytics |
| Genie AI/BI | — | 1 space for natural language queries |

### Catalog Convention

| Target | Catalog Name |
|--------|-------------|
| `dev` | `dev` |
| `hml` | `hml` |
| `prod` | `dd_chain_explorer` |

### Databricks Authentication

| Environment | Method |
|-------------|--------|
| DEV | PAT (Personal Access Token) in `~/.databrickscfg [dev]` |
| HML | PAT stored in GitHub Secrets |
| PRD | OAuth M2M (service principal client_id/secret in GitHub Secrets) |

---

## Infrastructure as Code

| Component | Version |
|-----------|---------|
| Terraform | >= 1.5 (CI uses 1.7.0) |
| AWS Provider | hashicorp/aws >= 5.0 |
| Databricks Provider | databricks/databricks (latest compatible) |
| State Backend | S3 `dm-chain-explorer-terraform-state` + DynamoDB lock |

### Module Inventory

| Module | Path | Purpose |
|--------|------|---------|
| `cloudwatch_logs` | `services/modules/cloudwatch_logs/` | Log groups with Firehose integration |
| `dynamodb` | `services/modules/dynamodb/` | Single-table DynamoDB with TTL + PITR |
| `ecs` | `services/modules/ecs/` | Cluster, ECR, service discovery |
| `iam` | `services/modules/iam/` | Roles and policies for ECS, Lambda, Databricks |
| `kinesis` | `services/modules/kinesis/` | Data Streams + Firehose → S3 |
| `lambda` | `services/modules/lambda/` | Functions, layers, S3 event triggers |
| `s3` | `services/modules/s3/` | Buckets with encryption, versioning, lifecycle |
| `sqs` | `services/modules/sqs/` | Queues with DLQs |
| `vpc` | `services/modules/vpc/` | VPC, subnets, IGW, SG, S3 VPC endpoint |

---

## CI/CD

| Component | Technology |
|-----------|-----------|
| Platform | GitHub Actions |
| Workflows | 7 (deploy apps, deploy infra, destroy infra, destroy all, auto-bump, drift detection, plan on PR) |
| CI scripts | 16 Bash scripts in `scripts/ci/` |
| Integration tests | 4 Bash scripts in `scripts/` |
| Terraform in CI | `terraform_wrapper: false` to preserve exit codes |
| Docker base image | `python:3.12-slim` |

---

## External APIs

| API | Authentication | Usage | Key Storage |
|-----|---------------|-------|------------|
| Ethereum RPC (Infura/Alchemy) | API key per provider | Block and transaction fetching (Jobs 1, 3, 4) | SSM `/infura-api-keys`, `/alchemy-api-keys` |
| Etherscan API v2 | API key | Contract ABI retrieval, 4-byte signatures, popular contracts | SSM `/etherscan-api-keys` |
| 4byte.directory | None | Fallback 4-byte selector resolution | Public API |

---

## Development Tools

| Tool | Purpose |
|------|---------|
| `make` | All developer shortcuts (60+ targets) |
| `docker compose` | DEV streaming app (services/dev/00_compose/app_services.yml) |
| `databricks bundle` | DABs deploy/validate/run |
| `cookiecutter` / `beteugeuse` | DABs component scaffolding (sibling project) |
