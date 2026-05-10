# Architecture — DD Chain Explorer

> System design reference. Source of truth for structural decisions.  
> Current state validated from: code, Terraform state, and live Databricks DEV catalog (2026-04).

---

## End-to-End Data Flow

```
Ethereum Mainnet (RPC)
    │
    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  CAPTURE LAYER — 5 Python Jobs on ECS Fargate                       │
│                                                                      │
│  Job 1: MinedBlocksWatcher                                           │
│    └─ polls eth_getBlock('latest') every 1s                          │
│    └─ emits block events → SQS [mainnet-mined-blocks-events]         │
│                                                                      │
│  Job 2: OrphanBlocksWatcher                                          │
│    └─ consumes SQS, verifies block hashes via RPC                    │
│    └─ checks DynamoDB TTL cache (BLOCK_CACHE, TTL 1h)                │
│    └─ flags chain reorgs → re-emits to same SQS                      │
│                                                                      │
│  Job 3: BlockDataCrawler                                             │
│    └─ consumes SQS, fetches full block (18+ fields) via RPC          │
│    └─ → Firehose Direct Put [mainnet-blocks-data]                    │
│    └─ fan-out tx hashes → SQS [mainnet-block-txs-hash-id]           │
│                                                                      │
│  Job 4: MinedTxsCrawler (×6 replicas)                               │
│    └─ consumes SQS, fetches tx details via Infura (17 API keys)      │
│    └─ DynamoDB SEMAPHORE for distributed key rotation                │
│    └─ → Kinesis [mainnet-transactions-data]                          │
│                                                                      │
│  Job 5: TxsInputDecoder (×3 replicas)                               │
│    └─ consumes Kinesis, decodes calldata (4-stage pipeline)          │
│    └─ DynamoDB ABI cache / ABI_NEG negative cache                   │
│    └─ → Firehose Direct Put [mainnet-transactions-decoded]           │
└─────────────────────────────────────────────────────────────────────┘
    │
    ▼ (all Firehose streams → S3 NDJSON, hourly partitioned)
┌─────────────────────────────────────────────────────────────────────┐
│  S3 RAW LAYER                                                        │
│  bucket: dm-chain-explorer-raw-data (PRD)                            │
│  raw/mainnet-blocks-data/year=Y/month=M/day=D/hour=H/               │
│  raw/mainnet-transactions-data/year=Y/month=M/day=D/hour=H/         │
│  raw/mainnet-transactions-decoded/year=Y/month=M/day=D/hour=H/      │
│  raw/app_logs/year=Y/month=M/day=D/hour=H/                          │
│  raw/batch/year=Y/month=M/day=D/ (Lambda contracts)                 │
└─────────────────────────────────────────────────────────────────────┘
    │
    ▼ (Auto Loader cloudFiles, triggered every 5 min by dm-trigger-dlt-all)
┌─────────────────────────────────────────────────────────────────────┐
│  DATABRICKS DLT — MEDALLION ARCHITECTURE                             │
│                                                                      │
│  Pipeline: dm-ethereum                                               │
│  ├─ Bronze (b_ethereum): eth_mined_blocks, eth_transactions,         │
│  │   eth_txs_input_decoded, popular_contracts_txs                   │
│  ├─ Silver (s_apps): eth_blocks, eth_transactions_staging,           │
│  │   eth_blocks_withdrawals, txs_inputs_decoded_fast,               │
│  │   transactions_ethereum, eth_canonical_blocks_index (MV)         │
│  └─ Gold (g_apps, g_network): 15 MVs                                │
│                                                                      │
│  Pipeline: dm-app-logs                                               │
│  ├─ Bronze (b_app_logs): b_app_logs_data                            │
│  ├─ Silver (s_logs): logs_streaming, logs_batch                     │
│  └─ Gold (g_api_keys): etherscan_consumption, web3_keys_consumption  │
└─────────────────────────────────────────────────────────────────────┘
    │
    ├─► Databricks Lakeview Dashboards (4)
    ├─► Databricks Genie AI/BI (1)
    ├─► S3 Gold Exports (job_export_gold)
    └─► DynamoDB (CONSUMPTION entities via gold_to_dynamodb Lambda)
```

---

## Architectural Decisions

### ADR-001: No Apache Kafka / No Schema Registry

**Decision:** Use Kinesis Data Streams + Firehose Direct Put as the event bus. Use JSON (NDJSON) natively with no Avro/Protobuf/Schema Registry.

**Rationale:** Kafka MSK introduces significant operational overhead and cost for a single-pipeline platform. Kinesis provides comparable throughput (1 shard = 1 MB/s) at lower operational complexity. JSON simplicity avoids schema evolution friction with minor payload overhead.

**Constraints:** Serialization coupling is implicit in code (no schema contract). Schema changes require coordinated code and DLT pipeline updates.

---

### ADR-002: Firehose Direct Put vs Kinesis Intermediary

**Decision:** Blocks data and decoded transactions go directly to Firehose Direct Put. Only raw transactions flow through Kinesis Data Streams (because Job 5 reads from Kinesis — a Kinesis intermediary is required for the multi-replica consumer pattern).

**Rationale:** Jobs 3 and 5 do not need the consumer group/shard offset functionality — they only need reliable S3 delivery. Only Job 4→Job 5 requires the Kinesis consumer model (multiple replicas, shard iteration).

---

### ADR-003: Single-Table DynamoDB Design

**Decision:** One DynamoDB table (`dm-chain-explorer`) for all entity types, using PK+SK composite key with entity type as PK prefix.

**Rationale:** Simplifies IAM policy (single resource ARN), avoids table proliferation, standard single-table design pattern with clear entity boundaries.

---

### ADR-004: DABs Component Atomicity

**Decision:** Each Databricks component (DLT pipeline, batch job, dashboard, alert, Genie) is an autonomous Databricks Asset Bundle with its own `databricks.yml` and 3-target config (dev/hml/prod).

**Rationale:** Enables independent deployment and lifecycle management. A fix in `job_delta_maintenance` does not require redeploying `dlt_ethereum`. Enables CI/CD parallelization and independent versioning tags.

**Tool:** `beteugeuse` CLI generates the component skeleton via Cookiecutter templates.

---

### ADR-005: Lambda Architecture for Transactions

**Decision:** `transactions_lambda` Gold MV unions streaming transactions (from `transactions_ethereum`) with batch contract transactions (from `popular_contracts_txs` Bronze, sourced via Lambda) with deduplication by `tx_hash` and priority by decode quality.

**Rationale:** Streaming pipeline captures recent transactions but has limited decode depth (Etherscan rate-limited). Batch Lambda provides richer, Etherscan-verified data for popular contracts. Union covers both recency and depth.

---

### ADR-006: Distributed API Key Rotation via DynamoDB Semaphore

**Decision:** Job 4 (MinedTxsCrawler) runs as 6 parallel replicas coordinating API key assignment via a DynamoDB-based semaphore (SEMAPHORE entity with TTL=60s).

**Rationale:** Single-node API key management would bottleneck at Infura rate limits (17 keys × ~100 RPS/key). Distributed semaphore allows each replica to claim an exclusive API key slot, maximizing throughput across the key pool without a central coordinator.

---

## Environment Topology

| Aspect | DEV | HML | PRD |
|--------|-----|-----|-----|
| Streaming apps | Docker Compose (local) | ECS Fargate (ephemeral, per-deploy) | ECS Fargate (persistent) |
| Databricks | Free Edition (`dev` catalog) | Free Edition (`hml` catalog) | Databricks Workspace (`dd_chain_explorer` catalog) |
| S3 | `dm-chain-explorer-dev-ingestion` | `dm-chain-explorer-hml-*` | `dm-chain-explorer-raw-data` + `dm-chain-explorer-lakehouse` |
| DynamoDB | `dm-chain-explorer-dev` | `dm-chain-explorer-hml` | `dm-chain-explorer` |
| Terraform state | `dev/` prefix in TF state bucket | `hml/` prefix | `prd/` prefix |
| Auth (streaming) | `~/.aws` profile | GitHub Secrets IAM user | ECS IAM task role |
| Auth (Databricks) | PAT (`[dev]` profile) | PAT (GitHub Secret) | OAuth M2M service principal |

---

## PRD Deploy Order (Terraform)

```
Phase 1 (parallel): 02_vpc + 04_peripherals
    │
    ▼
Phase 2: 03_iam
    │
    ▼
Phase 3 (parallel): 05a_databricks_account + 06_lambda + 07_ecs
    │
    ▼
Phase 4: 05b_databricks_workspace
```

**Destroy order** (reverse): 05b → (05a + 06 + 07 parallel) → 04 → 03 → (02) → never destroy 01.
