# Consolidated Full-Platform Audit — dd-chain-explorer

> **Date:** 2026-08-23 (UTC stamp 20260823T145726Z) · **Session:** 4db47555
> **Branch audited:** `feature/v0.4.0` @ `c6feb17` (local ahead-1 of origin; `develop` 107 behind, ff-able; default branch `master` 192 ahead / 4 behind)
> **Coordinator:** main session (operator-requested full audit), fan-out of 7 read-only evidence lanes.
> **Evidence reports (this directory):**
> - `sdd-drift-lane.md` — project-auditor: specs, releases, memory, backlog, bugs, prior audits, scorecard
> - `implementation-deadcode-lane.md` — implementation health, dead code, lint/type/CVE gates, docs drift
> - `cicd-terraform-lane.md` — code-reviewer: 7 workflows, scripts/ci, Terraform stacks/modules, repo governance
> - `security-lane.md` — security-reviewer: full scan (secrets, IAM, CI, deps, code, DABs) + prior-findings status
> - `qa-test-pyramid-lane.md` — qa-engineer: 158 tests, pyramid, stewardship, CI wiring
> - `live-aws-lane.md` — live AWS dev/hml/prd vs Terraform state vs code, data freshness, cost
> - `databricks-lane.md` — DABs bundles vs live Free-Edition workspace vs memory
>
> **Method:** read-only throughout. No repo file modified, no `terraform` against a real backend, no AWS/Databricks mutation, no secret value read. One known side-effect: `databricks workspace export` bumped `modified_at` metadata on two hml notebooks (content verified unchanged).
>
> **Prior audits:** `20260609T013037Z` (fully dispositioned by `audit-remediation-r5`/v0.3.0 — archivable), `20260611T001412Z-cb56f84c` (70 findings, **zero per-finding dispositions**, not archivable), recap handoff `2026-08-19T002955Z-project-auditor-full-recap-audit` (10 findings, 5 decisions — **0 actioned**; all 10 re-verified today, 3 still-valid verbatim, 7 re-verified live: unchanged).

---

## 1. Verdict

**The platform is a correctly-retired capture layer with no successor yet, documented as if it still ran, and governed by a CI that cannot authenticate.**

- **Implementation of v0.4.0 is honest and complete** (16/16 tasks, deliverables spot-checked on disk) — but the release was never closed: no `CLOSURE.md`, no memory update, `ACTIVE.md` still `IMPLEMENTATION`, branch unmerged.
- **Every memory atom on the data path describes the pre-v0.4.0 world** (5 ECS jobs, Kinesis/Firehose/SQS, PRD workspace). An agent self-pulling memory today is grounded in a system that has not existed for two months.
- **The platform is idle end-to-end**: S3 raw-data empty (last data 2026-05-23, misdirected), 4 DLT pipelines IDLE with 0 updates, 18 jobs with 0 runs in 60 days, all 29 `dev` UC tables last written 2026-04-28, DynamoDB 0 items. dd-chain-capture (VPS) has delivered nothing. Project run-rate ≈ US$ 1/month.
- **CI is structurally non-functional**: all 55 `configure-aws-credentials` steps read `vars.AWS_DEPLOY_ROLE_*` which do not exist; the OIDC roles in `prd/03_iam/oidc.tf` were never applied; no branch protection on `master`/`develop`; `drift_detection.yml` has never fired (absent from default branch). Last CI run: 2026-04-11.
- **Deployed Databricks code ≠ repo** in 3 of 4 pipelines (app-logs Fluent-Bit reader never deployed; hml ethereum pre-R1); trigger/full-refresh/reconcile jobs are broken as deployed; alert/genie bundles are no-ops.
- **44 % of Python LOC and ~72 % of tests serve the retired capture layer**; the live surface (2 lambdas, DABs jobs, DLT expectations) has zero tests.
- **Security**: 0 CRITICAL / 3 HIGH. The June "Infura key in history" finding is **debunked** (it was an SSM parameter name). New: dependency-confusion exposure (`dm-chain-utils` unclaimed on PyPI, installed from the public index), committed 37 MB Lambda layer with 31 CVEs that contradicts its own version gate, and — the repo being **PUBLIC** — a dangling static AWS key pair in the secret store plus the operator's personal e-mail hard-coded in 12 DABs prod targets.

| Lane | CRITICAL | HIGH | MEDIUM | LOW | INFO |
|---|---|---|---|---|---|
| SDD drift | — | 4 | 11 | 10 | 4 |
| Implementation / dead code | — | 5 | 9 | 4 | 2 |
| CI/CD + Terraform | 1 (+1 x-lane) | 9 | 8 | 5 | 1 |
| Security (full scan) | 0 | 3 | 6 | 12 | 6 |
| QA / tests | 1 | 1 | 3 | 4 | 1 |
| Live AWS | — | 2 | 4 | 5 | 2 |
| Databricks | — | 5 | 6 | 4 | — |
| **Total (raw, before dedup)** | **2** | **29** | **47** | **44** | **16** |

---

## 2. Compliance scorecard (dd-audit-project rubric)

| Dimension | Score | Rationale (one line) |
|---|---|---|
| A — Architecture | **3** | `architecture.md` declares a 4-layer system whose first layer was deleted; 3/6 ADRs describe a superseded event bus, no superseding ADR; 16 dead modules + ECS/IAM/firehose IaC shells survive |
| B — Product | **3** | Rank-1/2 catalog features document destroyed infra; `index.md` ≠ `catalog.json`; deployed DLT code ≠ repo; `data-catalog` claims 30 objects (29 live) — DRIFT-N01..N04 from June still undispositioned |
| C — Tech stack | **4** | Python/Databricks/Terraform sections accurate, but: `dm-chain-utils==0.2.9` pin is 404 on PyPI, no `.terraform.lock.hcl`, committed stale layer zip, TF version drift 1.7→1.15, two undocumented version axes |
| D — Security | **4** | 3 HIGH (dep-confusion, admin-escalating deploy roles as declared, vulnerable committed artifact), dangling static keys + PII in a public repo, dead capture IAM grants with resurrect-by-name wildcards, Databricks token in TF state |
| E — Tests | **4** | 158/158 green but inverted pyramid (113 test retired code), 0 tests on live lambdas/DABs/DLT, CI runs 1 of 3 suites (`scripts/ci/tests` — the CI's own safety guards — never run) |
| F — Design / serving | **5** | 4 dashboards ACTIVE but hard-code `dev.` catalog; embed setting drifted from bundle; alerts/genie never deployed; warehouse STOPPED so nothing can execute |
| **Final** | **3.6 / 10** | weighted 3.60 · floor 3 → cap 5 → **3.6** — **significant drift** |

`weighted = 3(0.20)+3(0.25)+4(0.15)+4(0.20)+4(0.15)+5(0.05) = 3.60`. No dimension < 3 (no floor breach). Recommendation band `< 5` → **one dedicated remediation release**; `project-auditor` recommends, `project-manager` opens, operator decides.

---

## 3. Consolidated findings (deduplicated, severity-ordered)

Cross-refs point to lane ids in the evidence reports. `DRIFT-n` ids are the ones a remediation release's `TASKS.md` must map 1:1.

### 3.1 CRITICAL — the platform cannot be operated as-is

| ID | Finding | Evidence | Cross-ref |
|---|---|---|---|
| DRIFT-01 | **CI cannot authenticate to AWS.** All 55 OIDC steps read `${{ vars.AWS_DEPLOY_ROLE_{DEV,HML,PRD,READONLY} }}`; `gh api .../actions/variables` → `[]` at repo and environment level; the 4 roles (`dm-chain-explorer-gha-*`) declared in `prd/03_iam/oidc.tf` were never applied (prd/iam state = 12 res., none of them live). The v0.3.0 "OIDC cutover" is code-only. | `.github/workflows/*` (55 steps); `gh variable list` empty; `aws iam list-roles` no `gha-*`; OIDC provider exists | CI F-01, LA-03, SEC I1 |
| DRIFT-02 | **The only app-deploy workflow re-provisions the retired capture layer.** `deploy_all_dm_applications.yml` builds the stream image, provisions HML Kinesis/SQS (`hml_provision.sh:28-36` calls `aws sqs get-queue-url` on destroyed queues → hard-fail under `set -e`), launches 5 ECS producers, updates 5 destroyed PRD services, and runs `terraform destroy -target='module.kinesis'` on a deleted module; PRD DABs + Lambda deploys are `needs:`-chained behind it. Its gate script (`hml_integration_test_optimized.sh`) is an unconditional `exit 0`. `.github/workflows/` was in no v0.4.0 write set — this is the "streams come back" vector SPEC §3.2 targeted. | `deploy_all_dm_applications.yml:257,293-294,326-327,366-370,539,559-566,785,876-889`; `scripts/ci/hml_provision.sh:5-36` | SDD-03, QA F1/F2, IMPL F-01, CI x-lane |

### 3.2 HIGH

| ID | Area | Finding | Cross-ref |
|---|---|---|---|
| DRIFT-03 | Release | v0.4.0 done-but-open: no `CLOSURE.md`, no memory update, `ACTIVE.md`=IMPLEMENTATION, `feature/v0.4.0` unmerged + ahead-1 unpushed; 4 acceptance criteria (AC-4/5/7) carry no evidence; AC-7 unsatisfiable while `drift_detection.yml` is absent from the default branch | SDD-01/07/08 |
| DRIFT-04 | Memory | 6 atoms STALE/DEAD (~40 cited claims): `architecture.md`, `tech-stack.md:152,155`, `product/aws-resources.md`, `product/capture-layer.md` (whole), `product/index.md` vs `catalog.json` (5 vs 6 features; stale keys), `data-catalog`/`medallion-pipelines` (30 vs 29 objects, `popular_contracts_txs`), `serving-layer` (streaming-jobs reader), `quality-assurance` (71→78 tests, no `scripts/ci/tests`), `cicd-pipeline` ("no static keys", "`vars.AWS_DEPLOY_ROLE_*`", "hml required_reviewers", "7 workflows"). `architecture.md` is **not** on SPEC §8's CLOSURE list | SDD-12..17, DBX-05, IMPL F-08, CI stale-claims, QA §5 |
| DRIFT-05 | Audits | 2026-06-11 audit (5C/17H/28M/20L) has **zero per-finding dispositions** two months on; 2026-08-19 recap's 5 decisions: 0 actioned; `20260609` archivable now (blocked only by missing `specs/audits/_archive/`) | SDD-23 |
| DRIFT-06 | Security / supply chain | **Dependency confusion**: `dm-chain-utils==0.2.9` pinned in 3 production manifests + Dockerfile, installed from the default public index, name **unclaimed on PyPI (404)**; currently fails closed by luck. Plus: no hash pinning, `>=` floors make manifest CVE scans a permanent false negative | SEC H1/M6, IMPL F-09 |
| DRIFT-07 | Security / integrity | Committed **37 MB `dm_chain_utils_layer.zip`** (built 2026-03 from a different codebase: kafka/redis/msk modules) is what Terraform ships (`source_code_hash`); contains `dm_chain_utils-0.1.0` while CI asserts `==0.2.9` by text grep; **31 CVEs / 4 packages** (aiohttp ×25, urllib3, idna, requests). 5 binary deploy artifacts tracked in total; perpetual plan diff | SEC H3/M5, IMPL F-03 |
| DRIFT-08 | Security / IAM (as declared) | All 3 OIDC deploy roles in `oidc.tf` = `PowerUserAccess` + inline `iam:CreateRole/PutRolePolicy/AttachRolePolicy/UpdateAssumeRolePolicy/PassRole` on `*` → account-admin escalation; read-only role trusts `:pull_request` (any branch) + `ReadOnlyAccess` → state-bucket read. Not live today (DRIFT-01) — must be fixed **before** `prd/03_iam` is ever applied | SEC H2/M1, CI F-14 |
| DRIFT-09 | Governance / security | Repo is **PUBLIC**: static `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` (2026-03-20) + 3 capture-era secrets (`DYNAMODB_TABLE`, `ECS_TASK_*_ROLE_ARN`) sit unreferenced in the secret store; the IAM user behind CI still holds 2 active access keys (older one last used 2026-06-15); operator personal e-mail hard-coded as `run_as.user_name` in 12 DABs prod targets; workspace host in 12 bundles; workflow YAML is a reconnaissance map of the account | CI F-02/F-20/F-21, SEC L6/L7 |
| DRIFT-10 | Governance | No branch protection on `master` or `develop`; `plan_on_pr.yml` triggers only on PRs to `develop` → the shipping PR `develop→master` gets no fmt/validate/plan; `hml` environment has no protection rules, `hml-apps` does not exist; default branch `master` (no `main`), 192 ahead / 4 behind, different workflow set → `drift_detection` cron can never fire; 10 stale remote branches | CI F-04/F-16, SDD-24/25, LA-13 |
| DRIFT-11 | Versioning | Two disjoint version axes: `VERSION`=0.2.9 / tags `v0.2.9-*` (CI, auto-bump patch) vs SDD releases v0.3.0 shipped / v0.4.0 in flight — no `v0.3.0*`/`v0.4.0*` tag; a PRD deploy today mints `v0.2.10-infra`; `__version__` 0.1.0 in the lib; 15 DABs `VERSION` files at 1.0.0 so `deploy_all.sh` would SKIP all 15 | CI F-03, SDD-26, IMPL F-19, DBX-14 |
| DRIFT-12 | Dead code | **16 dead Python modules, ~4,540 LOC (44 %)**: 6/9 `dm_chain_utils` modules with zero live callers (`dm_kinesis`, `dm_sqs`, `dm_firehose`, `dm_web3_client`, `dm_cloudwatch_logger`, `api_keys_manager`) still re-exported and shipped in the layer (+ `web3`/`hexbytes` chain); all of `apps/docker/onchain-stream-txs/**` (2,867 LOC, unbuildable image); `scripts/prod_ecs_logs.py`; 6 unreferenced scripts; promised backlog item `dm-chain-utils-capture-handler-cleanup` was never created | IMPL F-04/F-05/F-16/F-17 |
| DRIFT-13 | Dead IaC | ECS shells in `prd/07_ecs` + `hml/07_ecs`/`modules/ecs` (cluster + capacity providers + 2 ECR repos, 0 task defs/services; 4 dead locals); firehose branch of `modules/cloudwatch_logs` universally `count=0` (+ `outputs.tf:17` `[0]` index risk); Kinesis/Firehose/SQS grants in `prd/03_iam/iam.tf:57-92`, `hml/03_iam/main.tf:91-123` (creates a firehose role), `modules/iam` — with name-pattern wildcards that resurrect by name; `prd/05_databricks` (524-line monolith, own backend key never created, absent from stack map, never destroyed); `kinesis_sqs` remote-state alias; 6 unused variables; `modules/s3` `prevent_destroy` var ignored | SDD-02/05/06, IMPL F-06/F-07/F-18, CI F-08/F-11/F-12/F-22/F-23, SEC M4, LA-09 |
| DRIFT-14 | CI safety | `scripts/ci/tests/` (45 tests: stack-map integrity, plan-gate, apply-path guards) executed by **no** workflow — every guard is decorative; `stack_map.json` declares `modules: []` for DEV stacks that consume 4 modules (`test_dev_stacks_have_no_module_edges` enshrines the defect); prd stacks carry 4 phantom edges; hard-coded stack lists in 4 places despite "single source" claim | CI F-06/F-07, QA F3, SDD-04 |
| DRIFT-15 | CI safety | `deploy_all_dm_applications.yml` (25 jobs incl. PRD `terraform apply`) has **no `concurrency:`**; deploy vs destroy of the same env use different groups → can race one remote state; `all-hml-infra-apply` runs `-auto-approve` under the reviewer-less `hml-apps`; no `.terraform.lock.hcl` anywhere (floating `aws >= 5.0`); `destroy_all` omits `hml/05b_databricks_workspace`; `auto-bump-version` pushes from a detached HEAD | CI F-05/F-09/F-10/F-15/F-17/F-18 |
| DRIFT-16 | Live infra | **2 stale Terraform state locks** since 2026-04-22 on `prd/databricks-account` and `hml/peripherals` → next apply fails | LA-01 |
| DRIFT-17 | Live infra | **24 leaked CI security groups** `dm-hml-sg-<run>` in `ChainExplorer-vpc` (teardown `\|\| true`); proves CI secret `HML_VPC_ID` = the "orphan" legacy VPC → it is the load-bearing HML substrate, unmanaged | LA-02 |
| DRIFT-18 | Databricks deploy drift | `dm-app-logs` deployed in **both** targets is the old CloudWatch `binaryFile` UDF reader — the Fluent-Bit NDJSON fix (2026-05-23) never deployed → VPS deliveries would not parse; hml `dm-ethereum` is pre-R1 code with weaker expectations and bucket config ≠ bundle | DBX-01/02 |
| DRIFT-19 | Databricks broken assets | `dm-trigger-all-dlts` (dev+hml) and hml `dm-dlt-full-refresh` deployed with **empty `pipeline_id`**; `dm-reconcile-orphan-blocks` notebook missing in repo and workspace (deleted `67f8faf`), job scheduled UNPAUSED daily; full-refresh wheel absent; `alert_*`/`genie_ethereum` bundles use resource types unknown to the CLI → validate OK with 0 resources, **never deployed** (memory says "DEV validated SUCCEEDED"); DLT `schedule:` is an unknown field → silently dropped everywhere | DBX-03/04/09, IMPL F-02 |
| DRIFT-20 | Tests | Inverted pyramid: 113/158 tests cover retired code; **0** tests on `apps/lambda` (392 LOC), `apps/dabs` (~3,800 LOC), the 3 live utils modules, DLT expectations; CI runs only `utils/tests/unit` (dead-module tests gate the lambda build); no Terraform policy tooling | QA F1..F10, IMPL F-12 |

### 3.3 MEDIUM

| ID | Area | Finding | Cross-ref |
|---|---|---|---|
| DRIFT-21 | Live infra | PRD `contracts-ingestion` hourly schedule ENABLED: 168 inv/7 d, `contracts_processed:0` every run, DynamoDB 0 items → burns Etherscan quota + logs for nothing (since capture retirement) | LA-04 |
| DRIFT-22 | Live infra | HML half-alive: `hml/peripherals` state declares 2 buckets that 404; `hml/iam` keeps 19 live IAM resources (unused since 04-09); empty ECS cluster; 42 `hml-*` log groups; 60 ACTIVE `dm-*` task-def revisions; the 3 hml buckets referenced by DABs bundles/external location do not exist; `hml` UC catalog has no schemas | LA-05/LA-08, DBX-08 |
| DRIFT-23 | Live infra | Cross-project: `capture/ecr` state (dd-chain-capture ECR+RolesAnywhere+KMS, 11 res.) lives in this repo's state bucket with no source here; KMS `alias/dd-chain-capture-ssm` protects **0** params (US$ 1/mo for nothing); 2 ECR repos empty; scraper role last assumed 2026-07-12 | LA-06 |
| DRIFT-24 | Live infra | Orphans: legacy Lambda `dd-chain-explorer-dev-gold-to-dynamodb` + role + LG; `dm-databricks-dev-s3-role` (the Free-Edition UC→S3 dev credential, no code/state); `dm-hml-firehose-role`; Lambda log groups without retention; `dev/peripherals` state claims a `raw/.keep` object that isn't live | LA-07/10/11 |
| DRIFT-25 | Databricks | prod target `host: ""` falls back to the DEFAULT CLI profile — `validate -t prod` passes ×15, a `deploy -t prod` would create `prd`-catalog assets **on Free Edition**; dashboards hard-code `dev.` catalog in SQL; published `embed_credentials=true` vs bundle `false`; `job_ddl_setup` pre-creates DLT-owned tables and `job_delta_maintenance` OPTIMIZE/VACUUMs ST/MVs (unsupported) | DBX-06/07/11 |
| DRIFT-26 | Security | Databricks bootstrap token persisted cleartext in S3 TF state (`05*/outputs.tf:9`, unchanged since June); unpinned `curl \| bash` actionlint installer in a PR-triggered job; Etherscan key-tail log leak (`etherscan_multi.py:115`), latent bulk-decryption helper `ParameterStoreClient.list_parameters()`, Dockerfile runs as root with floating tag, ECR `MUTABLE`+`force_delete`, SG all-protocol ingress from VPC CIDR, f-string SQL in `job_ddl_setup` | SEC M2/M3/L1..L5/L8/L10 |
| DRIFT-27 | Possibly-dead serving path | `job_export_gold → S3 exports → gold_to_dynamodb λ → DynamoDB PK=CONSUMPTION` existed to feed the retired Job 4's `APIKeysManager`; no in-repo reader remains — if dd-chain-capture doesn't read it, the whole chain (dev+prd lambdas, S3 notifications) is dead; `app_logs_pipeline.py` silver filters on the retired producers' logger names | IMPL F-14/F-15 |
| DRIFT-28 | Docs | README/AGENTS.md/apps READMEs cite **16 nonexistent Makefile targets** (open since 06-11); README, `apps/docker/README.md`, DLT notebook headers, DDL comments, `apps/dabs/README.md` (monolithic bundle), DEPLOYMENT_GUIDE (prod schedule promise) describe Firehose/ECS/Kinesis; `dev_dlt_integration_test.sh` prerequisite "Firehose → S3" | IMPL F-10/F-11, DBX-12, QA F9 |
| DRIFT-29 | Quality gates | No ruff/mypy config; 46/60 files unformatted; 36 default-rule ruff errors (7 `F821 spark`, 19 F401); mypy 13 errors default / 48 strict on `utils/src`; working-tree pollution (`.hypothesis/`, 16 `apps/dabs/*/.databricks/` with nested `.terraform/`), duplicate `test/`+`tests/` trees | IMPL F-13/F-20, SDD-29 |
| DRIFT-30 | Backlog | 7 loose files, no `BACKLOG.md` (ACTIVE+LEDGER), no `specs/backlog/_archive/`; obsolete-by-retirement items still "active" (CAND-R2-01/03/05/07, WS-B4, all 9 `streaming-jobs-security-hardening`, LOW-4, INV-1); GAP-LD-2..6 duplicated; `remediation-audit-20260609.md` is entirely LEDGER material; v0.4.0 executed epic WS-E/E2 without it being picked, WS-E/E1 (deprecation ADR) never written | SDD-20/21/22 |
| DRIFT-31 | Governance | `specs/constitution.md` is a 33-byte stub with no product law (231-line version survives only in `_archive/legacy-memory`); the single open bug `sdd-artifact-linter-mutates-task-markers` is a dadaia-workspace tooling bug misfiled in this ledger (blocks a clean Dispositions sweep); `drift-04` resolved event timestamp precedes its reported evidence | SDD-18/27/28 |

### 3.4 LOW / INFO (record-only unless picked)

Archive cosmetics (SDD-09/10/11), `specs/memory/AGENTS.md` upstream contradiction → route to dadaia-workspace (SDD-19), `img/` slop (IMPL F-17), `destroy_cloud_infra.yml:103` direct interpolation (CI F-19), account noise outside the project (every-minute HelloWorld Lambda with 738 MB log group, ECS-Anywhere hours, Databricks quickstart CFN stacks, SageMaker domain — LA-12), Free-Edition warehouse STOPPED / Statements API refused (DBX-15), test intent-declaration retrofit (QA F8), TF version drift 1.7→1.15 (LA-13), `.bundle/dd-chain-explorer` stale remote state + orphan queries/credential/catalogs (DBX-13).

---

## 4. What is healthy (so the remediation does not re-solve it)

- v0.4.0 deliverables are real: Kinesis/SQS modules gone, 0 Kinesis/Firehose/SQS live, cost collapsed May US$ 62.71 → Aug MTD US$ 4.22 (project ≈ US$ 1/mo).
- 158/158 tests green (~4.5 s), no flakes, no skips, no tombstones in the permanent suite.
- `terraform fmt -check` clean; 21/24 stacks `validate` OK (3 not exercised), 0 failures.
- 100 % of third-party Actions SHA-pinned; least-privilege `permissions:` on every workflow; no `pull_request_target`; zero static keys referenced by any workflow; S3/state bucket hardening correct; Lambda env vars carry SSM pointers only; working tree + 6,530 history blobs: zero real secrets.
- `[dev] dm-ethereum` deployed code == repo; ethereum Auto Loader path contract (`raw/mainnet-{blocks-data,transactions-data,transactions-decoded}/`, JSON, `partitionColumns=""`) is compatible with a Kafka-Connect-style `year=/month=/…` layout — field-name compatibility with the new sink **unverified** (dd-chain-capture not in workspace).
- `dadaia specs doctor`: 0 errors (20 warnings, all inventoried above).

---

## 5. Decisions required from the operator

1. **Close v0.4.0** (memory update incl. `architecture.md` → CLOSURE with honest Validations/Drifts/Dispositions → archive → ff-merge `develop` → diff security review → push). Prerequisite for everything else; the longer it waits, the more agents ground on dead memory.
2. **Re-feed contract with dd-chain-capture** (bucket/prefix/format/field names) — or explicitly declare the platform parked. Until decided: disable the hourly PRD `contracts-ingestion` schedule (DRIFT-21) and keep DLT triggers paused.
3. **CI recovery path**: (a) apply a **least-privilege rewrite** of `prd/03_iam/oidc.tf` (DRIFT-08 first) and set the 4 `AWS_DEPLOY_ROLE_*` variables; (b) delete the dangling static key pair from GitHub **and** IAM (rotate the IAM user's older key); (c) purge the capture lane from `deploy_all_dm_applications.yml`; (d) branch protection + default-branch/`main` decision so `drift_detection` can fire.
4. **Dependency-confusion closure**: either claim `dm-chain-utils` on PyPI, or install only from the local `utils/` build (`--no-index` / path install) and drop the `==0.2.9` public pin; rebuild the layer zip from source in CI (stop tracking binaries).
5. **Fate of HML + orphans**: destroy `hml/iam` + `state rm` phantom buckets, or re-apply HML; import or retire `ChainExplorer-vpc`; sweep the 24 SGs, 42 log groups, task-def revisions, legacy lambda/roles; force-unlock the 2 stale locks.
6. **Dead-code/test purge scope**: delete `apps/docker/onchain-stream-txs/**` + 6 dead utils modules + their tests (qa-engineer verdict per test-stewardship), or keep as archive — then write the minimal live pyramid (lambdas, DABs jobs, DLT expectations).
7. **Privacy posture of a PUBLIC repo**: replace personal e-mail `run_as` with a service principal, decide on host/account identifiers, and confirm the repo should stay public.
8. **Disposition the 2026-06-11 audit** — this audit **supersedes** it where findings overlap (mapped in the lane reports); one remediation release must give all findings of both a terminal token, then both archive.
9. **Constitution**: author a real `specs/constitution.md` or ratify its absence. **Misfiled bug**: re-register under dadaia-workspace.

---

## 6. Disposition status

| Finding set | Status |
|---|---|
| DRIFT-01..31 (this audit) | **open** — awaiting PM intake report → operator pick → one remediation release (`TASKS.md` rows must cite each `DRIFT-n`) |
| 2026-08-19 recap #1–#10 | superseded by this audit (re-verified; mapped to DRIFT-03/04/17/21/22/23/24/25, CI items) |
| 2026-06-11 audit (70 findings) | still undispositioned; overlap mapped in `security-lane.md §7`, `sdd-drift-lane.md §4.2`, `databricks-lane.md` (DRIFT-N01..N04) |
| 2026-06-09 audit | fully dispositioned (`audit-remediation-r5`, v0.3.0) — archive once `specs/audits/_archive/` exists |

This audit archives to `specs/audits/_archive/` only when the remediation release that dispositions every `DRIFT-n` is approved, naming that release.
