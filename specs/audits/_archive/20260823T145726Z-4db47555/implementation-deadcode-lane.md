# dd-chain-explorer — Implementation Health + Dead Code lane (2026-08-23)

**Repo:** `<repo>` @ `c6feb17` (branch `feature/v0.4.0`, clean tree)
**Lane:** read-only code audit — no repo writes, no caches, no terraform/AWS/Databricks mutation.
**Tooling:** ruff 0.15.20, vulture 2.16, mypy, pip-audit 2.10, pytest 9.1 (throwaway venv under `.dadaia/tmp/software-engineer/20260823/venv`; workspace venv lacks web3/boto3).
**Context:** v0.4.0 "Capture Retirement" removed Kinesis/Firehose/SQS + the 5 ECS producer task-defs from Terraform and destroyed the live resources (T-4.1 DONE). Capture now lives in `dd-chain-capture` (VPS → S3). The release scope was explicitly *Terraform + operator tooling*; application code (`apps/docker`, `utils/`), the deploy workflow, Makefile and docs were left for "follow-up backlog" — which was never created. This lane measures what that left behind.

---

## 0. Headline metrics

| Metric | Value |
|---|---|
| Tracked files | 373 (289 outside `specs/`) |
| Python LOC (tracked) | **10,296** across 47 files |
| Python LOC that only serves the retired capture layer | **~4,540 (44%)** — `apps/docker/onchain-stream-txs/**` 2,867 + dead `utils/src` modules 984 + `utils/tests` 551 + `scripts/prod_ecs_logs.py` 140 |
| Terraform LOC | 6,316 (modules 1,588 · dev 264 · hml 1,182 · prd 3,282) |
| Shell LOC | 3,084 · Workflow YAML 2,950 · DABs YAML 1,251 · Makefile 477 |
| Dead Python modules (zero live callers) | **16** (6 in `utils/src`, 8 in `apps/docker/.../src`, 1 `test/test_server.py`, 1 `scripts/prod_ecs_logs.py`) + 6 dead test modules |
| Dead/unreferenced Terraform | `modules/iam` firehose/kinesis/sqs statements, `modules/cloudwatch_logs` firehose branch (~140/186 lines, all 3 call sites `firehose_enabled=false`), `modules/ecs` + `hml/07_ecs` + `prd/07_ecs` (cluster shells with zero task-defs), `modules/lambda` (dev-only), `prd/03_iam` Kinesis/SQS/Firehose statements |
| Unreferenced scripts | 6: `scripts/ci/check_app_version.sh`, `scripts/dev_dlt_integration_test.sh`, `scripts/dev_integration_test.sh`, `scripts/prod_resume.sh`, `scripts/prod_standby.sh`, `scripts/tf_validate_all.sh` (+3 no-op stubs referenced only by the dead deploy workflow) |
| Tests | **158 passed / 0 failed** in ~4.5 s (utils 35 · docker 78 · scripts/ci 45). **113 of 158 (72%) exercise retired capture code**; 0 tests cover the live `dm_dynamodb`/`dm_etherscan`/`dm_parameter_store`, the two lambdas, or any DABs code. No skip/xfail/quarantine markers. |
| ruff default (E4,E7,E9,F) | **36** (F401 19 · F821 7 · E402 7 · F841 1 · E701 1 · E731 1) |
| ruff E+F full | 494 (458 E501) · broad rule-set 232 · `ruff format --check`: **46 of 60 files would be reformatted** |
| mypy | not configured in repo. Informational default run: `utils/src` 13 errors/6 files; lambdas, `scripts/ci`, ops scripts clean. `--strict utils/src`: 48 errors/9 files |
| pip-audit | **0 known CVEs** across `apps/lambda/*/requirements.txt`, `apps/docker/.../requirements.txt`, `utils/pyproject.toml` deps — with the caveat that all are floor-pinned (`>=`), so the audit resolved to *today's latest*; no lockfile exists. `dm-chain-utils==0.2.9` pin is **unresolvable on PyPI (HTTP 404)** |
| Largest tracked blob | `services/prd/06_lambda/.lambda_zip/dm_chain_utils_layer.zip` **38 MB** (built 2026-03-19, contains `dm_kafka_*`, `dm_msk_iam`, `dm_redis`, `dm_schema_reg_client` — modules that no longer exist in `utils/src`) |

---

## 1. Inventory

### 1.1 Python packages / modules (tracked, LOC)

| Area | Module | LOC | Status post-v0.4.0 |
|---|---|---|---|
| `utils/src/dm_chain_utils` | `__init__.py` | 26 | live (re-exports 9 handlers; 6 of them dead) |
| | `dm_dynamodb.py` | 301 | **live** — `contracts_ingestion` uses `put_item`, `query` only |
| | `dm_etherscan.py` | 266 | **live** — `call_count`, `get_block_by_timestamp`, `get_contract_txs_by_block_interval` |
| | `dm_parameter_store.py` | 147 | **live** — `get_parameters_by_path` only |
| | `api_keys_manager.py` | 86 | **dead** — only caller `4_mined_txs_crawler.py` (retired) |
| | `dm_cloudwatch_logger.py` | 212 | **dead** — only callers are the 5 producers; `contracts_ingestion/handler.py:40` explicitly removed it |
| | `dm_firehose.py` | 101 | **dead** — Firehose destroyed |
| | `dm_kinesis.py` | 229 | **dead** — Kinesis destroyed |
| | `dm_sqs.py` | 249 | **dead** — SQS destroyed |
| | `dm_web3_client.py` | 107 | **dead** — only producers |
| `utils/tests/unit` | `test_kinesis.py` 129 · `test_sqs.py` 178 · `test_cloudwatch_logger.py` 208 · `test_web3_client.py` 36 | 551 | **all 4 test dead modules**; 0 tests for the 3 live modules |
| `apps/docker/onchain-stream-txs/src` | `1_mined_blocks_watcher.py` 104 · `2_orphan_blocks_watcher.py` 121 · `3_block_data_crawler.py` 113 · `4_mined_txs_crawler.py` 193 · `5_txs_input_decoder.py` 449 · `utils_decode/{abi_cache,etherscan_multi,__init__}.py` 302 | 1,282 | **dead** — the 5 producers whose ECS task-defs were deleted (T-A.1); image no longer deployable (§2.3) |
| `apps/docker/onchain-stream-txs/tests/unit` | 6 test modules + conftest | 1,567 | **dead** (tests of dead code; conftest stubs every `dm_chain_utils` submodule) |
| `apps/docker/onchain-stream-txs/test/test_server.py` | | 18 | **dead** — pre-existing scratch (IPC geth connector), never imported, not collected by pytest (dir `test/` not `tests/`) |
| `apps/lambda/contracts_ingestion/handler.py` | | 309 | live (PRD lambda) |
| `apps/lambda/gold_to_dynamodb/handler.py` | | 83 | live (dev + prd lambda) — but see F-14 (its DynamoDB consumer was the retired producers) |
| `apps/dabs/dlt_ethereum/src/streaming/ethereum_pipeline.py` | | 1,519 | live |
| `apps/dabs/dlt_app_logs/src/streaming/app_logs_pipeline.py` | | 337 | live (source = Fluent Bit NDJSON; filters on retired logger names, F-15) |
| `apps/dabs/job_ddl_setup/src/dd_chain_explorer/{ddl/setup_ddl.py 748, check/check_tables.py 120, setup.py}` | | 874 | live |
| `apps/dabs/job_delta_maintenance/src/batch/dm_delta_maintenance/*` (5 tasks) | | 558 | live |
| `apps/dabs/job_export_gold/src/batch/dm_export_gold/export_gold.py` | | 102 | live |
| `scripts/ci/{changed_stacks.py 92, tests/* 777}` | | 869 | live (CI) |
| `scripts/pause_databricks_clusters.py` 176 · `resume_databricks_clusters.py` 187 | | 363 | live-ish (only via unreferenced `prod_standby/resume.sh`) |
| `scripts/prod_ecs_logs.py` | | 140 | **dead** — tails ECS tasks of a cluster with zero services (Makefile `prod_logs_ecs*` still points at it) |

### 1.2 Terraform modules → stacks

| Module (`services/modules/`) | LOC | Referenced by | Verdict |
|---|---|---|---|
| `s3` | 133 | dev/01_peripherals, hml/04_peripherals (×3), prd/04_peripherals (×3) | live |
| `dynamodb` | — | dev/01, hml/04, prd/04 | live |
| `cloudwatch_logs` | 186+72+outputs | dev/01, hml/04, prd/04 — **all with `firehose_enabled = false`** | log-group part live; **firehose branch (6 resources, ~140 lines, `firehose_*` vars/output, tracked `.lambda_zip/cw_logs_transform.zip` never referenced) dead** |
| `vpc` | 102+74 | hml/02_vpc only (prd/02_vpc is inline `network.tf`) | live for HML only (duplicated logic vs prd) |
| `iam` | 434+105 | hml/03_iam only (prd/03_iam inline) | live for HML; **Kinesis/SQS/Firehose statements + `kinesis_stream_suffix`/`sqs_queue_suffix` vars dead** (`main.tf:56-73,110-113`) |
| `ecs` | 47+71 | hml/07_ecs only | **dead shell** — cluster + capacity providers + log group + Cloud Map namespace, `ecr_repositories = {}`, zero task-defs/services anywhere |
| `lambda` | 50+96 | dev/02_lambda only (prd/06_lambda inline) | live for DEV only |

Stacks with no module use: `prd/{01_tf_state,02_vpc,03_iam,05*,06_lambda,07_ecs}`, `hml/05*`, — all inline. `prd/07_ecs` (82+45+locals) after T-A.1 = ECS cluster, capacity providers, `/ecs/dm-chain-explorer` log group, Cloud Map namespace, 2 ECR repos, and `locals.ecs_network_config / log_config / ecr_image_stream / ecr_image_batch` with **no consumer left** (`ecs.tf:43-58`, `locals.tf:3-6,20-28`) — dead locals inside a shell stack.

### 1.3 Scripts → referrers

| Script | LOC | Referenced by | Verdict |
|---|---|---|---|
| `scripts/ci/{branch_guard,bump_version,changed_stacks.py,check_commit_confirmation,check_prd_version,databricks_account_import,deploy_env,destroy_env,detect_changes,empty_s3_and_ecr,plan_env,plan_gate_check,stack_map.json,tf_plan,tf_state_lock_check,wait_eni_release}` | — | workflows / each other | live |
| `scripts/ci/check_app_version.sh` | 26 | **nothing** | dead (superseded by inline step in `deploy_all_dm_applications.yml:64-85`) |
| `scripts/ci/check_infra_prerequisites.sh` | 94 | `deploy_all_dm_applications.yml` only | live only through the dead-by-design workflow (F-01) |
| `scripts/ci/hml_provision.sh` / `hml_teardown.sh` | 54 / 44 | `deploy_all_dm_applications.yml` | **stale** — `hml_provision.sh:30-36` does `aws sqs get-queue-url mainnet-*-hml` (queues never existed in HML, module deleted) → hard-fails |
| `scripts/hml_integration_test.sh`, `hml_integration_test_optimized.sh`, `dev_integration_test.sh` | 22/20/26 | workflow / nothing / nothing | v0.4.0 reduced to `exit 0` no-op stubs — tombstones |
| `scripts/dev_dlt_integration_test.sh` | 274 | **nothing** | stale: waits for Firehose app-logs delivery (`:112-131`) |
| `scripts/hml_dlt_integration_test.sh` | 263 | workflow `all-hml-test-dabs` | live-if-workflow-lives |
| `scripts/prod_resume.sh` / `prod_standby.sh` | 75 / 77 | **nothing** (README/AGENTS.md cite `make prod_resume/standby`, targets don't exist) | orphaned; content already trimmed to Databricks-only |
| `scripts/prod_ecs_logs.py` | 140 | `Makefile: prod_logs_ecs, prod_logs_ecs_svc` | dead (no ECS services) |
| `scripts/tf_validate_all.sh` | 133 | **nothing** | unreferenced |
| `scripts/empty_s3_bucket.sh` | 48 | `destroy_all_cloud_infra.yml` | live |
| `apps/dabs/check_versions.sh`, `deploy_all.sh` | — | `deploy_all_dm_applications.yml` (+ dead `dev_dlt_integration_test.sh`) | live-if-workflow-lives |

### 1.4 Docker images

| Image | Built by | Used by | Verdict |
|---|---|---|---|
| `apps/docker/onchain-stream-txs/Dockerfile` → ECR `onchain-stream-txs` | `deploy_all_dm_applications.yml` job `all-stream-build-rc` (docker/build-push), `Makefile build_stream/push_stream` (Docker Hub), `services/dev/00_compose/app_services.yml` (5 services, 6+3 replicas) | **no ECS task definition anywhere** (prd/07_ecs producers deleted; hml launches ad-hoc tasks from the workflow) | **dead** — and **unbuildable**: `requirements.txt:4 dm-chain-utils==0.2.9` is not on PyPI (pip 404) while the Dockerfile also COPYs `utils/src` in (double install) |
| ECR `onchain-batch-txs` (`prd/07_ecs/ecs.tf:72`) | nobody (only a commented `docker push` in `Makefile:315`) | nobody | dead (already flagged L3 in the 2026-06-11 architecture audit; v0.4.0 SPEC kept it claiming "surviving batch workload" — no such workload exists in the repo) |
| `marcoaureliomenezes/spark-batch-jobs`, `spark-streaming-jobs` (`Makefile:314-318 publish_apps`) | nothing | nothing | dead Docker Hub targets, undefined `$(current_branch)` |

---

## 2. Findings

| ID | Sev | Area | Finding | Evidence | Recommendation |
|---|---|---|---|---|---|
| F-01 | **HIGH** | CI/CD | The **only** application deploy workflow is hard-wired to the retired capture layer: builds the stream RC image, provisions HML Kinesis/SQS/Firehose, launches 5 ECS tasks, runs streaming tests, and PRD DABs + Lambda deploys are `needs:` chained **behind** `all-prod-stream-deploy`, which does `aws ecs describe-task-definition dm-mined-blocks-watcher …` + `aws ecs wait services-stable` on services that no longer exist. DABs and Lambda cannot reach PRD through CI any more. | `.github/workflows/deploy_all_dm_applications.yml:7-16,109-148,285-420,538-580,829-895,896-898,973-975`; `scripts/ci/hml_provision.sh:30-36` | Rewrite the workflow as DABs + Lambda only (drop `all-stream-*`, `all-hml-provision`, `all-hml-stream-launch`, `all-hml-test-streaming`, the ECS cluster step 263-283); delete `hml_provision.sh`/`hml_teardown.sh`; drop `ECS_CLUSTER/HML_ECS_CLUSTER/ECR_REPO` env. |
| F-02 | **HIGH** | DABs | `job_reconcile_orphans` bundle points to notebook `src/batch/reconcile_orphan_blocks`, deleted in `67f8faf` ("remove deprecated monolith bundle"). Bundle has no `src/` at all; job is scheduled **UNPAUSED daily 03:00** → fails every run wherever deployed; included in `make dabs_deploy_phase2`/`dabs_deploy_all`/`deploy_all.sh`. | `apps/dabs/job_reconcile_orphans/resources/workflows/workflow_reconcile_orphans.yml:22,36`; `find apps/dabs/job_reconcile_orphans -name '*.py'` → none | Either restore the notebook (from `67f8faf^`) or delete the bundle + Makefile targets + its row in docs; verify live job state in the environment lane. |
| F-03 | **HIGH** | Repo hygiene / IaC | A **38 MB** prebuilt Lambda layer zip is tracked in git, built 2026-03-19 from a *different* `dm_chain_utils` (contains `dm_kafka_admin/client`, `dm_msk_iam`, `dm_redis`, `dm_schema_reg_client`, `dm_logger` — none exist in `utils/src`). Terraform `prd/06_lambda` hashes this file (`source_code_hash`), CI overwrites it at deploy (`workflow:995`) → every `plan_on_pr` / `drift_detection` plan of PRD/Lambda against the committed blob reports a layer replacement; committed content is stale and unreviewable. | `services/prd/06_lambda/.lambda_zip/dm_chain_utils_layer.zip` (37,576 KB); `lambda_contracts_ingestion.tf:13-16`; `.github/workflows/deploy_all_dm_applications.yml:995`; also tracked: `contracts_ingestion.zip`, `gold_to_dynamodb.zip`, `services/dev/02_lambda/.lambda_zip/gold_to_dynamodb.zip`, `services/modules/cloudwatch_logs/.lambda_zip/cw_logs_transform.zip` (referenced by nothing) | `git rm` all `.lambda_zip/*`, gitignore `**/.lambda_zip/`, build the layer in the plan job too (or use `archive_file` + S3 artifact) so plan and apply see the same hash; purge the blob from history before any push of a public remote. |
| F-04 | **HIGH** | Dead code | `apps/docker/onchain-stream-txs/**` (2,867 LOC incl. tests, + Dockerfile, requirements, `.hypothesis/` cache dir inside the repo) is the retired producer code. No task-def, no compose target that can run (dev SQS/Kinesis destroyed), image unbuildable (F-09). Kept "out of scope" by v0.4.0 OQ-5 with a promised backlog item `dm-chain-utils-capture-handler-cleanup` that **does not exist** in `specs/backlog/`. | `specs/releases/v0.4.0/SPEC.md:338,362-364`; `specs/releases/v0.4.0/TASKS.md:214-215`; `ls specs/backlog/` | Delete `apps/docker/`, `services/dev/00_compose/`, Makefile `deploy_dev_stream/stop_dev_stream/watch_dev_stream/build_stream/push_stream/build_and_push_stream/publish_apps`; archive `specs/backlog/streaming-jobs-security-hardening.md` (hardens a dead image). Create the missing backlog item or fold into a v0.4.1 cleanup. |
| F-05 | **HIGH** | Dead code | 6 of 9 `dm_chain_utils` modules have zero live callers — `api_keys_manager`, `dm_cloudwatch_logger`, `dm_firehose`, `dm_kinesis`, `dm_sqs`, `dm_web3_client` (984 LOC). `__init__.py` still re-exports them, and the Lambda layer ships them (+ `web3`, `hexbytes` dependency chain the lambdas never import). The 551-LOC utils test suite tests **only** these dead modules. | `utils/src/dm_chain_utils/__init__.py:5-26`; cross-ref table §3.1; `apps/lambda/contracts_ingestion/handler.py:27-29` is the only live importer | Trim the library to `dm_dynamodb`, `dm_etherscan`, `dm_parameter_store`; drop `web3`/`hexbytes` deps; write tests for the 3 live modules; bump version and fix `__version__="0.1.0"` vs pyproject `0.2.9`. |
| F-06 | **MEDIUM** | IaC dead code | `modules/cloudwatch_logs` firehose branch is universally disabled (all 3 call sites `firehose_enabled=false`) — 6 `count`-gated resources, `firehose_*` variables, `firehose_arn` output, and the never-referenced `cw_logs_transform.zip` remain. `modules/iam` (HML) still grants `kinesis:*`, `sqs:*`, `firehose:*` on `mainnet-*-hml` ARNs; `hml/03_iam` declares a `firehose` role + `KinesisReadAccess`; `prd/03_iam/iam.tf` ECS task role still grants Kinesis/Firehose/SQS on `mainnet-*-prd` resources that no longer exist. | `services/modules/cloudwatch_logs/main.tf:44-186`; `services/modules/iam/main.tf:56-73,110-113`; `services/hml/03_iam/main.tf:63-64,75-123`, `outputs.tf:9`; `services/prd/03_iam/iam.tf:44-90` | Strip firehose from the module (or inline a plain log-group resource); remove capture statements from IAM; remove `ecs_task` role entirely if ECS stays a shell (F-07). |
| F-07 | **MEDIUM** | IaC dead code | ECS is a shell in both envs: `prd/07_ecs` = cluster + capacity providers + Cloud Map + 2 ECR repos + orphan locals (`ecs_network_config`, `log_config`, `ecr_image_*`, `var.docker_image_stream/batch`); `hml/07_ecs` → `modules/ecs` same shell with `ecr_repositories = {}`. Zero task definitions or services in the repo. `drift_detection.yml`/`plan_on_pr.yml` still spend jobs planning `PRD/ECS`; `destroy_all_cloud_infra.yml` still empties ECR before destroying it. | `services/prd/07_ecs/ecs.tf:43-58,61-82`, `locals.tf:3-6,20-28`; `services/hml/07_ecs/main.tf:54-67`; `services/modules/ecs/*`; `.github/workflows/drift_detection.yml:229-260`, `plan_on_pr.yml:376-399` | Decide: retire ECS + ECR (both envs, stack_map rows, workflow jobs, IAM ECS roles) or document a real future consumer. The v0.4.0 SPEC's stated reason ("referenced by surviving batch workload") has no referent in the repo. |
| F-08 | **MEDIUM** | Docs drift (memory) | `specs/memory/product/capture-layer.md` still describes 5 ECS jobs + Kinesis/Firehose/SQS as *current* product truth; `serving-layer.md` says the DynamoDB export exists so "streaming jobs" can read key consumption. v0.4.0 has no CLOSURE and memory was never updated (release still open on `feature/v0.4.0`). | `specs/memory/product/capture-layer.md:5-6,12,21,39-40,55-65`; `specs/memory/product/serving-layer.md:21,38` | Run v0.4.0 closure: memory update → CLOSURE → archive (DADAIA §5). |
| F-09 | **MEDIUM** | Dependencies | `dm-chain-utils==0.2.9` is pinned in 3 requirement files and enforced by CI (`deploy_all…yml:88-107`), but the package is **not on PyPI** (404). Docker build (`pip install -r requirements.txt`) cannot resolve it; lambdas only work because the layer is built from `utils/` and `requirements.txt` is never installed. `gold_to_dynamodb/requirements.txt` pins it but the handler imports nothing from it. README/AGENTS.md call it "PyPI". No lockfile anywhere → pip-audit result (0 CVEs) reflects today's latest, not what was deployed. | `apps/docker/onchain-stream-txs/requirements.txt:4`; `apps/lambda/*/requirements.txt:3-4`; `apps/lambda/gold_to_dynamodb/handler.py:10-15`; `README.md:30`; `AGENTS.md:69` | Drop the fictional pin + CI check; install the lib from path; add a lock (pip-compile) per deployable; remove `dm-chain-utils` from `gold_to_dynamodb`. |
| F-10 | **MEDIUM** | Docs / Makefile | README, AGENTS.md, `apps/dabs/README.md`, `apps/lambda/README.md` reference **16 Makefile targets that do not exist** (`help`, `dabs_deploy_dev`, `dabs_ddl_dev`, `dabs_run_dev`, `dabs_status_dev`, `dabs_deploy_dev_dashboards`, `pause_dlt_pipelines`, `run_dev_pipelines`, `prod_standby`, `prod_resume`, `prod_ecs_logs`, `tf_apply_dev_lambda`, `tf_destroy_dev_lambda`, `tf_apply_dev_peripherals`, `tf_plan_dev_peripherals`, `targets`). Makefile itself references 4 missing paths (`services/compose/airflow_orchestration_layer.yml`, `services/prd/0_remote_state`, `scripts/setup_databricks_profiles.sh`, `.github/workflows/deploy_infrastructure.yml`) and an undefined target `tf_destroy_free_resources` used by `prod_destroy_infra` (make aborts mid-destroy). All of this was already reported in the 2026-06-11 audit (`architecture-review.md:51`) and is still open. | `README.md:73-81`; `AGENTS.md:93-95`; `apps/dabs/README.md`; `Makefile:306,327-330,363,394,408-409` | Rewrite the Makefile against reality (DABs + TF dev/hml/prd only); regenerate README/AGENTS.md target lists from `grep '^[a-z_]*:' Makefile`. |
| F-11 | **MEDIUM** | Docs drift | README (`:5,15-17,25,43-44,61,75-81,98,110`), `apps/docker/README.md` (171 lines, whole file), `apps/dabs/README.md:100,108,153`, `utils/README.md:15`, `AGENTS.md:11`, DLT notebook headers (`ethereum_pipeline.py:5-11,45-62,83,97,111,250`, `app_logs_pipeline.py` silver headers), DDL table comments (`setup_ddl.py:116,145,172,191,198,215`) still describe ECS Fargate + Kinesis/Firehose/SQS as the live architecture. `docs/README.md` and `AGENTS.md:21-31` point at `specs/SPEC.md`, `specs/memory/constitution.md`, `specs/memory/product.md`, `specs/domains/*` — none exist. README "Deploy" table names workflow sub-jobs `streaming-apps`/`databricks-dabs`/`lambda-functions` that are not workflow inputs. | as listed | One docs pass: S3-first architecture diagram (dd-chain-capture → S3 raw → DLT → serving); delete `apps/docker/README.md` with the app; fix spec paths. |
| F-12 | **MEDIUM** | Tests | Test pyramid is inverted: 113/158 tests cover retired code; the live surface (`contracts_ingestion`, `gold_to_dynamodb`, the 3 live utils modules, DDL/maintenance/export jobs, DLT expectations) has **zero** unit tests. CI (`all-lambda-build-artifacts:161-163`) runs only `utils/tests/unit` — i.e. only dead-module tests gate the lambda build. | `utils/tests/unit/*`; `apps/docker/onchain-stream-txs/tests/unit/*`; `.github/workflows/deploy_all_dm_applications.yml:160-163` | Under `dadaia-test-stewardship`: delete tests with their subjects (qa-engineer verdict), add SMALL tests for `DMDynamoDB.put_item/query`, `EtherscanClient`, both handlers (moto/botocore stubs), and `scripts/ci` stays. |
| F-13 | **MEDIUM** | Code quality | Lint/format gates absent: no ruff/mypy config, 46/60 files unformatted, 36 default-rule ruff errors incl. 7 `F821 undefined name spark` in DLT notebooks (expected in Databricks, but means the files are not lint-clean under any config — needs `# noqa`/`builtins` config), 19 unused imports (6 pyspark types in `ethereum_pipeline.py:40`, `logging` in live `dm_etherscan.py:24`, `os` in `pause_databricks_clusters.py:21`). `plan_on_pr.yml` `quality` job exists — check what it runs vs these numbers (it does not fail today, so it is not running ruff over this tree). | ruff output §3.2; `.github/workflows/plan_on_pr.yml:42-74` | Add `ruff.toml` at repo root (`builtins = ["spark","dbutils"]` for `apps/dabs/**`), run `ruff check`/`ruff format --check` in `quality`, then fix. |
| F-14 | **MEDIUM** | Architecture / possibly-dead serving path | `job_export_gold → S3 exports/gold_api_keys → gold_to_dynamodb λ → DynamoDB PK=CONSUMPTION` exists to feed `APIKeysManager` (DynamoDB semaphore) of the retired Job 4. No in-repo reader of `CONSUMPTION` rows remains. If `dd-chain-capture` does not read this table, the whole export→lambda→DynamoDB chain (dev+prd lambdas, S3 notifications, IAM) is dead serving infrastructure that still runs on every export. | `apps/lambda/gold_to_dynamodb/handler.py:1-6`; `apps/dabs/job_export_gold/src/batch/dm_export_gold/export_gold.py:61-79`; `specs/memory/product/serving-layer.md:21,38`; `utils/src/dm_chain_utils/api_keys_manager.py` (dead) | Confirm with dd-chain-capture (environment lane) whether anything reads `PK=CONSUMPTION`; if not, retire export_gold + both `gold_to_dynamodb` lambdas + `dev/02_lambda` stack + `modules/lambda`. |
| F-15 | **LOW** | DLT | `app_logs_pipeline.py` silver layer filters `logger IN (MINED_BLOCKS_EVENTS, ORPHAN_BLOCKS_CRAWLER, BLOCK_DATA_CRAWLER, RAW_TXS_CRAWLER, TRANSACTION_INPUT_DECODER)` / `CONTRACT_TRANSACTIONS_CRAWLER` — the retired producers' logger names (comment cites a nonexistent `1_capture_and_ingest_contracts_txs.py`). If dd-chain-capture's Fluent Bit logs use other logger names, `s_logs.*` and the 2 `g_api_keys` MVs (and the `alert_api_keys` / `dashboard_api_health` bundles on top) are silently empty. Could not cross-check: `dd-chain-capture` is not on this machine. | `apps/dabs/dlt_app_logs/src/streaming/app_logs_pipeline.py:33-42,144,179` | Make the name list a pipeline config (`spark.conf`) sourced from the capture repo's contract; verify in the environment lane. |
| F-16 | **LOW** | Dead code (functions) | Unused public API in live utils modules: `DMDynamoDB.{get_item, delete_item, update_item, conditional_put_item, query_all_keys, batch_write, batch_delete, item_exists, delete_all_by_pk, ping}` (only `put_item`, `query` used); `EtherscanClient.{get_contract_abi, get_4byte_signature, get_internal_txs_by_block_interval, _fetch_abi_from_etherscan, _load_from_disk, _save_to_disk}`; `ParameterStoreClient.{get_parameter, list_parameters, put_parameter, delete_parameter}`. `dm_dynamodb.py:256` `B018 useless expression`. Duplicated `_location()` helper across 6 DABs batch tasks (vulture flags as unused in each — it is used via `self._location` only in some). | §3.1 table; vulture §3.3 | Prune when trimming the lib (F-05); centralise `_location` in a shared module or drop. |
| F-17 | **LOW** | Tracked artefacts | Unreferenced/derived files: `img/*.png` (4 screenshots, 372 KB, no referrer), `apps/docker/onchain-stream-txs/test/test_server.py` (geth IPC scratch), `apps/dabs/check_versions.sh`+`deploy_all.sh` (only the dead workflow). Ignored-but-present local slop: `apps/docker/onchain-stream-txs/.hypothesis/`, `apps/dabs/src/**` (only egg-info/dist leftovers), recursively nested `build/lib/dm_export_gold/build/lib/...` (5 levels) in `job_export_gold` and `job_delta_maintenance` — `setup.py` builds pick up previous `build/` output each run. | `git ls-files img`; `git status --ignored` | Delete `img/` or reference it; add `build/`, `dist/`, `*.egg-info` to the DABs `sync.exclude`, and clean locally. |
| F-18 | **LOW** | stale remote-state alias | `prd/06_lambda/main.tf:47` still names the peripherals remote state `kinesis_sqs` (`CLOUDWATCH_LOG_GROUP = data.terraform_remote_state.kinesis_sqs.outputs…`, `lambda_contracts_ingestion.tf:119`); peripherals headers (`prd/04_peripherals/main.tf:4`, `peripherals.tf:4`, `hml/04_peripherals/main.tf:4`, `dev/01_peripherals/main.tf:4`) and Makefile comments (`:333-338,415`) still describe Kinesis/SQS. `services/dev/00_compose/conf/dev.dynamodb.conf:12-20` hard-codes destroyed SQS URLs / stream names with the AWS account id. | as listed | Rename alias to `peripherals`; fix headers; delete compose conf with F-04. |
| F-19 | **INFO** | Versions | `utils/src/dm_chain_utils/__init__.py:15 __version__ = "0.1.0"` vs `pyproject.toml version = "0.2.9"` vs root `VERSION 0.2.9`; all 15 DABs `VERSION` files are `1.0.0` while `deploy_all` tags `v{VERSION}-dabs` from root VERSION. | as listed | Single version source. |
| F-20 | **INFO** | Type-checking | mypy not configured; `utils/src` has 13 default-mode errors (6 files), 48 under `--strict`; lambdas/scripts clean. | mypy run §3.4 | Add `[tool.mypy]` to `utils/pyproject.toml` once the lib is trimmed. |

---

## 3. Dead-code candidates

### 3.1 Module / file level

| Path | Kind | Confidence | Reason |
|---|---|---|---|
| `apps/docker/onchain-stream-txs/src/1_mined_blocks_watcher.py` | module (producer) | 100% | ECS task-def deleted (T-A.1); SQS target destroyed |
| `apps/docker/onchain-stream-txs/src/2_orphan_blocks_watcher.py` | module (producer) | 100% | idem |
| `apps/docker/onchain-stream-txs/src/3_block_data_crawler.py` | module (producer) | 100% | Firehose/SQS destroyed |
| `apps/docker/onchain-stream-txs/src/4_mined_txs_crawler.py` | module (producer) | 100% | Kinesis/SQS destroyed |
| `apps/docker/onchain-stream-txs/src/5_txs_input_decoder.py` | module (producer) | 100% | Kinesis/Firehose destroyed |
| `apps/docker/onchain-stream-txs/src/utils_decode/{__init__,abi_cache,etherscan_multi}.py` | package | 100% | only imported by `5_txs_input_decoder.py` |
| `apps/docker/onchain-stream-txs/tests/unit/*` (6 tests + conftest) | tests | 100% | test the above |
| `apps/docker/onchain-stream-txs/test/test_server.py` | scratch | 100% | never imported/collected |
| `apps/docker/onchain-stream-txs/{Dockerfile,requirements.txt}` | build | 100% | no consumer; unbuildable pin |
| `services/dev/00_compose/{app_services.yml,conf/dev.dynamodb.conf}` | compose | 100% | runs the producers against destroyed SQS/Kinesis |
| `utils/src/dm_chain_utils/dm_kinesis.py` | module | 100% | 0 live callers; Kinesis gone |
| `utils/src/dm_chain_utils/dm_firehose.py` | module | 100% | 0 live callers; Firehose gone |
| `utils/src/dm_chain_utils/dm_sqs.py` | module | 100% | 0 live callers; SQS gone |
| `utils/src/dm_chain_utils/dm_web3_client.py` | module | 95% | 0 live callers (producers only); `job_reconcile_orphans` notebook that might have used web3 no longer exists |
| `utils/src/dm_chain_utils/dm_cloudwatch_logger.py` | module | 95% | 0 live callers; lambdas log natively (`contracts_ingestion/handler.py:40`) |
| `utils/src/dm_chain_utils/api_keys_manager.py` | module | 95% | only `4_mined_txs_crawler.py`; DynamoDB semaphore semantics belong to capture |
| `utils/tests/unit/{test_kinesis,test_sqs,test_cloudwatch_logger,test_web3_client}.py` | tests | 100% | test dead modules |
| `scripts/prod_ecs_logs.py` | script | 100% | no ECS services to tail |
| `scripts/ci/check_app_version.sh` | script | 100% | unreferenced; superseded inline |
| `scripts/ci/hml_provision.sh`, `scripts/ci/hml_teardown.sh`, `scripts/ci/check_infra_prerequisites.sh` | scripts | 90% | only the capture-coupled workflow; provision hard-fails on SQS lookup |
| `scripts/{hml_integration_test,hml_integration_test_optimized,dev_integration_test}.sh` | no-op stubs | 100% | `exit 0` tombstones |
| `scripts/dev_dlt_integration_test.sh` | script | 90% | unreferenced; asserts Firehose delivery |
| `scripts/prod_resume.sh`, `scripts/prod_standby.sh`, `scripts/tf_validate_all.sh` | scripts | 70% | unreferenced (docs cite nonexistent make targets); content still potentially useful manually |
| `services/modules/ecs/*`, `services/hml/07_ecs/*`, `services/prd/07_ecs/*` | terraform | 85% | cluster shells, zero workloads; ECR `onchain-batch-txs` has no producer |
| `services/modules/cloudwatch_logs/main.tf:44-186`, `variables.tf` firehose vars, `outputs.tf:17`, `.lambda_zip/cw_logs_transform.zip` | terraform | 100% | `firehose_enabled=false` everywhere; zip referenced by nothing |
| `services/modules/iam/main.tf:56-73,110-113` + vars `kinesis_stream_suffix`, `sqs_queue_suffix`; `services/hml/03_iam/main.tf:75-123`, `outputs.tf:9-11`; `services/prd/03_iam/iam.tf:54-90` | terraform | 100% | permissions on resources that no longer exist |
| `services/prd/07_ecs/locals.tf:3-6,20-28`, `ecs.tf:43-58`, `variables.tf docker_image_*` | terraform locals | 100% | no consumer after task-def removal |
| `services/prd/06_lambda/.lambda_zip/*.zip`, `services/dev/02_lambda/.lambda_zip/*.zip` | tracked build output | 100% | CI regenerates; committed copies are stale |
| `.github/workflows/deploy_all_dm_applications.yml` jobs `all-stream-build-rc`, `all-hml-infra-apply`(ECS steps), `all-hml-provision`, `all-hml-stream-launch`, `all-hml-test-streaming`, `all-prod-stream-deploy`, `all-hml-teardown` ECS part | workflow | 100% | operate on destroyed resources |
| `Makefile` targets `deploy_dev_stream`, `stop_dev_stream`, `watch_dev_stream`, `publish_apps`, `deploy_dev_all`, `tf_apply_remote_state`, `prod_logs_ecs`, `prod_logs_ecs_svc`, `build_stream`, `push_stream`, `build_and_push_stream`, `dabs_run_reconcile_orphans`, `dabs_deploy_job_reconcile_orphans` | make | 95% | capture-only, missing paths, or broken bundle |
| `img/*.png` | assets | 80% | no referrer |
| `specs/backlog/streaming-jobs-security-hardening.md` | backlog | 90% | hardens the retired Docker image |

### 3.2 Symbol level (live modules)

| Path | Symbol | Confidence | Reason |
|---|---|---|---|
| `utils/src/dm_chain_utils/dm_dynamodb.py` | `get_item`, `delete_item`, `update_item`, `conditional_put_item`, `query_all_keys`, `batch_write`, `batch_delete`, `item_exists`, `delete_all_by_pk`, `ping` | 80% | 0 callers outside retired producers; lambda uses `put_item`/`query` only |
| `utils/src/dm_chain_utils/dm_etherscan.py` | `get_contract_abi`, `get_4byte_signature`, `get_internal_txs_by_block_interval`, `_fetch_abi_from_etherscan`, `_load_from_disk`, `_save_to_disk` | 80% | 0 live callers |
| `utils/src/dm_chain_utils/dm_parameter_store.py` | `get_parameter`, `list_parameters`, `put_parameter`, `delete_parameter` | 80% | 0 live callers |
| `apps/lambda/contracts_ingestion/handler.py:51` | `self.paths` | 60% | assigned, never read (vulture) |
| `apps/lambda/*/handler.py` | `context` param | — | Lambda signature, false positive |
| `apps/dabs/job_{delta_maintenance,export_gold}/.../*.py` | `_location()` ×6 | 60% | vulture flags each copy; duplicated helper |
| `apps/dabs/dlt_ethereum/src/streaming/ethereum_pipeline.py:40` | `StringType, StructType, StructField, LongType, ArrayType, IntegerType` | 90% | unused imports (ruff F401 + vulture) |
| `apps/dabs/dlt_*` `@dlt.table` functions | — | — | vulture false positives (decorator-registered) |
| `utils/tests/…`, `apps/docker/…/tests` mock `.return_value/.side_effect` | — | — | vulture false positives |

### 3.3 Raw tool output summary
- **vulture** (`--min-confidence 60`, all tracked .py): 155 lines; after removing the `@dlt.table` and mock-attribute false positives → 23 real candidates (listed above).
- **ruff** default E4/E7/E9/F: 36 (`F401`×19, `F821`×7 `spark`, `E402`×7, `F841`×1 `test_server.py:13`, `E701`, `E731`). E+F: 494 (E501 458). Broad set: 232 (UP006 61, I001 32, UP045 29, BLE001 23, F401 19, UP035 19, B023 7, F821 7, RUF012 6 …). `ruff format --check`: 46/60 need reformatting.
- **mypy** default: `utils/src` 13 errors / 6 files; `apps/lambda/*`, `scripts/ci`, ops scripts: clean. `--strict utils/src`: 48 errors / 9 files.
- **pytest** (`-p no:cacheprovider`): utils 35 passed 1.68 s · docker 78 passed 0.81 s · scripts/ci 45 passed 2.03 s → **158/158 green**, 0 skipped/xfail/quarantine. Note `utils/pyproject.toml` has no `pythonpath`, the suite only collects with `PYTHONPATH=src` or after `pip install utils/` (as CI does).
- **pip-audit**: 0 vulnerabilities for `contracts_ingestion`, `gold_to_dynamodb`, `onchain-stream-txs` requirement sets (after dropping the unresolvable `dm-chain-utils==0.2.9` line) and for `utils` deps (`requests>=2.28, web3>=7.8, boto3>=1.26, hexbytes>=1.3`). All floor pins → audit reflects latest resolvable versions, not a lock.

---

## 4. Stale-reference classification (outside `specs/`)

Hit counts: `kinesis` 274 hits/37 files · `firehose` 243/36 · `sqs` 325/37 · `ecs` 420/63 · `producer` 17/11 · `watcher` 66/8 · `dm-chain-explorer-*-ingestion` 23/15 · `stream` 568/84 (the 38 MB zip alone accounts for 159 kinesis/firehose/sqs hits).

| Bucket | Where | Verdict |
|---|---|---|
| Retired code still shipped | `utils/src/dm_{kinesis,sqs,firehose}.py`, `utils/tests/unit/*`, `apps/docker/onchain-stream-txs/**`, `services/dev/00_compose/**` | **leftover** — delete |
| Retired infra still declared/permitted | `modules/cloudwatch_logs` firehose branch; `modules/iam`, `hml/03_iam`, `prd/03_iam` Kinesis/SQS/Firehose statements; `prd/07_ecs` + `hml/07_ecs` + `modules/ecs` shells; `prd/06_lambda/main.tf:47` alias `kinesis_sqs` | **leftover** |
| Retired operations in CI | `deploy_all_dm_applications.yml` stream/HML-provision/ECS jobs; `hml_provision.sh`, `hml_teardown.sh`, `check_infra_prerequisites.sh`; `drift_detection.yml`/`plan_on_pr.yml` PRD/ECS jobs; `destroy_all_cloud_infra.yml` ECR/ECS jobs | **leftover** (ECS drift/destroy jobs are "live" only while the shell stacks exist) |
| Retired operator tooling | `Makefile` stream/ECS targets + comments, `scripts/prod_ecs_logs.py`, `scripts/dev_dlt_integration_test.sh`, the three `exit 0` stubs | **leftover** |
| Docs/memory describing capture as current | `README.md`, `apps/docker/README.md`, `apps/dabs/README.md:100,108,153`, `utils/README.md`, `AGENTS.md`, `specs/memory/product/{capture-layer,serving-layer}.md`, DLT headers, DDL comments | **leftover** (docs drift) |
| Legitimately live mentions | `dm-chain-explorer-dev-ingestion` S3 bucket (DLT config, Makefile `DEV_S3_BUCKET`, dev peripherals/lambda) — the S3 boundary is the live contract; `stream` in DLT (`readStream`, `dlt.read_stream`), DABs `layer: streaming` tags, `scripts/ci/destroy_env.sh:76-78` warning comment, v0.4.0 retirement comments in `prod_resume.sh`/`hml_teardown.sh`/peripherals headers | **live-needed** |

---

## 5. Notes for other lanes
- Environment lane: verify (a) `dm-reconcile-orphan-blocks` job run history (F-02), (b) whether anything reads DynamoDB `PK=CONSUMPTION` (F-14), (c) Fluent Bit logger names vs `STREAMING_APP_NAMES` (F-15), (d) whether the Auto Loader prefixes `raw/mainnet-{blocks,transactions}-data/`, `raw/mainnet-transactions-decoded/`, `raw/app_logs/` match what dd-chain-capture writes (all in-repo descriptions still say "Firehose").
- Governance lane: v0.4.0 is DONE-but-open (no CLOSURE, no merge, memory stale); the promised `dm-chain-utils-capture-handler-cleanup` backlog item was never created; 2026-06-11 audit Makefile findings remain open; `specs/backlog/BACKLOG.md` single-source file does not exist (backlog is 7 loose files).
