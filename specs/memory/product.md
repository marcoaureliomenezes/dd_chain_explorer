# Product: DD Chain Explorer

## What It Is

DD Chain Explorer is a **real-time Ethereum blockchain data platform** that captures, processes, and serves on-chain transaction data. Built for operational analytics and API key consumption monitoring, it transforms raw Ethereum RPC data into queryable Gold-layer analytics using a Medallion architecture on Databricks.

## Problem Being Solved

Ethereum mainnet produces ~300,000 transactions per day. Understanding which contracts are popular, how gas is consumed, and how transactions are distributed between EOAs and contracts requires continuous ingestion of raw blockchain data and low-latency aggregation — work that cannot be done with on-demand queries against a node.

## Core Value Proposition

1. **Continuous capture** of all Ethereum mainnet transactions with < 2 min latency
2. **Decoded transaction inputs** (calldata → method name + arguments) via ABI resolution
3. **Gold-layer analytics** available via Databricks SQL Dashboards, Genie AI/BI, and S3 exports
4. **Operational visibility** into API key consumption and system health

---

## What the Product Does

### Data Capture (Streaming Layer)

Five Docker jobs running on AWS ECS Fargate capture Ethereum data in a DAG:

1. **Mined Blocks Watcher** — polls Ethereum RPC `eth_getBlock("latest")` every second, detects block gaps, emits block events to SQS.
2. **Orphan Blocks Watcher** — consumes block events, detects chain reorgs using DynamoDB TTL cache, flags orphaned blocks.
3. **Block Data Crawler** — fetches full block data from Ethereum RPC, delivers to Firehose (S3), fans out tx hashes to SQS.
4. **Mined Txs Crawler** — 6 parallel replicas fetch transaction details from Infura/Alchemy via API key rotation semaphore, publish to Kinesis.
5. **Txs Input Decoder** — 3 parallel replicas consume Kinesis, decode contract calldata through a 4-stage pipeline (DynamoDB ABI cache → Etherscan → 4byte.directory → raw selector), deliver to Firehose.

### Data Processing (DLT Pipelines)

Two Databricks Delta Live Tables (DLT) pipelines implement the Medallion architecture:

**Pipeline: dm-ethereum**
- Bronze: raw ingestion via Auto Loader from S3 (blocks, transactions, decoded inputs, batch contracts)
- Silver: parsed, deduplicated, type-cast, joined tables (8 tables in `s_apps`)
- Gold: materialized views for analytics (popular contracts ranking, P2P transfers, gas analytics, Lambda-unified transactions, network metrics)

**Pipeline: dm-app-logs**
- Bronze: CloudWatch Logs (double-gzip) via Auto Loader
- Silver: structured log records
- Gold: API key consumption metrics with time-windowed aggregations (Etherscan, Infura/Alchemy)

### Batch Enrichment (Lambda)

- **contracts_ingestion**: EventBridge hourly → Etherscan API → S3 batch → Bronze → Silver (contract metadata enrichment)
- **gold_to_dynamodb**: S3 PutObject trigger → reads Gold export JSON → writes to DynamoDB for real-time lookup by streaming jobs

### Data Serving

- **Lakeview Dashboards** (4): network overview, gas analytics, hot contracts, API health
- **Genie AI/BI Space** (1): natural language queries over Ethereum data
- **Databricks Alerts** (2): API key threshold, DynamoDB deadlock
- **S3 Exports**: Gold tables exported as JSON/CSV for external consumers

---

## Who Uses It

- **Platform engineers**: monitor streaming jobs, API key health, and data pipeline freshness
- **Data analysts**: query Gold tables via Databricks SQL dashboards
- **System operators**: use Genie space for ad-hoc questions in natural language
- **Cost analysts**: track Etherscan/Infura API key consumption and rotation efficiency

---

## Environments

| Environment | Purpose | Infrastructure |
|-------------|---------|---------------|
| **DEV** | Local development and experimentation | Docker Compose + Databricks Free Edition |
| **HML (Staging)** | CI/CD integration gate — ephemeral, created per deploy run | Ephemeral ECS tasks + Free Edition Databricks |
| **PRD (Production)** | Live production system | ECS Fargate + Databricks Workspace + Unity Catalog (AWS sa-east-1) |

---

## What It Does NOT Do

- Multi-chain support (Ethereum mainnet only)
- Historical backfill for arbitrary date ranges (full refresh workflow covers pipeline data only)
- Public REST API endpoint (future roadmap)
- User authentication or access control for dashboard viewers
- Real-time alerts for on-chain events (only operational infrastructure alerts)
