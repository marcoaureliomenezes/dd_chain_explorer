# TASKS: pipeline-restart-r1

**Status:** Aprovado
**Release:** pipeline-restart-r1
**Phase:** TASKS

Parallel groups are declared below. Tasks within the same group (A, B, E) may run concurrently.
Work-Package D (serving layer) depends on Work-Package C (DEV restart) completing first.

---

## Work-Package A — IAM + Security (devops-engineer)

<!-- Write-set: services/prd/03_iam/, apps/dabs/dashboard_*/resources/, apps/docker/, apps/lambda/ -->

- [x] T-R1-01 — **Remove dynamodb:Scan from ECS task role** | Owner: devops-engineer | Effort: S
  Evidence: ISSUE-008, `iam/main.tf:104–108`
  Write-set: `services/prd/03_iam/iam/main.tf`
  Done: `dynamodb:Scan` absent; only GetItem/PutItem/DeleteItem/UpdateItem in DynamoDB policy block.

- [x] T-R1-02 — **Replace IAM wildcard ARNs with explicit region+account** | Owner: devops-engineer | Effort: S
  Evidence: ISSUE-009, `iam/main.tf:62–92`
  Write-set: `services/prd/03_iam/iam/main.tf`
  Done: No `*:*` in region or account field of any Kinesis, SQS, or SSM ARN.

- [x] T-R1-03 — **Remove SSM Etherscan/Web3 access from Databricks cluster role** | Owner: devops-engineer | Effort: S
  Evidence: ISSUE-010, `iam/main.tf:384–395`
  Write-set: `services/prd/03_iam/iam/main.tf`
  Done: Databricks cluster IAM role has no SSM permissions for etherscan or web3 key paths.

- [x] T-R1-04 — **Scope Lambda CloudWatch IAM ARN** | Owner: devops-engineer | Effort: S
  Evidence: ISSUE-023, `iam/main.tf:438–442`
  Write-set: `services/prd/03_iam/iam/main.tf`
  Done: Lambda logs policy uses `arn:aws:logs:${var.region}:${var.account_id}:log-group:/aws/lambda/${var.name_prefix}-*`.

- [x] T-R1-05 — **Set embed_credentials: false in all 4 dashboard bundles** | Owner: devops-engineer | Effort: S
  Evidence: ISSUE-020, `dashboard_*/resources/dashboards/*.yml:5`
  Write-set: `apps/dabs/dashboard_*/resources/dashboards/*.yml`
  Done: `embed_credentials: false` confirmed in all 4 dashboard resource YAMLs.

- [x] T-R1-06 — **Pin dm-chain-utils==0.2.9 in all production artifacts** | Owner: devops-engineer | Effort: S
  Evidence: ISSUE-021, `constitution.md: dm-chain-utils >= 0.2.9`; SEC-02
  Write-set: `apps/docker/onchain-stream-txs/requirements.txt`, `apps/lambda/contracts_ingestion/requirements.txt`, `apps/lambda/gold_to_dynamodb/requirements.txt`
  Done: `==0.2.9` pinned in all 3 requirements.txt files; CI step validates exact version.

- [x] T-R1-07 — **Document LGPD PII classification in constitution.md** | Owner: devops-engineer | Effort: S
  Evidence: ISSUE-022, DE-SEC-004
  Write-set: `specs/memory/constitution.md`
  Done: "Data Classification" section added stating Ethereum addresses are pseudo-anonymous per LGPD Art. 7 VI.

---

## Work-Package B — Repository Hygiene (software-engineer-python)

<!-- Write-set: .gitignore, apps/dabs/ -->

- [x] T-R1-08 — **Add build artifacts to .gitignore and clean git index** | Owner: software-engineer-python | Effort: S
  Evidence: ISSUE-033, DE-Q-001, `apps/dabs/*/src/*/build/`
  Write-set: `.gitignore`
  Done: `build/`, `*.egg-info/`, `dist/` in root `.gitignore`; `git status` shows no tracked build/ directories.

- [x] T-R1-09 — **Delete deprecated monolith bundle and pre-split source tree** | Owner: software-engineer-python | Effort: S
  Evidence: ISSUE-034, PATTERN-02, PATTERN-03, `apps/dabs/_MONOLITH_DEPRECATED.databricks.yml`
  Write-set: `apps/dabs/` (deletions only)
  Done: `apps/dabs/_MONOLITH_DEPRECATED.databricks.yml` absent; pre-split source tree confirmed unreferenced and removed.

---

## Work-Package C — DEV Pipeline Restart (devops-engineer)

<!-- Write-set: Databricks workspace (DABs deploy), no source files modified -->
<!-- BLOCKED-BY-OPERATOR-DECISION: OQ-2 (default: DEV-first) -->

- [-] T-R1-10 — **Pause DEV DLT trigger; start Docker Compose streaming stack** | Owner: devops-engineer | Effort: S
  Evidence: ISSUE-001, CRIT-DBX-001
  Write-set: Databricks DEV workspace (trigger job config)
  BLOCKED-BY-OPERATOR-DECISION: OQ-2 (confirm DEV-first assumption)
  Done: `dm-trigger-all-dlts` is PAUSED; `make deploy_dev_stream` confirms all 5 containers running;
        S3 objects appear under `dm-chain-explorer-dev-ingestion/raw/mainnet-*/`.

- [-] T-R1-11 — **Fix DEV trigger cron to 5-min and set pause_status: PAUSED** | Owner: devops-engineer | Effort: S
  Evidence: ISSUE-012, NFR-DE-003, drift matrix row 3
  Write-set: `apps/dabs/dlt_ethereum/databricks.yml` (DEV target schedule)
  Done: DEV target cron is `0 */5 * * * ?` with `pause_status: PAUSED`.

---

## Work-Package D — Serving Layer Fixes (data-analyst + data-engineer)

<!-- Depends on: T-R1-10 complete (S3 data confirmed in DEV) -->

- [ ] T-R1-12 — **Fix DynamoDB deadlock alert table reference** | Owner: data-analyst | Effort: S
  Evidence: ISSUE-002, DA-004, `alert_dynamodb_deadlock.yml:19`; LAKEHOUSE-02
  Write-set: `apps/dabs/alert_dynamodb_deadlock/resources/alert_dynamodb_deadlock.yml`
  Done: Query uses `s_logs.logs_streaming`; alert deploys without error; manual trigger returns result (not table-not-found).

- [ ] T-R1-13 — **Embed warehouse_id in all 4 dashboard bundle targets** | Owner: data-analyst | Effort: S
  Evidence: ISSUE-004, DA-001, UC-03, `dashboard_*/databricks.yml:8`
  Write-set: `apps/dabs/dashboard_*/databricks.yml`
  Done: All 4 dashboard bundle YAMLs have non-empty `warehouse_id` per target; dashboards render in DEV.

- [ ] T-R1-14 — **Fix 4 wrong Genie table FQNs** | Owner: data-analyst | Effort: S
  Evidence: ISSUE-005, DA-005, LAKEHOUSE-03, `genie_ethereum.yml:19–37`
  Write-set: `apps/dabs/genie_ethereum/genie_ethereum.yml`
  Done: All 7 FQNs in Genie YAML reference existing tables; at least 1 NL query returns results without table-not-found.

- [ ] T-R1-15 — **Fix network-overview dashboard: remove non-existent table references** | Owner: data-analyst | Effort: M
  Evidence: ISSUE-006, DA-002, `01_network_overview.lvdash.json:5,10`
  Write-set: `apps/dabs/dashboard_network_overview/resources/dashboards/01_network_overview.lvdash.json`
  Done: All dataset queries reference `g_network.network_metrics_hourly` or `g_network.block_production_health`; no `dev.gold.*` hardcoded references remain; dashboard renders.

- [ ] T-R1-16 — **Fix hot-contracts and gas-analytics dashboards to use Gold MVs** | Owner: data-analyst | Effort: S
  Evidence: ISSUE-007, DA-003, `02_hot_contracts.lvdash.json`, `03_gas_analytics.lvdash.json`
  Write-set: `apps/dabs/dashboard_hot_contracts/resources/dashboards/02_hot_contracts.lvdash.json`, `apps/dabs/dashboard_gas_analytics/resources/dashboards/03_gas_analytics.lvdash.json`
  Done: Hot-contracts queries `g_apps.popular_contracts_ranking`; gas-analytics uses `g_apps.gas_price_distribution_hourly`; both dashboards render data.

---

## Work-Package E — DLT Pipeline Code Fixes (data-engineer)

<!-- Independent — no dependency on C or D for code changes; validation requires C complete -->

- [x] T-R1-17 — **Fix HML ingestion bucket name in DLT bundle config** | Owner: data-engineer | Effort: S
  Evidence: ISSUE-014, DE-S-004, `dlt_ethereum/databricks.yml:46`
  Write-set: `apps/dabs/dlt_ethereum/databricks.yml`
  Done: HML target `ingestion_s3_bucket` is `"dm-chain-explorer-hml-raw"`.

- [x] T-R1-18 — **Remove lakehouse S3 folder prefixes (medallion naming violation)** | Owner: data-engineer | Effort: S
  Evidence: ISSUE-029, AWS-03, `peripherals.tf:50–51`
  Write-set: `services/prd/04_peripherals/peripherals.tf`
  Done: `folder_prefixes = ["bronze","silver","gold"]` removed; `.keep` objects deleted from S3 bucket.

- [x] T-R1-19 — **Promote from_address to expect_or_drop in DLT** | Owner: data-engineer | Effort: S
  Evidence: ISSUE-030, DE-P-003, `ethereum_pipeline.py:208–209`
  Write-set: `apps/dabs/dlt_ethereum/src/*/ethereum_pipeline.py`
  Done: `from_address` DLT expectation is `expect_or_drop`; `to_address` remains `expect`.

- [x] T-R1-20 — **Refactor eth_canonical_blocks_index to bounded rolling window** | Owner: data-engineer | Effort: M
  Evidence: ISSUE-003, DE-P-001, `ethereum_pipeline.py:486–505`
  Write-set: `apps/dabs/dlt_ethereum/src/*/ethereum_pipeline.py`
  Done: `eth_canonical_blocks_index` uses rolling window of last 1,000 blocks; blocks outside window marked canonical; DLT run completes without O(N^2) scan warning; validated in DEV after T-R1-10 complete.

---

## CLOSURE Tasks (product-engineer — CLOSURE phase only)

- [ ] T-R1-CL-01 — **Convert specs/memory/architecture.md to specs/memory/architecture.html**
  Owner: product-engineer | Phase: CLOSURE only
  Done: `specs/memory/architecture.html` exists and reflects post-R1 operational architecture.

- [ ] T-R1-CL-02 — **Convert specs/memory/aws-resources.md to specs/memory/aws-resources.html**
  Owner: product-engineer | Phase: CLOSURE only
  Done: `specs/memory/aws-resources.html` exists and reflects post-R1 IAM fixes applied.

- [ ] T-R1-CL-03 — **Convert specs/memory/data-catalog.md to specs/memory/data-catalog.html**
  Owner: product-engineer | Phase: CLOSURE only
  Done: `specs/memory/data-catalog.html` exists with corrected Gold/Silver schema; stale FQNs removed.

---

## Task Summary

| ID | Work-Package | Owner | Effort | Issue |
|----|-------------|-------|--------|-------|
| T-R1-01 | A — Security | devops-engineer | S | ISSUE-008 |
| T-R1-02 | A — Security | devops-engineer | S | ISSUE-009 |
| T-R1-03 | A — Security | devops-engineer | S | ISSUE-010 |
| T-R1-04 | A — Security | devops-engineer | S | ISSUE-023 |
| T-R1-05 | A — Security | devops-engineer | S | ISSUE-020 |
| T-R1-06 | A — Security | devops-engineer | S | ISSUE-021 |
| T-R1-07 | A — Security | devops-engineer | S | ISSUE-022 |
| T-R1-08 | B — Hygiene | software-engineer-python | S | ISSUE-033 |
| T-R1-09 | B — Hygiene | software-engineer-python | S | ISSUE-034 |
| T-R1-10 | C — Restart | devops-engineer | S | ISSUE-001 (OQ-2) |
| T-R1-11 | C — Restart | devops-engineer | S | ISSUE-012 |
| T-R1-12 | D — Serving | data-analyst | S | ISSUE-002 |
| T-R1-13 | D — Serving | data-analyst | S | ISSUE-004 |
| T-R1-14 | D — Serving | data-analyst | S | ISSUE-005 |
| T-R1-15 | D — Serving | data-analyst | M | ISSUE-006 |
| T-R1-16 | D — Serving | data-analyst | S | ISSUE-007 |
| T-R1-17 | E — DLT | data-engineer | S | ISSUE-014 |
| T-R1-18 | E — DLT | data-engineer | S | ISSUE-029 |
| T-R1-19 | E — DLT | data-engineer | S | ISSUE-030 |
| T-R1-20 | E — DLT | data-engineer | M | ISSUE-003 |
| T-R1-CL-01 | CLOSURE | product-engineer | M | Memory migration |
| T-R1-CL-02 | CLOSURE | product-engineer | M | Memory migration |
| T-R1-CL-03 | CLOSURE | product-engineer | M | Memory migration |

**Total implementation tasks:** 20
**Total CLOSURE tasks:** 3
**Grand total:** 23
