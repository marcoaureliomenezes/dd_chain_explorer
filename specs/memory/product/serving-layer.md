---
slug: serving-layer
title: Serving Layer
category: product
tldr: Four Lakeview dashboards over gold, plus a gold-export → S3 → Lambda → DynamoDB chain; alerts and the Genie space are declared but never deployed.
summary: The serving layer exposes gold-layer Databricks tables. Four Lakeview dashboards are ACTIVE in the dev target and read the gold schemas through the single serverless SQL warehouse, which is stopped by default on Free Edition. Two alert bundles and one Genie space are declared with resource types the deployed CLI does not recognise, so they have never been created. A batch gold export writes JSON to S3, whose PutObject event triggers a Lambda that writes CONSUMPTION entities to DynamoDB — a chain that exists but currently has no verified reader.
tags:
  - serving
  - dashboards
  - lambda
  - dynamodb
  - analytics
last_updated: "2026-08-23"
release_origin: v0.4.0
---

## Propósito

The serving layer is how humans and downstream systems consume the gold analytics produced by [[medallion-pipelines]]. It has three surfaces, in decreasing order of how real they currently are:

1. **Lakeview dashboards** — four dashboards (`Network Overview`, `Gas Analytics`, `Hot Contracts`, `API Health`) are deployed and ACTIVE with the `[dev]` name prefix, each reading two or three gold tables.
2. **Gold export chain** — a batch job exports gold tables as JSON to an S3 `exports/` prefix; a PutObject event on that prefix invokes the `gold_to_dynamodb` Lambda, which writes entities under a `CONSUMPTION` partition key to DynamoDB.
3. **Alerts and natural-language querying** — bundles exist for two SQL alerts and one Genie space, but they declare resource types the deployed Databricks CLI does not recognise, so they validate to **zero resources and have never been created** (gap — no alert and no project Genie space exists in the workspace).

Everything executes on a **single serverless SQL warehouse** which, on Free Edition, is **stopped** and does not auto-start from the API. Until an operator starts it from the UI, no dashboard, alert or ad-hoc query returns anything.

## Fluxo de uso

1. A DLT pipeline update refreshes the gold materialized views.
2. An operator starts the serverless SQL warehouse (stopped by default, 10-minute auto-stop).
3. Dashboards query the gold schemas through that warehouse and render.
4. The gold export job, when run, writes JSON per table to the S3 `exports/` prefix.
5. The S3 PutObject event invokes the `gold_to_dynamodb` Lambda, which upserts CONSUMPTION entities into DynamoDB for low-latency lookup.

## Trigger típico

Dashboards are opened ad-hoc by the operator when investigating chain or API-key behaviour. The export chain fires only when the export job is run — which has not happened in this platform's current idle state.

## Diferencial

Without the serving layer, every gold answer would require a notebook or a hand-written SQL session. The dashboards turn the medallion into a glanceable operational view, and the DynamoDB export gives a millisecond-latency key-value surface for API-key consumption that no analytical query could match.

## Estado runtime tocado

- Four Lakeview dashboards in the Databricks workspace, published, `[dev]`-prefixed
- One serverless SQL warehouse (shared by all dashboards; stopped by default)
- Databricks gold schemas `g_apps`, `g_network`, `g_api_keys` in catalog `dev`
- S3 `exports/` prefix — destination of the gold export job
- Lambda `gold_to_dynamodb` and the DynamoDB table it writes (see [[aws-resources]])

### Known gaps

All recorded in audit `20260823T145726Z-4db47555`:

- **Catalog hard-coded.** Every dashboard dataset SQL names the `dev.` catalog literally, so deploying the dashboards to any other target would still query `dev` (gap).
- **Publish drift.** The live dashboards are published with embedded credentials while their bundles declare the opposite (gap).
- **Alerts and Genie never deployed.** The two alert bundles and the Genie-space bundle declare resource types unknown to the deployed CLI; they validate cleanly with zero resources. There is no live alert and no project Genie space (gap).
- **Export chain has no verified consumer.** The gold export → S3 → Lambda → DynamoDB chain is intact in code and infrastructure, but its only known historical reader was a capture-layer job that this release retired. Whether the external dd-chain-capture project reads these DynamoDB entities is **unverified** (gap — audit DRIFT-27). The export job itself has never been run in this workspace.
- **Nothing executes while the warehouse is stopped** — a Free Edition environment limit, not a defect.

## Dependências

- **Upstream**: [[medallion-pipelines]] — populates every gold table the dashboards and the export job read
- **Upstream**: [[data-catalog]] — authoritative names of the gold objects referenced by dashboard SQL
- **Infrastructure**: [[aws-resources]] — the S3 export prefix, the Lambda and the DynamoDB table
- **Deployment**: [[cicd-pipeline]] — dashboards, alerts and the export job ship as Databricks Asset Bundles through the applications workflow
