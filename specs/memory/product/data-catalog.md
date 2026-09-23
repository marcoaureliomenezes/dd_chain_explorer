---
slug: data-catalog
title: Data Catalog
category: product
tldr: One us-east-1 metastore; catalogs dev and prd, ISOLATED; schemas b_market (12 tables), s_market (8), g_market (3) and ops (volume bundle_artifacts); every table external Delta on the env's lakehouse bucket.
summary: Canonical Unity Catalog inventory after release v0.7.0's rulings. Metastore dm-chain-explorer-use1 (account stack); per environment a persistent UC stack owns the storage credential dm-<env>-uc with file events, external locations raw (read-only) and lakehouse, catalog dev or prd (ISOLATED, bound to its own workspace, storage_root on the lakehouse bucket, force_destroy false), schemas b_market/s_market/g_market/ops, volume ops.bundle_artifacts, and grants to the env deploy SP. The medallion job creates 12 bronze, 8 silver and 3 gold external tables. Status 2026-09-23 — decided and coded; no object exists yet.
tags:
  - databricks
  - unity-catalog
  - data-catalog
  - bronze
  - silver
  - gold
last_updated: "2026-09-23"
release_origin: v0.7.0
---

## Propósito

**Status 2026-09-23 — DECIDED, not live.** No us-east-1 metastore, catalog or table exists;
the account holds metastores only in other regions. Everything below is created by
`account/databricks`, `{env}/04_unity_catalog` (infra PR-β) and the first job run.

The one place that names every Unity Catalog object, who owns it, and what each table holds.

## Fluxo de uso

1. The account stack creates metastore `dm-chain-explorer-use1`; each workspace unit
   assigns it.
2. The UC stack creates credential `dm-<env>-uc` (IAM role `dm-chain-explorer-<env>-uc`),
   locations `dm-<env>-raw` (read-only) and `dm-<env>-lakehouse`, both `enable_file_events`,
   catalog `<env>`, its workspace binding, the four schemas and the volume.
3. Each medallion task runs `CREATE TABLE IF NOT EXISTS … USING DELTA LOCATION
   '<lakehouse>/<schema>/<table>'`, so registrations survive a workspace rebuild.

## Trigger típico

Consulted before writing SQL, adding a table, changing a key, or granting access.

## Diferencial

ISOLATED catalogs make dev and prd unreachable from each other's workspace (R31); external
tables plus a stack-owned catalog keep data and registrations through a rebuild.

## Estado runtime tocado

### Grants (deploy SP `dm-chain-explorer-<env>-deploy`)

Catalog `USE_CATALOG, USE_SCHEMA, CREATE_TABLE, MODIFY, SELECT`; raw location `READ_FILES`;
lakehouse `READ_FILES, WRITE_FILES, CREATE_EXTERNAL_TABLE`; volume `READ_VOLUME,
WRITE_VOLUME`.

### Schema `b_market` — bronze, 12 tables

`raw_manifests` (MERGE on `source, dataset, ingest_date, manifest_sha256`) plus one
undecoded-bytes table per dataset, insert-only on `content_sha256`: `b3_cotahist`,
`b3_ibov_portfolio`, `b3_instruments_consolidated`, `b3_trade_information_consolidated`,
`cvm_cad_cia_aberta`, `cvm_fca`, `cvm_dfp`, `cvm_itr`, `cvm_fre`, `cvm_ipe`, `bcb_sgs`.

### Schema `s_market` — silver, 8 tables (lineage `ingest_date, content_sha256`)

| Table | From | MERGE key (winner) |
|---|---|---|
| `b3_quotes` | cotahist | `data_pregao, codbdi, codneg, tpmerc` (ingest_date) |
| `b3_ibov_portfolio` | ibov_portfolio | `date, cod` |
| `b3_instruments` | instruments_consolidated | `rpt_dt, tckr_symb` |
| `cvm_companies` | cad_cia_aberta | `cnpj_cia` |
| `cvm_fca_securities` | fca | `codigo_negociacao` (dt_refer) |
| `cvm_statements` | dfp, itr | `cnpj, dt_refer, statement, grupo_dfp, ordem_exerc, cd_conta, dt_ini_exerc` (versao) |
| `cvm_capital_composition` | dfp, itr | `cnpj, dt_refer` (versao) |
| `bcb_series` | sgs | `code, date` |

`trade_information_consolidated`, FRE and IPE stay bronze-only.

### Schema `g_market` — gold, 3 tables (overwrite)

- `company_daily_price` — quotes with market cap via `cvm_fca_securities`; NULL when unknown.
- `ibov_constituents_daily` — Ibovespa portfolio per day.
- `company_fundamentals_snapshot` — TTM, EBITDA = EBIT + D&A, `pl, pvp, ev_ebitda, roe,
  roic`, margins, `dl_ebitda`; `dy` NULL (deferred), bank EBITDA NULL, no CAGR.

### Schema `ops`

Volume `bundle_artifacts` (MANAGED) — the bundle's `artifact_path`.

## Dependências

- **[[medallion-pipelines]]** — creates and fills every table
- **[[aws-resources]]** — lakehouse and raw buckets, UC IAM roles
- **[[serving-layer]]** — reads `g_market`

## Referência

### Retirado do inventário

The Free Edition `dev`/`hml` catalogs and the Ethereum schemas `b_ethereum`, `b_app_logs`,
`s_apps`, `s_logs`, `g_apps`, `g_network`, `g_api_keys` were abandoned with that
organization (R21, R27); they are not recreated.
