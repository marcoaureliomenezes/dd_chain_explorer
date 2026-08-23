---
slug: serving-layer
title: Serving Layer
category: product
tldr: Four Lakeview dashboards over gold, plus a gold-export → S3 → Lambda → DynamoDB chain; alerts and Genie are not part of the surface.
summary: The serving layer exposes gold-layer Databricks tables. Four Lakeview dashboards read the gold schemas through the single serverless SQL warehouse, which is stopped by default on Free Edition; their catalog is a bundle variable, so the same dashboard deploys to any target. A batch gold export writes JSON to S3, whose PutObject event triggers a Lambda that writes CONSUMPTION entities to DynamoDB — a chain that exists but currently has no verified reader. SQL alerts and Genie spaces are not expressible in the deployed Databricks CLI and are therefore not part of this surface.
tags:
  - serving
  - dashboards
  - lambda
  - dynamodb
  - analytics
last_updated: "2026-08-23"
release_origin: v0.5.0
---

## Propósito

The serving layer is how humans and downstream systems consume the gold analytics produced by [[medallion-pipelines]]. It has two surfaces:

1. **Lakeview dashboards** — four dashboards (`Network Overview`, `Gas Analytics`, `Hot Contracts`, `API Health`), one bundle each, deployed to the `dev` and `hml` targets. Their catalog is a bundle variable, so a dashboard renders against whichever catalog its target names.
2. **Gold export chain** — a batch job exports gold tables as JSON to an S3 `exports/` prefix; a PutObject event on that prefix invokes the `gold_to_dynamodb` Lambda, which writes entities under a `CONSUMPTION` partition key to DynamoDB.

Every bundle runs as the workspace **service principal**, never a personal identity, and reads its workspace host from a variable rather than a literal.

Everything executes on a **single serverless SQL warehouse** which, on Free Edition, is **stopped** and does not auto-start from the API. Until an operator starts it from the UI, no dashboard or ad-hoc query returns anything.

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

- Four Lakeview dashboards in the Databricks workspace, `[dev]`-prefixed in the `dev` target and unprefixed in `hml`
- One serverless SQL warehouse (shared by all dashboards; stopped by default)
- Databricks gold schemas `g_apps`, `g_network`, `g_api_keys` in the target's catalog
- S3 `exports/` prefix — destination of the gold export job
- Lambda `gold_to_dynamodb` and the DynamoDB table it writes (see [[aws-resources]])

### Limites conhecidos

- **The export chain has no verified consumer.** The gold export → S3 → Lambda → DynamoDB chain is intact in code and infrastructure, but its only known historical reader was a capture-era job. Whether the external dd-chain-capture project reads these DynamoDB entities is **unverified**; the chain is deliberately kept until that is answered. The export job has never been run in this workspace.
- **No alerts, no Genie space.** The deployed Databricks CLI does not know those resource types, so declaring them would produce bundles that validate to zero resources and lie about the surface. Reinstatement waits on CLI support.
- **Nothing executes while the warehouse is stopped** — a Free Edition environment limit, not a defect.
- **No authentication or access control for dashboard viewers**, and no public API over gold.

## Dependências

- **Upstream**: [[medallion-pipelines]] — populates every gold table the dashboards and the export job read
- **Upstream**: [[data-catalog]] — authoritative names of the gold objects referenced by dashboard SQL
- **Infrastructure**: [[aws-resources]] — the S3 export prefix, the Lambda and the DynamoDB table
- **Deployment**: [[cicd-pipeline]] — the dashboards and the export job ship as Databricks Asset Bundles through the applications workflow
