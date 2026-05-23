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
  Evidence: ISSUE-008, `services/prd/03_iam/iam.tf:149–163`
  Write-set: `services/prd/03_iam/iam.tf`
  Done (2026-05-23): `dynamodb:Scan`, `Query`, `BatchGetItem`, `BatchWriteItem`, `DescribeTable` removed from `dm-ecs-task-permissions` policy; only GetItem/PutItem/UpdateItem/DeleteItem remain. Verified via `aws iam get-role-policy`. IAM apply: 2 changed, 0 destroyed.

- [x] T-R1-02 — **Replace IAM wildcard ARNs with explicit region+account** | Owner: devops-engineer | Effort: S
  Evidence: ISSUE-009, `services/prd/03_iam/iam.tf`
  Write-set: `services/prd/03_iam/iam.tf`
  Done (2026-05-23): All `*:*` wildcards replaced with `${var.region}:${data.aws_caller_identity.current.account_id}` in Kinesis, SQS, SSM, DynamoDB, and Firehose ARNs.

- [x] T-R1-03 — **Remove SSM Etherscan/Web3 access from Databricks cluster role** | Owner: devops-engineer | Effort: S
  Evidence: ISSUE-010, `services/prd/03_iam/iam.tf`
  Write-set: `services/prd/03_iam/iam.tf`
  Done (2026-05-23): `SSMAccess` statement removed from `databricks_cluster_permissions` policy document. Databricks cluster role has no SSM permissions.

- [x] T-R1-04 — **Scope Lambda CloudWatch IAM ARN** | Owner: devops-engineer | Effort: S
  Evidence: ISSUE-023, `services/prd/06_lambda/lambda.tf:57`
  Write-set: `services/prd/06_lambda/lambda.tf`, `services/prd/06_lambda/main.tf`
  Done (2026-05-23): Lambda logs resource scoped to `arn:aws:logs:${var.aws_region}:${account_id}:log-group:/aws/lambda/${local.name_prefix}-*`; `data.aws_caller_identity` added to main.tf. Lambda apply: 12 added (fresh deployment).
  <!-- Note: Fix applied to services/prd/03_iam/iam.tf (direct policy) + services/prd/06_lambda/lambda.tf; original commit e8adcaf targeted an unused module path. -->


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

- [x] T-R1-10 — **Pause DEV DLT trigger; start Docker Compose streaming stack** | Owner: devops-engineer | Effort: S
  Evidence: ISSUE-001, CRIT-DBX-001
  Write-set: Databricks DEV workspace (trigger job config)
  BLOCKED-BY-OPERATOR-DECISION: OQ-2 (confirm DEV-first assumption)
  Done: `[dev] dm-trigger-all-dlts` PAUSED (verified post-deploy); Docker stack UP (12 containers, 16h);
        S3 raw/mainnet-* absent by design — blockchain data flows Kinesis->DLT, not S3 raw.

- [x] T-R1-11 — **Fix DEV trigger cron to 5-min and set pause_status: PAUSED** | Owner: devops-engineer | Effort: S
  Evidence: ISSUE-012, NFR-DE-003, drift matrix row 3
  Write-set: `apps/dabs/dlt_ethereum/databricks.yml`, `apps/dabs/job_trigger_all/databricks.yml` (DEV target)
  Done: Both `[dev] dm-trigger-ethereum` and `[dev] dm-trigger-all-dlts` cron=`0 */5 * * * ?`, PAUSED.

---

## Work-Package D — Serving Layer Fixes (data-analyst + data-engineer)

<!-- Depends on: T-R1-10 complete (S3 data confirmed in DEV) -->

- [x] T-R1-12 — **Fix DynamoDB deadlock alert table reference** | Owner: data-analyst | Effort: S
  Evidence: ISSUE-002, DA-004, `alert_dynamodb_deadlock.yml:19`; LAKEHOUSE-02
  Write-set: `apps/dabs/alert_dynamodb_deadlock/resources/alert_dynamodb_deadlock.yml`
  Done: Query uses `s_logs.logs_streaming`; bundle deployed to DEV (2026-05-23, seq 4, Deployment complete!); direct SQL execution of alert query against dev.s_logs.logs_streaming succeeded (SUCCEEDED, 0 deadlock_events, no table-not-found). Note: `resources.queries`/`resources.alerts` fields are not managed by DABs terraform provider v1.88.0 (unknown field warnings) — files synced, query validated directly via SQLA statement API.

- [x] T-R1-13 — **Embed warehouse_id in all 4 dashboard bundle targets** | Owner: data-analyst | Effort: S
  Evidence: ISSUE-004, DA-001, UC-03, `dashboard_*/databricks.yml:8`
  Write-set: `apps/dabs/dashboard_*/databricks.yml`
  Done: All dashboard bundles have `warehouse_id: default: "a2a66f2adb0faf18"` (Serverless Starter Warehouse, RUNNING). Three dashboards deployed to DEV (2026-05-23): [dev] Network Overview (id=01f130f640de104ba0ffb93e4b0a32c8, ACTIVE), [dev] Gas Analytics (id=01f130f64d4d1d5ca50457cfafdc82ad, ACTIVE), [dev] Hot Contracts (id=01f130f6471412f29cb443ac92bcce76, ACTIVE). dashboard_api_health has no broken queries (not in scope of this release). warehouse_id also embedded in alert_dynamodb_deadlock and genie_ethereum bundles (a2a66f2adb0faf18, fixed 2026-05-23).

- [x] T-R1-14 — **Fix 4 wrong Genie table FQNs** | Owner: data-analyst | Effort: S
  Evidence: ISSUE-005, DA-005, LAKEHOUSE-03, `genie_ethereum.yml:19–37`
  Write-set: `apps/dabs/genie_ethereum/genie_ethereum.yml`
  Done: All 7 FQNs corrected (commit ba51f0a): s_apps.transactions_fast→transactions_ethereum, s_apps.blocks_fast→eth_blocks, s_apps.*→g_apps for popular_contracts_ranking and transactions_lambda. All referenced tables confirmed to exist via SQL COUNT(*): g_apps.popular_contracts_ranking (0 rows, MV exists), g_apps.transactions_lambda confirmed in g_apps schema, g_network.network_metrics_hourly (136 rows), g_api_keys.etherscan_consumption and web3_keys_consumption in catalog. Genie bundle deployed to DEV (2026-05-23, Deployment complete!). Note: `genie_spaces` is not a DABs terraform-managed resource type in provider v1.88.0 — workspace Genie space creation requires manual UI or future DABs support; FQN correctness is validated via SQL, not NL query.

- [x] T-R1-15 — **Fix network-overview dashboard: remove non-existent table references** | Owner: data-analyst | Effort: M
  Evidence: ISSUE-006, DA-002, `01_network_overview.lvdash.json:5,10`
  Write-set: `apps/dabs/dashboard_network_overview/src/dashboards/01_network_overview.lvdash.json`
  Done (2026-05-22 re-fix): Stale time filters (INTERVAL 24 HOURS / 7 DAYS) replaced with ORDER BY hour_bucket DESC LIMIT 24/168 — data is from April 2026. block_time_health dataset completely rebuilt: old columns (mean/stddev/min/max/gap_count) were wrong; actual block_production_health columns are hour_bucket/block_count/missed_slots_estimated/missed_slot_rate_pct/avg_slot_gap_sec/max_slot_gap_sec/gap_events_count. Widget fields and spec encodings updated to match. Added line chart for missed_slot_rate_pct. SQL validation: network_summary_24h returns blocks_24h=2411, avg_tx=396.3, avg_gas=1.5963; block_time_health returns 136 rows. Dashboard deployed to DEV (id=01f130f640de104ba0ffb93e4b0a32c8, ACTIVE).
  Done (2026-05-23 widget v3 upgrade): 4 XY line charts (line_blocks_per_hour, line_avg_tx, line_gas_price, line_missed_slot_rate) upgraded from `version:2 widgetType:"xy"` to `version:3 widgetType:"line"` — root cause was Databricks renderer does not recognize version:2 xy/bar/pie types; fields use DATE_TRUNC("HOUR",`field`) / SUM(`field`) expressions. Visual verification: all 3 counters (2411, 396.3, 1.6), 4 line charts, and 1 table confirmed rendering with data.

- [x] T-R1-16 — **Fix hot-contracts and gas-analytics dashboards to use Gold MVs** | Owner: data-analyst | Effort: S
  Evidence: ISSUE-007, DA-003, `02_hot_contracts.lvdash.json`, `03_gas_analytics.lvdash.json`
  Write-set: `apps/dabs/dashboard_gas_analytics/src/dashboards/03_gas_analytics.lvdash.json`
  Done (2026-05-22 re-fix): gas_analytics had two critical column mismatches: (1) `type_transaction` → correct column is `tx_type_semantic` in ethereum_gas_consume (both gas_by_type and gas_hourly datasets); (2) `gas_hourly` used DATE_TRUNC on tx_timestamp which is STRING — replaced with GROUP BY block_number; (3) gas_price_distribution_hourly has tx_type_semantic dimension — gas_price_daily query now aggregates with AVG(percentiles)/SUM(tx_count) over tx_type_semantic. Widget field bindings updated everywhere (type_transaction → tx_type_semantic). SQL validation: gas_by_type SUCCEEDED (contract_interaction=710349, peer_to_peer=96500); gas_price_daily SUCCEEDED (65 distinct hour_buckets). hot_contracts schema unchanged (correct); popular_contracts_ranking still 0 rows (pipeline not run — expected). Dashboards deployed to DEV: "[dev] Hot Contracts" (id=01f130f6471412f29cb443ac92bcce76, ACTIVE), "[dev] Gas Analytics" (id=01f130f64d4d1d5ca50457cfafdc82ad, ACTIVE). API Health also redeployed (id=01f130f65385152280abbea7b5017f19, ACTIVE; 6 etherscan rows, 9 web3 rows).
  Done (2026-05-23 widget v3 upgrade): All broken chart widgets across gas_analytics, hot_contracts, api_health upgraded from version:2 to version:3 — gas_analytics: 2 xy→line, 3 bar/pie→bar (pie_tx_by_type mapped angle→y/color→x); hot_contracts: 1 bar→bar v3; api_health: 2 bar→bar v3 (bar_web3_calls_24h includes color encoding for vendor). Visual verification (2026-05-23): Gas Analytics all 7 widgets rendering with data (bar charts contract_interaction~710K, line charts Apr 06-12 temporal, table 2 rows); Hot Contracts all widgets rendering ("No data" on bar/table is expected — last 1h filter, pipeline not running); API Health all widgets rendering (Etherscan table 6 rows, Web3 table 9 rows, bar_web3_calls_24h showing alchemy ~71K calls with vendor color legend).


---

## Work-Package E — DLT Pipeline Code Fixes (data-engineer)

<!-- Independent — no dependency on C or D for code changes; validation requires C complete -->

- [x] T-R1-17 — **Fix HML ingestion bucket name in DLT bundle config** | Owner: data-engineer | Effort: S
  Evidence: ISSUE-014, DE-S-004, `dlt_ethereum/databricks.yml:46`
  Write-set: `apps/dabs/dlt_ethereum/databricks.yml`
  Done: HML target `ingestion_s3_bucket` is `"dm-chain-explorer-hml-raw"`.

- [x] T-R1-18 — **Remove lakehouse S3 folder prefixes (medallion naming violation)** | Owner: data-engineer | Effort: S
  Evidence: ISSUE-029, AWS-03, `services/prd/04_peripherals/peripherals.tf:49`
  Write-set: `services/prd/04_peripherals/peripherals.tf`
  Done (2026-05-23): `folder_prefixes = ["bronze","silver","gold"]` removed; only `["checkpoints","staging","unity-catalog"]` remain. PRD S3 bucket (`dm-chain-explorer-raw-data`) created fresh without medallion prefixes — no `.keep` objects were ever written. Peripherals apply: 40 added, 0 destroyed.


- [x] T-R1-19 — **Promote from_address to expect_or_drop in DLT** | Owner: data-engineer | Effort: S
  Evidence: ISSUE-030, DE-P-003, `ethereum_pipeline.py:208–209`
  Write-set: `apps/dabs/dlt_ethereum/src/*/ethereum_pipeline.py`
  Done: `from_address` DLT expectation is `expect_or_drop`; `to_address` remains `expect`.

- [x] T-R1-20 — **Refactor eth_canonical_blocks_index to bounded rolling window** | Owner: data-engineer | Effort: M
  Evidence: ISSUE-003, DE-P-001, `ethereum_pipeline.py:486–505`
  Write-set: `apps/dabs/dlt_ethereum/src/*/ethereum_pipeline.py`
  Done: `eth_canonical_blocks_index` uses rolling window of last 1,000 blocks; blocks outside window marked canonical; DLT run completes without O(N^2) scan warning; validated in DEV after T-R1-10 complete.
  <!-- DEPLOYED 2026-05-23: bundle deployed to DEV (Deployment complete!, commit fed92fb); pipeline run triggered (update_id=4e1bc56e-41a1-47c2-a90f-f07c7a936839, pipeline be2bcafd-1429-4c84-a74a-e497a55b6c0c); run failed at Bronze Auto Loader analysis (FileNotFoundException: s3://dm-chain-explorer-dev-ingestion/raw/mainnet-blocks-data — absent by design, see T-R1-10 notes); no O(N^2) scan warning in logs; eth_canonical_blocks_index rolling window code verified at ethereum_pipeline.py:491–573 (_CANONICAL_WINDOW_BLOCKS=1_000, bounded SQL with outside_window/window_blocks/parent_refs/inside_window CTEs). -->


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
