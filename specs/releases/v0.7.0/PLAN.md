# PLAN — Release v0.7.0 — Market-data restart: batch capture runtime + medallion landing

> **Status:** Aprovado
> **Release ID:** v0.7.0
> **Owner:** product-engineer — approved under the operator standing order of 2026-09-13 ("faça tudo que puder, avance") after ratifying grill rulings R1-R17
> **Depends on:** SPEC.md v0.7.0 (`Aprovado`)
> **Branch:** `feature/0.7.0` in `dd-chain-infrastructure` and the new `dd-chain-explorer`, each stacked on `feature/0.6.0` (`DADAIA.md` §4, `dd-gitflow-default`); merges into `develop` only after v0.6.0's candidate merge (SPEC O-1)
> **Amended:** 2026-09-23 — operator rulings R18-R26 (SPEC §11): §9 replaces the DLT design of §4 with the batch job `job_market_data`, sequences the Ethereum and lambda-seam teardown, designs the trust seed and the event-chained lanes, and maps M1..M15; §1.4, §1.6, §2 K6, §3.5 `FORCE`, §4, §5, §7 rows `T-X7.6`/`T-O7.x` superseded where §9 says so.
> **Amended (2):** 2026-09-23 — rulings R27-R36 (SPEC 53d9a7f) + main-thread rulings Q1-Q5: §9 rewritten — us-east-1 single-region, serverless DEV/PRD workspaces as rebuildable per-env units, persistent account/UC/GitHub stacks, S3-native locking, SSE-S3, seed S1-S3, sa-east-1 teardown before bring-up (O-12), rebuild drill. Decisions: Q1 drill destroys the dev workspace itself (§9.3 survival analysis); Q2 prod bundle validated, not deployed; Q3 non-colliding names `dm-chain-explorer-{dev,prd}-{raw,lakehouse}`, state `dm-chain-explorer-tfstate-use1`; Q4 system.billing default-on, no stack resource (§9.7); Q5 constitution §2 clause operator-confirmed at T-O7.5.
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

## 9. Amendment 2026-09-23 — R18-R36

R27-R36 (SPEC 53d9a7f) retire the Free Edition, move every resource to us-east-1 and add the Databricks account, workspace and GitHub stacks. This section replaces the R18-R26 §9 wholesale; §1.4, §1.6, §2 K6, §3.5 `FORCE`, §4, §5 and the §7 rows `T-X7.6`/`T-O7.x` stay superseded where this section says so.

### 9.1 Deletion test — the balance of the amendment

**Dies:** the DLT pipeline and `dlt_market_data/`; the seven Ethereum bundles; `apps/lambda/`, `utils/`, `publish-artifacts.yml`, dashboard tooling; the `bundles` dispatch filter; infra `dev/02_lambda`, `prd/06_lambda`, modules `dynamodb` + `lambda`, `s3_ingestion`, `s3_artifacts`, `gha_artifacts_publish`, `resolve_*.sh` (6), `--target explorer`; `changed_files_since_base()`, `FORCE`, `force_apply`, `destroy_ack`; the DynamoDB lock table, its grants, every `dynamodb_table =` backend line, `tf_state_lock_check.sh`; every KMS key and `aws:kms` setting (R30); the Free Edition UC stack and its hand-made catalog/credential (R27); the `raw/` 8,000-object drift check (R36); seed steps S4-S7 and blockers B1/B2; `docs/runbooks/00-bootstrap-apply.md`; every `sa-east-1` literal (35). **Grows:** three PySpark task modules (a rewrite, not a wrapper), one account stack, two per-env workspace units, two rewritten UC stacks, two GitHub stacks, one seed script, `capture_run.yml`, `rebuild_drill.yml`, one dispatch step per lane, one temporary retire step that dies in the region-move commit. Bug-surface verdict: every hand-kept object of the M-ledger gets exactly one owning stack; the chain loses its two hand-kept enumerations (bundle filter, git-diff detection) and one seam; no stack gains a second code path.

### 9.2 WS-X — bundle `job_market_data` (X1-X7, R19/R20/R24, R31)

**Layout.** `apps/dabs/job_market_data/{databricks.yml, VERSION, resources/job_market_data.yml, src/dm_market_parsers/** (git mv, byte-identical), src/market_data/{bronze.py, silver.py, gold.py, _spark.py}}`. Variables `catalog`, `raw_data_url`, `lakehouse_url`. Targets: `dev` (`run_as` dev SP, `[dev] ` prefix, `catalog=dev`, `raw_data_url=s3://dm-chain-explorer-dev-raw/raw/`), `prod` (`catalog=prd`, prd URLs; validated in CI, never deployed — O-7). Host never in the tree: `DATABRICKS_HOST` from the GitHub environment. `workspace.artifact_path: /Volumes/<catalog>/ops/bundle_artifacts` (the volume is owned by the UC stack, §9.4). `performance_target: STANDARD`.

**Schemas are not bundle-owned** (changed from R18-R26): `b_market`, `s_market`, `g_market` and `ops` belong to the UC stack. Why: the bundle's deployment state lives in the workspace (`.bundle/`); the AC-29 drill destroys the workspace, and a redeploy with a fresh state would try to re-create schemas that the metastore still holds. The bundle owns only the job — a workspace object that dies and returns with the workspace.

**Tables.** Every table is created by its task with `CREATE TABLE IF NOT EXISTS … USING DELTA LOCATION '<lakehouse_url>/<schema>/<table>'` — external, on the lakehouse external location (R31); the metastore keeps the registration across a workspace rebuild.

**Job.** One job `dm-market-data`; three `spark_python_task`s `bronze → silver → gold` (`depends_on`, `run_if: ALL_SUCCESS`), `environment_key: default` (serverless, client `2`, no dependencies — each entrypoint puts its `src/` on `sys.path`). No `pipelines:`, no `dlt`, no `%pip`, no wheel. `max_concurrent_runs: 1`, `queue.enabled: true`.

**Trigger (R20, R36).** `file_arrival.url: ${var.raw_data_url}`, `UNPAUSED` in `dev`, `min_time_between_triggers_seconds: 300`, `wait_after_last_change_seconds: 120` (data first, `_manifest.json` last — one partition, one fire). File events are on the storage credential's external location (§9.4), so the 10,000-file listing cap does not apply and the drift-lane object count dies. A fire with no new manifest is a counted no-op.

**Bookkeeping, idempotency, medallion keys** — unchanged from the R18-R26 design: `b_market.raw_manifests` MERGE key `(source, dataset, ingest_date, manifest_sha256)`; bronze insert-only on `content_sha256`, `bronze_at` last; silver on `silver_at IS NULL`, natural keys as listed in SPEC §6 / X4, `versao` rule; gold by overwrite, NULL-never-fabricate; task values `rows` per layer + rejection sums (AC-22 read from the run output). A second fire changes no count.

**Tests.** Parser suite unchanged (41). `test_bundle_targets_contract.py`: exactly one bundle; 1 job, 3 ordered serverless tasks, `file_arrival`, `max_concurrent_runs = 1`, no `host:` literal, no `schemas:` resource. `test_no_dlt_import` greps `apps tests`. Key/rejection helpers unit-tested beside the parsers; Spark I/O stays in `_spark.py`.

### 9.3 Target architecture — stacks, state keys, apply order

**State.** One bucket `dm-chain-explorer-tfstate-use1` (us-east-1, versioned, PAB, SSE-S3), created by seed S1 from `prd/01_tf_state` (operator-only, local state). Every backend: `bucket`, `key`, `encrypt = true`, `use_lockfile = true`; no `region`, no `dynamodb_table` (R33).

| Group | Stack (dir) | Key | Owns | Life |
|---|---|---|---|---|
| seed | `prd/01_tf_state` | local | state bucket | operator |
| seed | `prd/00_bootstrap` | `prd/bootstrap/…` | OIDC roles, boundary, grants | operator (S1) |
| account | `account/databricks` | `account/databricks/…` | metastore us-east-1, SPs `dm-chain-explorer-{dev,prd}-deploy` + OAuth secrets, budget alert | persistent |
| prd | `prd/04_peripherals` | `prd/peripherals/…` | ECR ×3, `dm-chain-explorer-prd-{raw,lakehouse}` | persistent |
| prd | `prd/05_workspace` | `prd/workspace/…` | workspace `dm-chain-explorer-prd` (SERVERLESS) + metastore assignment + permission assignments; no warehouse | rebuildable |
| prd | `prd/04_unity_catalog` | `prd/unity-catalog/…` | UC IAM role, credential, locations, catalog `prd`, schemas, volume, binding, grants | persistent |
| prd | `prd/06_github` | `prd/github/…` | env `production` secrets/vars, default branch `develop` (infra, explorer) | persistent |
| dev | `dev/01_peripherals` | `dev/peripherals/…` | `dm-chain-explorer-dev-{raw,lakehouse}`, capture writer role | persistent |
| dev | `dev/03_capture` | `dev/capture/…` | cluster, SG (default VPC), task roles/defs, schedules `DISABLED` | persistent |
| dev | `dev/05_workspace` | `dev/workspace/…` | workspace `dm-chain-explorer-dev` + assignment + permission assignments + SQL warehouse 2X-Small, auto-stop 1 min, max 1 cluster | **rebuildable (AC-29)** |
| dev | `dev/04_unity_catalog` | `dev/unity-catalog/…` | as prd, catalog `dev` | persistent |
| dev | `dev/06_github` | `dev/github/…` | env `dev` secrets/vars | persistent |

**Survival analysis — why the workspace unit and the UC stack are separate.** A Databricks workspace holds only workspace objects: jobs, warehouses, workspace files (`.bundle/`), permission assignments. Storage credentials, external locations, catalogs, schemas, volumes and table registrations are **metastore** objects; they outlive a workspace as long as the metastore (account stack) lives. If they sat in the workspace unit, the AC-29 destroy would drop the catalog (and with it every table registration and the `SHOW TABLES` 12/8/3 proof). So the unit that is destroyed holds only what dies with the workspace, and the UC stack is persistent per env. The UC stack's `databricks` provider targets the current workspace — `host` read from the workspace unit's remote-state output — and authenticates as the account SP (account admin, metastore admin, workspace `ADMIN` by the unit's permission assignment). Its resources are addressed by name/metastore id, so after a rebuild the same state converges against the new host: the catalog-workspace binding (`databricks_workspace_binding`, workspace id from the unit's output) is replaced to the new workspace id, grants on account identities are unchanged, and nothing else plans. The UC IAM role lives in the UC stack beside its credential, because its trust needs the credential's `external_id` and the credential needs the role ARN (self-assume + `time_sleep`) — one stack breaks the cycle without a second apply. Account-level UC APIs do not manage these objects, so there is no account-core alternative; the prd workspace host is not used for dev objects (would need binding the `dev` catalog to prd, violating R31).

**Alternatives rejected.** (a) Everything per env in one unit — fails AC-29 (catalog destroyed). (b) Workspaces in the account stack (SPEC I13 as written) — the drill would have to destroy one resource of a shared state (`-target`), an unsafe routine. (c) UC objects in the account stack via the prd host — cross-env coupling, breaks isolation.

**Apply order (map `upstreams`).** account → prd/04, dev/01 (buckets, ECR) → `*/05_workspace` → `*/04_unity_catalog` → `*/06_github` → dev/03_capture. `stack_map.json` gains the `account` group (applied in the prd lane behind `production`). The dev lane applies dev without approval, so the drill never needs `production`.

**Provider auth per stack.**
- AWS (all): GitHub OIDC → `gha-deploy-{dev,prd}` / readonly-plan; `region = var.aws_region`.
- `account/databricks`, `*/05_workspace`: `databricks` provider, `host = https://accounts.cloud.databricks.com`, `account_id` + OAuth M2M client id/secret from infra repo secrets `DATABRICKS_ACCOUNT_ID`, `DATABRICKS_ACCOUNT_CLIENT_ID`, `DATABRICKS_ACCOUNT_CLIENT_SECRET` (seed S3), passed as `TF_VAR_*`/`DATABRICKS_*` env.
- `*/04_unity_catalog`: `databricks` workspace provider, `host = data.terraform_remote_state.workspace.outputs.host`, same account SP credentials.
- `*/06_github`: `github` provider with `app_auth` (`CI_APP_ID`, `CI_APP_INSTALLATION_ID`, `CI_APP_PRIVATE_KEY`). Inputs: host + warehouse id (workspace unit), SP client id/secret (account stack). Writes env `dev`/`production` in infra + explorer: `DATABRICKS_HOST`, `DATABRICKS_CLIENT_ID`, `DATABRICKS_CLIENT_SECRET`, `DATABRICKS_WAREHOUSE_ID` (dev), `DATABRICKS_ACCOUNT_ID`.

**Region single-source (I12).** The workflow `env: AWS_REGION: us-east-1` (one line per workflow file, pinned equal by a contract test) is the source: the S3 backend and AWS CLI read `AWS_REGION`; `TF_VAR_aws_region=$AWS_REGION` feeds `var.aws_region` (declared without default in every stack, so a missing value fails, never falls back). Workspace units pass `aws_region = var.aws_region` to `databricks_mws_workspaces`; the metastore `region` likewise. The seed exports the same value. Capture: `publish-images.yml` `AWS_REGION: us-east-1` + its test. Grep gate AC-25.

**Encryption (R30).** Every bucket `sse_algorithm = "AES256"`, `bucket_key_enabled` n/a; no `aws_kms_key` anywhere (AC-27).

### 9.4 UC stack content (I14, R31, R36)

Per env: IAM role `dm-chain-explorer-<env>-uc` (trust: UCMasterRole + self + `sts:ExternalId` = credential external id; S3 on its env's raw (read) + lakehouse (RW); file-event statements on `csms-*` SNS/SQS and bucket notifications); `databricks_storage_credential` `dm-<env>-uc`; `databricks_external_location` raw (`read_only = true`) and lakehouse, both `enable_file_events = true` (managed SNS/SQS); `databricks_catalog` `<env>`, `isolation_mode = ISOLATED`, `storage_root` = lakehouse location; `databricks_workspace_binding` to the unit's workspace id; schemas `b_market`, `s_market`, `g_market`, `ops`; volume `ops.bundle_artifacts`; grants: deploy SP `USE_CATALOG`, `USE_SCHEMA`, `CREATE_TABLE`, `MODIFY`, `SELECT` on the catalog, `READ_FILES` on raw, `READ_FILES`/`WRITE_FILES` on lakehouse, `READ_VOLUME`/`WRITE_VOLUME` on the volume. `force_destroy = false` on the catalog — a code path that drops the catalog does not exist. Outputs: catalog, location URLs.

### 9.5 Ethereum, lambda-seam and sa-east-1 teardown (I10, I12, R21, R23, R34, O-10, O-12)

Teardown happens entirely in sa-east-1, against the old backend, **before** any us-east-1 apply.
1. **PR-α destroy commit (T-I7.12), old backend:** `dev/01`, `dev/02_lambda`, `dev/03_capture`, `prd/04`, `prd/06_lambda` reduced to backend + provider; `prevent_destroy` lifted in `modules/s3`; `dev/04_unity_catalog` removed from the map (its Free Edition state is abandoned with the old bucket, R27). A `retire` job (`scripts/ci/retire.sh` + `retired_objects.json`, idempotent: absent = pass) runs first: empties every listed bucket by exact name (`empty_s3_buckets.sh`), then `terraform destroy` (whole, not targeted — R34) of `capture/ecr` through the source-less config `services/retired/capture_ecr/` (backend + `aws` provider; 11 resources incl. KMS with the minimum 7-day deletion window and Roles Anywhere). The lanes apply dev on merge and prd behind `production`; run ids recorded (AC-23, AC-26).
2. **Seed S1 (Phase C)** deletes the last sa-east-1 objects no lane owns: the old state bucket and lock table, after migrating `prd/bootstrap` state to the new bucket.
3. **PR-β region-move commit (T-I7.16):** deletes `dev/02_lambda`, `prd/06_lambda`, `services/retired/`, `retire.sh`, `resolve_*`, modules `dynamodb`/`lambda`, `tf_state_lock_check.sh`, lock/Lambda/DynamoDB/artifacts/KMS grants; re-adds `dev/01`, `dev/03`, `prd/04` content for us-east-1 with the new names; adds §9.3 stacks. Its merge is the bring-up.
4. **Explorer (T-X7.8, T-X7.10):** delete-only — nothing is deployed in a workspace we own (X8). No retire step, no PR-α/β ordering in explorer.

### 9.6 The automated chain (I11, X9, R26, R35)

| Step | Trigger | Workflow · job |
|---|---|---|
| 1 | `push` to `develop` (infra) | `deploy_cloud_infra` · `dev-deploy` → `prd-plan` → `prd-apply` (`production`, only on a prd/account plan exit 2) |
| 2 | step 1 dev green | `signal-explorer`: App token → `repository_dispatch infra-dev-applied` |
| 3 | `push` `develop` or `infra-dev-applied` (explorer) | `ci` · `deploy-dev` (`bundle deploy -t dev`) → `signal-infra`: `explorer-dev-deployed` |
| 4 | `explorer-dev-deployed` (infra) | `capture_run` · one Fargate Spot task per image, `ecs wait tasks-stopped`, exit 0 + `_manifest.json` → `capture-landed` |
| 5 | file arrival | job `[dev] dm-market-data` |
| 6 | `capture-landed` (explorer) | `ci` · `e2e-verify`: waits for the `FILE_ARRIVAL` run, reads task values, fails on 0 gold rows or any sha rejection |

- **Plan as detector (M11):** every map stack `plan -detailed-exitcode`, apply on exit 2; git-diff detection, `FORCE`, `force_apply`, `destroy_ack` die. The prd destroy acknowledgement is the `production` approval over a plan summary listing destroys.
- **Default branch `develop`** (R35) in infra and explorer, written by `prd/06_github` (`github_branch_default`): dispatch, `repository_dispatch` and `schedule` read it (M10, M15).
- **GitHub App `dm-chain-explorer-ci`** (R26; one name set, replaces `CHAIN_APP_*`): installed on the 3 repos; secrets `CI_APP_PRIVATE_KEY`, variables `CI_APP_ID`, `CI_APP_INSTALLATION_ID` (infra, explorer). App permissions: Contents RW, Actions RW, Variables RW, Secrets RW, Environments RW, Administration RW, Metadata R. **Security lens:** the widened set exists only for the `06_github` stacks; every job mints its own 1-hour token (`actions/create-github-app-token`, SHA-pinned) with `repositories:` = the one target and `permission-*:` = the subset it needs — signalling jobs `contents: write` only; the private key never leaves the secret; no PAT.
- **Loops:** step 4 never signals infra; `concurrency` per lane.
- Capture keeps `publish-images.yml` (push-triggered, now us-east-1).

**Rebuild drill (AC-29, `rebuild_drill.yml`, infra, `workflow_dispatch`, env `dev`).** (1) snapshot `SHOW TABLES` + `count(*)` per table through the dev warehouse; (2) `terraform destroy` `dev/05_workspace`; (3) `deploy_env.sh dev` — the unit recreates the workspace + warehouse, the UC stack re-binds the catalog, `dev/06_github` writes the new host/warehouse id; (4) `infra-dev-applied` → explorer redeploys the bundle; (5) snapshot again, compare equal, list lakehouse objects unchanged; (6) `capture_run` → next file arrival fires the job. The dispatch click is the only human act (same class as an environment approval).

### 9.7 The trust seed (I11: S1-S3; M1, M3, O-8, O-11)

`scripts/seed/trust_seed.sh` + `docs/runbooks/trust-seed.md` (replaces `00-bootstrap-apply.md`), run by the operator in a real terminal (admin AWS with MFA, `gh` as repo admin). Every step reads before it writes; run 2 makes no change and echoes no secret (stdin → `gh secret set`, never argv, never logs).

| Step | Does | M |
|---|---|---|
| S1 | AWS: `prd/01_tf_state` apply (bucket `dm-chain-explorer-tfstate-use1`); `prd/00_bootstrap` `init -migrate-state` to it + plan-then-apply; `publish_oidc_vars.sh --target infra\|capture\|explorer`; account S3 Block Public Access; after verifying no old key is still read, delete the sa-east-1 state bucket + lock table | M1, M3 |
| S2 | GitHub App: verify `dm-chain-explorer-ci` installed on the 3 repos (created by the operator via the manifest URL printed by the script); store `CI_APP_ID`, `CI_APP_INSTALLATION_ID`, `CI_APP_PRIVATE_KEY`; create env `production` with the operator as reviewer (adopted by `prd/06_github` via `import`) | R26, M4 |
| S3 | Databricks: read the account SP `dm-chain-explorer-terraform` (account admin, created in the console) OAuth secret from stdin, store `DATABRICKS_ACCOUNT_ID/CLIENT_ID/CLIENT_SECRET` in infra; list metastores in us-east-1 and print the import id if one exists | M6 |

Tests `scripts/seed/tests/`: stub `terraform`/`gh`/`aws`/`databricks` on `PATH` record calls; run 1 performs each step, run 2 issues zero mutating calls, no recorded argv or output holds the fake secret; `shellcheck` clean. The Phase B bootstrap delta is applied at the PR-α head (old backend) through the still-present `00-bootstrap-apply.md` (T-O7.8); the seed exists only for the new backend.

**system.billing (AC-30).** `databricks_system_schema` is a workspace-provider resource and cannot live in the account stack; the `billing` schema is enabled by default on every metastore and is not toggleable. T-V7.3 asserts `SELECT … FROM system.billing.usage` returns rows; no stack resource is needed.

### 9.8 M-ledger map

| M | Replacement |
|---|---|
| M1 | seed S1 |
| M2 | retired one-off — hml gone (ADR-10) |
| M3 | seed S1 (`publish_oidc_vars.sh`) |
| M4 | `*/06_github` environments; `production` reviewer seeded in S2 |
| M5 | `*/06_github` env secrets/vars |
| M6 | `account/databricks` SP secrets → `*/06_github`; account SP secret seed S3 |
| M7 | `*/04_unity_catalog` (credential, locations, catalog, grants) |
| M8 | `*/04_unity_catalog`; Free Edition objects abandoned (R27) |
| M9 | retired one-off; every remaining object → CI destroy |
| M10 | `prd/06_github` default branch `develop` |
| M11 | plan-as-detector lanes; `force_apply`, `destroy_ack`, bundle filter deleted |
| M12 | lambda seam deleted; ECR precedes capture pushes; `repository_dispatch` chain |
| M13 | file-arrival trigger |
| M14 | `capture_run` workflow |
| M15 | `prd/06_github` default branch — drift runs on the deploy branch |

### 9.9 Risks added

| Risk | Handling |
|---|---|
| ISOLATED catalog unreadable from the rebuilt, not-yet-bound workspace during UC refresh | T-V7.2 pre-drill probe: `catalogs get dev` from a second workspace as metastore admin; if refused, move `databricks_workspace_binding` into `dev/05_workspace` (catalog name as a variable) — design change reported before the drill |
| Workspace name reuse right after delete | the unit sets no `deployment_name`; retry in the lane |
| SP secrets in Terraform state | state bucket readable by deploy/readonly roles only (bootstrap); SSE-S3; no output marked non-sensitive |
| KMS key in `capture/ecr` enters a 7-day pending deletion | AC-26 counts `PendingDeletion` as absent from use; alias deleted at once |
| Old backend deleted while a state is still read | S1 checks every old key's stack is gone from the map and its state empty before deleting |
| Global bucket name taken by a third party | S1 `head-bucket` probe for all five names before any apply |
| Account spend | budget alert (account stack); dev warehouse 1-min auto-stop; prd no warehouse |
| Capture run per explorer deploy | three short Spot tasks; accepted for dev |
