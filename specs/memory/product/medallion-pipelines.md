---
slug: medallion-pipelines
title: Medallion Job — job_market_data
category: product
tldr: One bundle, one serverless job [dev] dm-market-data — three chained PySpark batch tasks bronze → silver → gold over the raw landing, fired by file arrival; idempotent MERGE by sha256 and natural keys; no DLT.
summary: The processing core. Bundle apps/dabs/job_market_data in the new dd-chain-explorer holds one Databricks job, dm-market-data, of three spark_python_task steps (bronze, silver, gold) on serverless compute (environment client 2, performance_target STANDARD). A file-arrival trigger on the env's raw external location (file events on) fires it when a partition's _manifest.json lands. Bronze stores undecoded bytes per dataset keyed by content_sha256 plus raw_manifests; silver decodes with the reused pure-Python dm_market_parsers and MERGEs on natural keys, rejecting (never coercing) bad rows; gold overwrites three analytic tables. Tables are external Delta on the lakehouse bucket; the bundle owns only the job. Status 2026-09-23 — coded (explorer PR #5), not deployed; no workspace exists yet.
tags:
  - databricks
  - job
  - batch
  - medallion
  - bronze
  - silver
  - gold
  - file-arrival
last_updated: "2026-09-23"
release_origin: v0.7.0
---

## Propósito

**Status 2026-09-23 — DECIDED, coded in explorer PR #5 (`feature/0.7.0`), not deployed.**
`bundle validate -t dev` fails in CI until the dev workspace exists (expected); the first
deploy comes through the chain after infra PR-β ([[cicd-pipeline]]).

Turn every landed raw partition into queryable company prices and fundamentals, once,
with a rerun that changes nothing. One bundle, one job, three tasks — the smallest shape
that keeps layers separate and ordered (R19, R24).

## Fluxo de uso

1. `_manifest.json` lands under `s3://dm-chain-explorer-dev-raw/raw/`; the file-arrival
   trigger (`min_time_between_triggers_seconds: 300`, `wait_after_last_change_seconds:
   120`, UNPAUSED in dev) fires one run; `max_concurrent_runs: 1`, queue on.
2. **bronze** — for each partition whose manifest sha256 is not yet in
   `b_market.raw_manifests`: read files as `binaryFile`, write one row per file
   (`source, dataset, ingest_date, file_name, content, content_sha256, manifest_sha256,
   _ingested_at`) into the dataset's table, insert-only on `content_sha256`; record the
   manifest last.
3. **silver** — decode pending bronze rows with `dm_market_parsers`; MERGE on each natural
   key; a parse failure, a sha256 not in the partition manifest, or `versao IS NULL` is
   rejected and counted. `cvm_statements` keeps max `VERSAO` per (cnpj, dt_refer,
   statement, grupo_dfp) and `ORDEM_EXERC = ÚLTIMO`, value × `ESCALA_MOEDA`.
4. **gold** — overwrite three tables; a missing input gives NULL, never a fabricated value.
5. Each task emits a `MARKET_DATA_SUMMARY` (rows per layer, rejections); `e2e-verify` reads
   it and fails on 0 gold rows or any sha rejection.

## Trigger típico

Consulted for any change to parsing, keys, table shapes, the trigger, or the bundle
targets. Table-level truth lives in [[data-catalog]].

## Diferencial

Batch tasks over immutable raw replace streaming tables: nothing runs between landings,
every run is idempotent (manifest bookkeeping + MERGE), and the parsers are tested
off-cluster without Spark. Tables are external and schemas are stack-owned, so destroying
the workspace (rebuild drill, AC-29) loses no table.

## Estado runtime tocado

- `apps/dabs/job_market_data/`: `databricks.yml`, `resources/job_market_data.yml`,
  `src/market_data/{bronze,silver,gold,_spark,contract}.py`, `src/dm_market_parsers/**`
- Targets: `dev` (`run_as` the dev deploy SP, `[dev] ` prefix, catalog `dev`,
  `root_path ~/.bundle/job-market-data/dev`); `prod` (`mode: production`, catalog `prd`,
  validated in CI, never deployed — R28/O-7). Host from the GitHub environment, never in
  the tree.
- `workspace.artifact_path = /Volumes/<catalog>/ops/bundle_artifacts`
- Tables under `<lakehouse>/<schema>/<table>` on `dm-chain-explorer-<env>-lakehouse`

## Dependências

- **[[capture-layer]]** — the raw partitions and manifests
- **[[data-catalog]]** — the catalog, schemas and volume the UC stack provides
- **[[cicd-pipeline]]** — deploy on `infra-dev-applied`/`develop` push, `e2e-verify`

## Referência

### Retirado do inventário

The DLT pipelines `dm-ethereum` and `dm-app-logs`, `dlt_market_data`, `job_export_gold`,
the four Lakeview dashboard bundles, Auto Loader, and the Free Edition workspace they ran in
are gone (R19, R21, R27). No `dlt` import and no `pipelines:` resource may return without a
ruling.
