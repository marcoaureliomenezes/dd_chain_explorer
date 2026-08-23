---
slug: medallion-pipelines
title: Medallion Pipelines
category: product
tldr: Two serverless Databricks DLT pipelines (dm-ethereum 24 tables, dm-app-logs 5) build the bronze/silver/gold medallion over S3 raw JSON.
summary: dm-ethereum ingests three raw Ethereum prefixes via Auto Loader and produces 3 bronze streaming tables, 6 silver objects and 15 gold materialized views, guarded by 11 silver expectations. dm-app-logs ingests Fluent-Bit application logs into 1 bronze, 2 silver and 2 gold objects with 4 expectations. Both run serverless in a single Free Edition workspace, have no DLT-level schedule, and are currently idle because raw ingestion is empty. Several deployed artifacts drift from repo code and several companion jobs are broken or conflict with Unity Catalog DLT ownership.
tags:
  - databricks
  - dlt
  - medallion
  - bronze
  - silver
  - gold
last_updated: "2026-08-23"
release_origin: v0.4.0
---

## Propósito

Two Databricks Delta Live Tables (DLT) pipelines implement the medallion architecture over the raw JSON that the external **dd-chain-capture** project lands in S3. They are the only writers of the objects listed in [[data-catalog]].

`dm-ethereum` (24 tables: 3 bronze streaming tables, 6 silver — 5 streaming tables plus the bounded `eth_canonical_blocks_index` MV — and 15 gold materialized views) handles block headers, raw transactions and decoded calldata. It carries **11 data-quality expectations, all on the silver layer** (9 `expect_or_drop`, 2 advisory `expect`); bronze and gold declare none.

`dm-app-logs` (5 tables: 1 bronze streaming table, 2 silver streaming tables, 2 gold MVs) parses application logs into API-key consumption analytics, with 4 expectations on the silver layer.

Both pipelines run **serverless** (`serverless: true`, channel CURRENT) in the single Free Edition workspace: the `dev` bundle target deploys `[dev]`-prefixed pipelines writing catalog `dev`; the unprefixed target writes catalog `hml`.

## Fluxo de uso

1. dd-chain-capture writes newline-delimited JSON to the S3 raw prefixes, partitioned `year=/month=/day=/`.
2. Bronze Auto Loader streams (`cloudFiles.format=json`, `inferColumnTypes=true`, `partitionColumns=""`, per-stream `schemaLocation` checkpoints) pick up new files. `partitionColumns=""` makes the streams ignore the Hive-style partition directories and read the payload only.
3. Silver streaming tables parse, type-cast, apply the expectations and join the three Ethereum streams into `transactions_ethereum`.
4. Gold materialized views aggregate silver into analytics-ready summaries.
5. A pipeline update is started by its trigger job or manually — there is no schedule on the pipelines themselves.

### Pipeline `dm-ethereum`

| Layer | Schema | Objects |
|-------|--------|---------|
| Bronze | `b_ethereum` | `eth_mined_blocks` (`raw/mainnet-blocks-data/`), `eth_transactions` (`raw/mainnet-transactions-data/`), `eth_txs_input_decoded` (`raw/mainnet-transactions-decoded/`) |
| Silver | `s_apps` | `eth_blocks`, `eth_blocks_withdrawals`, `eth_transactions_staging`, `txs_inputs_decoded_fast`, `transactions_ethereum`, `eth_canonical_blocks_index` (MV, 1,000-block rolling window) |
| Gold | `g_apps` | 9 MVs — contract ranking, gas, P2P and method analytics |
| Gold | `g_network` | 6 MVs — network KPIs, chain health, burn, withdrawals, validators |

Only `mainnet-transactions-decoded` declares schema hints; blocks and transactions rely on inference over web3 camelCase keys. Any rename of those keys upstream would silently produce nulls and be dropped by the silver `expect_or_drop` rules — the field-name contract with dd-chain-capture is the pipeline's most fragile assumption.

### Pipeline `dm-app-logs`

| Layer | Schema | Objects |
|-------|--------|---------|
| Bronze | `b_app_logs` | `b_app_logs_data` — Fluent-Bit NDJSON from `raw/app_logs/`, explicit schema |
| Silver | `s_logs` | `logs_streaming`, `logs_batch` |
| Gold | `g_api_keys` | `etherscan_consumption`, `web3_keys_consumption` |

### Scheduling and companion jobs

Scheduling is **job-based**, never pipeline-based: the `schedule:` block written in both pipeline bundles is a field the Databricks CLI in use does not recognise, so it is silently dropped and no deployed pipeline carries a schedule or trigger. The trigger jobs (`dm-trigger-ethereum`, `dm-trigger-app-logs`, `dm-trigger-all-dlts`) are all deployed **paused**.

Known gaps, all recorded in audit `20260823T145726Z-4db47555`:

- The deployed `dm-app-logs` notebook (both targets) is the **older binary-envelope log reader**, not the Fluent-Bit NDJSON reader that lives in the repo — it cannot parse the log format the capture project now emits (gap — audit DRIFT-18).
- The deployed `hml` `dm-ethereum` notebook is **pre-remediation code**: no bounded canonical window, `from_address` only advisory (gap — audit DRIFT-18).
- `dm-trigger-all-dlts` is deployed with **empty pipeline ids** in both targets, so it triggers nothing (gap).
- `dm-reconcile-orphan-blocks` references a notebook that **no longer exists** in the repo or the workspace (gap).
- `job_ddl_setup` pre-creates the same object names the pipelines own, and `job_delta_maintenance` runs `OPTIMIZE`/`VACUUM` on streaming tables and MVs — both **conflict with Unity Catalog DLT ownership** and would fail or corrupt pipeline ownership if run (gap).

## Trigger típico

Started by a trigger job or a manual pipeline update whenever new raw data has landed. In practice, nothing has triggered since the platform went idle: raw ingestion is empty, every trigger job is paused, and all objects were last written 2026-04-28.

## Diferencial

Without the DLT medallion, every analytics question would full-scan raw JSON in S3. The pipelines materialize gold aggregations incrementally, so dashboards and ad-hoc queries answer in seconds. The bounded `eth_canonical_blocks_index` window is the key performance invariant — it keeps orphan/canonical classification linear instead of degrading quadratically as the chain grows.

## Estado runtime tocado

- Databricks DLT pipelines `dm-ethereum` and `dm-app-logs`, one instance per bundle target in the single Free Edition workspace
- Databricks catalogs `dev` (materialized) and `hml` (deployed pipelines, no schemas ever created)
- S3 raw prefixes read by Auto Loader and the per-stream schema/checkpoint locations (see [[aws-resources]])
- Databricks-managed Delta storage for every streaming table and MV
- Companion Databricks jobs: triggers, gold export, DDL setup, delta maintenance, full refresh, orphan reconciliation

## Dependências

- **Upstream**: [[capture-layer]] — the external dd-chain-capture project is the sole producer of the raw prefixes; nothing in this repo writes them
- **Upstream**: [[aws-resources]] — bucket names, prefixes and the storage credential/external location that grant Databricks read access
- **Defines**: [[data-catalog]] — every object in the catalog is owned by one of these two pipelines
- **Downstream**: [[serving-layer]] — dashboards and the gold export consume the gold schemas
- **Deployment**: [[cicd-pipeline]] — Databricks Asset Bundles are deployed through the applications workflow
