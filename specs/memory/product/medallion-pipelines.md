---
slug: medallion-pipelines
title: Medallion Pipelines
category: product
tldr: Two Databricks DLT pipelines (dm-ethereum, dm-app-logs) implementing bronze/silver/gold medallion architecture over S3 raw data — 30 total tables/MVs.
summary: Two Delta Live Tables pipelines process raw S3 NDJSON data through three layers. dm-ethereum handles Ethereum blockchain data (4 bronze, 6 silver, 15 gold). dm-app-logs handles CloudWatch application logs (1 bronze, 2 silver, 2 gold). Both use Auto Loader for incremental S3 ingestion and are triggered every 5 minutes by dm-trigger-all-dlts.
tags:
  - databricks
  - dlt
  - medallion
  - bronze
  - silver
  - gold
last_updated: "2026-06-11"
release_origin: v0.3.0
---

## Propósito

Two Databricks Delta Live Tables (DLT) pipelines implement the medallion architecture over S3 raw data. They transform raw NDJSON files (delivered by the capture layer) into queryable Gold-layer materialized views via Auto Loader incremental ingestion.

The `dm-ethereum` pipeline handles all Ethereum blockchain data: block headers, raw transactions, and decoded calldata. It produces 15 Gold MVs covering contract ranking, gas analytics, P2P transfers, network metrics, and validator withdrawals. The bounded `eth_canonical_blocks_index` Silver MV (1,000-block rolling window) is a key performance invariant.

The `dm-app-logs` pipeline processes CloudWatch application logs from the 5 streaming jobs, producing Gold MVs for API key consumption monitoring.

## Fluxo de uso

1. S3 raw data lands in `dm-chain-explorer-raw-data/raw/` (Firehose delivery, hourly partitioned).
2. `dm-trigger-all-dlts` Databricks job triggers both pipelines every 5 minutes (cron `0 */5 * * * ?`).
3. Auto Loader (`cloudFiles`) in Bronze tables detects new S3 files and ingests them as streaming tables.
4. Silver streaming tables parse, deduplicate, type-cast, and join bronze data.
5. Gold materialized views aggregate Silver data into analytics-ready summaries.

### Pipeline: dm-ethereum

| Layer | Schema | Tables |
|-------|--------|--------|
| Bronze | `b_ethereum` | eth_mined_blocks, eth_transactions, eth_txs_input_decoded, popular_contracts_txs |
| Silver | `s_apps` | eth_blocks, eth_blocks_withdrawals, eth_transactions_staging, txs_inputs_decoded_fast, transactions_ethereum, eth_canonical_blocks_index (MV, bounded 1,000 blocks) |
| Gold | `g_apps` | popular_contracts_ranking, peer_to_peer_txs, ethereum_gas_consume, transactions_lambda, contract_volume_ranking, contract_method_activity, contract_deploy_metrics_hourly, gas_price_distribution_hourly, p2p_transfer_metrics_hourly |
| Gold | `g_network` | network_metrics_hourly, chain_health_metrics, block_production_health, eth_burn_hourly, withdrawal_metrics, validator_activity |

### Pipeline: dm-app-logs

| Layer | Schema | Tables |
|-------|--------|--------|
| Bronze | `b_app_logs` | b_app_logs_data |
| Silver | `s_logs` | logs_streaming, logs_batch |
| Gold | `g_api_keys` | etherscan_consumption, web3_keys_consumption |

## Trigger típico

Used continuously — triggered every 5 minutes by the `dm-trigger-all-dlts` batch job when in production. In DEV, the trigger is PAUSED by default and activated manually for testing.

## Diferencial

Without the DLT medallion, raw S3 NDJSON files would require full-scan queries at every analytics request. The DLT medallion materializes Gold aggregations incrementally, enabling dashboard and Genie queries to complete in seconds rather than minutes. The `eth_canonical_blocks_index` bounded window prevents O(N²) self-join performance degradation as the dataset grows.

## Estado runtime tocado

- S3 `dm-chain-explorer-raw-data` (PRD) — read via Auto Loader
- S3 `dm-chain-explorer-lakehouse` (PRD) — Delta table storage and checkpoints
- Databricks `dd_chain_explorer` catalog (PRD) / `dev` catalog (DEV)
- DLT pipeline state managed by Databricks

## Dependências

- **Upstream**: `capture-layer` delivers raw NDJSON to S3
- **Lambda batch enrichment**: `contracts_ingestion` Lambda delivers batch contract data to S3 `raw/batch/` → Bronze `popular_contracts_txs`
- **Triggers downstream**: `serving-layer` (dashboards, Genie, alerts read Gold tables); `lambda-enrichment` (`gold_to_dynamodb` triggered by Gold S3 export)
