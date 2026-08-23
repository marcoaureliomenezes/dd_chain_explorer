# Databricks lane — code vs live vs memory (dd-chain-explorer)

Date: 2026-08-23 · Auditor: project-auditor (databricks lane) · Mode: READ-ONLY
Repo: `repos/dd-chain-explorer` @ `c6feb17` (branch `feature/v0.4.0`, clean)
Workspace: Databricks Free Edition `dbc-409f1007-5779` · CLI v0.270.0 · user `<operator-email>` (admins)
Scratch evidence: `.dadaia/tmp/project-auditor/20260823/databricks/` (pipelines/jobs/dashboards JSON, tfstates, validate outputs, remote notebooks)

Commands used: `pipelines list/get/list-updates/list-pipeline-events`, `jobs list/get/list-runs`, `lakeview list/get/get-published`, `alerts list`, `queries list`, `genie list-spaces/get-space`, `warehouses list/get`, `catalogs/schemas/tables list`, `external-locations list`, `storage-credentials list`, `workspace list/get-status/export`, `bundle validate -t {dev,hml,prod}` (all 15 bundles), `bundle schema`, `aws s3 ls / head-bucket` (buckets referenced by bundles), two `POST /api/2.0/sql/statements` attempts (refused — see §2.5). No deploy/run/update/delete issued.

> Side-effect note: `workspace export` of the two never-before-exported **hml** notebooks bumped their `modified_at` to 2026-08-23T14:51Z (server-side lazy materialisation). Content verified unchanged (old versions, see §3.4). No other live object was touched.

---

## 0. TL;DR

1. **Nothing has run since April.** 0 job runs in the 60-day run history (18 jobs), 0 DLT updates/events on all 4 pipelines, every `dev` table `updated_at` = **2026-04-28**; `hml` catalog has **no schemas at all** (only `default`). S3 sources for every target are empty (`dev-ingestion`, `raw-data`) or non-existent (all three `hml-*` buckets); only stray PRD Firehose app-logs (last 2026-05-23) sit in `dm-chain-explorer-lakehouse/raw/app_logs/`.
2. **The fixes of pipeline-restart-r1/r5 (05-22/23) were only partially deployed:** `[dev] dm-ethereum` notebook == repo; **hml `dm-ethereum` is the pre-R1 code** (no bounded canonical window, `from_address` still `expect`); **`dm-app-logs` in BOTH targets still runs the CloudWatch `binaryFile` UDF reader** — the Fluent-Bit NDJSON reader (T-R5-WP0-02) was never deployed. When the VPS starts delivering `raw/app_logs/*.json`, the live pipeline cannot parse it.
3. **Three bundles are no-ops on the CLI in use:** `resources.alerts`, `resources.queries`, `resources.genie_spaces` are *unknown fields* for CLI 0.270 (and CI's pinned 0.218) → `alert_api_keys`, `alert_dynamodb_deadlock`, `genie_ethereum` validate OK but declare **zero resources** (remote tfstates have 0 resources; live: 0 alerts, only an unrelated "New Space" Genie). The pipeline `schedule:` block is also unknown → silently dropped (live pipelines have no schedule; the "prod UNPAUSED" design is dead).
4. **Broken-as-deployed jobs:** `dm-trigger-all-dlts` (dev+hml) and `dm-dlt-full-refresh` (hml) have **empty `pipeline_id`** tasks (deployed with `--var` defaults `""`); `dm-reconcile-orphan-blocks` (dev+hml) points at notebook `src/batch/reconcile_orphan_blocks` that **does not exist** in the repo (deleted 2026-05-22) nor in the workspace; `dm-dlt-full-refresh` references a wheel path that is not uploaded in either target.
5. **prod target is not guarded:** `host: ""` falls back to the DEFAULT profile → `bundle validate -t prod` passes for all 15 bundles and a `deploy -t prod` would land `prd`-catalog resources on the Free Edition workspace (catalog `prd` does not exist).
6. **Dashboards hard-code `dev.` catalog** in every dataset SQL (4 bundles) → hml/prod deploys would still query `dev`. Live dashboards are published with `embed_credentials=true` while bundles say `false`.
7. **hml bucket/external-location mismatch:** bundles use `dm-chain-explorer-hml-raw` (dlt_ethereum) and `dm-chain-explorer-hml-lakehouse` (everything else); the only hml external location is `dm-hml-ingestion → s3://dm-chain-explorer-hml-ingestion/`; none of the three buckets exists.
8. Memory (`data-catalog`, `medallion-pipelines`, `serving-layer`, `tech-stack`) is stale on ~20 claims (§6): 30 vs 29 objects (`popular_contracts_txs` still documented — carried over from the 06-11 audit, never fixed), Firehose/CloudWatch/Kinesis sources, `raw-data` bucket, PRD catalog `dd_chain_explorer`, DBR 15.x, 5-min trigger, alert "validated", DEV/HML PAT auth, etc.

---

## 1. Bundle inventory (repo `apps/dabs/`, 15 bundles, 90 tracked files)

Common to all 15 `databricks.yml`: targets `dev` (`presets.name_prefix "[dev] "`, host hard-coded `https://dbc-409f1007-5779…`, `root_path ~/.bundle/<name>/dev`), `hml` (`"[hml] "`, same host, `~/.bundle/<name>/hml`), `prod` (`mode: production`, `host: ""`, `/Workspace/.bundle/<name>/prod`, `run_as <operator-email>` on 11 of 15 — the two DLT bundles and the two dashboards… see table). **No `permissions:` block in any bundle. No classic cluster anywhere: DLT `serverless: true`; jobs use serverless `environments` (`client: "1"/"2"`) — so "DBR 15.x LTS" (tech-stack) does not apply to anything.** VERSION = `1.0.0` in all 15; 15 git tags `dabs/<name>-v1.0.0` exist → `deploy_all.sh`/`check_versions.sh` would **SKIP every component** (exit 2 "nothing to deploy").

| Bundle | Resources declared | catalog dev/hml/prod | S3 bucket var dev/hml/prod | Schedule / trigger (pause) | Compute & libs | Entry files exist? | validate dev / hml / prod |
|---|---|---|---|---|---|---|---|
| `dlt_ethereum` | pipeline `dm-ethereum` (target `b_ethereum`, channel CURRENT, `development` dev=true/hml,prod=false, continuous=false); job `dm-trigger-ethereum` (pipeline_task) | dev/hml/prd | dev-ingestion / **hml-raw** / lakehouse | pipeline `schedule` `0 0/3 * * * ?` SP PAUSED (prod UNPAUSED) → **unknown field, dropped**; job dev override cron `0 */5` UTC PAUSED | serverless; notebook `src/streaming/ethereum_pipeline.py` (1,519 l.) | yes | OK(3 warn) / OK(3 warn) / OK(3 warn) — warnings: `schedule` ×2, `description` unknown |
| `dlt_app_logs` | pipeline `dm-app-logs` (target `b_app_logs`); job `dm-trigger-app-logs` | dev/hml/prd | dev-ingestion / **hml-lakehouse** / lakehouse | pipeline `schedule 0 2/3` PAUSED → dropped; job none | serverless; notebook `src/streaming/app_logs_pipeline.py` (337 l.) | yes | OK(3 warn) ×3 |
| `job_ddl_setup` | jobs `dm-ddl-setup`, `dm-check-tables` (python_wheel, artifact whl `./src`) | dev/hml/prd | dev-ingestion / hml-lakehouse / lakehouse | none | serverless env client 2; whl `dd_chain_explorer-0.1.0` | yes (`src/dd_chain_explorer/{ddl,check}`) | OK ×3 |
| `job_delta_maintenance` | job `dm-dm-delta-maintenance` (5 whl tasks optimize_bronze→silver→gold→vacuum→monitor) | dev/hml/prd | – | `0 0 4,16 * * ?` SP **PAUSED** | serverless client 2; whl `dm_delta_maintenance-0.1.0` | yes | OK ×3 |
| `job_export_gold` | job `dm-dm-export-gold` (whl) | dev/hml/prd | dev-ingestion / hml-lakehouse / **prd-lakehouse** (only bundle using that name) | none | serverless client 2; whl `dm_export_gold-0.1.0` | yes | OK ×3 |
| `job_full_refresh` | job `dm-dlt-full-refresh` (2 pipeline_task via `${var.pipeline_*_id}` default `""` + whl task) | dev/hml/prd | dev-ingestion / hml-lakehouse / lakehouse | none | env `serverless` dep `${workspace.file_path}/dm_export_gold-0.1.0-py3-none-any.whl`; artifact path `./src/batch/dm_export_gold` | **NO** — `job_full_refresh/src/` does not exist; whl never built/uploaded | OK ×3 (needs `--var pipeline_ethereum_id/app_logs_id`) |
| `job_reconcile_orphans` | job `dm-reconcile-orphan-blocks` (notebook_task `${workspace.file_path}/src/batch/reconcile_orphan_blocks`, client 1) | dev/hml/prd | dev-ingestion / hml-lakehouse / lakehouse | `0 0 3 * * ?` SP **UNPAUSED** | serverless | **NO** — no `src/` in bundle; file deleted in `67f8faf` (2026-05-22) | OK ×3 (validate does not check notebook existence) |
| `job_trigger_all` | job `dm-trigger-all-dlts` (2 pipeline_task via vars default `""`) | – | – | base `0 0 * * * ?` SP PAUSED; dev override `0 */5` UTC PAUSED | – | n/a | OK ×3 (needs `--var`s) |
| `dashboard_network_overview` | dashboard `Network Overview` (`parent_path /Shared/dd-chain-explorer/dashboards`, `embed_credentials false`, `warehouse_id a2a66f2adb0faf18`) + **stray** `resources/dev_network_overview.dashboard.yml` (not in `include`, generated file, hard-coded warehouse) | – | – | – | – | yes (`01_network_overview.lvdash.json`, + unreferenced `src/dev_network_overview.lvdash.json`) | OK ×3 |
| `dashboard_gas_analytics` / `_hot_contracts` / `_api_health` | 1 dashboard each, same shape | – | – | – | – | yes | OK ×3 |
| `alert_api_keys` | `queries.q_api_keys_error_rate` + `alerts.alert_api_keys_error_rate` (warehouse_id default `""`) | dev/hml/prd | – | – | – | n/a | OK ×3 but **`unknown field: queries/alerts` → 0 resources** |
| `alert_dynamodb_deadlock` | `queries` + `alerts` on `s_logs.logs_streaming` | dev/hml/prd | – | – | – | n/a | OK ×3, **0 resources** |
| `genie_ethereum` | `genie_spaces.ethereum_explorer` (7 tables) | dev/hml/prd | – | – | – | n/a | OK ×3, **`unknown field: genie_spaces` → 0 resources** |

`bundle schema` (CLI 0.270.0) resource types: apps, clusters, dashboards, database_*, experiments, jobs, model_serving_endpoints, models, pipelines, quality_monitors, registered_models, schemas, secret_scopes, sql_warehouses, synced_database_tables, volumes. Pipeline fields include `trigger` (not `schedule`) and no `description`.

prod: `validate -t prod` returns rc=0 for all 15 (resolved `host: null`, user resolved through the DEFAULT profile, root `/Workspace/.bundle/<name>/prod`, catalog `prd`). It does **not** fail — the "undeployable" assumption of the 08-19 recap is wrong in practice.

Docs: `apps/dabs/README.md` describes the **pre-04-05 monolithic bundle** (root `databricks.yml`, `workflow_maintenance.yml`, `dm-iceberg-maintenance`, `dm-batch-contracts`, `4_pipeline_ethereum.py`, catalog prod `dd_chain_explorer`, "CloudWatch → Firehose") — none of it exists. CI (`deploy_all_dm_applications.yml`) validates only `dlt_ethereum` (setup-cli v0.218.0) and later runs `databricks bundle run --target hml dm-trigger-all-dlts` from `$GITHUB_WORKSPACE` where no `databricks.yml` exists; last CI run 2026-04-09. Untracked but present locally: nested `build/lib/…/build/lib` recursion in `job_delta_maintenance` / `job_export_gold` (`packages.find where=[".."]`) — gitignored slop.

---

## 2. Live inventory

### 2.1 DLT pipelines (4)
| Pipeline id | Name | State | Updates / events | catalog.target | serverless / dev mode / channel | config | Notebook deployed | last_modified |
|---|---|---|---|---|---|---|---|---|
| `be2bcafd…` | `[dev] dm-ethereum` | IDLE | **none returned** | dev.b_ethereum | yes / true / CURRENT | bucket dev-ingestion, catalog dev, s3.export.path | == repo (file modified 2026-05-22T19:53Z) | 2026-04-05 |
| `61451730…` | `[dev] dm-app-logs` | IDLE | none | dev.b_app_logs | yes / true | bucket dev-ingestion | **OLD CloudWatch binaryFile UDF** (file 2026-04-05) | 2026-04-05 |
| `96390da7…` | `dm-ethereum` (hml) | IDLE | none | hml.b_ethereum | yes / null | bucket **hml-lakehouse** (bundle now says hml-raw), catalog hml | **pre-R1 code** (1,451 l.; `@dlt.expect("valid_from_address")`, no `_CANONICAL_WINDOW_BLOCKS`) | 2026-04-09 |
| `81004e2c…` | `dm-app-logs` (hml) | IDLE | none | hml.b_app_logs | yes / null | bucket hml-lakehouse | OLD CloudWatch UDF | 2026-04-09 |
No `schedule`/`trigger` on any pipeline. No tags on hml pipelines. Edition ADVANCED, photon null, `run_as` the operator.

### 2.2 Jobs (18 — 9 `[dev]`, 9 unprefixed=hml; all `deployment.kind=BUNDLE`, `UI_LOCKED`)
| Job | Schedule (pause) | Tasks | Runs (60-day history / last 30 d) | Notes |
|---|---|---|---|---|
| `[dev] dm-trigger-ethereum` | `0 */5 * * * ?` UTC PAUSED | pipeline be2bcafd | 0 / 0 | ok |
| `[dev] dm-trigger-app-logs` | none | pipeline 61451730 | 0 / 0 | ok |
| `[dev] dm-trigger-all-dlts` | `0 */5` UTC PAUSED | **2 pipeline tasks with empty pipeline_id** | 0 / 0 | broken |
| `[dev] dm-dlt-full-refresh` | none | pipelines set; whl dep `files/../job_export_gold/src/batch/dm_export_gold/dist/…whl` (path outside bundle root, not present) | 0 / 0 | broken |
| `[dev] dm-reconcile-orphan-blocks` | `0 0 3 * * ?` SP **PAUSED** (bundle: UNPAUSED) | notebook `…/dev/files/src/batch/reconcile_orphan_blocks` **absent** | 0 / 0 | broken |
| `[dev] dm-dm-export-gold` | none | whl export `s3://dm-chain-explorer-dev-ingestion/exports` | 0 / 0 | |
| `[dev] dm-dm-delta-maintenance` | `0 0 4,16` SP PAUSED | 5 whl tasks | 0 / 0 | OPTIMIZE/VACUUM on DLT ST/MV (see §4) |
| `[dev] dm-ddl-setup` / `[dev] dm-check-tables` | none | whl | 0 / 0 | |
| `dm-trigger-ethereum` / `dm-trigger-app-logs` (hml) | none | pipelines 96390da7 / 81004e2c | 0 / 0 | |
| `dm-trigger-all-dlts` (hml) | `0 0 * * * ?` SP PAUSED | **empty pipeline_ids** | 0 / 0 | broken |
| `dm-dlt-full-refresh` (hml) | none | **empty pipeline_ids** + whl `…/hml/files/dm_export_gold-0.1.0-py3-none-any.whl` **absent** | 0 / 0 | broken |
| `dm-reconcile-orphan-blocks` (hml) | `0 0 3` SP PAUSED | notebook absent | 0 / 0 | broken |
| `dm-dm-export-gold` / `dm-dm-delta-maintenance` (PAUSED) / `dm-ddl-setup` / `dm-check-tables` (hml) | as bundle | catalog hml, bucket hml-lakehouse | 0 / 0 | hml catalog has no schemas → would fail |
`jobs list-runs` (global, 60-day retention) → `[]`.

### 2.3 Lakeview dashboards (5)
| Dashboard | State | Created / updated | Published | Warehouse | Datasets → tables |
|---|---|---|---|---|---|
| `[dev] Network Overview` | ACTIVE | 2026-04-05 / 2026-05-23T02:23Z | yes, **embed_credentials=true** (rev 05-23) | a2a66f2adb0faf18 | `dev.g_network.{network_metrics_hourly,block_production_health}` |
| `[dev] Gas Analytics` | ACTIVE | 04-05 / 05-23T02:40Z | yes, embed=true | same | `dev.g_apps.{ethereum_gas_consume,gas_price_distribution_hourly}` |
| `[dev] Hot Contracts` | ACTIVE | 04-05 / 05-23T02:40Z | yes, embed=true | same | `dev.g_apps.popular_contracts_ranking` |
| `[dev] API Health` | ACTIVE | 04-05 / 05-23T02:40Z | yes, embed=true | same | `dev.g_api_keys.{etherscan_consumption,web3_keys_consumption}` |
| `Workspace Usage Dashboard` | ACTIVE | 2025-09-04 / 2025-09-24 | no | same | orphan (Databricks sample, `/Users/...`) |
No `[hml]`/unprefixed project dashboards (remote hml tfstates: 0 resources).

### 2.4 Alerts / queries / Genie
- `alerts list` → **0**; `alerts-legacy list` → 0.
- `queries list` → 7 ad-hoc/orphan queries (`01_explore_bronze`, `02_explore_silver`, `03_explore_gold`, "New Query …" ×3, "Example Hosted Function") — none from bundles.
- Genie: 1 space `New Space` (`01f09a47…`) — not "Ethereum Explorer"; orphan.

### 2.5 SQL warehouses / compute / cost
- 1 warehouse: `Serverless Starter Warehouse` (`a2a66f2adb0faf18`) PRO, serverless, 2X-Small, auto-stop 10 min, **STOPPED**. Two `POST /sql/statements` (`SELECT 1`, then a 29-table COUNT union) were refused with "The request could not be processed by the warehouse" and the warehouse stayed STOPPED → **row counts not obtained**; I did not issue `warehouses start`. This itself is a Free-Edition signal (warehouse not auto-starting from the Statements API).
- `clusters list` → none; `instance-profiles` → none; `secrets list-scopes` → none. Entitlements `allow-cluster-create` present but no classic compute exists.
- Billing/DBU: no account-level or `system.billing` access possible without a running warehouse → **not available** (expected on Free Edition).

### 2.6 Unity Catalog
Catalogs: `dev` (MANAGED, 2025-12-31), `hml` (MANAGED, 2026-03-22), `workspace`, `samples`, `system`, 2 Delta-Sharing marketplace catalogs (`bright_data_…`, `dataplatr_…` — orphans). **No `prd`/`dd_chain_explorer` catalog.**
- `dev`: 7 project schemas (`b_ethereum`, `b_app_logs`, `s_apps`, `s_logs`, `g_apps`, `g_network`, `g_api_keys`, created 04-04/05) → **29 objects**: 12 STREAMING_TABLE + 17 MATERIALIZED_VIEW, all owned by pipelines `be2bcafd`/`61451730`; every `updated_at` = **2026-04-28T10:0x** (ethereum tables 10:01–10:03, app-logs 10:04). Full list: `b_ethereum{eth_mined_blocks,eth_transactions,eth_txs_input_decoded}`, `b_app_logs{b_app_logs_data}`, `s_apps{eth_blocks,eth_blocks_withdrawals,eth_transactions_staging,txs_inputs_decoded_fast,transactions_ethereum,eth_canonical_blocks_index(MV)}`, `s_logs{logs_streaming,logs_batch}`, `g_apps{popular_contracts_ranking,peer_to_peer_txs,ethereum_gas_consume,transactions_lambda,gas_price_distribution_hourly,p2p_transfer_metrics_hourly,contract_method_activity,contract_deploy_metrics_hourly,contract_volume_ranking}`, `g_network{network_metrics_hourly,eth_burn_hourly,validator_activity,withdrawal_metrics,block_production_health,chain_health_metrics}`, `g_api_keys{etherscan_consumption,web3_keys_consumption}`.
- `hml`: only `default` + `information_schema` → **0 project tables** (DDL/pipelines never ran in hml).
- External locations: `dm-dev-ingestion → s3://dm-chain-explorer-dev-ingestion/` (cred `dm-dev-s3-credential`), `dm-hml-ingestion → s3://dm-chain-explorer-hml-ingestion/` (same cred; **bucket does not exist**), plus managed. Storage credentials: `dm-dev-s3-credential` (role `dm-databricks-dev-s3-role`), `de-lakehouse-credential` (role `de-coding-interview-…` — **orphan from another project**).
- S3 (aws cli, read-only): `dm-chain-explorer-dev-ingestion` exists, **`raw/` empty**; `dm-chain-explorer-raw-data` exists, **empty**; `dm-chain-explorer-lakehouse` exists with only `raw/app_logs/year=2026/month=05/day=23/hour=16/firehose-app-logs-prd-…gz` (last object 2026-05-23T16:21Z); `hml-ingestion`, `hml-lakehouse`, `hml-raw` → **NoSuchBucket**.

### 2.7 Workspace `.bundle/` roots (`/Users/<operator-email>/.bundle/`)
16 dirs: the 15 current bundles (each with `dev/` and `hml/` → `state/`, `files/`, `artifacts/`) + **orphan `dd-chain-explorer/`** (the pre-04-05 monolithic bundle; remote tfstate serial 220 (dev) / 27 (hml) still lists 13/8 resources — 4 dashboards `01f1206a…`, jobs `workflow_batch_contracts`, `workflow_maintenance`, pipelines `79212b6d…`/`5043f160…` — **none of which exist live**: stale state, resources deleted out-of-band). Remote tfstates for `genie-ethereum`, `alert-api-keys`, `alert-dynamodb-deadlock`, `dashboard-*` **hml** = serial 1, 0 resources; their `dev` dirs have no tfstate (genie/alerts) . Local `.databricks/bundle/*/terraform/terraform.tfstate` match remote for the 12 deployed bundles.

---

## 3. Drift matrix

### 3.1 Bundle resource → live
| Bundle resource | dev live | hml live | Name match | Config match | Notes |
|---|---|---|---|---|---|
| dlt_ethereum / pipeline `dm-ethereum` | ✔ `[dev] dm-ethereum` | ✔ `dm-ethereum` (no `[hml]` prefix — deployed before preset) | dev ✔ / hml ✗ prefix | dev: code ✔, schedule dropped; hml: **code stale (pre-R1)**, bucket `hml-lakehouse` ≠ bundle `hml-raw`, no tags | a redeploy would rename hml → `[hml] dm-ethereum` |
| dlt_ethereum / job `dm-trigger-ethereum` | ✔ (cron 5-min PAUSED) | ✔ (no schedule) | as above | ✔ | |
| dlt_app_logs / pipeline `dm-app-logs` | ✔ | ✔ | dev ✔ / hml ✗ prefix | **code stale in both** (CloudWatch UDF vs Fluent Bit NDJSON) | |
| dlt_app_logs / job `dm-trigger-app-logs` | ✔ | ✔ | | ✔ | |
| job_ddl_setup / `dm-ddl-setup`, `dm-check-tables` | ✔ | ✔ | | ✔ | |
| job_delta_maintenance / `dm-dm-delta-maintenance` | ✔ PAUSED | ✔ PAUSED | | ✔ | |
| job_export_gold / `dm-dm-export-gold` | ✔ | ✔ | | ✔ | |
| job_full_refresh / `dm-dlt-full-refresh` | ✔ | ✔ | | dev: pipeline ids set, whl path bogus; hml: **pipeline ids empty**, whl absent | |
| job_reconcile_orphans / `dm-reconcile-orphan-blocks` | ✔ **PAUSED** | ✔ **PAUSED** | | bundle says **UNPAUSED**; notebook missing everywhere | paused out-of-band (or never unpaused) |
| job_trigger_all / `dm-trigger-all-dlts` | ✔ PAUSED | ✔ PAUSED | | **pipeline ids empty in both** | |
| dashboard_* (4) | ✔ `[dev] …` ×4 ACTIVE | ✗ none (hml state 0 res) | ✔ | `embed_credentials` live true vs bundle false; SQL hard-codes `dev.` | `dashboard_network_overview` extra `dev_network_overview.dashboard.yml` is not included (no effect) |
| alert_api_keys / alert_dynamodb_deadlock (query+alert) | ✗ never (unknown resource type) | ✗ | – | – | memory claims "DEV validated" |
| genie_ethereum | ✗ never | ✗ | – | – | live "New Space" is unrelated |

### 3.2 Live assets not in any bundle (orphans)
`Workspace Usage Dashboard`; Genie `New Space`; 7 ad-hoc queries; `.bundle/dd-chain-explorer/{dev,hml}` dirs with stale state; storage credential `de-lakehouse-credential`; external location `dm-hml-ingestion` (bucket gone); Delta-Sharing catalogs `bright_data_…`, `dataplatr_…`; catalog `hml` (empty shell).

### 3.3 Bundle resources never deployed
`alert_api_keys`, `alert_dynamodb_deadlock`, `genie_ethereum` (all targets); all four `dashboard_*` for hml; everything for prod.

### 3.4 Memory `data-catalog.md` (30 objects / 7 schemas) vs live `dev`
- Live = **29** (12 ST + 17 MV). Missing vs memory: `b_ethereum.popular_contracts_txs` (no DLT table, no DDL, nothing produces it) — **same DRIFT-N01/N04 already reported 2026-06-11, still in memory**. Memory summary table also says s_apps "5 ST + 1 MV = 6" ✔, g_apps 9 ✔, g_network 6 ✔, g_api_keys 2 ✔, s_logs 2 ✔, b_app_logs 1 ✔, b_ethereum 4 ✗ (3).
- No renamed tables. Extra live: none. hml: 0 of 29 exist. `prd`/`dd_chain_explorer`: catalog does not exist.
- Source prefixes: memory `raw/mainnet-mined-blocks-data/` vs code `raw/mainnet-blocks-data/`; memory `b_app_logs_data` = "CloudWatch double-gzip binaryFile" vs repo Fluent-Bit NDJSON (but **live** is still binaryFile — memory accidentally matches the stale deployment, not the code).
- `medallion-pipelines`: "triggered every 5 minutes by dm-trigger-all-dlts" — live trigger jobs are PAUSED and have **no pipeline ids**; "CloudWatch application logs" stale; "dm-chain-explorer-raw-data/raw/ (Firehose delivery)" — bucket empty, Firehose destroyed (v0.4.0).

---

## 4. Code health — DLT & jobs

**`dlt_ethereum/src/streaming/ethereum_pipeline.py`** (1,519 l., 24 `@dlt.table`: 3 bronze ST, 6 silver (5 ST + 1 MV), 15 gold MV)
- Expectations: **11** (`expect_or_drop` ×9: blocks `valid_block_number`,`valid_hash`; staging `valid_hash`,`valid_block`,`valid_from_address`; decoded ×2; transactions_ethereum ×2; `expect` ×2: `valid_to_address`, +1). Only Silver has rules; Bronze and Gold have none.
- Sources: Auto Loader `cloudFiles.format=json`, `inferColumnTypes=true`, `partitionColumns=""`, `schemaLocation s3://<bucket>/checkpoints/schemas/<stream>`; paths `s3://${ingestion.s3.bucket}/raw/{mainnet-blocks-data,mainnet-transactions-data,mainnet-transactions-decoded}/`. Schema hints only on `mainnet-transactions-decoded` (`tx_hash, contract_address, method, parms, method_id, decode_type, decode_source, decode_confidence`); blocks/txs rely on inference of web3-style camelCase keys (`number,hash,parentHash,timestamp,miner,…,withdrawals` / `hash,blockNumber,blockHash,from,to,gas,gasPrice,input,nonce,r,s,v,type,accessList,transactionIndex,value`).
- Post-retirement contract (capture-decoupling-r5 SPEC, `dd-chain-capture` not in this workspace): Kafka-Connect S3 sink, `JsonFormat`/`schemas.enable=false` NDJSON, `path.format 'year'=YYYY/'month'=MM/'day'=dd/'hour'=HH`, same three prefixes → **prefixes and format compatible**; `partitionColumns=""` correctly ignores Hive dirs. **Unverified risk:** Avro→JSON field names must stay camelCase exactly as above (any snake_case change breaks silently via schema inference → nulls → `expect_or_drop` drops everything). No retired Kinesis/SQS/Firehose API usage in code — only comments/table `comment`s still say "Firehose"/"Kinesis" (cosmetic, 6 places).
- Hard-coded defaults: `ingestion.s3.bucket` fallback `dm-chain-explorer-dev-ingestion`, `catalog` fallback `dev`. Pipeline config `s3.export.path` is **unused** by the notebook (dead config). `_CANONICAL_WINDOW_BLOCKS = 1_000` (bounded window present in repo & dev, absent in hml).
- Silver `eth_canonical_blocks_index` uses `spark.sql` over `{CATALOG}.s_apps.eth_blocks` (reads the UC table directly instead of `dlt.read`) — creates an implicit external dependency on the catalog name; fine for serverless DLT but invisible to the DLT graph.

**`dlt_app_logs/src/streaming/app_logs_pipeline.py`** (337 l., 5 tables: 1 bronze ST, 2 silver ST, 2 gold MV): 4 expectations (`expect_or_drop valid_level/valid_message` ×2). Source `raw/app_logs/` via Fluent Bit NDJSON, explicit schema `timestamp LONG, logger, level, filename, function_name, message`, schemaLocation `…/checkpoints/schemas/app_logs_v2`. Matches the r5 contract (`raw/app_logs/year=…/*.ndjson`). Caveat: the only logs physically in S3 today are PRD Firehose `.gz` CloudWatch envelopes in the **lakehouse** bucket — neither format nor bucket matches; new reader would read nothing.

**Jobs**
- `job_ddl_setup/setup_ddl.py` (748 l.): `CREATE TABLE IF NOT EXISTS` for the same 29 names the DLT pipelines own (+ pre-creating MVs as plain tables). DLT serverless/UC refuses to take over a pre-existing non-pipeline table with the same name → running `dm-ddl-setup` **before** the pipelines (as its docstring mandates) would make the pipeline fail; it has never been run in either target (dev tables are all pipeline-owned). Design conflict.
- `job_delta_maintenance`: `OPTIMIZE … ZORDER BY`, `VACUUM … RETAIN` over the 29 DLT-owned ST/MV — not supported on UC streaming tables / materialized views (maintenance is pipeline-managed). Entry-point names inconsistent (`dm-delta-maintenance-optimize-bronze` vs `dm_delta_maintenance-*`). Never run.
- `job_export_gold`: exports `g_api_keys.*` to `s3://<bucket>/exports/` for the `gold_to_dynamodb` Lambda — downstream consumer belongs to the retired/partly-destroyed AWS lane (08-19 recap: legacy dev Lambda orphan).
- `job_reconcile_orphans`: notebook removed 2026-05-22, bundle left dangling; schedule UNPAUSED in bundle (live PAUSED) with `ethereum_rpc_url` default `""`.
- `job_full_refresh`/`job_trigger_all`: require `--var pipeline_*_id`; deployed with empty ids; `job_full_refresh` declares an artifact path that does not exist in its own dir.
- Dead notebooks not referenced by any bundle: `dashboard_network_overview/src/dev_network_overview.lvdash.json` (+ its un-included yml). No stray `.py` notebooks in repo (old `apps/dabs/src/` tree removed; only untracked egg-info/dist residue).
- Hard-coded ids/hosts: workspace host in all 15 `databricks.yml` (×2-3 each), warehouse id `a2a66f2adb0faf18` in 7 files, operator e-mail `run_as` in 11 files.

---

## 5. Findings

| ID | Sev | Area | Finding | Evidence | Recommendation |
|---|---|---|---|---|---|
| DBX-01 | HIGH | deploy drift | `dm-app-logs` deployed notebook (dev **and** hml) is the CloudWatch `binaryFile` UDF version; Fluent-Bit NDJSON reader (`d727d54`, 2026-05-23) never deployed | `workspace export …/dlt-app-logs/{dev,hml}/files/src/streaming/app_logs_pipeline` = 418 l. with `cloudFiles.format binaryFile`; repo 337 l.; dev file modified 2026-04-05 | redeploy `dlt_app_logs` to dev (and hml once hml has a real bucket) before any VPS delivery test |
| DBX-02 | HIGH | deploy drift | hml `dm-ethereum` is pre-R1 code: unbounded O(N²) canonical index, `from_address` `expect` not `expect_or_drop`; hml bucket config ≠ bundle (`hml-lakehouse` vs `hml-raw`) | remote notebook 1,451 l. vs repo 1,519; `pipelines get 96390da7` conf; `444a814` | decide hml's fate (destroy or redeploy with a real bucket + external location) |
| DBX-03 | HIGH | bundle no-op | `alert_api_keys`, `alert_dynamodb_deadlock`, `genie_ethereum` declare resource types unknown to CLI 0.270 (`queries`,`alerts`,`genie_spaces`) → validate OK with 0 resources; never deployed; memory says alert "DEV validated SUCCEEDED" | validate warnings; remote tfstate serial 1 / 0 resources; `alerts list` = []; Genie = "New Space" | either upgrade CLI to a version that supports `alerts`/`queries` (and drop Genie from DABs — no DABs resource exists) or manage them by script; fix memory |
| DBX-04 | HIGH | broken jobs | `dm-trigger-all-dlts` (dev+hml) & `dm-dlt-full-refresh` (hml) deployed with empty `pipeline_id`; `dm-reconcile-orphan-blocks` (dev+hml) notebook missing (repo+workspace); `dm-dlt-full-refresh` wheel path absent in both | `jobs get` tasks; `workspace list …/files`; `git log 67f8faf` | make pipeline ids resolvable (lookup `${resources…}` via a combined bundle or `lookup:` vars); delete or restore `job_reconcile_orphans`; fix `job_full_refresh` artifact |
| DBX-05 | HIGH | memory | `data-catalog`/`medallion-pipelines` still document `b_ethereum.popular_contracts_txs` (30 objects) — 29 live/in code; same DRIFT-N01..N04 from the 06-11 audit, dispositioned nowhere | `tables list dev b_ethereum` = 3; `ethereum_pipeline.py` 24 tables | product-engineer rewrite (CLOSURE/DEFINITION phase) |
| DBX-06 | MED | prod guard | `host: ""` on prod falls back to DEFAULT profile; `validate -t prod` passes ×15; `deploy -t prod` would create `prd`-catalog assets on Free Edition | validate prod JSON: host null, root `/Workspace/.bundle/<name>/prod` | set an explicit sentinel host or `DATABRICKS_HOST` requirement / remove prod target until a PRD workspace exists |
| DBX-07 | MED | dashboards | Dataset SQL hard-codes `dev.` catalog in all 4 dashboards → hml/prod deploys query dev; live published `embed_credentials=true` vs bundle `false` (T-R1-05 regressed or republished by hand) | `lvdash.json` greps; `lakeview get-published` | parametrize catalog (dashboard parameters or per-target lvdash), republish with embed false |
| DBX-08 | MED | S3/UC | hml buckets referenced by bundles (`hml-raw`, `hml-lakehouse`) and by the only hml external location (`hml-ingestion`) do **not exist**; hml catalog empty; inconsistent bucket names across hml bundles | `aws s3api head-bucket` NoSuchBucket ×3; `schemas list hml` | pick one hml bucket name (or drop hml target) and align external location |
| DBX-09 | MED | silent drop | DLT `schedule:` in both pipeline ymls (and prod `UNPAUSED` override) is an unknown field → no pipeline schedule anywhere; prod "automatic schedule" promise in DEPLOYMENT_GUIDE is void | validate warnings; `pipelines get` schedule null | use `trigger:` / job-based scheduling deliberately; update guide |
| DBX-10 | MED | idle platform | 0 job runs (60 d), 0 DLT updates/events, all 29 dev tables last written 2026-04-28; sources empty since 05-23; all trigger jobs PAUSED | §2 | expected under v0.4.0 capture retirement — record as known state; re-validate once VPS delivers |
| DBX-11 | MED | design conflict | `job_ddl_setup` pre-creates the 29 DLT-owned tables as plain Delta tables; `job_delta_maintenance` runs OPTIMIZE/VACUUM on ST/MVs — both unsupported with UC DLT | `setup_ddl.py` docstring/DDL list; `vacuum.py`/`optimize_*.py` | retire or scope these jobs to non-DLT tables |
| DBX-12 | LOW | docs | `apps/dabs/README.md` describes the removed monolithic bundle (`dm-iceberg-maintenance`, `dm-batch-contracts`, `4_pipeline_ethereum.py`, prod catalog `dd_chain_explorer`); CI validates only `dlt_ethereum` with setup-cli 0.218 and `bundle run` from repo root (no `databricks.yml`) | README lines 9-38, 44-48, 74-84; workflow lines 213-229, 621 | rewrite README; fix CI job dirs |
| DBX-13 | LOW | hygiene | Orphans: `.bundle/dd-chain-explorer/{dev,hml}` with stale remote state (13/8 resources that no longer exist); `Workspace Usage Dashboard`; Genie `New Space`; 7 ad-hoc queries; `de-lakehouse-credential`; 2 Delta-Sharing catalogs; stray `dev_network_overview.dashboard.yml`/`.lvdash.json` | §2.7, §3.2 | clean up after operator confirmation |
| DBX-14 | LOW | config | `s3.export.path` pipeline config unused; `deploy_all.sh` would SKIP all 15 components (tags `…-v1.0.0` exist while code changed); warehouse id/host/e-mail hard-coded | §1 | bump VERSIONs or drop tag-skip; `lookup:` for warehouse |
| DBX-15 | LOW | Free Edition | Serverless warehouse STOPPED and Statements API refuses (`could not be processed by the warehouse`) → dashboards/Genie/alerts cannot execute until it starts; no clusters, no instance profiles | §2.5 | note as environment limit; verify warehouse starts from UI before demo |

---

## 6. Delta vs 2026-08-19 recap

| 08-19 claim | 08-23 re-verification |
|---|---|
| All on Free Edition `dbc-409f1007-5779`; `[dev]` = dev target/catalog dev; unprefixed = hml target/catalog hml (pre-preset) | **Confirmed** (18 jobs 9+9, 4 pipelines 2+2; remote/local tfstates agree) |
| prod target `host: ""` → undeployable; PRD workspace does not exist | **Partly wrong**: no PRD workspace ✔, but `validate -t prod` passes for all 15 (DEFAULT profile fallback) — deploy would target Free Edition |
| 4 `[dev]` Lakeview dashboards ACTIVE | **Confirmed** (+ orphan Workspace Usage Dashboard); new: published with embed=true, SQL hard-codes `dev.` |
| DLT pipelines IDLE, trigger jobs PAUSED in both targets | **Confirmed**; new: 0 updates/events, 0 runs in 60 d, tables frozen at 2026-04-28; trigger-all jobs have empty pipeline ids |
| S3 raw empty since 2026-05-23 (app-logs delivered wrongly to lakehouse) | **Confirmed** (`dev-ingestion` and `raw-data` `raw/` empty; lakehouse has only Firehose app-logs 05-23) |
| — (new) | hml `dm-ethereum` stale pre-R1 code; `dm-app-logs` stale in both targets (DBX-01/02) |
| — (new) | alert/genie bundles are no-ops; pipeline schedules dropped (DBX-03/09) |
| — (new) | hml catalog has no schemas; hml buckets/external location don't exist (DBX-08) |
| — (new) | `.bundle/dd-chain-explorer` orphan with stale state; `de-lakehouse-credential` orphan |

---

## 7. Memory staleness list

| Claim | File:line | Reality (2026-08-23) |
|---|---|---|
| "30 tables/MVs across 7 schemas … 12 streaming tables and 18 MVs" | `specs/memory/product/data-catalog.md:5,23,156-165` | 29 live in dev (12 ST + 17 MV); `popular_contracts_txs` absent everywhere |
| `b_ethereum.popular_contracts_txs` STREAMING_TABLE from `raw/batch/` | `data-catalog.md:66`; `medallion-pipelines.md:38,69` | no definition, no DDL, no table |
| Bronze `eth_mined_blocks` source `raw/mainnet-mined-blocks-data/` "via SQS/Firehose"; txs "via Kinesis"; decoded "Firehose Direct Put" | `data-catalog.md:63-65` | code reads `raw/mainnet-blocks-data/`; Kinesis/Firehose/SQS destroyed (v0.4.0); contract is Kafka-Connect S3 sink |
| `b_app_logs_data` = "CloudWatch structured logs … double-gzip binaryFile" | `data-catalog.md:74`; `medallion-pipelines.md:6,24` | repo = Fluent Bit NDJSON (`d727d54`); live deployment still binaryFile (never redeployed) |
| "Catalog `dev` maps to `dd_chain_explorer` in PRD"; PRD catalog `dd_chain_explorer` | `data-catalog.md:21,45`; `medallion-pipelines.md:63`; `serving-layer.md:21,42`; `tech-stack.md:119-123` | bundles use `prd`; no PRD workspace/catalog exists |
| "S3 `dm-chain-explorer-raw-data` — read via Auto Loader"; "S3 raw data lands in dm-chain-explorer-raw-data/raw/ (Firehose delivery, hourly partitioned)" | `medallion-pipelines.md:28,61`; `data-catalog.md:46` | bucket empty; dev pipelines read `dm-chain-explorer-dev-ingestion` (also empty); hml buckets don't exist |
| "dm-trigger-all-dlts triggers both pipelines every 5 minutes (cron `0 */5 * * * ?`)" / "Used continuously" | `medallion-pipelines.md:6,29,53` | PAUSED in both targets, pipeline ids empty, 0 runs |
| "Alert `alert_dynamodb_deadlock` … DEV validated: SUCCEEDED, 0 deadlock_events" | `data-catalog.md:150` | 0 alerts live; bundle resource type unknown to CLI → never deployed |
| "MVs reflect historical data from last pipeline run (April 2026)" / "State validated 2026-05-23" | `data-catalog.md:6,104` | consistent (last write 2026-04-28) — but tables never refreshed after the R1 code change; `eth_canonical_blocks_index` bounded-window MV never materialised |
| Serving: "Genie AI/BI space … 7 Gold table FQNs"; "4 Lakeview dashboards"; dashboards query `dd_chain_explorer.g_*` in PRD | `serving-layer.md:5,6,21,27`; `tech-stack.md:114-115` | Genie space never deployed (orphan "New Space" only); 4 `[dev]` dashboards exist, SQL hard-codes `dev.` |
| `job_export_gold` → S3 PutObject → `gold_to_dynamodb` Lambda (PRD) | `serving-layer.md:28-30,45,50` | export job never run; PRD Lambda/Firehose lane destroyed (08-19 recap); only legacy dev Lambda orphan |
| "Runtime DBR 15.x LTS — DLT pipelines and cluster nodes" | `tech-stack.md:109` | everything serverless (DLT `serverless: true`, jobs `environments client 1/2`); no clusters exist |
| "Auto Loader: S3 JSON and binaryFile (CloudWatch Logs)" | `tech-stack.md:112` | binaryFile removed from code (still live — DBX-01) |
| "Unity Catalog enforced in PRD; DEV/HML use Free Edition" / "SQL Warehouses Serverless" | `tech-stack.md:110,113` | only Free Edition exists; single serverless warehouse, STOPPED and refusing statements |
| "DEV: PAT in `~/.databrickscfg [dev]`; HML PAT in GitHub Secrets; PRD OAuth M2M" | `tech-stack.md:129-131` | CLI uses profile `DEFAULT` (OAuth/valid); CI secrets `DATABRICKS_HML_HOST/TOKEN` target the same Free Edition workspace |
| `capture-layer`: "Firehose `firehose-mainnet-blocks-data[-dev]` → S3 raw/…" | `capture-layer.md:56-58` | Firehose destroyed; delivery contract is Kafka-Connect from VPS (`dd-chain-capture`, not yet delivering) |
| `apps/dabs/README.md` structure/targets/workflows (monolithic bundle, `dm-iceberg-maintenance`, `dm-batch-contracts`, prod catalog `dd_chain_explorer`, `dynamodb_table` var) | `apps/dabs/README.md:9-38,44-48,52-93,166-175` | per-bundle layout since `044641a`; none of those workflows exist |
