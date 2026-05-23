# SPEC: pipeline-restart-r1 — Restore Pipeline Operational Capability + Security Hardening

**Status:** Aprovado
**Owner:** product-engineer
**Priority bucket:** security > correctness > operational
**Generated from:** `.dadaia/reports/dd-chain-explorer/project-manager/2026-05-22T150000Z-mediation-index.html` (Part 2: Decision Matrix)
**Issues covered:** ISSUE-001 through 010, 012, 014, 020–024, 029, 030, 033, 034

---

## Goal

Restore full pipeline operational capability in DEV, fix all serving-layer broken references
(dashboards, Genie, alerts), and apply all security-bucket fixes that do not require operator
decisions — making the dd-chain-explorer platform functional and security-compliant for the first
time since its initial implementation.

## Scope In

### Operational Recovery

- **ISSUE-001** — Pause DEV trigger job `dm-trigger-all-dlts`. Start Docker Compose streaming stack.
  Re-enable only after S3 Bronze data is confirmed in `dm-chain-explorer-dev-ingestion`.
- **ISSUE-012** — Set `pause_status: PAUSED` for DEV DLT trigger. Fix cron from hourly to 5-min
  (NFR-DE-003). Document in DevOps bundle SPEC.

### Serving Layer Fixes (Dashboard + Genie + Alerts)

- **ISSUE-002** — Replace dead `s_logs.apps_logs_fast` in `alert_dynamodb_deadlock.yml:19` with
  `s_logs.logs_streaming`. Upgrade Databricks CLI for alerts resource type.
- **ISSUE-004** — Embed correct Starter warehouse ID in all 6 bundle YAMLs (4 dashboards + 2 other
  targets). Run `databricks warehouses list` to discover ID per target.
- **ISSUE-005** — Fix 4 wrong Genie FQNs: `transactions_fast`→`s_apps.transactions_ethereum`,
  `blocks_fast`→`s_apps.eth_blocks`, `s_apps.popular_contracts_ranking`→`g_apps`,
  `s_apps.transactions_lambda`→`g_apps`. Upgrade Databricks CLI for genie_spaces type.
- **ISSUE-006** — Rewrite 3 dataset queries in `01_network_overview.lvdash.json` from
  `dev.gold.blocks_hourly_summary` to `g_network.network_metrics_hourly` and
  `g_network.block_production_health`. (OQ-3 affects catalog prefix — implement DEV fix now;
  full multi-env parameterization deferred to Release 4.)
- **ISSUE-007** — Redirect hot-contracts dashboard from `s_apps.popular_contracts_ranking` to
  `g_apps`. Replace inline Silver percentile computation in gas-analytics with
  `g_apps.gas_price_distribution_hourly`.

### Security Fixes

- **ISSUE-008** — Remove `dynamodb:Scan` from ECS task role. Restrict to GetItem, PutItem,
  DeleteItem, UpdateItem per entity type (`iam/main.tf:104–108`).
- **ISSUE-009** — Replace IAM wildcard `*:*` region+account with explicit
  `${var.region}:${var.account_id}` in all Kinesis/SQS/SSM ARNs (`iam/main.tf:62–92`).
- **ISSUE-010** — Remove SSM Etherscan/Web3 access from Databricks cluster role
  (`iam/main.tf:384–395`).
- **ISSUE-020** — Set `embed_credentials: false` in all 4 dashboard resource YAMLs.
- **ISSUE-021** — Pin `dm-chain-utils` to exact version `==0.2.9` in production Dockerfiles
  and Lambda requirements.txt. Add CI version validation step.
- **ISSUE-022** — Document in `specs/memory/constitution.md`: Ethereum addresses are
  "pseudo-anonymous public data" per LGPD Art. 7 VI. No UC masking required unless KYC-linked
  addresses are added.
- **ISSUE-023** — Scope Lambda CloudWatch IAM from `arn:aws:logs:*:*:*` to
  `arn:aws:logs:${var.region}:${var.account_id}:log-group:/aws/lambda/${var.name_prefix}-*`
  (`iam/main.tf:438–442`).

### Infrastructure Fixes

- **ISSUE-014** — Change HML `ingestion_s3_bucket` in `dlt_ethereum/databricks.yml:46` from
  `"dm-chain-explorer-hml-lakehouse"` to `"dm-chain-explorer-hml-raw"`.
- **ISSUE-029** — Remove `folder_prefixes = ["bronze","silver","gold"]` from lakehouse S3 module
  call in `peripherals.tf:50–51`. Delete `.keep` placeholder objects.
- **ISSUE-030** — Promote `from_address` validation from `expect` to `expect_or_drop` in DLT.
  Keep `to_address` as `expect` (NULL valid on contract deploys). (`ethereum_pipeline.py:208–209`).

### Scalability Pre-launch Gate

- **ISSUE-003** — Refactor `eth_canonical_blocks_index` from O(N^2) cross-join to bounded rolling
  window (last 1,000 blocks). Archive older blocks as permanently canonical.
  (`ethereum_pipeline.py:486–505`)

### Repository Hygiene

- **ISSUE-033** — Add `build/`, `*.egg-info/`, `dist/` to root `.gitignore`. Run
  `git rm -r --cached apps/dabs/*/src/*/build/`.
- **ISSUE-034** — Verify no active bundle references `apps/dabs/src/`. Delete deprecated bundle
  file `apps/dabs/_MONOLITH_DEPRECATED.databricks.yml` and pre-split source tree.

## Scope Out

- Kinesis ON_DEMAND switch → Release 2 (ISSUE-019)
- DynamoDB semaphore conditional put → Release 2 (ISSUE-011)
- FARGATE Spot strategy → Release 2 (ISSUE-017, ISSUE-026, pending OQ-6)
- S3 lifecycle rules → Release 2 (ISSUE-024)
- Firehose buffer alignment → Release 2 (ISSUE-025)
- Event-time windows in Gold MVs → Release 3 (ISSUE-016)
- Data-contract tests → Release 3 (ISSUE-015)
- Schema evolution strategy → Release 3 (ISSUE-028)
- canonical blocks bounded window → Release 3 (wait: ISSUE-003 must land first in R1)
- transactions_lambda Lambda Architecture resolution → Release 3 (ISSUE-031, pending OQ-5)
- Dashboard multi-env catalog parameterization → Release 4 (ISSUE-032, pending OQ-3)
- UC column descriptions → Release 4 (ISSUE-018)
- Genie context instruction block → Release 4
- Orphaned Gold MVs decision → Release 4 (ISSUE-027, pending OQ-4)
- PRD catalog name alignment → Release 4 (ISSUE-013, pending OQ-1)
- REST API implementation → not in any release yet
- Memory HTML atom migration → CLOSURE phase of this release only

## Blocked items (operator decision pending)

- **OQ-2** — DEV vs HML as first validated environment. This SPEC defaults to DEV-first.
  If operator selects HML-first, Task T-R1-01 scope changes. Mark tasks affected with
  `BLOCKED-BY-OPERATOR-DECISION: OQ-2`.

## Success Criteria (Acceptance Gate)

1. DEV DLT pipeline `dm-ethereum` produces rows in at least one Gold MV (`g_apps` or `g_network`)
   after Docker Compose stack is confirmed running with S3 data present.
2. All 4 Lakeview dashboards render data (no empty widget errors, `warehouse_id` non-empty).
3. Genie AI/BI space responds to at least one natural language query without "table not found" error.
4. P1 DynamoDB deadlock alert (`alert_dynamodb_deadlock`) evaluates correctly against
   `s_logs.logs_streaming` (no query failure).
5. IAM audit: `dynamodb:Scan` removed from ECS task role, no `*:*` wildcard ARNs in
   Kinesis/SQS/SSM policies, `embed_credentials: false` in all dashboard bundles.
6. `dm-chain-utils` pinned to `==0.2.9` in all production Dockerfiles and Lambda requirements.txt.
7. `eth_canonical_blocks_index` uses bounded rolling window (verified by code review and DLT run).
8. No `build/` directories in git index (verified by `git status` clean after `.gitignore` update).

## Dependencies on Other Releases

- This release has no dependency on subsequent releases.
- Releases 2, 3, and 4 depend on this release being in ARCHIVED state (DEV pipeline operational).

## Risks

- OQ-2 unresolved: if operator selects HML-first, T-R1-01 must be revised before implementation
  begins. Low probability — PM default is DEV-first.
- ISSUE-003 canonical blocks refactor has M effort. If DLT behavior is unexpected after bounded
  window, may require additional iteration. Mitigation: test with the last 1,000 blocks window in
  DEV before PRD.
- `embed_credentials` fix (ISSUE-020) may require dashboard re-deploy with viewer permissions
  review. Coordinator: data-analyst agent.

## Memory Files Affected at CLOSURE

- `specs/memory/architecture.html` — to be created from `architecture.md` during CLOSURE
- `specs/memory/aws-resources.html` — to be created from `aws-resources.md` during CLOSURE
- `specs/memory/data-catalog.html` — to be created from `data-catalog.md` during CLOSURE
- `specs/memory/tech-stack.md` — unchanged in this release; HTML migration deferred to R2
- `specs/memory/constitution.md` — LGPD classification note added (ISSUE-022)
- `specs/memory/product.md` — unchanged in this release
