---
slug: serving-layer
title: Serving Layer
category: product
tldr: Four Lakeview dashboards, one Genie AI/BI space, DynamoDB export Lambda, and S3 gold exports serving analytics over Ethereum blockchain data.
summary: The serving layer exposes Gold-layer Databricks tables to users via 4 Lakeview dashboards (Network Overview, Gas Analytics, Hot Contracts, API Health), 1 Genie AI/BI natural language space, a DynamoDB CONSUMPTION export Lambda triggered by S3 PutObject, and S3 gold exports for external consumers.
tags:
  - serving
  - dashboards
  - genie
  - lambda
  - analytics
agent_tier: self-pull
token_estimate: 600
last_updated: "2026-06-08"
release_origin: memory-compliance-migration
---

## Propósito

The serving layer exposes the Gold-layer analytics produced by the DLT medallion to platform engineers, data analysts, and system operators. It provides four Lakeview dashboards for operational monitoring, a Genie AI/BI space for natural language queries, a Lambda function that exports Gold data to DynamoDB for real-time lookup by streaming jobs, and S3 gold exports for external consumers.

All dashboards use the `dd_chain_explorer.g_apps.*` and `dd_chain_explorer.g_network.*` Gold tables in PRD. The DynamoDB export enables streaming jobs to look up API key consumption data at runtime without querying Databricks SQL.

## Fluxo de uso

1. Gold tables are populated by `dm-ethereum` and `dm-app-logs` DLT pipeline runs.
2. Lakeview dashboards query Gold tables via Serverless SQL Warehouse (`warehouse_id: a2a66f2adb0faf18`).
3. Genie AI/BI space accepts natural language queries and translates them to SQL over 7 Gold table FQNs.
4. `job_export_gold` batch job exports Gold tables as JSON to S3 `exports/{table_name}/`.
5. S3 PutObject event on `exports/` prefix triggers `dm-chain-explorer-gold_to_dynamodb` Lambda.
6. Lambda reads the Gold JSON export and writes CONSUMPTION entities to DynamoDB for real-time lookup.

## Trigger típico

Dashboards and Genie are accessed ad-hoc by analysts and operators. The DynamoDB export Lambda fires automatically after each `job_export_gold` run via S3 event trigger.

## Diferencial

Without the serving layer, Gold analytics would require direct Databricks notebook access or SQL warehouse queries for every lookup. The Lambda DynamoDB export enables streaming jobs to check API key consumption thresholds without adding Databricks SQL latency to the hot path.

## Estado runtime tocado

- Databricks `dd_chain_explorer` catalog (PRD) — Gold tables queried by dashboards and Genie
- S3 `dm-chain-explorer-raw-data/exports/` — Gold JSON exports written by `job_export_gold`
- DynamoDB `dm-chain-explorer` — CONSUMPTION entities written by Lambda
- AWS Lambda `dm-chain-explorer-gold_to_dynamodb` (PRD)

## Dependências

- **Upstream**: `medallion-pipelines` populates Gold tables that dashboards and Genie query
- **Lambda trigger**: `job_export_gold` → S3 PutObject → `gold_to_dynamodb` Lambda → DynamoDB
- **Streaming jobs** read DynamoDB CONSUMPTION entities populated by this layer
