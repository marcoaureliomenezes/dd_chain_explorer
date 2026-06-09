---
slug: capture-layer
title: Capture Layer
category: product
tldr: Five ECS Fargate jobs continuously ingesting Ethereum blocks, transactions, and decoded calldata to S3 via Kinesis/Firehose/SQS.
summary: The streaming capture layer consists of 5 Docker/ECS jobs forming a processing DAG. Job 1 polls Ethereum RPC for new blocks, Job 2 detects chain reorgs, Job 3 fetches full block data, Job 4 (6 replicas) fetches transaction details via API key rotation, and Job 5 (3 replicas) decodes contract calldata. Output is delivered to S3 via Kinesis and Firehose.
tags:
  - capture
  - ecs
  - streaming
  - ethereum
  - kinesis
agent_tier: self-pull
token_estimate: 800
last_updated: "2026-06-08"
release_origin: memory-compliance-migration
---

## Propósito

The capture layer continuously ingests raw Ethereum mainnet data and delivers it to S3. Five Python Docker jobs run as ECS Fargate services in production and as Docker Compose services in development. They form a sequential processing DAG where each job consumes from its predecessor's output.

The layer handles three types of Ethereum data: block headers (Job 3 via Firehose Direct Put), raw transactions (Job 4 via Kinesis), and decoded transaction calldata (Job 5 via Firehose Direct Put). A distributed DynamoDB semaphore coordinates API key rotation across 6 parallel transaction-fetching replicas.

The ABI decoding pipeline (Job 5) uses a 4-stage fallback: DynamoDB ABI cache → Etherscan API → 4byte.directory → raw selector. This maximizes decode coverage while minimizing external API calls.

## Fluxo de uso

1. Job 1 (`MinedBlocksWatcher`) polls `eth_getBlock("latest")` every second and emits block events to SQS `mainnet-mined-blocks-events`.
2. Job 2 (`OrphanBlocksWatcher`) consumes the SQS queue, checks DynamoDB BLOCK_CACHE (TTL 1h) to detect chain reorgs, and re-emits valid block events.
3. Job 3 (`BlockDataCrawler`) fetches full block data from Ethereum RPC (18+ fields), delivers to Firehose `mainnet-blocks-data`, and fans out transaction hashes to SQS `mainnet-block-txs-hash-id`.
4. Job 4 (`MinedTxsCrawler`, 6 replicas) consumes transaction hashes from SQS, fetches transaction details via Infura API keys coordinated by DynamoDB SEMAPHORE, and publishes to Kinesis `mainnet-transactions-data`.
5. Job 5 (`TxsInputDecoder`, 3 replicas) consumes Kinesis, decodes contract calldata through the 4-stage ABI resolution pipeline, and delivers decoded records to Firehose `mainnet-transactions-decoded`.

## Trigger típico

Used continuously in production — the capture layer runs 24/7 processing every Ethereum block (~300,000 transactions/day) with target latency < 2 minutes from block mining to S3 delivery.

## Diferencial

Without the capture layer, Ethereum transaction data would only be available via on-demand RPC queries against a node — which can't handle the volume of 300K transactions/day at analytics query latency. The capture layer transforms the raw event stream into a queryable S3 lake with Hive-partitioned NDJSON files that Databricks Auto Loader can efficiently ingest incrementally.

## Estado runtime tocado

- DynamoDB `dm-chain-explorer[-dev|-hml]` — entities: BLOCK_CACHE (TTL 1h), SEMAPHORE (TTL 60s), ABI, ABI_NEG
- SQS `mainnet-mined-blocks-events[-dev|-hml]` — blocks coordination queue
- SQS `mainnet-block-txs-hash-id[-dev|-hml]` — transaction hash fan-out queue
- Kinesis `mainnet-transactions-data[-dev|-hml]` — raw transaction stream
- Firehose `firehose-mainnet-blocks-data[-dev]` → S3 `raw/mainnet-blocks-data/`
- Firehose `firehose-mainnet-transactions-decoded[-dev]` → S3 `raw/mainnet-transactions-decoded/`
- S3 `dm-chain-explorer-raw-data` (PRD) / `dm-chain-explorer-dev-ingestion` (DEV)
- SSM `/dm-chain-explorer/infura-api-keys`, `/dm-chain-explorer/etherscan-api-keys`

## Dependências

- **Ethereum RPC** (Infura/Alchemy) — required for all block and transaction fetching
- **AWS infrastructure** (`capture-layer` → `aws-infrastructure`) — ECS cluster, ECR, DynamoDB, Kinesis, Firehose, SQS, SSM must exist
- **dm-chain-utils** (`>= 0.2.9`) — shared library providing KinesisHandler, FirehoseHandler, SQSHandler, DMDynamoDB, Web3Handler, APIKeysManager
- **Triggers** → `medallion-pipelines` (downstream consumer via S3 Auto Loader)
