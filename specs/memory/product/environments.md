---
slug: environments
title: Environments — dev and prd
category: ops
tldr: Two environments, dev and prd, each a serverless Databricks workspace + ISOLATED catalog + raw/lakehouse buckets in us-east-1; dev carries the workload and the rebuild drill, prd is platform-only behind the production approval.
summary: What exists per environment and who may change it. dev — workspace dm-chain-explorer-dev (rebuildable), catalog dev, buckets dm-chain-explorer-dev-{raw,lakehouse}, capture runtime, bundle deployed, file-arrival trigger UNPAUSED, SQL warehouse; applied on every develop push without approval. prd — workspace dm-chain-explorer-prd (permanent, rebuildable, no destroy path), catalog prd, buckets, ECR; no workload, no warehouse; applied behind the GitHub environment production (operator approval). The account group is gated like prd. GitHub environments dev and production in infra and explorer carry Terraform-written Databricks secrets. hml and Free Edition are retired. Status 2026-09-23 — decided, not live.
tags:
  - environments
  - dev
  - prd
  - databricks
  - github-environments
last_updated: "2026-09-23"
release_origin: v0.7.0
---

## Propósito

**Status 2026-09-23 — DECIDED, not live.** Neither workspace exists; GitHub environments
`dev` and `production` exist in infra and explorer; the Terraform-written secrets arrive
with `*/06_github` after PR-β.

State, once, what differs between dev and prd, so no change assumes parity that is not
there (R4, R27, R28).

## Fluxo de uso

| Aspect | dev | prd |
|---|---|---|
| Workspace | `dm-chain-explorer-dev`, SERVERLESS — rebuildable unit `dev/05_workspace` | `dm-chain-explorer-prd`, SERVERLESS — `prd/05_workspace`, permanent, no destroy path |
| Catalog | `dev`, ISOLATED | `prd`, ISOLATED |
| Buckets | `dm-chain-explorer-dev-{raw,lakehouse}` (`dev/01_peripherals`) | `dm-chain-explorer-prd-{raw,lakehouse}` + ECR ×3 (`prd/04_peripherals`) |
| Capture runtime | `dev/03_capture`, schedules DISABLED, runs via `capture_run` | none |
| Bundle | `job_market_data` deployed, trigger UNPAUSED | `prod` target validated only |
| SQL warehouse | 2X-Small, 1-min auto-stop | none |
| Apply | on `develop` push, no approval | `production` approval over a plan summary; `account` group likewise |
| GitHub env secrets | `DATABRICKS_HOST/CLIENT_ID/CLIENT_SECRET`, `DATABRICKS_WAREHOUSE_ID`; var `DATABRICKS_ACCOUNT_ID` | same minus the warehouse |

## Trigger típico

Consulted before any change that touches prd, any environment approval, or the drill.

## Diferencial

Resilience is proven where it is cheap: the dev rebuild drill (AC-29) destroys the dev
workspace, re-applies it, re-binds the catalog, redeploys the bundle and compares table
counts — the same stacks rebuild prd if ever needed.

## Estado runtime tocado

- GitHub environments `dev`, `production` (infra + explorer); `production` created by seed
  S2 with the operator as reviewer, adopted by `prd/06_github` (reviewers never touched)
- `prd/06_github` sets the default branch `develop` in infra and explorer (R35)
- Deploy SPs `dm-chain-explorer-{dev,prd}-deploy` (account stack)

## Dependências

- **[[cicd-pipeline]]** — lanes, gates, drill
- **[[aws-resources]]**, **[[data-catalog]]**

## Referência

### Retirado do inventário

`hml` (environment, stacks, catalog, role) and the Free Edition workspace that served
dev/hml are retired (v0.6.0 ADR-10, R27). A PRD workload is backlog
`prod-environment-official-account`.
