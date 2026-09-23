# PLAN — Release v0.7.0 — Market-data restart: batch capture runtime + medallion landing

> **Status:** Aprovado
> **Release ID:** v0.7.0
> **Owner:** product-engineer — approved under the operator standing order of 2026-09-13 ("faça tudo que puder, avance") after ratifying grill rulings R1-R17
> **Depends on:** SPEC.md v0.7.0 (`Aprovado`)
> **Branch:** `feature/0.7.0` in `dd-chain-infrastructure` and the new `dd-chain-explorer`, each stacked on `feature/0.6.0` (`DADAIA.md` §4, `dd-gitflow-default`); merges into `develop` only after v0.6.0's candidate merge (SPEC O-1)
> **Amended:** 2026-09-23 — operator rulings R18-R26 (SPEC §11): §9 replaces the DLT design of §4 with the batch job `job_market_data`, sequences the Ethereum and lambda-seam teardown, designs the trust seed and the event-chained lanes, and maps M1..M15; §1.4, §1.6, §2 K6, §3.5 `FORCE`, §4, §5, §7 rows `T-X7.6`/`T-O7.x` superseded where §9 says so.
> **Lifecycle:** pre-staged — v0.6.0 is the live release until its C-DAY; this PLAN becomes executable when v0.7.0 turns ACTIVE

This release adds capability, so its acceptance shapes are **existence + equality proofs**: a resource exists and its declared state plans clean (AC-4..AC-6, AC-9), a grant is effective (AC-7), a partition lands from Fargate (AC-16), a table carries rows whose `content_sha256` matches the manifest (AC-14). Every growth is justified against the deletion test (`dd-codebase-design`): the module grown, the leverage gained, the slop that dies in the same change.

## 1. Strategy

1. **Bug ledger first (`DADAIA.md` §7.1).** The four prior infra bugs on this surface were all "hand-maintained map/policy with no cross-check". The scheduler gap is the fifth of the family; it is closed by a test that *derives* the required grants from `services/**` (T-I7.1 RED → T-I7.2 GREEN), so any future stack declaring a new AWS namespace fails the suite until the bootstrap grants it. No grant lands without that test.
2. **Replace, don't layer.** The dev deploy lane already duplicates the stack enumeration (static jobs + `detect_changes.sh`) — the defect the prd lane fixed. Two more stacks would grow that copy; instead the lane becomes map-driven and `detect_changes.sh` dies. `publish_oidc_vars.sh --target` replaces a hand-run `gh variable set`. `force_delete` on ECR kills the ECR branch of `empty_s3_and_ecr.sh`.
3. **One credential per environment, one adapter per seam.** The dev storage-credential role is widened to the new bucket (no second role for one bucket). The writer role and the task roles share one policy shape (`raw/*` vs `raw/<source>/*`). The registry host comes from `ecr-login`, never a variable.
4. **Raw is evidence; bronze is bytes; silver parses; gold computes** (R13). Bronze never decodes. Every parser is a pure function tested off-cluster; batch tasks only call them; every rejection is a silver-task count *(amended: DLT closures/expectations → §9.2, R19)*.
5. **Dev only, prod-shaped** (R4). The `prod` bundle target is declared and validated, never deployed; no prd environment resource is created; the account-scoped registry lives in `prd/04_peripherals` because shared artifact stores already live there.
6. **Schedules stay `DISABLED`.** The runtime is proven by one workflow-run Fargate task per image (§9.4, M14) *(amended: was one operator `run-task`)*; enabling is a later one-variable ruling.

**Deletion test — the balance.** Dies: `scripts/ci/detect_changes.sh`; the ECR branch and name of `empty_s3_and_ecr.sh` (→ `empty_s3_buckets.sh`, 3 callers updated); `"s3:HeadObject"`; `services/databricks/README.md` §"Not in stack_map"; the "on its own VPS / Nothing in this repository captures" sentences in `AGENTS.md` and `README.md`; `vars.ECR_REGISTRY` (never created); the stale "7 bundles" wording in the explorer. Grows: one infra stack + ~15 IAM statements (justified: the IAM growth closes a latent HIGH with the test that ends its family; the dev lane and the publisher get smaller); one DAB bundle + one parser package (justified: without the package, eleven DLT closures would each hold Latin-1/layout logic with no off-cluster test). The `dm-ethereum` pipeline is untouched (R1).

**Layers affected:** IAM bootstrap and boundary; the prd registry; dev S3/IAM; a new dev ECS + Scheduler stack; the UC stack's home and grants; the infra CI control plane; one new DAB bundle (bronze/silver/gold); the cross-repo contract; constitution §1/§6/§7/§10.

## 2. Cross-workstream couplings

| # | Coupling | Resolution |
|---|---|---|
| K1 | O-2 — no grant before the RED test | `T-I7.1` (bug record + RED test, two commits) precedes `T-I7.2`; AC-1 records both runs |
| K2 | O-3 — capture cannot push, and `dev/03_capture` cannot resolve an image, until the bootstrap is applied and ECR exists | `T-I7.2` → `T-I7.3` verdict → `T-O7.1` apply + publish → `T-I7.4` ECR via prd lane → capture `publish-images.yml` (`T-O7.4a`) → `T-I7.6` plan resolves `<ecr-url>:dev` |
| K3 | O-4 — external-location creation validates the credential against the bucket | `T-I7.5` (bucket + policy widening) applies before `T-I7.7`'s CI apply (`T-O7.3`); `upstreams: [peripherals]` in the map |
| K4 | O-5 — relocating a half-imported stack would leave two homes | `T-I7.7` is blocked by v0.6.0 `T-I.12`'s `No changes`; the `git mv` and the three adds ride one PR |
| K5 | The UC stack's CI plan needs Databricks credentials the infra repo does not hold | `T-O7.2` types the three secrets + the SP application-id variable into the infra `dev` environment before `plan-dev-unity-catalog` first runs; PR-plan jobs otherwise carry no environment |
| K6 | O-6 — bronze needs real partitions | `T-X7.6` is blocked by `T-O7.4` (smoke + one Fargate `run-task`); `T-X7.1..5` proceed on fixtures and `bundle validate` meanwhile |
| K7 | Seam 3 has one producer (capture CI, already shipped) and two consumers (task definitions, the contract doc) | `T-X7.1` pins registry/tag/variable names exactly as capture v0.5.0 CLOSURE §11.1-2 fixed them; `T-I7.6` consumes the same constants via `prd/04` outputs — no third statement |
| K8 | O-9 — two possible homes for `specs/**` | marker flips before C-DAY only through the PM in the legacy tree; after C-DAY all writes in the new explorer; `T-X7.7` runs wherever authority is at that moment |
| K9 | Constitution §10 requires a classification review for every new data source | `T-O7.5` adds the row; until then FRE `posicao_acionaria` is bronze-only (`T-X7.4`) |

Everything else is parallel: WS-I inside `dd-chain-infrastructure`, WS-X inside the new `dd-chain-explorer`, WS-O on settings and live acts.

## 3. WS-I — `dd-chain-infrastructure`

### 3.1 Stacks, keys, map

| Stack | State key | Change |
|---|---|---|
| `prd/00_bootstrap` (operator) | `prd/bootstrap` | + role `gha_capture_publish`; + deploy/read-only grants; + PassRole services; + 3 boundary statements; operator user may assume the writer role; + output |
| `prd/04_peripherals` | `prd/peripherals` | + `ecr.tf`: 3 repos + lifecycle; + outputs |
| `dev/01_peripherals` | `dev/peripherals` | + `module.s3_raw_data`; + writer role + policy; `databricks_dev_s3_policy` widened; + outputs |
| `dev/03_capture` (new) | `dev/capture/terraform.tfstate` | cluster, capacity providers, log group, SG, exec role, 3 task roles, 3 task definitions, scheduler role, 7 schedules |
| `services/databricks` → `dev/04_unity_catalog` | `databricks/unity-catalog/terraform.tfstate` (unchanged) | + external location; + 2 `databricks_grant`; enters `stack_map` |

`stack_map.json` `dev.stacks` order: `peripherals` · `lambda` · `capture` (upstreams `peripherals`, modules `cloudwatch_logs`) · `unity_catalog` (upstreams `peripherals`). `$comment` records the `prd/peripherals` remote-state edge (ECR URLs) like the bootstrap edge — documented, never modelled in `upstreams`.

### 3.2 Bootstrap statements (`T-I7.2`)

- **`gha_capture_publish`** — trust `AssumeRoleWithWebIdentity`, `aud = sts.amazonaws.com`, `sub ∈ {repo:<owner>/<capture-repo>:environment:dev, …:environment:production}` (`var.github_capture_repo`, default `dd-chain-capture`); boundary; `gha_self_mutation_deny`; policy: `ResourcelessEcrAuthToken` (`ecr:GetAuthorizationToken` on `"*"`), `CaptureEcrPushPull` (`BatchCheckLayerAvailability, GetDownloadUrlForLayer, BatchGetImage, InitiateLayerUpload, UploadLayerPart, CompleteLayerUpload, PutImage, DescribeImages, ListImages` on `local.capture_ecr_repository_arns` — three exact ARNs from `var.capture_images`).
- **Deploy roles add** `ProjectEcr` (`ecr:*` on `local.ecr_repository_arns`), `ProjectEcsClusters` (`ecs:*` on `local.ecs_cluster_arns`), `ProjectEcsTaskDefTags` (`ecs:TagResource, UntagResource, ListTagsForResource` on `local.ecs_task_definition_arns`), `ProjectScheduler` (`scheduler:*` on `local.scheduler_schedule_arns`), `ProjectEc2SgCreate` (`ec2:CreateSecurityGroup` on SG + VPC ARNs), `ProjectEc2SgTagOnCreate` (`ec2:CreateTags` cond `ec2:CreateAction = CreateSecurityGroup`), `ProjectEc2SgMutate` (`Authorize/RevokeSecurityGroupEgress, RevokeSecurityGroupIngress, DeleteSecurityGroup, CreateTags, DeleteTags` cond `aws:ResourceTag/project = dd-chain-explorer`), `ResourcelessApis` (`ecr:GetAuthorizationToken, ecs:RegisterTaskDefinition, DeregisterTaskDefinition, DescribeTaskDefinition, ListTaskDefinitions, ec2:DescribeVpcs, DescribeSubnets, DescribeSecurityGroups, DescribeSecurityGroupRules, DescribeNetworkInterfaces` on `"*"`); `ProjectIamPassRole` cond `iam:PassedToService` += `ecs-tasks.amazonaws.com`, `scheduler.amazonaws.com`.
- **Read-only role adds** `ecs:Describe*, List*` on clusters; `ecr:Describe*, Get*, List*` (minus auth token) on repos; `scheduler:Get*, List*`; `ResourcelessReads` (`ecs:DescribeTaskDefinition, ListTaskDefinitions, ec2:Describe*`).
- **Boundary adds** `BoundaryProjectEcr`, `ResourcelessEcrAuthToken`, `BoundaryProjectEcsRunTask` (`ecs:RunTask` on task-definition ARNs), `BoundaryCapturePassRoleToEcs` (`iam:PassRole` on `local.capture_task_role_arns` = `role/dm-chain-explorer-capture-*`, cond `iam:PassedToService = ecs-tasks.amazonaws.com`).
- **`operator_debug_user_assume_only`** resource = `[operator_debug_role_arn, capture_dev_writer_role_arn]`; verb stays `sts:AssumeRole`. Runbook `operator-debug-credential.md` states the one write now reachable (`raw/` on the dev raw bucket, behind MFA, via a second role).
- New locals added to `ALLOWED_RESOURCE_LOCALS`: `ecr_repository_arns`, `ecs_cluster_arns`, `ecs_task_definition_arns`, `capture_task_role_arns`, `ec2_security_group_arns`, `ec2_vpc_arns`, `capture_ecr_repository_arns`, `capture_dev_writer_role_arn`. Deleted: `"s3:HeadObject"` in `services/prd/06_lambda/lambda_contracts_ingestion.tf`.
- **`publish_oidc_vars.sh --target infra|explorer|capture`**: `infra` = the existing three maps; `explorer` = `gha_artifacts_publish_role_arn → AWS_ARTIFACTS_PUBLISH_ROLE`; `capture` = `gha_capture_publish_role_arn → AWS_CAPTURE_PUBLISH_ROLE`.

### 3.3 Stack policies and resources

- **`dev/03_capture` exec role:** `ecr:GetAuthorizationToken` `"*"`; pull actions on the 3 repo ARNs; `logs:CreateLogStream, PutLogEvents` on the log group. **Task role per image:** `s3:PutObject, GetObject, AbortMultipartUpload` on `<bucket>/raw/<source>/*`; `s3:ListBucket` cond `s3:prefix StringLike raw/<source>/*`. **Scheduler role:** `ecs:RunTask` on `task-definition/dm-chain-explorer-capture-dev-*:*` cond `ecs:cluster = <cluster>`; `iam:PassRole` on `[exec, task[*]]` cond `iam:PassedToService = ecs-tasks`.
- **Writer role (`dev/01_peripherals`):** same shape on `raw/*`; trust = bootstrap `operator_debug_user_arn` with `Bool aws:MultiFactorAuthPresent = true`; `max_session_duration = 3600`; boundary. **Bucket:** `module.s3_raw_data` (`../../modules/s3`), `bucket_name = "dm-chain-explorer-dev-raw-data"`, module PAB + SSE-S3, one lifecycle rule `raw-intelligent-tiering` (prefix `""`, transition day 0 `INTELLIGENT_TIERING`), **no expiration**; `module.s3_ingestion` untouched.
- **Cluster and network:** `dm-chain-explorer-capture-dev`, `containerInsights = disabled`, capacity providers `FARGATE` + `FARGATE_SPOT` (Spot default, weight 1); data sources `aws_vpc.default`, `aws_subnets.default` (`default-for-az`); SG no ingress, egress tcp 443 (+80 only if a redirect is observed), tag `project = dd-chain-explorer`; log group `/apps/dm-chain-explorer-capture-dev`, 14 d (module `cloudwatch_logs`).
- **Task definitions:** family `dm-chain-explorer-capture-dev-<image>`, `awsvpc`, `FARGATE`, `X86_64`, cpu/memory from `var.capture_images` (256/512; cvm 512/1024), container `name = <image>`, `image = "${prd_peripherals.capture_ecr_repository_urls[<image>]}:${var.image_tag}"`, env `RAW_BUCKET`, `RAW_SOURCE`, `ENVIRONMENT`, `awslogs` prefix `<image>`, no command.
- **Schedules:** `dm-chain-explorer-capture-dev-<job>`, group `default`, UTC, window OFF, `state = var.schedules_enabled ? "ENABLED" : "DISABLED"` (default `false`), target cluster + scheduler role, `ecs_parameters` (task definition without revision, `FARGATE_SPOT`, default-VPC subnets, the SG, `assign_public_ip = true`, `LATEST`, count 1), `input` = `containerOverrides` `command: [<entrypoint>]`. Jobs: `b3_cotahist_daily`, `b3_ibov_portfolio_daily`, `b3_consolidated_files_daily` (`cron(30 0 * * ? *)`); `cvm_cadastro_fca`, `cvm_statements_dfp_itr`, `cvm_fre_ipe` (`cron(0 3 ? * SUN *)`); `bcb_macro_series` (`cron(0 1 * * ? *)`). Cadence change later = variable edit.
- **ECR (`prd/04_peripherals`, `ecr.tf`):** `aws_ecr_repository.capture[<image>]` = `dm-chain-explorer-capture/<image>`, `image_tag_mutability = MUTABLE`, `scan_on_push`, `force_delete = true`; lifecycle rule 1 untagged > 1 day expire, rule 2 `imageCountMoreThan 10` expire; outputs `capture_ecr_repository_urls`, `capture_ecr_repository_arns`; variables `capture_images` (same default as bootstrap), `capture_ecr_namespace`.
- **UC stack:** `databricks_external_location.dm_dev_raw_data` (`s3://dm-chain-explorer-dev-raw-data/`, `credential_name = dm_dev_s3_credential`); `databricks_grant.dev_catalog_sp` (catalog `dev`; `USE_CATALOG, USE_SCHEMA, CREATE_SCHEMA, CREATE_TABLE, CREATE_MATERIALIZED_VIEW, SELECT, MODIFY`); `databricks_grant.dev_raw_data_sp` (`READ_FILES` on the location); `var.databricks_dev_sp_application_id` with no default (`test_no_secret_defaults`).

### 3.4 Contract tests (`T-I7.1`, `T-I7.2`, `T-I7.6`, `T-I7.8`)

Extended: `ALLOWED_RESOURCE_LOCALS` (+8); `test_every_allow_statement_resource_is_project_scoped` accepts `"*"` only when `sid` starts with `Resourceless` and every action ∈ `RESOURCELESS_ACTIONS`; `test_ci_boundary_grants_no_iam_action` → exactly one `iam:` statement, `iam:PassRole`, conditioned to `ecs-tasks`, scoped to `capture_task_role_arns`; `test_all_four_gha_roles…` → five; `test_pass_role_requires_passed_to_service_condition` (+2 services); `test_operator_debug_user_is_assume_only` (2 resources, one verb); `test_every_project_iam_role_sets_permissions_boundary` (5 → 9); `test_stack_map.py` capture → `cloudwatch_logs` edge; `test_map_equals_on_disk_survivors` (passes once the UC stack moves); `test_destroy_all_stack_set_equals_map_destroyable_set` (RED until the destroy-all jobs exist); `test_publish_oidc_vars_tf_output_names_exist_in_bootstrap_outputs` (every `[key]=VAR` pair, 5); `test_deploy_apply_path.py` dev-lane case (stub terraform: apply order = map order; unchanged stacks skipped; `FORCE=true` applies all).

Added: `test_every_aws_service_namespace_declared_in_services_is_granted` (§1.1 — the resource→namespace mapping is a small table in the test with one row per `aws_<svc>` prefix seen on disk; an unmapped prefix fails the test, unknown is never silently allowed), `test_capture_publish_permissions_grant_only_ecr_push_pull`, `test_capture_images_list_equal_in_bootstrap_and_prd_peripherals`, `test_schedules_default_disabled` (`variables.tf` default `false`), `test_task_role_policies_are_prefix_scoped` (every `s3:PutObject` resource under `03_capture` ends in `/raw/${…source}/*`), `test_schedule_override_names_its_container` (each schedule's `containerOverrides[0].name` equals its task definition's container name).

### 3.5 CI (`T-I7.8`)

Map-driven and automatic: `plan_env.sh`, `deploy_env.sh prd`, `destroy_env.sh dev` (reverse order), `changed_stacks.py` (emits `dev_capture`, `dev_unity_catalog`). `deploy_env.sh dev` gains `deploy_dev()`: for each id in `stack_list.sh dev`, if `changed_stacks.py dev <id>` exits 0 or `FORCE=true` → init, validate, `tf_plan.sh`, apply. One `dev-deploy` job replaces `dev-detect-changes` + the two static dev jobs in `deploy_cloud_infra.yml`; `detect_changes.sh` is deleted. Static edits: `plan_on_pr.yml` (+ outputs `dev_capture`, `dev_unity_catalog`; + jobs `plan-dev-capture`, `plan-dev-unity-catalog` — the latter `environment: dev`), `drift_detection.yml` (+2 jobs, +2 summary rows), `destroy_all_cloud_infra.yml` (+ `dev-destroy-capture`, `dev-destroy-unity-catalog` before `dev-destroy-peripherals`). Posture unchanged: SHA-pinned actions, `persist-credentials: false`, runner hardening, `-lock=false` on read-only plans, OIDC preflight on every role-assuming job.

**Verification.** `terraform fmt -check -recursive`, `validate`; per-stack CI plan; `aws iam get-role`/`simulate-principal-policy`; `aws ecr describe-repositories`; `aws s3api` bucket probes; `aws scheduler list-schedules`; `databricks grants get-effective`, `external-locations validate`; `pytest scripts/ci/tests`; `actionlint`; `zizmor`. ACs: AC-1..AC-10.

## 4. WS-X — `dd-chain-explorer` *(superseded by §9.2 — R19; §4.2 parsers stand unchanged)*

### 4.1 Bundle shape (`T-X7.1`)

`apps/dabs/dlt_market_data/{databricks.yml, VERSION, resources/dlt/pipeline_market_data.yml, resources/workflows/workflow_trigger_market_data.yml, src/market_data/{pipeline.py, parsers/…}}`. Variables: `catalog`, `raw_data_bucket`, `dlt_development`. `dev`: `run_as` the dev SP, `[dev] ` prefix, `catalog=dev`, `raw_data_bucket=dm-chain-explorer-dev-raw-data`, trigger job schedule `PAUSED`. `prod`: `mode: production`, no `run_as`, no `workspace.host`, `catalog=prd`, `raw_data_bucket` = the prd raw bucket name **as a placeholder** (no prd resource is created; revisited when prod is defined; `deploy-dabs` on `prod` already sits behind the `production` environment gate and R4 forbids a prod deploy this release). Pipeline: `name: dm-market-data`, `catalog: ${var.catalog}`, `target: b_market`, `serverless: true`, `continuous: false`, `channel: CURRENT`, configuration `raw.s3.bucket`, `catalog`; tables in other schemas are named `s_market.<t>` / `g_market.<t>` (the `dm-ethereum` pattern). Trigger job `dm-trigger-market-data` with one `pipeline_task`. The pipeline source imports the parsers as workspace files shipped with the bundle (`libraries: file:` entries beside the notebook); no `%pip`, no wheel.

### 4.2 Parsers (`T-X7.2`) — interface, one function per format

`parse_cotahist_line(line: bytes) -> Quote | None` (record `01` only; 245 chars enforced; `FATCOT`-aware ÷100); `iter_zip_members(content: bytes, pattern) -> Iterator[(name, bytes)]`; `iter_latin1_csv(content: bytes, *, delimiter=";", skip_status_line=False) -> Iterator[dict]` (decodes ISO-8859-1, strips CRLF, decimal comma → `Decimal` on request); `parse_index_portfolio(content: bytes) -> (header, rows)` (requires `header.date`, `results[].cod/part/theoricalQty`; raises `PayloadShape`); `parse_sgs(content: bytes) -> Iterator[(date, Decimal)]` (`dd/MM/yyyy`, string `valor`); `dedupe_latest_version(rows, key=(cnpj, dt_refer, statement, grupo_dfp)) -> rows` (max `VERSAO`); `ytd_to_quarter(rows)` (ITR YTD differencing; Q4 = DFP − 9M; dedupe by max `VERSAO` first, difference within the same cohort; a missing prior quarter yields NULL, never a full-year value). All pure, `Decimal`-typed, no Spark import, no I/O.

### 4.3 Medallion (`T-X7.3`..`T-X7.5`)

- **Bronze reader:** `spark.readStream.format("cloudFiles").option("cloudFiles.format", "binaryFile").option("cloudFiles.schemaLocation", …).load(f"s3://{bucket}/raw/{source}/{dataset}/")`, `_manifest.json` excluded by a filter on `path` (`~col("path").endswith("/_manifest.json")`); derived columns via regex on `path`; `content_sha256 = sha2(content, 256)`. `raw_manifests`: `cloudFiles.format = json` over `raw/*/*/ingest_date=*/_manifest.json` with the `raw-manifest-v1` schema declared explicitly (`files` = array of struct). Free Edition / serverless limits are respected by size: COTAHIST annual ZIPs ≤ 90 MB, CVM ZIPs ≤ 13 MB; the first update runs on one small partition (`bcb/sgs`).
- **Silver columns.** `b3_quotes`: `data_pregao, codbdi, codneg, tpmerc, nomres, especi, preabe, premax, premin, premed, preult, preofc, preofv, totneg, quatot, voltot, codisi, dismes, ingest_date`. `b3_ibov_portfolio`: `date, cod, asset, type, part, theoricalQty, reductor`. `b3_instruments`: `rpt_dt, tckr_symb, isin, scty_ctgy_nm, crpn_nm, mkt_cptlstn, corp_govn_lvl_nm, sgmt_nm`. `cvm_companies`: `cnpj_cia, denom_social, cd_cvm, sit, setor_ativ, categ_reg, controle_acionario, auditor` (latest `ingest_date`). `cvm_fca_securities`: `cnpj, codigo_negociacao, mercado, segmento, data_inicio_negociacao`. `cvm_statements`: `cnpj, cd_cvm, dt_refer, versao, statement ∈ {dfp, itr}, grupo_dfp, ordem_exerc, dt_ini_exerc, dt_fim_exerc, cd_conta, ds_conta, vl_conta, st_conta_fixa`. `cvm_capital_composition`: `cnpj, dt_refer, versao, qt_acao_ordin, qt_acao_pref, qt_acao_total, qt_tesouro_ordin, qt_tesouro_pref, qt_tesouro_total`. `bcb_series`: `code, date, value`.
- **Gold account codes** (`ST_CONTA_FIXA = S`, consolidated): revenue `3.01`, gross `3.03`, EBIT `3.05`, net income `3.11`; assets `1`, current assets `1.01`, cash `1.01.01 + 1.01.02`, current liabilities `2.01`, loans `2.01.04 + 2.02.01`, equity `2.03`; D&A from `DFC_MI` adjustment lines (mapping validated on ≥ 3 fixture companies and recorded in the pipeline source). Ratios use market cap at the last trading day ≤ `dt_refer` from `company_daily_price`; `roic = ebit × (1 − 0.34) / (equity + net debt)`. Every division by a NULL/zero denominator yields NULL.

### 4.4 Tests and CI (`T-X7.2`, `T-X7.5`)

`tests/dabs/test_market_data_parsers.py` — intent `CONTRACT — SPEC v0.7.0 X2/AC-11`, size small; fixtures in `tests/dabs/fixtures/market_data/` (one COTAHIST `01` line, a Latin-1 `;` snippet with `ç`/`ã`, a consolidated header + 2 rows, an indexProxy JSON page, an SGS JSON array, a DFP/ITR snippet pair for YTD differencing) — synthetic or truncated public data, no personal identifier. `test_bundle_targets_contract.py::test_seven_bundles…` becomes `test_eight_bundles…`. `test_dlt_expectations_contract.py` picks up the new pipeline source automatically or is extended to. Makefile: `dabs_run_dlt_market_data`. CI: no new job — `quality` runs the parsers, `bundle-validate-dev` validates the eighth bundle.

**Verification.** `pytest tests -p no:cacheprovider` (no `pyspark`); `make dabs_validate_all TARGET=dev`; `databricks bundle validate -t prod` (CI on `main`); `bundle summary -t dev`; `SHOW TABLES`; a `SELECT` joining `b_market.bcb_sgs` to `raw_manifests` on `content_sha256`. ACs: AC-11..AC-15.

## 5. WS-O — operator-only *(amended: T-O7.2/7.3/7.4(b,c) superseded by the trust seed and the chain, §9.4-9.5)*

Ordered by K2/K3/K5/K6: `T-O7.1` bootstrap apply + `publish_oidc_vars.sh --target capture` (after the `T-I7.3` verdict) → `T-O7.2` infra `dev` environment secrets + SP application-id variable → `T-O7.3` dispatch the first dev-lane apply of `unity_catalog` (exactly 3 adds) → `T-O7.4` first landing (capture `publish-images.yml` on `develop`; `make batch-smoke-real` via the writer role with MFA; one `aws ecs run-task` of `bcb-sgs macro_series` per the backfill runbook) → `T-O7.5` constitution amendment (confirmed before the product-engineer writes it). No agent runs any of these; agents author inputs and verify outcomes.

## 6. Technical risks (beyond SPEC §10)

| Risk | Handling |
|---|---|
| `ec2:CreateSecurityGroup` cannot be tag-conditioned at create time | `ProjectEc2SgCreate` on SG + VPC ARNs and `ProjectEc2SgTagOnCreate` with `ec2:CreateAction`; mutation statements are tag-conditioned |
| Scheduler `input` JSON vs task-definition container name mismatch | container `name = <image>`; `test_schedule_override_names_its_container` |
| `databricks_grant` singular import if v0.6.0 T-X.8(a) was hand-applied first | import `catalog/dev/<principal>`; a hand grant becomes Terraform-owned, never re-created |
| `pathGlobFilter` cannot express "not `_manifest.json`" | filter on `path` after load; `raw_manifests` reads the complementary set |

## 7. Rollback

| Step | Rollback |
|---|---|
| Bootstrap delta (`T-O7.1`) | re-apply `00_bootstrap` at the previous commit; one apply |
| ECR (`T-I7.4`) | `terraform destroy` on the three repos (`force_delete`); images are rebuildable |
| Dev raw landing (`T-I7.5`) | remove bucket/role blocks and re-apply (bucket must be empty — operator deletes objects first) |
| `dev/03_capture` (`T-I7.6`) | `destroy_env.sh dev` removes it before peripherals; nothing else depends on it |
| UC relocation (`T-I7.7`) | `git mv` back; the key is unchanged, state untouched; the three adds are `terraform destroy`-able without touching imported objects |
| Dev lane rewrite (`T-I7.8`) | revert the commit; the static jobs return |
| Bundle deploy (`T-X7.6`) | `databricks bundle destroy -t dev` in the bundle directory; Ethereum bundles were never deployed |
| Constitution (`T-O7.5`) | revert the commit; operator-confirmed both ways |

## 8. Version axis and the v0.6.0 overlap

Root `VERSION` and every `apps/dabs/*/VERSION` read `0.7.0` on `feature/0.7.0` in both repositories (constitution §3.4); `feature/0.6.0` keeps `0.6.0` until v0.6.0 ships. v0.6.0 `T-X.8(a)` (hand grants on catalog `dev`) is superseded by `T-I7.7`: if it was already executed, the grants are imported, not re-created. v0.6.0 `T-I.12` remains the gate of `T-I7.7` (K4). Nothing in this PLAN edits a v0.6.0 artifact.

## 9. Amendment 2026-09-23 — R18-R26

### 9.1 Deletion test — the balance of the amendment

**Dies:** the DLT pipeline, its trigger job and `dlt_market_data/`; the seven Ethereum bundles; `apps/lambda/`, `utils/` (`dm_chain_utils`), `publish-artifacts.yml`, dashboard tooling (`render_dashboard_templates.sh`, `deploy_all.sh`, `check_versions.sh` if it only walks the dead bundles); the `bundles` dispatch filter; infra `dev/02_lambda`, `prd/06_lambda`, modules `s3_ingestion` + `dynamodb` (dev), `s3_artifacts` + `dynamodb` (prd), `gha_artifacts_publish`, `resolve_*.sh` (6), `publish_oidc_vars.sh --target explorer`; `changed_files_since_base()`, `FORCE`, the `force_apply` and `destroy_ack` inputs; `docs/runbooks/00-bootstrap-apply.md` (→ the seed runbook). **Grows:** three PySpark task modules (the DLT source is rewritten, not wrapped — net smaller: no decorators, no `dlt` shim), one seed script, one capture-run workflow, one dispatch step per lane, two temporary retirement steps that die in the teardown's delete commit. Bug-surface verdict: the chain loses its two hand-kept enumerations (bundle filter, git-diff change detection — the M11 cause) and one whole seam; it gains no second code path.

### 9.2 WS-X — bundle `job_market_data` (X1-X7, R19/R20/R24)

**Layout.** `apps/dabs/job_market_data/{databricks.yml, VERSION, resources/job_market_data.yml, resources/schemas.yml, src/dm_market_parsers/** (git mv, byte-identical), src/market_data/{bronze.py, silver.py, gold.py, _spark.py}}`. Variables `catalog`, `raw_data_url` (`s3://dm-chain-explorer-dev-raw-data/raw/`). `dev`: `run_as` dev SP, `[dev] ` prefix, `catalog=dev`; `prod`: declared, placeholder URL, never deployed (R18). `schemas.yml` declares `b_market`, `s_market`, `g_market` — the bundle owns them, so destroy is complete.

**Job.** One job `dm-market-data`; three `spark_python_task`s `bronze → silver → gold` (`depends_on`, `run_if: ALL_SUCCESS`), each `environment_key: default` (serverless, client `2`, no dependencies — parsers ride as workspace files; each entrypoint puts its own `src/` on `sys.path` from `__file__`). No `pipelines:`, no `dlt` import, no `%pip`, no wheel. `max_concurrent_runs: 1`, `queue.enabled: true`.

**Trigger (R20).** `trigger.pause_status: UNPAUSED` (dev), `file_arrival.url: ${var.raw_data_url}`, `min_time_between_triggers_seconds: 300`, `wait_after_last_change_seconds: 120` (a capture run writes data then `_manifest.json` last — the wait coalesces one partition into one fire). A fire that sees no new manifest is a counted no-op, never a failure. **File-count cap decision:** without file events a file-arrival URL may hold at most 10,000 files; the landing never expires (R14). Dev volume is ~10-30 objects/day, so the cap is ≥ 1 year away; v0.7.0 does **not** enable file events (it would widen the hand-made credential's IAM role with SNS/SQS/notification grants). Bound instead: the infra drift lane counts `raw/` objects and fails at 8,000 — a signal, not a silent stop. File events are the recorded remedy for prod (`prod-environment-official-account`); the operator may reverse it.

**Bookkeeping and idempotency.** `b_market.raw_manifests` (explicit `raw-manifest-v1` schema + `manifest_sha256`, `bronze_at`, `silver_at`, `rejected_parse`, `rejected_sha`, `rejected_versao`), MERGE key `(source, dataset, ingest_date, manifest_sha256)`.
- **bronze:** list `raw/*/*/ingest_date=*/_manifest.json`; keep manifests whose sha256 is not in `raw_manifests`; read exactly the manifest's `files[]` via `binaryFile`; MERGE each dataset table on `content_sha256` (insert-only); upsert the manifest row with `bronze_at` **last** — a crash re-processes the partition and the MERGE adds nothing.
- **silver:** rows of `raw_manifests` with `silver_at IS NULL`; parse through `dm_market_parsers`; a parse failure, a `content_sha256 ∉ files[].sha256` or a NULL `versao` is dropped and counted into the manifest row; MERGE on the natural key; set `silver_at`. Keys: `b3_quotes (data_pregao, codneg, tpmerc)`; `b3_ibov_portfolio (date, cod)`; `b3_instruments (rpt_dt, tckr_symb)`; `cvm_companies (cnpj_cia)` (update only from a newer `ingest_date`); `cvm_fca_securities (cnpj, codigo_negociacao, mercado)`; `cvm_statements (cnpj, dt_refer, statement, grupo_dfp, ordem_exerc, cd_conta)` updated only when `source.versao ≥ target.versao`, `ORDEM_EXERC = ÚLTIMO`; `cvm_capital_composition (cnpj, dt_refer)` same `versao` rule; `bcb_series (code, date)`.
- **gold:** the three §4.3 tables recomputed by `CREATE OR REPLACE TABLE … AS` (overwrite), NULL-never-fabricate; the task publishes `rows` per layer and the three rejection sums as task values — the AC-22 evidence is read from the run output, no SQL warehouse needed.
- **Second fire** over the same partition: bronze finds no new manifest, silver has no `silver_at IS NULL` row, gold overwrites identical inputs → no count changes (AC-22).

**Tests.** Parser suite unchanged (41). `test_bundle_targets_contract.py`: every `apps/dabs/*` dir is `job_market_data` or listed in `apps/dabs/RETIRED` (T-X7.8), tightened to exactly one bundle when the list dies (T-X7.10); job contract — 1 job, 3 tasks in order, every task serverless, `file_arrival` present, `max_concurrent_runs = 1`. `test_no_dlt_import` greps `apps tests`. Pure helpers that decide keys/rejections live beside the parsers and are unit-tested; Spark I/O stays in `_spark.py` (thin, untested off-cluster by design).

### 9.3 Ethereum and lambda-seam teardown (X8, I10, R21, R23, R25, O-10)

**Order (destroy before delete; AWS before Databricks-live).**
1. **Infra destroy commit (T-I7.12):** `dev/02_lambda` and `prd/06_lambda` keep only backend + provider (the lane's plan shows every resource destroyed); `dev/01`: modules `s3_ingestion`, `dynamodb` removed, `databricks_dev_s3_policy` narrowed to the raw bucket; `prd/04`: modules `s3_artifacts`, `dynamodb` removed. A `retire` job (`scripts/ci/retire.sh` + `scripts/ci/retired_objects.json`, idempotent: absent = pass) runs **before** the stack applies: empties `dm-dev-ingestion` and the prd artifacts bucket (reusing `empty_s3_buckets.sh`), then the foreign-state destroy below. The lanes (§9.4) apply dev on merge and prd behind the `production` approval.
2. **Infra delete commit (T-I7.13), after the run ids exist:** delete both stack dirs, their `stack_map.json` entries, `resolve_*.sh`, `retire.sh` + list, `gha_artifacts_publish` and every Lambda/DynamoDB/artifacts statement in the bootstrap (reaches AWS at the next seed run), `--target explorer`; tests follow (namespace coverage stays green because the declaring stacks are gone; "five GHA roles" → four).
3. **Explorer retire commit (T-X7.8, PR-α):** `apps/dabs/RETIRED` lists the eight bundles; the CI deploy job runs `databricks bundle destroy -t dev --auto-approve` for each listed dir still in the tree **before** any deploy, then drops the stateless UC objects no state owns — external location `dm-dev-ingestion` and the seven schemas (`DROP SCHEMA … CASCADE` / `external-locations delete`, idempotent). PR-α reaches `develop` alone.
4. **Explorer delete commit (T-X7.10, PR-β), after PR-α's run id:** the eight dirs, `apps/lambda/`, `utils/`, `publish-artifacts.yml`, dashboard tooling, their tests, `RETIRED` and the retire step. `job_market_data` rides PR-β, so the DLT pipeline is gone before the job exists — no DLT table shadows a job table (O-10).

**Where ECR `stream`/`connect` live (R25) — located.** The repositories are `dd-chain-capture-stream` and `dd-chain-capture-connect`, tracked in the Terraform state key **`capture/ecr/terraform.tfstate` inside this project's state bucket** (backend in `dd-chain-capture` history, `infra/aws/main.tf` at `1a559df`; the source `infra/aws/*.tf` was deleted from `dd-chain-capture` in `137d6f2`, so today the state has **no source and no lane in any repository**). The state also holds Roles Anywhere + KMS (11 resources, backlog `capture-ecr-state-and-kms-ownership-transfer`). Removal stays state-consistent: `retire.sh` inits a source-less config (`services/retired/capture_ecr/`, backend + `aws` provider only, never in `stack_map.json`) and runs `terraform destroy -target=aws_ecr_repository.stream -target=aws_ecr_repository.connect`; the other nine resources are untouched. Fallback, only if Terraform refuses (provider aliases in state): `aws ecr delete-repository` + `terraform state rm` of the two addresses in the same step — the R25 retirement-job path. The prd deploy role's scope is `dm-*`, so T-I7.10 adds one exact-ARN statement (`ecr:DescribeRepositories, ListImages, BatchDeleteImage, DeleteRepository` on the two ARNs, deploy policy + boundary) that dies in T-I7.13.

### 9.4 The automated chain (I11, X9, R26)

| Step | Trigger | Workflow · job | Replaces |
|---|---|---|---|
| 1 | `push` to `develop` (infra) | `deploy_cloud_infra` · `retire` (while listed) → `dev-deploy` → `prd-plan` → `prd-apply` (`environment: production`, runs only when a prd plan exits 2) | M11 (dev), M10 |
| 2 | step 1 green | same run · `signal-explorer`: App token → `repository_dispatch infra-dev-applied` to explorer | M12 |
| 3 | `push` to `develop` or `infra-dev-applied` (explorer) | `ci` · `deploy-dev` (retire while listed → `bundle deploy -t dev`) → `signal-infra`: `explorer-dev-deployed` | M11 (bundle filter), M13 prerequisite |
| 4 | `explorer-dev-deployed` (infra) | `capture_run` · one Fargate task per image (`bcb_macro_series`, `b3_cotahist_daily`, `cvm_cadastro_fca`) on `FARGATE_SPOT`, `ecs wait tasks-stopped`, exit 0 + `_manifest.json` present → `repository_dispatch capture-landed` | M14 |
| 5 | file arrival | Databricks job `[dev] dm-market-data` | M13 |
| 6 | `capture-landed` (explorer) | `ci` · `e2e-verify`: waits for the `FILE_ARRIVAL` run, reads task values (12/8/3, rows, rejections), fails on 0 gold rows or any sha rejection | AC-22 evidence |

- **Change detection (M11).** Git-diff detection dies: every map stack is planned with `-detailed-exitcode` and applied only on exit 2 — the plan *is* the detector, identical on push and on dispatch; `FORCE`/`force_apply`/`destroy_ack` go. The prd destroy acknowledgement is the `production` approval over a plan summary that lists destroys.
- **Default branch = `develop`** in infra and explorer (seed S3). `workflow_dispatch`, `repository_dispatch` and `schedule` all read the default branch, so hand `develop → main` PRs (M10) are unnecessary and weekly drift plans the deploy branch (M15). Promote PRs `develop → main` are unchanged.
- **GitHub App (R26).** Created by the seed via the manifest flow; installed on the 3 repos; permissions `contents: write` (dispatch) + `metadata: read`. Each signalling job mints a 1-hour token with `actions/create-github-app-token` (SHA-pinned) scoped to the one target repository; key in secret `CHAIN_APP_PRIVATE_KEY`, id in variable `CHAIN_APP_ID` (infra, explorer). No PAT.
- **Loops.** Step 3 on an explorer push also fires step 4 — each dev deploy is proven by one landing; step 4 never signals infra, so the chain terminates. `concurrency` groups serialise each lane.
- Capture keeps its own push-triggered `publish-images.yml`; the registry now outlives every capture push, so M12's capture half is retired by structure — no edit in `dd-chain-capture`.

### 9.5 The trust seed (M1, M3-M8, R26, O-8, O-11)

`scripts/seed/trust_seed.sh` + `docs/runbooks/trust-seed.md` (replaces `00-bootstrap-apply.md`), run by the operator with admin AWS (MFA), `gh` as repo admin and Databricks workspace-admin. Every step reads before it writes; a second run makes no change and echoes no secret (values move stdin → `gh secret set`, never argv, never logs).

| Step | Does | M |
|---|---|---|
| S1 | `terraform apply` `prd/00_bootstrap` (plan-then-apply; no change = skip) | M1 |
| S2 | `publish_oidc_vars.sh --target infra\|capture` | M3 |
| S3 | GitHub settings per repo: environments `dev`/`production` (reviewer on `production`), default branch `develop`, capture `develop` exists | M4, M10, M15 |
| S4 | Databricks dev SP OAuth secret: reuse if the stored one authenticates, else mint | M6 |
| S5 | secrets/variables: infra + explorer env `dev` `DATABRICKS_HOST/CLIENT_ID/CLIENT_SECRET`, `TF_VAR_databricks_dev_sp_application_id` | M5 |
| S6 | UC bootstrap as workspace admin: ensure Free-Edition-only catalog `dev` + credential `dm-dev-s3-credential`; SP `MANAGE` on `dev`, `CREATE_EXTERNAL_LOCATION` on the credential **and on the metastore** (owned by "System user"; only `workspace-admins` can grant — the current AC-7 blocker), `MANAGE` on location `dm-dev-ingestion` (so T-X7.8 can drop it) | M7, M8 |
| S7 | GitHub App: create (manifest flow, one browser confirm), install on the 3 repos, store key/id | R26 |

Tests: `scripts/seed/tests/` runs the script against stub `terraform`/`gh`/`databricks`/`aws` binaries on `PATH` (fakes recording calls): run 1 performs each step, run 2 over the recorded state issues zero mutating calls, and no recorded argv or output contains the fake secret. `shellcheck` clean.

**Not seedable — operator account act (blocker B1):** the Free Edition organisation refuses compute (warehouse, pipeline `RESOURCE_EXHAUSTED`, jobs create 403 "organization cancelled or not active"). Every Databricks-live task (T-X7.12, T-V7.1) is blocked by it; nothing is faked.

### 9.6 M-ledger map

| M | Replacement |
|---|---|
| M1 | seed S1 |
| M2 | retired one-off — hml environment gone (ADR-10) |
| M3 | seed S2 |
| M4 | seed S3 |
| M5 | seed S5 |
| M6 | seed S4 |
| M7 | seed S6 (catalog, credential, metastore grants) |
| M8 | seed S6 for Free-Edition-only objects; `dm-dev-ingestion` location → explorer retire step |
| M9 | retired one-off; every remaining object → CI `bundle destroy` / retire steps |
| M10 | seed S3 default branch `develop` |
| M11 | plan-as-detector lanes on `push`; `force_apply`, `destroy_ack`, bundle filter deleted |
| M12 | lambda seam deleted (R23); ECR precedes capture pushes; `repository_dispatch` chain |
| M13 | file-arrival trigger |
| M14 | `capture_run` workflow |
| M15 | seed S3 — drift runs on the default = deploy branch |

### 9.7 Risks added

| Risk | Handling |
|---|---|
| Databricks org inactive (B1); metastore grant (B2) | B1 operator account act; B2 seed S6; live tasks ordered last and blocked on both |
| Foreign-state targeted destroy fails on aliased providers | fallback in the same step (delete + `state rm`), evidence in the run log |
| Emptying `dm-dev-ingestion`/artifacts deletes data | Ethereum data has no consumer (R21); buckets listed by exact name, never glob |
| `DROP SCHEMA CASCADE` on a non-empty schema | the seven are empty (R21 inventory); the step logs table counts first |
| Capture run on every explorer deploy costs Fargate Spot minutes | three short tasks per deploy; accepted for dev |
| `prd-apply` from `develop` | unchanged practice (`branch_guard.sh` already requires `develop`); `check_prd_version.sh` and the `production` approval remain |
