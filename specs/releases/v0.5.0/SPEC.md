# SPEC — Release v0.5.0 — Remediation: clean restart of infra, CI and Databricks artifacts

> **Status:** Aprovado
> **Release ID:** v0.5.0
> **Owner:** product-engineer
> **Created:** 2026-08-23
> **Approved:** 2026-08-23 (definition self-check against `dd-release-definition` checklist; reviewer gates are run by the coordinator)
> **Consumes:** v050-ci-oidc-auth-recovery, v050-deploy-workflow-capture-lane-purge, v050-ci-safety-guards-concurrency-lockfile, v050-repo-governance-branch-protection-default-branch, v050-version-axis-unification, v050-public-repo-secret-store-and-pii-hygiene, v050-dependency-confusion-and-lambda-layer-rebuild, v050-dead-code-and-docs-purge-capture-era, v050-dead-iac-purge, v050-live-infra-cleanup-hml-orphans-state-locks, v050-contracts-ingestion-schedule-and-lambda-path-decision, v050-databricks-deploy-drift-redeploy-live-bundles, v050-databricks-bundle-config-hardening, v050-security-hardening-batch, v050-live-surface-test-pyramid, v050-quality-gates-ruff-mypy-worktree, v050-memory-truth-and-capture-deprecation-adr, v050-audit-dispositions-constitution-bug-ledger
> **Provenance:** audit `20260823T145726Z-4db47555` (DRIFT-01..31, score 3.6/10) · undispositioned audit `20260611T001412Z-cb56f84c` (70 findings) · PM intake report `2026-08-23T152638Z-intake-report-audit-20260823` (ratified operator directive) · grill record `2026-08-23T154350Z-refine-specs-v050` (D1–D13 + acceptance gate)
> **Scope (operator-locked):** the Terraform-deployed infrastructure, the GitHub Actions CI that deploys infra and apps, and the Databricks artifacts (DLT pipelines, workflows, dashboards). Data capture belongs to `dd-chain-capture` and is not rebuilt here.

---

## 1. Problem

The audit verdict: **"a correctly-retired capture layer with no successor yet, documented as if it still ran, and governed by a CI that cannot authenticate."**

- **CI is structurally non-functional.** All 55 OIDC steps read repository variables that do not exist; the deploy roles they name were never applied; the only application-deploy workflow still re-provisions the retired capture lane and hard-fails; the CI's own 45 safety tests are executed by no workflow; neither long-lived branch is protected and the scheduled drift check can never fire from the default branch.
- **Terraform declares an infrastructure that is half dead and half unmanaged.** Whole stacks (VPC, ECS, the split-brain Databricks monolith) are 0-resource or never applied; live AWS carries 24 leaked CI security groups inside an unmanaged legacy VPC, 19 unused HML IAM resources, two Terraform state locks stuck since April, orphan lambdas/roles/log groups and orphan state keys.
- **Deployed Databricks code ≠ repo** in 3 of 4 pipelines; trigger, full-refresh and reconcile jobs are broken as deployed; two bundles are silent no-ops; the prod target would deploy against whatever profile the CLI defaults to.
- **44 % of Python LOC and ~72 % of the tests serve the retired capture layer**, while the live surface (2 Lambdas, DABs job scripts, DLT expectations) has zero tests, no lint/type configuration and 16 documented Makefile targets that do not exist.
- **Two audits are undispositioned** (31 + 70 findings), the constitution is a 33-byte stub, and one bug in the ledger belongs to another project.

The platform is idle by design until `dd-chain-capture` delivers. This release does not restart the data flow — it restores a **clean, authenticatable, truthfully-declared platform** so the restart can happen on demand.

---

## 2. Scope — IN (five workstreams with disjoint write sets)

Workstreams are parallelisable: no two write sets intersect **at file level**, with exactly one
seam that is **ordered, not disjoint** — `utils/pyproject.toml` and
`utils/src/dm_chain_utils/__init__.py` are wholly WS-D's, and WS-D sets their version to
`0.5.0` **after** WS-A's `T-A.9` lands the axis (O-4). Every other carve-out is a whole-file
boundary stated explicitly on both sides; no Terraform stack has two appliers.

### 2.1 WS-A — CI authentication, workflow purge and repo governance (D5, D6, D7, D8)

**Goals**

| # | Goal |
|---|---|
| A1 | Author **a new operator-applied bootstrap stack** `services/prd/00_bootstrap/` (D14) — own backend key `prd/bootstrap`, same posture as `01_tf_state`: applied by the operator, never by CI, never destroyed. It holds the OIDC provider reference and the four roles `dm-chain-explorer-gha-deploy-{dev,hml,prd}` + `dm-chain-explorer-gha-readonly-plan`, each with: (a) **scoped allow** statements — project resource prefixes (`dm-chain-explorer-*`, `dm-dd-chain-explorer-*`, `dm-*` as applicable), the state bucket + lock table, the project SSM path prefixes, and Lambda/S3/DynamoDB/Logs/Events/`iam:PassRole` restricted to project roles; (b) an **explicit `Deny`** on `iam:*` against `arn:aws:iam::*:role/dm-chain-explorer-gha-*` and on `iam:CreateAccessKey`/`iam:AttachUserPolicy`/`iam:PutUserPolicy`; (c) trust conditions on `token.actions.githubusercontent.com:sub` — `repo:<owner>/<repo>:environment:<env>` for each deploy role, and `repo:<owner>/<repo>:pull_request` + `…:ref:refs/heads/develop` + `…:ref:refs/heads/main` for the read-only role. **No** `PowerUserAccess`/`AdministratorAccess`, **no** `iam:*` on `*`. `oidc.tf` ceases to exist in `prd/03_iam` (WS-B removes it). |
| A2 | Ship bootstrap as reproducible code and fail loudly without it: a checked-in `scripts/ci/publish_oidc_vars.sh` that reads the `00_bootstrap` outputs and runs `gh variable set AWS_DEPLOY_ROLE_{DEV,HML,PRD,READONLY}`; a **CI preflight step in every workflow** that fails fast when any `vars.AWS_DEPLOY_ROLE_*` is empty; a `scripts/ci/tests` case asserting the preflight exists in every workflow that assumes a role. Then: publish the four variables; delete the static `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` secrets and the capture-era secrets (`DYNAMODB_TABLE`, `ECS_TASK_*_ROLE_ARN`, `HML_VPC_ID`, `HML_SUBNET_ID`); deactivate the CI IAM user's legacy access key. |
| A3 | Purge the capture lane from `deploy_all_dm_applications.yml` — rewrite it as a direct Lambda + DABs deploy behind the informed gate; reduce `hml_provision.sh`/`hml_teardown.sh` to the minimal HML lane of WS-B; delete the tombstoned `hml_integration_test_optimized.sh` gate call. |
| A4 | CI safety: `concurrency:` per environment across deploy and destroy; wire `scripts/ci/tests`, `utils/tests` and the new lambda/DABs tests into `plan_on_pr`, together with **`ruff format --check`, `ruff check` and `mypy` jobs**; trigger `plan_on_pr` on PRs to **both** long-lived branches; the read-only plan path (`tf_plan.sh`, `plan_on_pr`, `drift_detection`) runs `terraform plan -lock=false` so the read-only role needs no lock-table write (covered by a `scripts/ci/tests` case); make `destroy_all` cover every live stack; pin the Terraform version (single-sourced `TF_VERSION` + exact `required_version`) and the actionlint installer (version + checksum); make `stack_map.json` truthful (dev module edges declared, phantom prd edges removed) and remove the four hard-coded stack lists; add a `pip-audit -r` step over the lock file; delete `auto-bump-version.yml`. |
| A5 | Governance: the `main` cut-over sequence of §5 O-8 (rename `master`→`main`, PR `develop`→`main` merged with a **merge commit**, protection named after the first `plan_on_pr` check run, reconciliation merge back to `develop`); protection on `main` (PR required + required status checks, no force-push/deletion) and on `develop` (no force-push/deletion); `production` and `hml` environments require the operator as reviewer; remove every `hml-apps` reference. Stale remote branches are **listed only**, as a committed artifact — the operator deletes. |
| A6 | One version axis = the SDD release id: `VERSION` → `0.5.0`, tag `v0.5.0` at ship; the 15 `apps/dabs/*/VERSION` files aligned; the tag-skip removed from `apps/dabs/deploy_all.sh`; `scripts/ci/check_prd_version.sh` reads `VERSION`. The library's own version declarations (`utils/pyproject.toml`, `utils/src/dm_chain_utils/__init__.py` → `0.5.0`) are **WS-D's**, ordered after this goal (O-4). |
| A7 | Wire the layer pipeline (D15): `plan_on_pr`/deploy build the layer via WS-D's `scripts/build_lambda_layer.sh`, upload it to `s3://dm-chain-explorer-artifacts/lambda-layers/dm-chain-utils/<sha256>.zip` (dev under a `dev/` prefix) and pass `-var layer_s3_key=… -var layer_sha256=…` to the Lambda stacks. |

**Write set:** `.github/workflows/**` · `scripts/ci/**` (helpers, `publish_oidc_vars.sh`, `stack_map.json`, `tests/`) · `services/prd/00_bootstrap/**` (new stack, WS-A only) · GitHub repository settings via `gh` (variables, secrets, branch protection, default branch, environments) · the CI IAM user's access keys and the operator-local apply of `prd/00_bootstrap` · **version-axis carve-out:** `VERSION`, `apps/dabs/*/VERSION`, `apps/dabs/deploy_all.sh`.

**Non-goals:** any other file under `services/**` — including the whole of `prd/03_iam` (WS-B); bundle content other than the `VERSION`/`deploy_all.sh` carve-out (WS-C); the library version declarations (WS-D); deleting stale remote branches; claiming any package name on a public index.

### 2.2 WS-B — Terraform purge, HML reduction and live AWS cleanup (D1-schedule, D2, D4)

**Goals**

| # | Goal |
|---|---|
| B1 | Delete the capture-era and never-applied IaC: `services/prd/{02_vpc,05_databricks,05a_databricks_account,05b_databricks_workspace,07_ecs}`, `services/hml/{02_vpc,03_iam,05_databricks,05b_databricks_workspace,07_ecs}`, `services/modules/{ecs,vpc}`; remove the firehose branch of `modules/cloudwatch_logs` (and its `[0]` index risk), the capture grants in `modules/iam` and `prd/03_iam/iam.tf`, the `kinesis_sqs` remote-state alias, the 6 unused variables and the ignored `prevent_destroy` variable in `modules/s3`. **`prd/03_iam` is wholly WS-B's** — including deleting `oidc.tf` from it once `00_bootstrap` holds the roles (O-1). Enumerated for removal in the same purge: the E2 cross-account / cluster-role set that served the PRD workspace destroyed 2026-04-11 (ADR-002 — no prod workspace; the load-bearing UC credential is `dm-databricks-dev-s3-role`, not these), the hard-coded `databricks_account_uuid` **default** (`variables.tf` — public repo; the variable stays, the default goes), and the `prd/vpc` remote-state alias at `main.tf:33`. |
| B2 | Reduce HML to a minimal lane. Canonical names, single source for WS-C: buckets **`dm-chain-explorer-hml-raw-data`** and **`dm-chain-explorer-hml-lakehouse`**, declared in `hml/04_peripherals`; UC credential roles — **import** the existing `dm-databricks-dev-s3-role` into `dev/01_peripherals` and **create** `dm-databricks-hml-s3-role` in `hml/04_peripherals`, each granting only its own environment's buckets. PRD keeps `01_tf_state`, `03_iam`, `04_peripherals`, `06_lambda`; DEV keeps `01_peripherals`, `02_lambda`. |
| B3 | Live cleanup: force-unlock the two stale state locks; delete the 24 `dm-hml-sg-*` security groups, then the unmanaged legacy VPC with its subnets and internet gateway; delete the empty ECS cluster, the two empty ECR repositories, the HML log groups and the ACTIVE `dm-*` task-definition revisions; delete the legacy dev `gold-to-dynamodb` lambda, its role and log group, and the orphan firehose role; remove the orphan 0-resource state keys and the phantom `hml/peripherals` bucket entries from the state bucket. Lambda log-group **retention is set through Terraform** — the groups are declared as `aws_cloudwatch_log_group` and **imported** into `prd/06_lambda` / `dev/02_lambda`, never set by CLI (so AC-10's clean plan proves it). |
| B6 | Artifact store and layer inputs (D15): create the **`dm-chain-explorer-artifacts`** S3 bucket in `prd/04_peripherals` (versioned, private, no public access; dev consumes the same bucket under a `dev/` prefix); make `prd/06_lambda` and `dev/02_lambda` read the layer from `s3_bucket`/`s3_key`/`source_code_hash` supplied as variables (`layer_s3_key`, `layer_sha256`) instead of `filebase64sha256` on a local path, and build the **handler** zips with `data "archive_file"` from `apps/lambda/<fn>/src` at plan time. |
| B4 | Disable the hourly PRD `contracts-ingestion` schedule **through Terraform** (the Lambda itself is kept); keep the `job_export_gold → gold_to_dynamodb → DynamoDB CONSUMPTION` chain, documented as consumer-unverified. |
| B5 | Reproducibility and hardening inside `services/**`: commit `.terraform.lock.hcl` for every surviving root stack; `required_providers` in modules; stop persisting the Databricks bootstrap token in state; remove the ECR `MUTABLE`/`force_delete` and VPC-CIDR all-protocol ingress declarations with their stacks; encode or drop the manual post-apply `.keep` step. |

**Write set:** `services/**` **except** `services/prd/00_bootstrap/**` (WS-A) — the whole of `prd/03_iam` and its apply included · `services/**/.terraform.lock.hcl` · live AWS mutations in the project's region (EC2/VPC, ECS/ECR, IAM, CloudWatch Logs, Lambda, EventBridge, DynamoDB lock table) · the Terraform state bucket's key space.

**Non-goals:** collapsing dev/hml/prd into one stack tree (deferred, §3); the `00_bootstrap` stack and its operator apply (WS-A); account-level resources outside this project; anything owned by `dd-chain-capture`.

### 2.3 WS-C — Databricks artifacts (D10)

**Goals**

| # | Goal |
|---|---|
| C1 | Drop the no-op `alert_*` and `genie_ethereum` bundles (resource types unknown to the CLI — reinstatement recorded as deferred backlog); remove `job_reconcile_orphans` (notebook deleted). |
| C2 | **Delete `apps/dabs/job_trigger_all` and `apps/dabs/job_full_refresh` entirely.** Both are cross-bundle duplicates of capability the DLT bundles already own natively: per-pipeline trigger jobs exist in-bundle (`dlt_*/resources/workflows/workflow_trigger_*.yml`), and full refresh is `databricks pipelines start-update --full-refresh <id>`, documented in `apps/dabs/README.md`. `${resources.pipelines.*.id}` does not resolve across bundles and a display-name `lookup` would couple bundles through `[dev]`-prefixed names — so the ADR-004 corollary **"no bundle references another bundle's resource"** is recorded in memory by WS-E. Remove the DLT `schedule:` blocks (job-based triggers only — the field is silently dropped). |
| C3 | Guard the workspace host on **every** target, not just prod: `dev`, `hml` and `prod` all read the host from a `DATABRICKS_HOST`-style environment variable or a bundle variable, and the prod variable has **no default**, so `validate -t prod` fails when it is unset. No `cloud.databricks.com` literal survives anywhere in `apps/dabs/**` (AC-19 and C3 then agree). Parametrise the dashboards' catalog instead of hard-coding `dev.`; align the published embed setting with the bundle. Set `run_as` to the service principal (no personal identifier anywhere in `apps/dabs/**`). |
| C6 | HML Unity Catalog: create or update the Databricks **storage credential** and **external location** for `hml` via the CLI (`databricks storage-credentials …`, `databricks external-locations …`) pointing at `dm-databricks-hml-s3-role` and the two canonical hml bucket names of B2, and align every `hml` bundle variable to those exact names. |
| C4 | Scope `job_ddl_setup` and `job_delta_maintenance` to non-DLT objects or remove them; remove the f-string SQL construction; retarget the app-logs silver filter away from the retired producers' logger names. Rewrite `apps/dabs/README.md`. |
| C5 | Deploy `dev` and `hml` so live state == repo — including the app-logs Fluent-Bit reader that was never deployed and the pre-R1 hml ethereum pipeline. Remove the stale `.bundle/dd-chain-explorer` roots and the orphan dashboard file left in the workspace. |

**Write set:** `apps/dabs/**` **except** `apps/dabs/*/VERSION` and `apps/dabs/deploy_all.sh` (WS-A) · the live Databricks workspace `dev` and `hml` targets, including their storage credentials and external locations.

**Non-goals:** any deploy to a prod target; DLT data-quality or dashboard enrichment (deferred — no data flowing); the Free-Edition warehouse state; tests for DABs job scripts (WS-D writes them under `tests/`).

### 2.4 WS-D — Dead code, supply chain, quality gates, tests and docs (D3, D9, D11)

**Goals**

| # | Goal |
|---|---|
| D1 | Delete the capture-era code — git history is the archive: `apps/docker/onchain-stream-txs/**`, the 6 dead `dm_chain_utils` modules and their re-exports, `scripts/prod_ecs_logs.py`, the unreferenced operator scripts, the tombstoned `hml_integration_test_optimized.sh`, and the `img/` slop. **Test deletions require a `qa-engineer` verdict** (test-stewardship) executed by `software-engineer`. |
| D2 | Supply chain (D15): write `scripts/build_lambda_layer.sh` — `pip install --require-hashes -r requirements.lock -t build/` for the third-party dependencies **plus** `pip install ./utils -t build/ --no-deps` for the library as a **path** requirement (the path install, not a flag, is what closes dependency confusion; `--no-index` is wrong here because the transitive deps do come from the index, hash-pinned) — and the `requirements.lock` it consumes; zip `build/` to `.lambda_zip/` (untracked + gitignored). Drop the public `==0.2.9` pin everywhere; untrack the tracked binary deploy artifacts; pin every lambda/utils requirement with `==`. CI upload + the Terraform variables are WS-A/WS-B (A7/B6). |
| D6 | Set the library version declarations to `0.5.0` (`utils/pyproject.toml`, `utils/src/dm_chain_utils/__init__.py`) — **after** WS-A's axis task lands (O-4). |
| D3 | Quality gates: add `ruff` (format + check) and `mypy` configuration to the repo and make them pass; clean the working tree (gitignore the bundle/terraform/hypothesis state dirs, remove the duplicate test tree); remove the residual key-tail logging and the bulk parameter-listing helper that survive in kept code. |
| D4 | Write the live-surface pyramid under a repo-level `tests/` tree: Lambda handlers, DABs job scripts, DLT expectation functions (local PySpark), plus the tests that the CI-script suite still lacks. Declare intent and size on every new test. |
| D5 | Docs: fix the 16 nonexistent Makefile targets (reduce the Makefile to thin wrappers over the scripts CI uses), and rewrite `README.md`, `docs/**`, the app READMEs, the DLT notebook headers, the DDL comments and the integration-test prerequisites to the post-capture scope. |

**Write set:** `apps/docker/**` (deletion) · `apps/lambda/**` (incl. `requirements.lock`) · `utils/**` **wholly**, `utils/pyproject.toml` and `utils/src/dm_chain_utils/__init__.py` included (ordered after `T-A.9`, O-4 — this is the one ordered-not-disjoint seam) · `scripts/**` **except** `scripts/ci/**` (WS-A) — `scripts/build_lambda_layer.sh` is WS-D's · `tests/**` (new) · `Makefile` · `README*`, `docs/**`, repo-local `AGENTS.md` · root `pyproject.toml`/ruff/mypy config · `.gitignore`, `.gitguardian.yml` · `img/`.

**Non-goals:** editing workflows (WS-A) or bundles (WS-C); deleting a test without a `qa-engineer` verdict; changing runtime behaviour of the kept Lambdas.

### 2.5 WS-E — Governance documents, audit dispositions and memory truth (D12)

**Goals**

| # | Goal |
|---|---|
| E1 | Author `specs/constitution.md` from the archived 231-line version, scoped to the infra / CI / Databricks reality. |
| E2 | Write the capture-deprecation ADR (supersession by `dd-chain-capture`, S3 as the sole boundary, parked-until-delivery posture, sunset criteria), rewrite the ADR-005 lambda-union claim to the streaming-only reality, and record the ADR-004 corollary **"no bundle references another bundle's resource"** (C2). All three land in `specs/memory/architecture.md`, which is gate-writable in DEFINITION/CLOSURE only — so they are **CLOSURE-phase memory writes** executed with `T-E.4`, never during implementation. |
| E3 | Give **every** DRIFT-01..31 and **every** 2026-06-11 finding id a terminal disposition (§7 is the source; CLOSURE `## Dispositions` is the ledger), then archive both audit directories with a `DISPOSITION.md` naming v0.5.0. |
| E4 | Bug ledger: terminal event for the misfiled tooling bug (re-registered upstream in the workspace library context); fix the resolved-before-reported timestamp anomaly; move the stray legacy release SPEC under `_archive/`. |
| E5 | At CLOSURE: update the memory atoms to the post-release truth (§8). |

**Write set:** `specs/constitution.md` · `specs/releases/v0.5.0/**` · `specs/releases/ACTIVE.md` · `specs/audits/**` · `specs/bugs/*.jsonl` · `specs/memory/**` (CLOSURE phase only) · `specs/_archive/**` via `git mv` only.

**Non-goals:** `specs/backlog/**` (project-manager curates; purge-on-pick rides the SPEC commit); authoring backlog entries for residuals — they are listed in CLOSURE for the PM's intake report.

---

## 3. Scope — OUT

| Out of scope | Reason |
|---|---|
| `capture/ecr` state, its KMS alias and RolesAnywhere resources | Owned by `dd-chain-capture` (DRIFT-23) — routed there; only the state-key documentation is this repo's |
| Anything else inside `dd-chain-capture` | Separate repository |
| Single stack tree + per-env tfvars; module interface hygiene; hardcoded backend/region collapse | Restructuring, not drift — deferred to a release after v0.5.0 (`terraform-single-stack-tree-per-env-tfvars`) |
| DLT data-quality enrichment, dashboard/analytics enrichment | Need flowing data; the platform has been dry since 2026-05-23 |
| Re-feed contract validation with the new sink (field-name compatibility), un-pausing DLT triggers, any data backfill | Parked until `dd-chain-capture` delivers (D1); the compatibility check is a documented TODO |
| REST API public endpoint | Outside the directive's scope; own planning session |
| Encryption-at-rest posture / CMK decision; S3 raw lifecycle tiering | Deferred — no new data at rest, prefix layout unconfirmed |
| Account-level noise outside the project (a per-minute unrelated Lambda and its log group, ECS-Anywhere hours, quickstart stacks, ML domain) | Operator account hygiene, routed without a backlog entry |
| Claiming the library name on a public package index | D9 chose path-install; the name claim is not required and is not a release deliverable |
| Deleting the 10 stale remote branches | Listed by WS-A; the operator executes |
| Reinstating alert/Genie Databricks assets | Deferred backlog — the CLI does not support those resource types today |

---

## 4. Acceptance criteria

Every criterion is mechanically verifiable. Commands run from the repository root with the environment's role context assumed; `<state-bucket>`, `<lock-table>` and `<ci-user>` are the values recorded in `specs/memory/product/aws-resources.md`.

| AC | WS | Verification | Pass condition |
|---|---|---|---|
| AC-1 | A | `gh variable list` | the 4 `AWS_DEPLOY_ROLE_{DEV,HML,PRD,READONLY}` variables exist with non-empty role ARNs |
| AC-2 | A | `aws iam list-roles --query "Roles[?contains(RoleName,'gha')].RoleName"` then `aws iam list-attached-role-policies` + `aws iam get-role-policy` per role; **plus** a `scripts/ci/tests` case over `terraform show -json services/prd/00_bootstrap` | the 4 `gha` roles exist and are declared by `00_bootstrap`, not `03_iam`; **no** `PowerUserAccess`/`AdministratorAccess`/`ReadOnlyAccess` attachment; no inline statement granting `iam:*` on `"*"`; the assertion script proves **every** `Allow` resource matches a project prefix or the state bucket/lock table, and that each role carries the explicit `Deny` on `arn:aws:iam::*:role/dm-chain-explorer-gha-*`; each deploy role's trust `sub` is `repo:<owner>/<repo>:environment:<env>`, the read-only role's is `pull_request` + `refs/heads/{develop,main}` |
| AC-2b | A | `aws iam simulate-principal-policy` per `gha` role: forbidden `iam:UpdateAssumeRolePolicy` on a `dm-chain-explorer-gha-*` role ARN, and one representative allowed action | forbidden action → `implicitDeny` or `explicitDeny` for all 4 roles; the allowed action → `allowed` |
| AC-3 | A | `gh secret list`; `aws iam list-access-keys --user-name <ci-user>` | no `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`/`DYNAMODB_TABLE`/`ECS_TASK_*`/`HML_VPC_ID`/`HML_SUBNET_ID` secrets remain; the 2025-vintage key is `Inactive` |
| AC-3b | A | `git ls-files scripts/ci/publish_oidc_vars.sh`; `grep -L 'AWS_DEPLOY_ROLE' .github/workflows/*.yml` for role-assuming workflows; the `scripts/ci/tests` preflight case; a deliberate empty-variable dry run | the publish script is checked in and reads the `00_bootstrap` outputs; every role-assuming workflow carries the preflight step; with a variable emptied, the job fails **at the preflight step** with an explicit message, not at `configure-aws-credentials` |
| AC-4 | A | `plan_on_pr` run on a PR into `main` from a fresh clone | run conclusion `success`, with fmt, validate, actionlint, **`ruff format --check`, `ruff check`, `mypy`**, the three test suites, `pip-audit -r` and per-stack plan (`-lock=false`) all green under OIDC |
| AC-4b | A | `grep -n 'lock=false' scripts/ci/tf_plan.sh`; the `scripts/ci/tests` case; `aws iam get-role-policy` for the read-only role | the read-only plan path passes `-lock=false`, asserted by a test; the read-only role grants **no** lock-table write (`dynamodb:PutItem`/`DeleteItem` absent) |
| AC-5 | A | `grep -rniE 'kinesis\|firehose\|sqs\|ecs\|onchain-stream' .github/workflows/ scripts/ci/` | 0 matches; `deploy_all_dm_applications.yml` job graph contains only Lambda + DABs deploy jobs |
| AC-6 | A | `gh workflow list`; grep each workflow for `concurrency:` | `auto-bump-version.yml` absent; every remaining workflow declares a per-environment `concurrency` group; deploy and destroy of the same environment share it |
| AC-7 | A | `gh repo view --json defaultBranchRef`; `gh api repos/{owner}/{repo}/branches/{main,develop}/protection`; `gh api repos/{owner}/{repo}/environments`; `gh api repos/{o}/{r}/contents/.github/workflows/drift_detection.yml?ref=main`; `gh workflow view drift_detection` | default branch `main`; `main` requires a PR and the `plan_on_pr` status check, no force-push/deletion; `develop` no force-push/deletion; `production` and `hml` carry a required reviewer; no `hml-apps` environment or reference; the drift workflow returns 200 on the default branch and shows as **enabled** (its next cron is the first real run — recorded as pending, not as evidence) |
| AC-7b | A | `git ls-files` for the stale-branch listing artifact; `gh api repos/{o}/{r}/branches --paginate` | a committed listing (CLOSURE section or `docs/` artifact) names each stale remote branch with its last-commit date; **no branch was deleted by this release** |
| AC-8 | A | `cat VERSION`; `git tag --list 'v0.5.0'`; `grep -rn '0\.2\.9' -- . ':!specs'`; `cat apps/dabs/*/VERSION \| sort -u`; `grep -n version utils/pyproject.toml utils/src/dm_chain_utils/__init__.py` | `0.5.0` everywhere; tag `v0.5.0` at ship; 0 hits on the old axis; every bundle VERSION and both library declarations `0.5.0` |
| AC-9 | A | `pytest scripts/ci/tests -p no:cacheprovider` and the `plan_on_pr` job log; `grep` for the pinned `TF_VERSION` and `required_version` | suite green **and** executed by CI; `stack_map.json` declares dev module edges and no phantom prd edges (asserted by a test); a test asserts `destroy_all`'s stack set equals `stack_map.json`'s survivors; the Terraform version is single-sourced and `required_version` is exact |
| AC-10 | B | `deploy_cloud_infra` plan phase for `dev` and `prd`, **from a fresh clone with no local `.lambda_zip/`** | plan summary `0 to add, 0 to change, 0 to destroy` on every kept stack (`dev/01_peripherals`, `dev/02_lambda`, `prd/00_bootstrap`, `prd/01_tf_state`, `prd/03_iam`, `prd/04_peripherals`, `prd/06_lambda`, `hml/04_peripherals`), with the layer resolved from `layer_s3_key`/`layer_sha256` and the handler zips from `archive_file` — no `filebase64sha256` on a working-tree path anywhere; the imported Lambda log groups plan clean with their retention |
| AC-11 | B | `ls services/prd services/hml services/modules`; `aws s3api list-objects-v2 --bucket <state-bucket> --query 'Contents[].Key'` | the deleted stacks and modules are absent from disk; no state key remains for a deleted stack; no phantom bucket entry in the HML peripherals state |
| AC-12 | B | `aws ec2 describe-security-groups --filters Name=group-name,Values=dm-hml-sg-*`; `aws ec2 describe-vpcs --filters Name=tag:Name,Values=ChainExplorer-vpc`; `aws ecs list-clusters`; `aws ecr describe-repositories`; `aws logs describe-log-groups --log-group-name-prefix /hml`; `aws lambda list-functions` | 0 security groups; 0 VPCs; no project ECS cluster; no `onchain-*` repository; 0 HML log groups; no legacy `gold-to-dynamodb` dev function or its role; every kept Lambda log group has a retention setting |
| AC-13 | B | `aws dynamodb scan --table-name <lock-table> --select COUNT` | `Count: 0` — both April locks released |
| AC-14 | B | `aws events list-rules` + `describe-rule` for the ingestion schedule | `State: DISABLED`, and the disabled state is declared in Terraform (AC-10 plan clean proves it) |
| AC-15 | B | `git ls-files 'services/**/.terraform.lock.hcl' \| wc -l` | equals the number of surviving root stacks |
| AC-16 | B | `grep -rniE 'kinesis\|firehose\|sqs' services/`; `aws iam list-roles --query "Roles[?contains(RoleName,'firehose')]"` | 0 matches; 0 roles |
| AC-17 | C | `for b in apps/dabs/*/; do databricks bundle validate -t dev; databricks bundle validate -t hml; done`; `databricks bundle validate -t prod` with the host variable unset | exit 0 for every surviving bundle in `dev` and `hml`; **non-zero** for `prod` without the host variable; `apps/dabs/job_trigger_all` and `apps/dabs/job_full_refresh` are absent from disk |
| AC-18 | C | `databricks workspace export <deployed-notebook-path>` **diffed against the repo file** per pipeline per target; `databricks bundle summary -t dev`/`-t hml`; `databricks jobs list` | `diff` exit **0** for every deployed pipeline's source notebook against its repo file (app-logs reader is the Fluent-Bit version; hml ethereum is current); no job carries an empty `pipeline_id`; the reconcile job is absent; no stale `.bundle` root or orphan dashboard remains |
| AC-18b | C | `aws s3api head-bucket` on both canonical hml buckets; `databricks external-locations get <hml>`; `databricks storage-credentials get <hml>`; `databricks bundle validate -t hml` | both `head-bucket` calls return 200; the external location's `url` matches the canonical hml bucket names of §2.2 B2 and its credential is `dm-databricks-hml-s3-role`; every hml bundle variable names those same buckets; validate clean |
| AC-19 | C | `grep -rniE '@\|cloud.databricks.com\|"dev\."' apps/dabs/`; `databricks service-principals list` | no personal identifier, no hard-coded workspace host **in any target**, no hard-coded catalog in dashboard SQL; every target's `run_as` is the service principal, and that principal (`dm_spn_user`) exists in the listing |
| AC-20 | D | `ls apps/docker`; `grep -rn 'dm_kinesis\|dm_sqs\|dm_firehose\|dm_web3_client\|dm_cloudwatch_logger\|api_keys_manager' --include='*.py' .`; the `qa-engineer` verdict handoff | directory absent; 0 references; a recorded verdict precedes every test deletion |
| AC-21 | D | `grep -rn 'dm-chain-utils==' .`; `git ls-files '*.zip' '*.whl'`; `git check-ignore .lambda_zip/`; the layer-build job log; `pip-audit -r apps/lambda/requirements.lock` | 0 public pins; 0 tracked binaries; `.lambda_zip/` gitignored; the layer is built from the **path** requirement `./utils --no-deps` plus `--require-hashes -r requirements.lock` for third-party deps, uploaded to `s3://dm-chain-explorer-artifacts/lambda-layers/dm-chain-utils/<sha256>.zip`; `pip-audit -r <lock>` reports no findings, or each finding is covered by an explicit ignore recorded in this row (an unfixed transitive CVE is documented, never silently passed) |
| AC-22 | D | `ruff format --check . --no-cache`; `ruff check . --no-cache`; `mypy` on the configured scope; `git status --porcelain` | all exit 0; working tree clean; no bundle/terraform/hypothesis state directory and no duplicate test tree tracked |
| AC-23 | D | `pytest -p no:cacheprovider` | green, and the suite includes tests for both Lambda handlers, the DABs job scripts and the DLT expectation functions; every new test declares intent and size; the demotion/deletion map carries a `qa-engineer` verdict |
| AC-24 | D | `make -n <target>` for every target cited in docs; `grep -rniE 'kinesis\|firehose\|ECS producer' README* docs/ apps/**/README*` | every cited target resolves (the 16 broken ones fixed); 0 stale-architecture matches; `img/` slop removed |
| AC-25 | E | `dadaia specs doctor`; `dadaia backlog doctor` | 0 errors; backlog clean |
| AC-26 | E | `wc -l specs/constitution.md`; read | a real, scoped constitution — not the 33-byte stub; the capture-deprecation ADR exists |
| AC-27 | E | CLOSURE `## Dispositions`; `ls specs/audits/_archive/` | every DRIFT-01..31 and every 2026-06-11 finding id carries a terminal token; both audit directories archived with a `DISPOSITION.md` naming v0.5.0 |
| AC-28 | E | `dadaia bugs status` | 0 open bugs in this context; the misfiled bug carries a terminal event referencing its upstream re-registration |

**Ship gate (grill acceptance, all must hold together):** a fresh clone with `plan_on_pr` green on a PR into `main` (AC-4); `deploy_cloud_infra` plan showing 0 diff on the kept dev/prd stacks (AC-10); live AWS free of every orphan in the audit's drift matrix (AC-11..AC-16); `databricks bundle validate -t dev`/`-t hml` clean **and** deployed state == repo (AC-17/AC-18); `dadaia specs doctor` 0 errors and `backlog doctor` clean (AC-25); **re-audit score ≥ 7 with no dimension below 5** — any dimension < 5 blocks ship.

---

## 5. Ordering safety

| # | Rule |
|---|---|
| O-1 | The `prd/00_bootstrap` stack is authored least-privilege, security-reviewed, then **applied locally by the coordinator with operator credentials** — the only apply in the release that does not run through CI, and the only one CI may never run. Its four ARNs are published as variables **before** any workflow run is used as evidence (O-9). `oidc.tf` is removed from `prd/03_iam` (WS-B) only **after** `00_bootstrap` holds the roles, and the removal is applied so `03_iam` plans clean. |
| O-1b | The `prd/vpc` remote-state alias and every consumer of it are removed **and applied** in the same commit as — and before — the `prd/vpc` state key is deleted (`T-B.11`). General rule: **every remote-state alias/consumer is edited in the same commit that removes the state key it points to.** |
| O-1c | The `dm-chain-explorer-artifacts` bucket exists (`T-B.14`) **before** the first CI layer upload; the layer object exists at its content-addressed key **before** any Lambda-stack plan that consumes `layer_s3_key`/`layer_sha256`. |
| O-2 | The two stale state locks are released **before** any plan or apply touches their stacks. |
| O-3 | Security groups are deleted **before** the legacy VPC; subnets and the internet gateway follow the VPC's dependency order. Nothing in HML is destroyed before WS-B has confirmed which buckets the bundles reference. |
| O-4 | The version-axis carve-out (A6) lands **before** WS-C or WS-D edit any file in it, so the carve-out never needs a second pass. |
| O-5 | `.terraform.lock.hcl` files are committed **before** the first gated apply, so the apply runs the provider version it planned against. |
| O-6 | Bundles are validated in `dev` and `hml` **before** any deploy; nothing is deployed to a prod target in this release. |
| O-7 | Dead code and tests are deleted **only after** the `qa-engineer` verdict, and the live-surface tests (D4) are written before the retired tests are removed — coverage never dips to zero in between. |
| O-8 | **`main` cut-over sequence — executed in this exact order** (the procedure of `T-R.3`): (1) every workstream merged to `develop` and pushed; (2) `plan_on_pr`'s trigger already lists `main` (landed by `T-A.7`); (3) rename the default branch `master`→`main` via `gh api --method POST repos/{o}/{r}/branches/master/rename` — GitHub preserves redirects; (4) open the PR `develop` → `main`; (5) the **first `plan_on_pr` run on that PR** is the source of the required check name; (6) set `main` protection requiring that check plus a PR, and `develop` protection (no force-push/deletion); (7) merge with a **merge commit — never squash** — so `master`'s 4 unique commits are reconciled rather than orphaned; (8) merge `main` back into `develop` locally and push `develop`; (9) verify `drift_detection.yml` on the default branch and the workflow enabled (AC-7); its next cron is the first real run, recorded as pending. |
| O-9 | The four repository variables exist **before** any workflow run is used as acceptance evidence. |
| O-10 | Audit archival (E3) happens at CLOSURE, after every disposition row has evidence — never before. |

---

## 6. Execution model

- Definition and implementation both run on `feature/0.5.0`, cut from `develop`.
- **Milestone (a):** when SPEC + PLAN + TASKS are all `Aprovado` — merge into local `develop`, diff-based security review of the delta, push `develop`.
- **alpha-1:** WS-A, WS-B, WS-C, WS-D and WS-E implemented and closed by a `qa-engineer` review committed to the branch. Workstreams may run in parallel (disjoint write sets, §2); live-mutating steps are operator-gated.
- **rc-1:** the full trio — `qa-engineer`, `code-reviewer` (six-axis on the delta), `security-reviewer` (diff-based) — all APPROVED.
- **Ship:** memory update → CLOSURE → archive, merge into `develop`, diff security review, push, PR `develop` → `main`, watch CI to green, then re-audit against the ship gate (§4).

---

## 7. Finding-disposition matrix

This section is what allows **both** audits to archive at CLOSURE. Every row's terminal token is re-asserted in CLOSURE `## Dispositions` with evidence.

### 7.1 Audit `20260823T145726Z-4db47555` — DRIFT-01..31 (31/31 dispositioned)

| Finding | Disposition |
|---|---|
| DRIFT-01 CI cannot authenticate | fixed by WS-A (A1 bootstrap stack, A2 publish script + preflight) |
| DRIFT-02 deploy workflow re-provisions capture | fixed by WS-A (A3) |
| DRIFT-03 v0.4.0 done-but-open | fixed by the v0.4.0 CLOSURE of 2026-08-23 (archived release + memory rewrite); re-verified by WS-E |
| DRIFT-04 six stale memory atoms | fixed by the v0.4.0 CLOSURE memory rewrite; residual (deprecation ADR + post-v0.5.0 truth) fixed by WS-E (E2, E5) |
| DRIFT-05 audits undispositioned | fixed by WS-E (E3 — this matrix) |
| DRIFT-06 dependency confusion | fixed by WS-D (D2) |
| DRIFT-07 committed layer zip, 31 CVEs | fixed by WS-D (D2 build script + lock), WS-A (A7 CI upload) and WS-B (B6 artifact bucket + Terraform variables) — the artifact leaves the module tree (D15) |
| DRIFT-08 admin-escalating deploy roles | fixed by WS-A (A1 — relocation out of the CI-applied stack + explicit self-mutation `Deny`, proven by AC-2/AC-2b) |
| DRIFT-09 public-repo secrets + personal identifier | fixed by WS-A (A2 — secret store, IAM key) **and** WS-C (C3 — `run_as`, host) |
| DRIFT-10 no branch protection, default branch | fixed by WS-A (A5) |
| DRIFT-11 two version axes | fixed by WS-A (A6) |
| DRIFT-12 16 dead Python modules | fixed by WS-D (D1) |
| DRIFT-13 dead IaC (ECS/firehose/grants/monolith) | fixed by WS-B (B1) |
| DRIFT-14 CI safety tests never run, stack map lies | fixed by WS-A (A4) |
| DRIFT-15 no concurrency, no lock files, destroy gaps | fixed by WS-A (A4) and WS-B (B5, lock files) |
| DRIFT-16 two stale state locks | fixed by WS-B (B3) |
| DRIFT-17 24 leaked SGs in the unmanaged VPC | fixed by WS-B (B3) |
| DRIFT-18 Databricks deploy drift | fixed by WS-C (C5) |
| DRIFT-19 broken/no-op DABs assets | fixed by WS-C (C1; C2 — `job_trigger_all` and `job_full_refresh` deleted outright, capability already native in the DLT bundles); alert/Genie reinstatement deferred (backlog, CLI lacks the resource types) |
| DRIFT-20 inverted test pyramid | fixed by WS-D (D1, D4) |
| DRIFT-21 hourly ingestion schedule burning quota | fixed by WS-B (B4) |
| DRIFT-22 HML half-alive | fixed by WS-B (B2 canonical bucket names + `dm-databricks-hml-s3-role`, B3 live cleanup, **`T-B.12`** import of `dm-databricks-dev-s3-role` into `dev/01_peripherals`) and WS-C (C6 storage credential + external location, `T-C.7`); proven by AC-18b |
| DRIFT-23 cross-project capture state + KMS | deferred (`capture-ecr-state-and-kms-ownership-transfer`) — resources owned by `dd-chain-capture`; the state-key documentation half fixed by WS-E (E5) |
| DRIFT-24 live orphans (lambda, roles, log groups) | fixed by WS-B (B3) |
| DRIFT-25 prod target, dashboards, DDL/maintenance jobs | fixed by WS-C (C3, C4) |
| DRIFT-26 security hardening batch | fixed by WS-A (actionlint pin), WS-B (token in state, ECR flags, SG ingress), WS-C (f-string SQL), WS-D (key-tail log, parameter-listing helper, container hardening removed with the image) |
| DRIFT-27 possibly-dead gold→DynamoDB chain | fixed by WS-E (E5) — chain **kept** per D1 and documented as consumer-unverified; the retired-logger silver filter fixed by WS-C (C4) |
| DRIFT-28 docs cite 16 nonexistent targets / dead architecture | fixed by WS-D (D5) |
| DRIFT-29 no quality gates, polluted worktree | fixed by WS-D (D3) |
| DRIFT-30 backlog structure | fixed at intake by project-manager (single-source `BACKLOG.md` + `_archive/`, 2026-08-23); re-verified by WS-E (AC-25) |
| DRIFT-31 stub constitution, misfiled bug, timestamp anomaly | fixed by WS-E (E1, E4) |

### 7.2 Audit `20260611T001412Z-cb56f84c` — 70 deduplicated findings across 82 lane ids (82/82 dispositioned)

Grouped where the disposition is identical. Lane ids per `architecture-review.md`, `cicd-terraform-review.md`, `security-review.md`, `sdd-drift-audit.md`; overlap maps in `security-lane.md §7`, `sdd-drift-lane.md §4.2`, `databricks-lane.md`.

| Finding id(s) | Disposition |
|---|---|
| ARCH-C1 split-brain PRD Databricks | fixed by WS-B (B1 — the monolith and both successor stacks are deleted) |
| ARCH-C2 HML does not validate PRD | superseded by DRIFT-22 → fixed by WS-B (B2) + WS-C (C5): HML becomes a minimal lane with unified bucket names; no PRD workspace exists to validate against |
| ARCH-H1, CI-H5, CI-H6, CI-H7, CI-M4, CI-M5, CI-M8, CI-L7 | deferred (`terraform-single-stack-tree-per-env-tfvars`) — restructuring, not drift |
| ARCH-H2, CI-L1..CI-L5 Makefile stale control plane | fixed by WS-D (D5) |
| ARCH-H3, ARCH-M1, ARCH-M2, ARCH-M4 memory/architecture fidelity | fixed by the v0.4.0 CLOSURE memory rewrite (2026-08-23); post-release truth re-asserted by WS-E (E5) |
| ARCH-H4, ARCH-M9, ARCH-M10, SEC-M-01, SEC-M-02, SEC-L-01, SEC-L-03 (runtime half), SEC-L-04 | rejected — obsolete: the streaming peripherals, task definitions and capacity model were destroyed in v0.4.0 and their modules deleted |
| ARCH-H5 capture supersession without ADR | fixed by WS-E (E2) |
| ARCH-H6, CI-H2, CI-M7 reproducibility | fixed by WS-B (B5 lock files, `required_providers`) + WS-A (A4 Terraform version pin) + WS-D (D3 gitignore) |
| ARCH-M3, ARCH-M5 DABs duplication / Genie scaffolding | fixed by WS-C (C1, C3 — parametrised targets; Genie dropped, reinstatement deferred) |
| ARCH-M6 vestigial ABI cache + dead IAM grants | fixed by WS-D (D1, code half) + WS-B (B1, IAM grants) |
| ARCH-M7, CI-L6 working-tree pollution | fixed by WS-D (D3) |
| ARCH-M8 REST API specced, zero implementation | deferred (`rest-api-public-endpoint`); the stray legacy spec file is archived by WS-E (E4) |
| ARCH-L1, ARCH-L2, ARCH-L4 stale comments, gitignore archaeology, duplicated integration scripts | fixed by WS-D (D1, D5) |
| ARCH-L3, ARCH-L7, SEC-L-02 orphan ECR repo, manual `.keep` step, ECR flags | fixed by WS-B (B1, B3, B5) |
| ARCH-L5 three naming patterns | rejected — advisory-only; the divergent surfaces are deleted by WS-B/WS-D and the survivors keep one prefix |
| ARCH-L6 dev compose mounts host credentials | rejected — obsolete: the compose stack no longer exists in `services/dev/` |
| ARCH-L8 stray legacy release SPEC outside `_archive/` | **already relocated at intake** (2026-08-23, before this SPEC was authored) — WS-E (`T-E.3`) re-verifies that no release SPEC other than the active one lives outside `_archive/` and records the verification as the evidence |
| CI-C1, CI-C2, CI-C3, CI-H1, CI-H3, CI-H4, CI-H8, CI-M2, CI-M3 | fixed in v0.3.0 (informed gate, per-stack apply signal, fmt/validate gate, timeouts, error-masking purge) — evidence: `_archive/releases/v0.3.0/CLOSURE.md`; the concurrency residual is DRIFT-15 → WS-A |
| CI-M1 pervasive `\|\| true` | partially fixed in v0.3.0; residual in the HML teardown fixed by WS-A (A3) |
| CI-M6 utils pin mismatch | fixed by WS-D (D2) |
| CI-M9 missing concurrency on the bump/drift workflows | fixed by WS-A (A4 — the bump workflow is deleted, the drift workflow gets a group) |
| CI-M10 branch-model ambiguity (tagging one branch, deploying another) | fixed by WS-A (A5, A6) |
| CI-M11 commented-out/dead code | fixed by WS-B (Terraform half) + WS-D (Makefile half) |
| SEC-H-01 raw key logged | rejected — debunked: the logged value is an SSM parameter name, not a secret (`security-lane.md §7`); the residual name-logging is hardened by WS-D (D3) |
| SEC-H-02, SEC-I-01, SEC-M-05 static keys / no federation / PR-plan credentials | fixed in v0.3.0 (code) **and** WS-A (A1, A2 — the live half: roles applied, variables published, static keys deleted, read-only role narrowed) |
| SEC-M-03 Databricks token in state | fixed by WS-B (B5) |
| SEC-M-04 CMK posture | deferred (`encryption-at-rest-posture-decision`) — no new data at rest |
| SEC-L-05 scanner ignore blind spot | fixed by WS-D (D3) |
| SEC-I-02, SEC-I-03 (positive observations: destroy guardrails, SHA pinning) | record-only — no fix surface; both properties are preserved, and WS-A adds the required environment reviewers the observation asked for |
| DRIFT-N01, N02, N03 ADR-005 union / dangling producer | fixed by WS-B (B4 — schedule disabled, Lambda kept) + WS-E (E2 — ADR rewritten to the streaming-only reality) |
| DRIFT-N04, N05, N11, N12 catalog totals, supersession cross-ref, frontmatter drift, stale line range | fixed by the v0.4.0 CLOSURE memory rewrite (the frontmatter schema no longer carries the drifting field) |
| DRIFT-N06 quality-assurance stub | fixed by the v0.4.0 CLOSURE (atom authored); refreshed by WS-E (E5) after WS-D's pyramid |
| DRIFT-N07, N09 dependency pin mismatch and floor drift | fixed by WS-D (D2) |
| DRIFT-N08 streaming tests not wired into CI | rejected — obsolete: those tests are deleted with the capture code (WS-D D1) and replaced by the live-surface pyramid (D4) |
| DRIFT-N10 Makefile target count | fixed by WS-D (D5) |

---

## 8. Memory files affected at CLOSURE (do NOT write now)

| Atom | Written when |
|---|---|
| `specs/memory/product/cicd-pipeline.md` | WS-A closes — the "Estado real e lacunas" gap list is replaced by the working OIDC/gate/protection reality; the workflow inventory drops the deleted bump workflow |
| `specs/memory/product/aws-resources.md` | WS-B closes — inventory reduced to the surviving stacks/resources; orphans, leaked SGs, stale locks and phantom state entries removed; the cross-project state key documented (DRIFT-23) |
| `specs/memory/architecture.md` | WS-B and WS-E close — layer map without the deleted VPC/ECS/Databricks-account stacks; the capture-deprecation ADR and the rewritten ADR-005 |
| `specs/memory/product/medallion-pipelines.md` | WS-C closes — pipeline inventory, trigger model without DLT `schedule:`, deployed-equals-repo statement |
| `specs/memory/product/serving-layer.md` | WS-C and WS-B close — dashboards parametrised, alerts/Genie removed from the surface, the gold-export→DynamoDB chain documented as consumer-unverified |
| `specs/memory/product/data-catalog.md` | WS-C closes **only if** the object inventory changes |
| `specs/memory/product/capture-layer.md` | WS-E closes — parked-until-delivery posture and the field-name compatibility TODO |
| `specs/memory/quality-assurance.md` | WS-D closes — the real pyramid, the gates now enforced in CI, the test-stewardship declarations |
| `specs/memory/tech-stack.md` | WS-D and WS-A close — path-installed library, pinned requirements, ruff/mypy, pinned Terraform, one version axis |
| `specs/memory/product/index.md` + `catalog.json` | only if a feature's rank changes or an atom is added/removed |

---

## 9. Dependencies & risks

| Risk | Mitigation |
|---|---|
| **Live mutation is irreversible** (VPC, IAM, ECR, log groups, state keys). | Every live-destructive step is operator-gated; deletion order is fixed by §5; each deletion has an AC that proves absence and a kept-resource AC that proves survival (AC-10, AC-12). |
| **Bootstrap paradox**: CI cannot authenticate until the roles it needs exist, and the roles were applied by the stack CI applies. | D14: the roles move to `prd/00_bootstrap`, a stack CI never applies, so the paradox disappears instead of being re-lived. Bootstrap is reproducible code, not tribal knowledge: the stack, `publish_oidc_vars.sh` and a runbook are checked in, and the CI preflight fails loudly on an empty variable (AC-3b). |
| **Self-escalation**: a deploy role able to rewrite its own trust policy is not least-privilege, whatever its prefix scoping. | Explicit `Deny` on `iam:*` against `arn:aws:iam::*:role/dm-chain-explorer-gha-*` and on the user-credential verbs, proven negatively by `simulate-principal-policy` (AC-2b). |
| **Layer artifact inside the module tree** produced DRIFT-07's perpetual diff and makes a fresh-clone plan impossible. | D15: the artifact lives in S3 at a content-addressed key and enters Terraform as variables; the handler zips are `archive_file` at plan time; `.lambda_zip/` is untracked. AC-10 is asserted from a fresh clone with no local zip. |
| **The repository is PUBLIC.** Workflow YAML, bundle configuration and evidence are world-readable. | No account id, host, personal identifier or key material in any artifact (AC-19); secrets deleted rather than rotated in place (AC-3); evidence in CLOSURE uses generic names. |
| **Free-Edition Databricks limits**: unsupported resource types, a stopped warehouse, one workspace for dev and hml. | C1 drops the unsupported bundles (deferred, not silently lost); no prod deploy (O-6); dashboard verification is by bundle/deployed-state comparison, not by query execution. |
| **Environment reviewers require the operator.** Any gated apply blocks until the operator approves. | Live steps are scheduled as operator-gated tasks in TASKS; the release does not assume unattended applies. |
| **Deleting tests can hide regressions.** | O-7: `qa-engineer` verdict before deletion; live-surface tests written first; the demotion map is recorded in CLOSURE. |
| **HML bucket names are referenced by bundles.** Reducing HML before WS-C settles names would break validation. | B2 unifies names with WS-C's bundle configuration; AC-17 validates `hml` before AC-12 asserts the destruction set. |
| **`dd-chain-capture` may deliver mid-release**, changing the S3 contract. | D1 parks the contract; the DLT code stays aligned to the documented layout and the field-name check is a documented TODO, not a blocker. |
| **Re-audit may score below the gate.** | The ship gate blocks; residuals are listed as CLOSURE intake candidates for the PM, never silently dropped. |

---

## 10. Decisions resolved (grill record `2026-08-23T154350Z-refine-specs-v050`)

- **D1 — Platform parked until delivery.** S3 contract as documented; DLT stays aligned; field-name check is a TODO; the hourly ingestion schedule is disabled (Lambda kept); the gold-export→DynamoDB chain is kept and documented as consumer-unverified.
- **D2 — HML reduced to a minimal lane**: the `hml` bundle target, the referenced S3 buckets and the minimal Unity-Catalog IAM. Everything else in HML is destroyed, including the unmanaged legacy VPC and its leaked security groups.
- **D3 — Dead capture code is deleted**, not archived (git history is the archive); test deletions require a `qa-engineer` verdict.
- **D4 — PRD capture-era IaC deleted**; PRD keeps state/IAM/peripherals/lambda, DEV keeps peripherals/lambda; orphan state keys removed.
- **D5 — CI auth rebuilt least-privilege**: scoped deploy roles, no `PowerUserAccess`, no `iam:*` on `*`, narrow read-only trust; the four variables published; static keys deleted and the legacy key deactivated.
- **D6 — Deploy workflow purged of the capture lane** and hardened: per-environment concurrency, tests wired in, plan-on-PR for both long-lived branches, truthful stack map, pinned tooling, bump workflow deleted.
- **D7 — Repo governance**: default branch renamed to `main` with protection on both long-lived branches, operator as environment reviewer, `hml-apps` removed; stale branches listed only.
- **D8 — One version axis** = the SDD release id, propagated to the library, the bundles and the version scripts.
- **D9 — Supply chain closed** by path-installing the library, dropping the public pin, building the layer in CI and pinning requirements, with a CVE scan in the PR gate.
- **D10 — Databricks artifacts rebuilt to reality**: no-op bundles dropped, broken jobs fixed or removed, prod target guarded, dashboards parametrised, service-principal `run_as`, dev and hml redeployed so live == repo.
- **D11 — Quality gates land in the repo** (ruff, mypy, clean worktree) and the live surface gets its first tests.
- **D12 — Governance documents authored**: a real constitution, the capture-deprecation ADR, finding-by-finding dispositions for both audits, and a terminal event for the misfiled bug.
- **D14 — OIDC bootstrap stack** (architecture review F-01/F-02, 2026-08-23). The OIDC provider reference and the four `gha` roles leave `prd/03_iam` for a new operator-applied stack `services/prd/00_bootstrap` with its own backend key `prd/bootstrap` — never applied by CI, never destroyed. Each role carries scoped allows, an explicit self-mutation `Deny`, and environment/`pull_request`-pinned trust subjects. Bootstrap ships as code (`scripts/ci/publish_oidc_vars.sh` + a runbook) with a fail-fast CI preflight and a `simulate-principal-policy` negative check. Consequence for §2: `prd/03_iam` becomes wholly WS-B's, one stack with one applier.
- **D15 — Layer artifact store** (F-03). The Lambda layer is built in CI (`--require-hashes -r requirements.lock` for third-party deps + `pip install ./utils --no-deps` for the library as a path requirement — the path install is the dependency-confusion closure, not `--no-index`), uploaded to `s3://dm-chain-explorer-artifacts/lambda-layers/dm-chain-utils/<sha256>.zip` (dev under a `dev/` prefix), and consumed by Terraform through `s3_bucket`/`s3_key`/`source_code_hash` variables. Handler zips are built by `data "archive_file"` at plan time. `.lambda_zip/*` is untracked and gitignored. Owners: build script + lock = WS-D, CI wiring + upload = WS-A, bucket + Terraform = WS-B.
- **D13 — Explicitly out of scope**: `dd-chain-capture`-owned resources, account-level noise, data-quality and dashboard enrichment, the REST API, the encryption-at-rest posture, and the single-stack restructuring.
