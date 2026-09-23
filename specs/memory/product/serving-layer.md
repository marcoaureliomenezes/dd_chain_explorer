---
slug: serving-layer
title: Serving Layer
category: product
tldr: SQL over g_market through one dev serverless SQL warehouse (2X-Small, 1-min auto-stop); no dashboards, no exports, no DynamoDB, no public API; PRD has no warehouse.
summary: The serving surface after release v0.7.0's rulings is deliberately minimal. Gold tables in g_market (company_daily_price, ibov_constituents_daily, company_fundamentals_snapshot) are read by SQL through the dev serverless PRO warehouse dm-chain-explorer-dev (2X-Small, auto-stop 1 minute, one cluster), declared in dev/04_unity_catalog and published to CI as DATABRICKS_WAREHOUSE_ID. PRD has no warehouse. Lakeview dashboards, the gold export job, the gold-to-dynamodb Lambda and DynamoDB are retired. Status 2026-09-23 — decided, not live.
tags:
  - serving
  - sql-warehouse
  - gold
  - analytics
last_updated: "2026-09-23"
release_origin: v0.7.0
---

## Propósito

**Status 2026-09-23 — DECIDED, not live** (no workspace yet).

Give analysts and the rebuild drill one way to read gold: SQL on a serverless warehouse
that costs nothing while idle.

## Fluxo de uso

1. The job overwrites `g_market` ([[medallion-pipelines]]).
2. An analyst, `e2e-verify` or the drill snapshot queries through warehouse
   `dm-chain-explorer-dev`; it starts on demand and stops after 1 minute idle.

## Trigger típico

Consulted when someone asks how to read the data, or proposes a dashboard, export or API.

## Diferencial

Zero fixed serving cost and no serving code to maintain; richer serving (dashboards, DY,
Genie) is deferred to backlog (`financial-sources-expansion-data-model`) and needs a ruling.

## Estado runtime tocado

- `databricks_sql_endpoint.dev` in `dev/04_unity_catalog` — serverless PRO, 2X-Small,
  min 1 / max 1 cluster, auto-stop 1 min (lives in the UC stack because its provider host
  is the workspace unit's output)
- GitHub env `dev` secret `DATABRICKS_WAREHOUSE_ID` (written by `dev/06_github`)
- Tables in [[data-catalog]] §`g_market`

## Dependências

- **[[medallion-pipelines]]**, **[[data-catalog]]**, **[[environments]]**

## Referência

### Retirado do inventário

Four Lakeview dashboards, `job_export_gold`, S3 `exports/`, the `gold-to-dynamodb` Lambda,
DynamoDB CONSUMPTION entities and the REST API idea are gone (R21; backlog
`rest-api-public-endpoint`, `dashboards-analytics-enrichment` rejected at CLOSURE).
