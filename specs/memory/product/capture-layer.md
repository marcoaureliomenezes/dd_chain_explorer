---
slug: capture-layer
title: Capture Layer
category: product
tldr: Three batch images from dd-chain-capture (b3-market-data, cvm-open-data, bcb-sgs), seven jobs run as Fargate Spot tasks by infra, landing untouched source bytes plus a raw-manifest-v1 _manifest.json in the raw bucket.
summary: How market data enters the platform. dd-chain-capture owns the code of three batch images and seven jobs and publishes them to ECR (the image seam); dd-chain-infrastructure owns the runtime — the dev/03_capture ECS cluster on Fargate Spot, per-image task roles scoped to raw/<source>/*, seven EventBridge Scheduler schedules kept DISABLED — and the capture_run workflow that starts one run per image after each explorer deploy. Every job writes raw/<source>/<dataset>/ingest_date=YYYY-MM-DD/ untouched bytes and then _manifest.json (raw-manifest-v1), the raw seam the medallion job fires on. Status 2026-09-23 — decided and coded, not yet live in us-east-1.
tags:
  - capture
  - ecr
  - fargate
  - raw
  - manifest
  - boundary
last_updated: "2026-09-23"
release_origin: v0.7.0
---

## Propósito

**Status 2026-09-23 — DECIDED, not live.** The images were published once to the
sa-east-1 ECR (run `35546515532`, 2026-09-21); those repos were emptied by the retire step
and the sa-east-1 runtime was destroyed (run `35817189275`). The us-east-1 registry and
runtime arrive with infra PR-β; capture PR #4 moves `publish-images.yml` to us-east-1.

Capture turns public Brazilian market sources into immutable raw partitions. Code and
runtime are split on purpose: `dd-chain-capture` owns what runs (images, jobs, the landing
library), `dd-chain-infrastructure` owns where and when it runs (registry, task
definitions, roles, schedules).

| Image | Jobs (schedule, UTC, all DISABLED) | Datasets landed |
|---|---|---|
| `b3-market-data` | `b3_cotahist_daily`, `b3_ibov_portfolio_daily`, `b3_consolidated_files_daily` (daily 00:30) | `b3/cotahist`, `b3/ibov_portfolio`, `b3/instruments_consolidated`, `b3/trade_information_consolidated` |
| `cvm-open-data` | `cvm_cadastro_fca`, `cvm_statements_dfp_itr`, `cvm_fre_ipe` (Sunday 03:00) | `cvm/cad_cia_aberta`, `cvm/fca`, `cvm/dfp`, `cvm/itr`, `cvm/fre`, `cvm/ipe` |
| `bcb-sgs` | `bcb_macro_series` (daily 01:00) | `bcb/sgs` |

History floor 2010 (R15), reached by runbook backfill (`capture-backfill.md`).

## Fluxo de uso

1. A push to capture `develop` (or `main`) runs `publish-images.yml`: environment `dev`
   pushes `dev-<sha>` + mutable `:dev`; `production` pushes `<sha>` + `latest`; role
   `dm-chain-explorer-gha-capture-publish` (ECR push/pull on the three repos only).
2. After each explorer dev deploy (`explorer-dev-deployed`), infra `capture_run.yml` starts
   one Fargate Spot task for `b3_cotahist_daily`, `cvm_cadastro_fca`, `bcb_macro_series`,
   waits for them, requires exit 0 and a `_manifest.json`, then signals `capture-landed`.
3. Each job writes its partition: data objects first, `_manifest.json` last. A present
   manifest means SKIP (`--force` overrides); a missing file at the source is `NO_FILE`,
   exit 0, no partition; CVM yearly ZIPs are compared by ETag/Last-Modified (UNCHANGED).
4. The manifest's arrival fires the medallion job ([[medallion-pipelines]]).

## Trigger típico

Consulted when a change touches an image, a job cadence (`var.capture_jobs` is the one
place), the raw layout, the task roles, or the question "where does the data come from".

## Diferencial

Raw is the untouched source response — ZIP, Latin-1 CSV or JSON exactly as fetched — so any
parser bug is fixed by re-reading raw, never by re-downloading (sources rotate; raw never
expires). The manifest gives every file a sha256 that bronze and silver re-check, and
landing last makes an interrupted run self-healing.

## Estado runtime tocado

- ECR `dm-chain-explorer-capture/{b3-market-data,cvm-open-data,bcb-sgs}` (`prd/04_peripherals`)
- `dev/03_capture`: cluster, SG (no ingress; HTTPS/HTTP egress), task definitions on
  `<repo>:dev`, task roles (`s3:PutObject` on `raw/<source>/*` of the dev raw bucket),
  log group (14 d), seven schedules DISABLED
- `s3://dm-chain-explorer-dev-raw/raw/<source>/<dataset>/ingest_date=YYYY-MM-DD/`
- MFA-gated operator role for backfill writes to `raw/*` (no delete)

## Dependências

- **dd-chain-capture** — image code; its own memory holds `raw-landing-contract` and
  `batch-capture-lane`
- **[[aws-resources]]** — registry, buckets, roles
- **[[cicd-pipeline]]** — `capture_run.yml` and the chain signals
- **Triggers → [[medallion-pipelines]]** — via file arrival

## Referência

### `_manifest.json` — `raw-manifest-v1`

`schema`, `source`, `dataset`, `ingest_date`, `job`, `image`, `image_tag`, `landed_at`,
`files[]` (`name`, `sha256`, `size_bytes`, `source_url`, `fetched_at`, `http_status`,
`etag`, `last_modified`, `content_type`).

### Retirado do inventário

The Ethereum capture lane (Kafka-Connect JSON under `raw/mainnet-*`, Fluent-Bit app logs,
the VPS producer, ECR `dd-chain-capture-stream`/`-connect`, the `capture/ecr` state with its
KMS key and Roles Anywhere anchor) is destroyed (R21, R34). Do not reintroduce it.
