---
slug: index
title: Product Catalog — DD Chain Explorer
category: product
tldr: A Brazilian market-data lakehouse — capture images land B3/CVM/BCB bytes in S3, a Databricks serverless batch job builds bronze/silver/gold, all in us-east-1 and owned by Terraform + GitHub Actions.
summary: Entry point for the product memory. The vision, users, the ordered feature catalog (capture, medallion job, data catalog, serving, environments, AWS resources, CI/CD), the capability map and the explicit limits as of 2026-09-23 — the v0.7.0 architecture is decided and coded but not yet live, and the Ethereum lane is retired.
tags:
  - catalog
  - product
  - index
last_updated: "2026-09-23"
release_origin: v0.7.0
---

## Visão atômica

**Status 2026-09-23.** DECIDED and coded (release v0.7.0, rulings R18-R36); not yet live in
us-east-1. Each atom carries its own LIVE/DECIDED line.

DD Chain Explorer lands public Brazilian market data — B3 quotes and index files, CVM
company filings, BCB macro series — as untouched bytes, and refines it into company daily
prices, Ibovespa constituents and fundamentals. Three repositories: `dd-chain-capture`
(images), `dd-chain-infrastructure` (every cloud object and the lanes), `dd-chain-explorer`
(the medallion bundle and, after C-DAY, `specs/`). The Ethereum lane is retired everywhere.

## Usuários

| Usuário | Descrição |
|---|---|
| Analysts | Query `g_market` through the dev SQL warehouse |
| Operator | Runs the trust seed once, approves `production`, dispatches the rebuild drill |
| Agents | Self-pull this catalog before touching capture, infrastructure, CI or the bundle |

## Catálogo de features

| Slug | Título | TL;DR |
|---|---|---|
| [capture-layer](capture-layer.md) | Capture Layer | 3 images, 7 jobs on Fargate Spot, untouched bytes + `_manifest.json` in the raw bucket |
| [medallion-pipelines](medallion-pipelines.md) | Medallion Job | One serverless job, bronze → silver → gold, fired by file arrival; no DLT |
| [data-catalog](data-catalog.md) | Data Catalog | ISOLATED catalogs `dev`/`prd`; `b_market` 12, `s_market` 8, `g_market` 3, `ops` volume |
| [serving-layer](serving-layer.md) | Serving Layer | SQL over `g_market` via one dev serverless warehouse; nothing else |
| [environments](environments.md) | Environments | dev carries the workload and the drill; prd is platform-only behind `production` |
| [aws-resources](aws-resources.md) | AWS Resources | us-east-1 target inventory + live sa-east-1 teardown status |
| [cicd-pipeline](cicd-pipeline.md) | CI/CD Pipeline | Plan-as-detector lanes, App-chained repos, trust seed, rebuild drill |

## Mapa de capacidades

```mermaid
flowchart LR
  CAP["dd-chain-capture<br/>publish-images"] --> ECR["ECR"]
  ECR --> RUN["Fargate capture run"]
  RUN --> RAW["S3 raw<br/>bytes + _manifest.json"]
  RAW -->|"file arrival"| JOB["job dm-market-data<br/>bronze → silver → gold"]
  JOB --> GOLD["g_market"]
  GOLD --> WH["dev SQL warehouse"]
  CI["infra lanes + GitHub App chain"] --> RUN & JOB
```

## Limites conhecidos

- Nothing runs yet in us-east-1; the POC gate (AC-22) is unproven.
- prd has no workload; capture schedules are DISABLED.
- No dashboards, exports, public API or DY/CAGR metrics.
- `constitution.md` still states the pre-R18 architecture until the operator's T-O7.5
  amendment.
