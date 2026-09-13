# PLAN — Release v0.7.0 — Market-data restart: batch capture runtime + medallion landing

> **Status:** Aprovado
> **Release ID:** v0.7.0
> **Owner:** product-engineer — approved under the operator standing order of 2026-09-13 ("faça tudo que puder, avance") after ratifying grill rulings R1-R17
> **Depends on:** SPEC.md v0.7.0 (`Aprovado`)
> **Branch:** `feature/0.7.0` in `dd-chain-infrastructure` and the new `dd-chain-explorer`, each stacked on `feature/0.6.0` (`DADAIA.md` §4, `dd-gitflow-default`); merges into `develop` only after v0.6.0's candidate merge (SPEC O-1)
> **Lifecycle:** pre-staged — v0.6.0 is the live release until its C-DAY; this PLAN becomes executable when v0.7.0 turns ACTIVE

This release adds capability, so its acceptance shapes are **existence + equality proofs**: a resource exists and its declared state plans clean (AC-4..AC-6, AC-9), a grant is effective (AC-7), a partition lands from Fargate (AC-16), a table carries rows whose `content_sha256` matches the manifest (AC-14). Every growth is justified against the deletion test (`dd-codebase-design`): the module grown, the leverage gained, the slop that dies in the same change.

## 1. Strategy

1. **Bug ledger first (`DADAIA.md` §7.1).** The four prior infra bugs on this surface were all "hand-maintained map/policy with no cross-check". The scheduler gap is the fifth of the family; it is closed by a test that *derives* the required grants from `services/**` (T-I7.1 RED → T-I7.2 GREEN), so any future stack declaring a new AWS namespace fails the suite until the bootstrap grants it. No grant lands without that test.
2. **Replace, don't layer.** The dev deploy lane already duplicates the stack enumeration (static jobs + `detect_changes.sh`) — the defect the prd lane fixed. Two more stacks would grow that copy; instead the lane becomes map-driven and `detect_changes.sh` dies. `publish_oidc_vars.sh --target` replaces a hand-run `gh variable set`. `force_delete` on ECR kills the ECR branch of `empty_s3_and_ecr.sh`.
3. **One credential per environment, one adapter per seam.** The dev storage-credential role is widened to the new bucket (no second role for one bucket). The writer role and the task roles share one policy shape (`raw/*` vs `raw/<source>/*`). The registry host comes from `ecr-login`, never a variable.
4. **Raw is evidence; bronze is bytes; silver parses; gold computes** (R13). Bronze never decodes. Every parser is a pure function tested off-cluster; DLT closures only call them. Every expectation is silver-only (the existing contract test enforces it).
5. **Dev only, prod-shaped** (R4). The `prod` bundle target is declared and validated, never deployed; no prd environment resource is created; the account-scoped registry lives in `prd/04_peripherals` because shared artifact stores already live there.
6. **Schedules stay `DISABLED`.** The runtime is proven by one operator `run-task`; enabling is a later one-variable ruling.

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

## 4. WS-X — `dd-chain-explorer`

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

## 5. WS-O — operator-only

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
