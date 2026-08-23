# Audit lane — GitHub Actions + Terraform components

- **Repo**: `dd-chain-explorer` (`marcoaureliomenezes/dd_chain_explorer`, **public**)
- **Reviewed ref**: `feature/v0.4.0` @ `c6feb17` (working tree clean, 1 ahead of `origin/feature/v0.4.0`)
- **Release context**: v0.4.0 "Capture Retirement", `specs/releases/ACTIVE.md` → `phase: IMPLEMENTATION`
- **Date**: 2026-08-23 · reviewer: `code-reviewer` · mode: STRICT read-only
- **Tooling used**: `git`, `gh` (read-only API), `terraform 1.15.6` (`fmt -check`, `init -backend=false`, `validate` — no plan/apply, `TF_DATA_DIR`/`TF_PLUGIN_CACHE_DIR` redirected out of the repo)
- **actionlint**: NOT INSTALLED locally → workflow linting NOT COVERED (see F-24)

## CI status

Last GitHub Actions run of any kind: **2026-04-11** (`Destroy Infra Cloud`, `workflow_dispatch`, `develop`, success). Every one of the last 25 runs is a `workflow_dispatch` from `develop`. **No CI has executed against any v0.3.0 or v0.4.0 code** — the entire post-v0.3.0 control plane (informed gate, OIDC cutover, stack map, plan-on-PR, drift detection) is unproven in production.

---

## 1. Workflows (7 files on `feature/v0.4.0`)

| Workflow | Triggers | `permissions` | OIDC role(s) | Secrets/vars (names only) | Environment gate | Concurrency | Pins | Stack map? |
|---|---|---|---|---|---|---|---|---|
| `auto-bump-version.yml` | `pull_request: [closed]` → `develop` | `contents: write` | none | `secrets.GITHUB_TOKEN` | none | `version-bump`, no-cancel | all SHA | no |
| `deploy_all_dm_applications.yml` | `workflow_dispatch` | `contents: read`, `id-token: write` | `vars.AWS_DEPLOY_ROLE_{HML,PRD,READONLY}` | `DATABRICKS_{CLIENT_ID,CLIENT_SECRET,HML_HOST,HML_TOKEN,PROD_HOST}`, `HML_VPC_ID`, `HML_SUBNET_ID` | `hml-apps` (9 jobs), `production` (4 jobs) | **NONE (F-05)** | all SHA | no — hardcoded |
| `deploy_cloud_infra.yml` | `workflow_dispatch` (5 inputs) | `contents: read`, `id-token: write` | `vars.AWS_DEPLOY_ROLE_{DEV,HML,PRD,READONLY}` | `DATABRICKS_{ACCOUNT_ID,CLIENT_ID,CLIENT_SECRET}`, `GITHUB_TOKEN` | `dev`, `hml`, `production` | per-job `tf-{dev,hml,prd}-deploy` | all SHA | **yes** (`plan_env.sh`/`deploy_env.sh`) |
| `destroy_all_cloud_infra.yml` | `workflow_dispatch` (`confirm`) | `contents: read`, `id-token: write` | `vars.AWS_DEPLOY_ROLE_{DEV,HML,PRD}` | `DATABRICKS_{ACCOUNT_ID,CLIENT_ID,CLIENT_SECRET}` | `dev`, `hml`, `production` | `destroy-all-cloud-infra` | all SHA | no — 14 hardcoded jobs |
| `destroy_cloud_infra.yml` | `workflow_dispatch` (3 inputs) | `contents: read`, `id-token: write` | `vars.AWS_DEPLOY_ROLE_{DEV,HML,PRD}` | `DATABRICKS_{ACCOUNT_ID,CLIENT_ID,CLIENT_SECRET}` | `dev`, `hml`, `production` | per-job `tf-*-destroy` | all SHA | no — `destroy_env.sh` hardcodes |
| `drift_detection.yml` | `schedule: 0 6 * * 1`, `workflow_dispatch` | `contents: read`, `id-token: write` | `vars.AWS_DEPLOY_ROLE_READONLY` (×7) | none | none | `drift-detection` | all SHA | no — 7 hardcoded dirs |
| `plan_on_pr.yml` | `pull_request` → **`develop`** only, paths `services/**`,`scripts/ci/**` | `contents: read`, `pull-requests: write`, `id-token: write` | `vars.AWS_DEPLOY_ROLE_READONLY` (×10) | none | none | `plan-pr-<n>`, cancel | all SHA **except** `curl \| bash` actionlint (F-13) | partial — `changed_stacks.py` for detection, 10 hardcoded plan jobs |

**Registered on GitHub (6, from default branch `master`):** `destroy_cloud_infra.yml`, `deploy_cloud_infra.yml`, `deploy_dm_applications.yml`†, `lib_release.yml`†, `deploy_all_dm_applications.yml`, `destroy_all_cloud_infra.yml`. († = files that exist only on `master`, deleted on `develop`/`feature/*` — still dispatchable.) `drift_detection.yml`, `plan_on_pr.yml`, `auto-bump-version.yml` are **not registered at all**.

**Action pinning:** 100% of `uses:` are 40-char SHAs (68 checkout, 55 configure-aws-credentials, 44 setup-terraform, 4 databricks/setup-cli, 4 upload-artifact, 2+2 download-artifact, 1 docker/build-push-action, 1 setup-python). Zero `@vN` tags. **Good.**

**Error masking:** every `|| true` / `2>/dev/null` occurrence carries an inline justification comment and sits in idempotent teardown or diagnostic-dump paths (`destroy_all_cloud_infra.yml:124-583`, `deploy_all_dm_applications.yml:412-446`). One `set +e` at `deploy_all_dm_applications.yml:199`. No masking observed on a pass/fail decision path. **Acceptable as written**, but unverified at runtime.

**Expression-injection surface:** all `workflow_dispatch` inputs and PR title/number are passed via `env:` blocks (safe). One exception: `destroy_cloud_infra.yml:103` interpolates `${{ github.event.inputs.full_destroy }}` directly into a `run:` command line — the input is `type: boolean`, so exploitation is not possible today (F-19, LOW).

---

## 2. `scripts/ci` inventory and stack-map coherence

18 Bash helpers + `changed_stacks.py` + `stack_map.json` + `tests/` (3 pytest files, 31 KB).

| Script | Called by |
|---|---|
| `branch_guard.sh` | deploy_cloud_infra, destroy_cloud_infra, destroy_all_cloud_infra |
| `bump_version.sh` | auto-bump-version |
| `changed_stacks.py` | plan_on_pr, `detect_changes.sh`, tests |
| `check_app_version.sh` | **NO CALLER — dead** |
| `check_commit_confirmation.sh` | destroy_cloud_infra |
| `check_infra_prerequisites.sh` | deploy_all_dm_applications |
| `check_prd_version.sh` | deploy_cloud_infra |
| `databricks_account_import.sh` | deploy_env.sh, destroy_env.sh |
| `deploy_env.sh` | deploy_cloud_infra |
| `destroy_env.sh` | destroy_cloud_infra |
| `detect_changes.sh` | deploy_cloud_infra |
| `empty_s3_and_ecr.sh` | destroy_all_cloud_infra, destroy_env.sh |
| `hml_provision.sh` / `hml_teardown.sh` | deploy_all_dm_applications |
| `plan_env.sh` / `plan_gate_check.sh` | deploy_cloud_infra |
| `tf_plan.sh` | drift_detection, deploy_cloud_infra, plan_on_pr |
| `tf_state_lock_check.sh`, `wait_eni_release.sh` | deploy_env.sh / destroy_env.sh (invoked via `bash …`, so their non-executable mode is harmless) |
| `scripts/ci/tests/*.py` | **NO CALLER — never run in CI (F-06)** |

Repo-root helpers with no CI caller: `dev_integration_test.sh`, `dev_dlt_integration_test.sh`, `prod_ecs_logs.py`, `prod_resume.sh`, `prod_standby.sh`, `tf_validate_all.sh` (the last three are plausibly operator tools, not CI dead code).

### Stack map vs disk

**In map, missing on disk:** none. **On disk, absent from the map:**

| Path | Status |
|---|---|
| `services/dev/00_compose` | not Terraform (docker-compose) — correctly absent |
| `services/prd/01_tf_state` | bootstrap stack, local state, applied out of band — defensible |
| `services/prd/05_databricks` | **legacy monolith, 524 lines, backend key `prd/databricks/terraform.tfstate`, superseded by `05a`+`05b` — dead (F-08)** |

### Stack→module edges vs actual `source =` references

| Env/stack | Map declares | Actually consumes | Verdict |
|---|---|---|---|
| dev/peripherals | `[]` | `s3`, `dynamodb`, `cloudwatch_logs` | **MISSING edges → under-trigger (F-07)** |
| dev/lambda | `[]` | `lambda` | **MISSING edge → under-trigger (F-07)** |
| hml/vpc, hml/iam, hml/ecs, hml/peripherals | `vpc` / `iam` / `ecs` / `s3,dynamodb,cloudwatch_logs` | identical | correct |
| prd/vpc | `["vpc"]` | none (inline `network.tf`) | phantom edge |
| prd/iam | `["iam"]` | none (inline `iam.tf`, 526 lines) | phantom edge |
| prd/lambda | `["lambda"]` | none (inline) | phantom edge |
| prd/ecs | `["ecs"]` | none (inline `ecs.tf`) | phantom edge |
| prd/peripherals | `["s3","dynamodb","cloudwatch_logs"]` | identical | correct |

`test_declared_modules_exist_on_disk` only checks the module *directory* exists, so neither direction of this drift is caught; `test_dev_stacks_have_no_module_edges` actively **asserts the missing-edge defect as intended behaviour** (`scripts/ci/tests/test_stack_map.py:148-155`).

### Single-source claim vs reality

`stack_map.json:$comment` states *"No stack name may be hardcoded in more than one place."* Only `deploy_env.sh` is map-driven (and `test_deploy_env_has_no_hardcoded_stack_paths` guards just that one file). Second sources of stack truth: `plan_on_pr.yml` (10 `working-directory:` jobs + 10 named outputs), `drift_detection.yml` (7), `destroy_all_cloud_infra.yml` (14 jobs), `destroy_env.sh` (`dev`/`hml`/`prd` ordered lists). The only drift guard is subset-direction (`plan_on_pr` ⊆ map); a stack added to the map is never required to gain a PR plan.

---

## 3. Terraform

`terraform fmt -check -recursive services/` → **exit 0, no findings.**

### Stacks, backends, providers, validate

| Env | Stack | Modules consumed | Backend key (bucket `dm-chain-explorer-terraform-state`, `sa-east-1`, lock `dm-chain-explorer-terraform-lock`) | `validate` |
|---|---|---|---|---|
| dev | `01_peripherals` | s3, dynamodb, cloudwatch_logs | `dev/peripherals/terraform.tfstate` | rc=0 |
| dev | `02_lambda` | lambda | `dev/lambda/terraform.tfstate` | rc=0 |
| hml | `02_vpc` | vpc | `hml/vpc/terraform.tfstate` | rc=0 |
| hml | `03_iam` | iam | `hml/iam/terraform.tfstate` | rc=0 |
| hml | `04_peripherals` | s3 ×3, dynamodb, cloudwatch_logs | `hml/peripherals/terraform.tfstate` | rc=0 |
| hml | `05_databricks` | — | `hml/databricks/terraform.tfstate` | rc=0 |
| hml | `05b_databricks_workspace` | — | `hml/databricks-workspace/terraform.tfstate` | rc=0 |
| hml | `07_ecs` | ecs | `hml/ecs/terraform.tfstate` | rc=0 |
| prd | `01_tf_state` | — | **no backend (local state)** | rc=0 |
| prd | `02_vpc` | — (inline) | `prd/vpc/terraform.tfstate` | rc=0 |
| prd | `03_iam` | — (inline) | `prd/iam/terraform.tfstate` | rc=0 |
| prd | `04_peripherals` | s3 ×3, dynamodb, cloudwatch_logs | `prd/peripherals/terraform.tfstate` | rc=0 |
| prd | `05_databricks` (legacy) | — | `prd/databricks/terraform.tfstate` | **NOT COVERED** |
| prd | `05a_databricks_account` | — | `prd/databricks-account/terraform.tfstate` | rc=0 |
| prd | `05b_databricks_workspace` | — | `prd/databricks-workspace/terraform.tfstate` | rc=0 |
| prd | `06_lambda` | — (inline) | `prd/lambda/terraform.tfstate` | **NOT COVERED** |
| prd | `07_ecs` | — (inline) | `prd/ecs/terraform.tfstate` | **NOT COVERED** |
| modules | `cloudwatch_logs`, `dynamodb`, `ecs`, `iam`, `lambda`, `s3`, `vpc` | — | — | all rc=0 |

**Coverage: 21/24 Terraform directories validated clean (rc=0), 0 failures. Still NOT COVERED: `prd/05_databricks` (legacy), `prd/06_lambda`, `prd/07_ecs`** — the sweep was still downloading providers when the review window closed (`<workspace>/.dadaia/tmp/code-reviewer/20260823/tfval.log`; rerun with `<workspace>/.dadaia/tmp/code-reviewer/20260823/tfval.sh`). Note the local binary is Terraform **1.15.6**; CI pins **1.7.0**, so these results are indicative, not CI-equivalent.

**Provider pinning:** every stack declares `required_version = ">= 1.5"` and `aws >= 5.0` / `databricks >= 1.36.0` — all floating lower bounds. **Zero `.terraform.lock.hcl` files are committed anywhere in `services/`** (F-09).

**Dead / unreferenced modules:** none of the 7 modules is fully unreferenced, but `vpc`, `iam`, `ecs`, `lambda` are consumed **only by hml/dev** — production reimplements all four inline (1 062 lines of prd inline vs 633 lines of module). The shared modules are therefore exercised only in non-production.

**Declared-but-unused variables:** `modules/dynamodb/variables.tf:1` (`environment`); `modules/ecs/variables.tf:6` (`region`); `modules/s3/variables.tf:1` (`environment`), `:6` (`region`), `:29` (`prevent_destroy`); `prd/05b_databricks_workspace/variables.tf:25` (`databricks_bucket_name`).

**Hard-coded identifiers:** no own-account ID appears in any `.tf` (all via `data.aws_caller_identity`). `sa-east-1` is hard-coded in ~20 backend/provider blocks (unavoidable for `backend "s3"`, avoidable in provider blocks). `arn:aws:iam::414351767826:root` (`prd/05_databricks/databricks.tf:28,145`, `prd/05a_databricks_account/databricks.tf:26,71`, `hml/05_databricks/databricks.tf:19,46`) is Databricks' published control-plane account — expected, INFO only.

**dev/hml/prd drift that reads as accident, not intent:** (a) hml uses `modules/{vpc,iam,ecs}`, prd inlines equivalents; (b) prd carries both `05_databricks` (legacy) and `05a`+`05b`, hml carries `05_databricks`+`05b` — the split was applied to prd only and the legacy stack was never removed; (c) `destroy_all_cloud_infra.yml` destroys hml `05_databricks/07_ecs/04/03/02` but **never `hml/05b_databricks_workspace`**, while the prd path does destroy `05b` (F-10).

**Capture-layer remnants after v0.4.0** — 131 `kinesis|firehose|sqs` matches across 14 `.tf` files. Live (not comment) grants and resources:
- `services/prd/03_iam/iam.tf:55-92` — `KinesisAccess`, `FirehoseAccess`, `SQSAccess` statements on `mainnet-*-prd` (dead grants).
- `services/modules/iam/main.tf:56-113` + `variables.tf:36-42` — same three statements, parameterised by `kinesis_stream_suffix` / `sqs_queue_suffix`, still passed `"hml"` at `services/hml/03_iam/main.tf:62-63`.
- `services/hml/03_iam/main.tf:75+` / `outputs.tf:9` — a live Firehose service role (`aws_iam_role.firehose`) with no Firehose left to assume it.
- `services/modules/cloudwatch_logs/` — full Firehose subsystem behind `firehose_enabled`, set `false` by all three callers (`dev/01_peripherals/main.tf:81`, `hml/04_peripherals/main.tf:142`, `prd/04_peripherals/peripherals.tf:94`). `outputs.tf:17` dereferences `aws_kinesis_firehose_delivery_stream.logs[0].arn` inside a conditional whose `count` is 0 (F-11).
- `services/prd/04_peripherals/main.tf:4` — stale header still advertising "Kinesis Data Streams + Firehose + SQS".
- `services/{hml,prd}/07_ecs` now create only a cluster + capacity providers — no task definitions, no services (F-12).

---

## 4. Repo governance

- **Default branch: `master`** (`gh api repos/... .default_branch`), last commit `be19d5d` **2026-05-11** — 103 days stale relative to `feature/v0.4.0`. `master` still carries `deploy_dm_applications.yml` and `lib_release.yml` (deleted downstream) and **lacks `drift_detection.yml` and `plan_on_pr.yml` entirely**.
- **Branch protection: NONE.** `gh api .../branches/master/protection` and `.../develop/protection` both return `404 Branch not protected`. No required checks, no required reviews, no `pr-source-guard`.
- **Environments:** `dev`, `hml`, `production` exist. Only `production` has `required_reviewers` (1, `prevent_self_review: false`). `hml` has **zero protection rules**. All three have `deployment_branch_policy: null` (any branch may deploy) and `can_admins_bypass: true`. **`hml-apps` does not exist** despite 9 jobs referencing it.
- **Repo variables: EMPTY.** No `AWS_DEPLOY_ROLE_DEV|HML|PRD|READONLY` at repo or environment level (F-01).
- **Repo secrets (13):** `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `DATABRICKS_{ACCOUNT_ID,CLIENT_ID,CLIENT_SECRET,HML_HOST,HML_TOKEN,PROD_HOST}`, `DYNAMODB_TABLE`, `ECS_TASK_EXECUTION_ROLE_ARN`, `ECS_TASK_ROLE_ARN`, `HML_SUBNET_ID`, `HML_VPC_ID`. The two AWS static keys and the three `DYNAMODB_TABLE`/`ECS_TASK_*` values are referenced by **no workflow on `feature/v0.4.0`** (F-02, F-20).
- **Repo is `"private": false` — PUBLIC.** Workflow YAML therefore publishes SSM parameter paths (`/web3-api-keys/alchemy/api-key-1`, `/web3-api-keys/infura/api-key-1-17`, `/etherscan-api-keys`), IAM role names, cluster/bucket/queue names (F-21).
- **Stale remote branches (14 total):**

| Last commit | Branch | ahead of `master` |
|---|---|---|
| 2025-03-31 | `feature/doc` | 11 |
| 2026-03-20 | `feature/dm-v4` | 0 |
| 2026-03-20 | `feature/lambda-tests-and-dry-run` | 0 |
| 2026-03-20 | `release/infra-v0.1.0` | 0 |
| 2026-04-24 | `fix/cicd-ecs-timeout` | 82 |
| 2026-04-24 | `fix/cicd-terraform-wrapper` | 83 |
| 2026-04-24 | `fix/sqs-polling-optimization` | 85 |
| 2026-05-10 | `develop` | 85 |
| 2026-05-11 | `feature/devops-audit-remediation-2026-05` | 86 |
| 2026-05-11 | `fix/revert-direct-master-commit` | 1 |
| 2026-06-09 | `feature/specs-first-docs-cleanup` | 141 |
| 2026-06-11 | `feature/v0.3.0` | 183 |
| 2026-06-22 | `feature/v0.4.0` | 191 |

  Nine branch names violate the four-pattern `dadaia-gitflow` contract; `develop` itself is 85 commits ahead of the default branch and has never been merged back.
- **VERSION vs tags:** `VERSION` = `0.2.9`. 24 tags; highest release family is `v0.2.9{,-dabs,-infra,-lambda}`. **No `v0.3.0*` or `v0.4.0*` tag exists** even though v0.3.0 shipped in the SDD lane (F-03).
- **`auto-bump-version.yml` coherence:** defaults to `patch`; `[minor]`/`[major]` come from the PR title. Next merge to `develop` yields `0.2.10`, never `0.4.0` — the CI version axis and the SDD release axis are fully disjoint. `check_prd_version.sh:18` gates PRD infra on `v${VERSION}-infra` not already existing, so a v0.4.0 PRD deploy would mint `v0.2.10-infra` (F-03).

---

## 5. Findings

| id | severity | area | finding | evidence (`file:line`) | recommendation |
|---|---|---|---|---|---|
| F-01 | **CRITICAL** | workflows / governance | Every OIDC step resolves `${{ vars.AWS_DEPLOY_ROLE_* }}` but **no repo or environment variable of that name exists**; `configure-aws-credentials` receives an empty `role-to-assume`. All 5 AWS-touching workflows are non-functional as written. | `gh api .../actions/variables` → `{"variables":[]}`; `plan_on_pr.yml:143,173,202,229,256,285,312,339,366,393`; `deploy_cloud_infra.yml`; `drift_detection.yml:53,87,120,151,182,213,244` | Create the 4 repo variables from `terraform output` of `services/prd/03_iam`, or fail-fast on an empty value in a pre-flight step so this cannot be discovered mid-deploy. |
| F-02 | **HIGH** | governance / security | Static long-lived `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` remain in the secret store of a **public** repo, unreferenced by any current workflow — a standing credential with no consumer and no rotation since 2026-03-20. | `gh api .../actions/secrets`; zero `secrets.AWS_` matches in `.github/workflows/*.yml` | Delete both secrets once F-01 is resolved and the OIDC path is proven; rotate the underlying IAM keys regardless. Route to `security-reviewer`. |
| F-03 | **HIGH** | governance | The CI version axis (`VERSION`=0.2.9, tags `v0.2.9-*`) is disjoint from the SDD release axis (v0.3.0 shipped, v0.4.0 in flight). A PRD deploy today tags `v0.2.10-infra`. | `VERSION:1`; `git tag`; `scripts/ci/bump_version.sh:34-40`; `scripts/ci/check_prd_version.sh:18` | Decide one axis. Either seed `VERSION` from the release id at release-definition time, or drop `auto-bump-version.yml` and derive infra tags from `specs/releases/ACTIVE.md`. |
| F-04 | **HIGH** | workflows | `plan_on_pr.yml` only triggers on PRs whose base is **`develop`**. The PR that actually ships (`develop` → `master`) receives **no** `fmt`/`validate`/`actionlint` gate and **no** terraform plan. Combined with zero branch protection, `master` can advance completely ungated. | `plan_on_pr.yml:15-20`; `gh api .../branches/master/protection` → 404 | Add `master` to `on.pull_request.branches` and make the quality job a required status check on `master`. |
| F-05 | **HIGH** | workflows | `deploy_all_dm_applications.yml` (25 jobs, incl. PRD ECS deploy, DABs deploy and a `terraform apply` on `prd/06_lambda`) declares **no `concurrency:` at any level**. Two dispatches race the shared HML environment and the prd lambda remote state. | `deploy_all_dm_applications.yml:20-44` (no `concurrency` key anywhere in the file) | Add a workflow-level `concurrency: {group: dm-applications, cancel-in-progress: false}`. |
| F-06 | **HIGH** | scripts/ci | `scripts/ci/tests/` (3 files, 31 KB — the stack-map integrity guard, the plan-gate guard, the apply-path guard) is **executed by no workflow**. The only pytest invocation in CI is `utils/tests/unit/`. Every "guard" in §2 is decorative. | `deploy_all_dm_applications.yml:163` is the sole `pytest` line; no workflow references `scripts/ci/tests` | Add a `pytest scripts/ci/tests -p no:cacheprovider` step to the `plan_on_pr.yml` quality job. |
| F-07 | **HIGH** | scripts/ci | `stack_map.json` declares `modules: []` for both DEV stacks, which **do** consume `s3`/`dynamodb`/`cloudwatch_logs`/`lambda`. A shared-module edit silently triggers no DEV plan or deploy. `test_dev_stacks_have_no_module_edges` asserts the defect as correct. | `scripts/ci/stack_map.json:31-46` vs `services/dev/01_peripherals/main.tf:46,65,74` and `services/dev/02_lambda/main.tf:97`; `scripts/ci/tests/test_stack_map.py:148-155` | Populate the DEV module edges, drop the phantom prd edges, delete/invert the test, and add a test that derives edges from `source =` lines. |
| F-08 | **HIGH** | terraform | `services/prd/05_databricks` — a 524-line legacy monolith superseded by `05a`+`05b` — is still on disk with its own live backend key, is absent from `stack_map.json`, is never planned, and is **never destroyed** by either destroy workflow. | `services/prd/05_databricks/main.tf:17-21`; absent from `scripts/ci/stack_map.json`; absent from `scripts/ci/destroy_env.sh:152-225` | Confirm the state object is empty, then `git rm` the directory and delete `prd/databricks/terraform.tfstate` from the bucket. |
| F-09 | **HIGH** | terraform | **No `.terraform.lock.hcl` is committed anywhere.** With `aws >= 5.0` floating, every CI run resolves the newest provider; an unattended gated PRD apply can execute against a provider version never planned against. | `find services -name .terraform.lock.hcl` → empty; `services/*/*/main.tf` `version = ">= 5.0"` | Commit lock files per stack and add `terraform init -lockfile=readonly` in CI. |
| F-10 | **HIGH** | terraform / workflows | The "nuclear" `destroy_all_cloud_infra.yml` destroys hml `05_databricks/07_ecs/04/03/02` but **omits `hml/05b_databricks_workspace`**, leaving Unity Catalog/workspace resources orphaned after a full teardown. The prd path does destroy `05b`. | `destroy_all_cloud_infra.yml:139-265` (job list) vs `scripts/ci/destroy_env.sh:108-118` | Add an `hml-destroy-databricks-workspace` job ahead of `hml-destroy-databricks`, or drive the whole workflow from `stack_map.json`. |
| F-11 | **MEDIUM** | terraform | `modules/cloudwatch_logs/outputs.tf:17` indexes `aws_kinesis_firehose_delivery_stream.logs[0].arn` in the true branch of a conditional whose `count` is 0 for **all three** callers. `validate` passes; a plan can still surface `Invalid index` on some provider/TF combinations. | `services/modules/cloudwatch_logs/outputs.tf:17`; callers `dev/01_peripherals/main.tf:81`, `hml/04_peripherals/main.tf:142`, `prd/04_peripherals/peripherals.tf:94` | Replace with `one(aws_kinesis_firehose_delivery_stream.logs[*].arn)`; better, delete the Firehose subsystem outright (dead since v0.4.0). |
| F-12 | **MEDIUM** | terraform | Post-capture-retirement `hml/07_ecs` and `prd/07_ecs` create only a cluster + capacity providers — zero task definitions, zero services. 178 lines of prd Terraform maintaining an empty cluster. | `services/prd/07_ecs/ecs.tf:4,15`; `services/modules/ecs/main.tf:1,12` | Give v0.4.0 CLOSURE an explicit disposition: retire the stacks, or document the cluster as an intentional placeholder. |
| F-13 | **MEDIUM** | workflows / supply chain | The only unpinned code execution in CI: `bash <(curl -fsSL https://raw.githubusercontent.com/rhysd/actionlint/main/scripts/download-actionlint.bash)` — mutable `main` ref, no checksum — in a workflow that elsewhere pins 100% of actions by SHA. | `plan_on_pr.yml:69-72` | Pin the installer to a tag/SHA and verify the binary checksum, or use a SHA-pinned action. |
| F-14 | **MEDIUM** | security / IAM | All three deploy roles attach AWS-managed `PowerUserAccess` **plus** an inline policy granting `iam:CreateRole`, `iam:AttachRolePolicy`, `iam:PutRolePolicy`, `iam:UpdateAssumeRolePolicy`, `iam:PassRole` on `Resource = "*"`. PowerUser + unrestricted IAM write is effectively account admin — including the **dev** role, whose `dev` environment has zero protection rules and no branch policy. | `services/prd/03_iam/oidc.tf:156-200` (`IamManagement`, `resources = ["*"]`), `:222-232` (dev PowerUser attachment); `gh api .../environments` → `dev.protection_rules: []` | Scope `IamManagement` to the role-name prefixes each pipeline manages; at minimum add a permissions boundary. Escalate to `security-reviewer`. |
| F-15 | **MEDIUM** | workflows / gates | `all-hml-infra-apply` runs `terraform apply -auto-approve` on `hml/03_iam` and `hml/04_peripherals` under the reviewer-less `hml-apps` environment — bypassing the entire ADR-R6-4/R6-5 informed-gate machinery those same two stacks go through in `deploy_cloud_infra.yml`. | `deploy_all_dm_applications.yml:235-262` | Route these applies through `plan_env.sh`/`deploy_env.sh`, or document the bypass as an accepted exception in the memory atom. |
| F-16 | **MEDIUM** | governance | The `hml` GitHub environment has **no protection rules**, so the "informed environment gate" for HML apply/destroy approves itself. `hml-apps` is referenced by 9 jobs but does not exist (it will be auto-created, unprotected and unbranch-policied, on first run). All three environments have `deployment_branch_policy: null` and `can_admins_bypass: true`. | `gh api .../environments`; `deploy_cloud_infra.yml:384`; `deploy_all_dm_applications.yml:113,239,289,311,453,542,586,657,741` | Add reviewers + a `develop`-only deployment branch policy to `hml`; declare `hml-apps` explicitly with its reviewer-less posture documented. |
| F-17 | **MEDIUM** | workflows | Deploy and destroy of the same environment use **different** concurrency groups (`tf-prd-deploy` vs `tf-prd-destroy`), and `destroy_all_cloud_infra.yml` uses a third (`destroy-all-cloud-infra`). A PRD deploy and a PRD destroy can run simultaneously against one remote state. | `deploy_cloud_infra.yml:200,257` vs `destroy_cloud_infra.yml:115` vs `destroy_all_cloud_infra.yml:34` | Collapse to one group per environment (`tf-prd`, `tf-hml`, `tf-dev`) shared by deploy, destroy and destroy-all. |
| F-18 | **MEDIUM** | workflows | `auto-bump-version.yml` checks out the `pull_request` merge ref (no `ref:` given) and then runs `git push origin develop` from a detached HEAD; the commit is not on any local branch named `develop`. Never executed, so never proven. | `auto-bump-version.yml:26-32`; `scripts/ci/bump_version.sh:58-59` | Add `ref: develop` to the checkout, or push explicitly with `HEAD:refs/heads/develop`. Cover with a test before relying on it. |
| F-19 | **LOW** | workflows | Only direct interpolation of an event value into a `run:` command line; the input is `type: boolean` so it is not exploitable, but it breaks the file's own env-passing convention. | `destroy_cloud_infra.yml:103` | Pass via `env: FULL_DESTROY:` like every other input in the repo. |
| F-20 | **LOW** | governance | `DYNAMODB_TABLE`, `ECS_TASK_EXECUTION_ROLE_ARN`, `ECS_TASK_ROLE_ARN` are repo secrets referenced by no workflow on this branch — orphans from the retired capture layer. | `gh api .../actions/secrets`; no matches in `.github/workflows/` | Delete after confirming no `master`-only workflow needs them. |
| F-21 | **LOW** | security / privacy | The repo is **public**; workflow YAML publishes SSM parameter paths, IAM role names, ECS cluster names, SQS queue names and bucket names. Not secrets, but a complete reconnaissance map of the account. | `deploy_all_dm_applications.yml:330-345` (`/web3-api-keys/alchemy/api-key-1`, `/web3-api-keys/infura/api-key-1-17`, `/etherscan-api-keys`), `:39-42` | Operator decision: make the repo private, or accept and ensure no parameter path is itself sensitive. Route to `security-reviewer`. |
| F-22 | **LOW** | terraform | `modules/s3` exposes a `prevent_destroy` variable that is **never read** — `main.tf:6` hard-codes `prevent_destroy = true`. A caller setting `prevent_destroy = false` is silently ignored. | `services/modules/s3/variables.tf:29` vs `services/modules/s3/main.tf:5-6` | Wire the variable through, or delete it so the contract stops lying. |
| F-23 | **LOW** | terraform | Six declared-but-unused variables across shared modules and one prd stack. | `modules/dynamodb/variables.tf:1`; `modules/ecs/variables.tf:6`; `modules/s3/variables.tf:1,6`; `prd/05b_databricks_workspace/variables.tf:25` | Remove, or reference them in `tags`/naming as originally intended. |
| F-24 | **INFO** | tooling | `actionlint` is not installed in this environment and the review is read-only, so the "actionlint must exit 0 on every workflow" gate could not be exercised locally. | `which actionlint` → not found | Rerun this lane on a runner with actionlint, or trust `plan_on_pr.yml:69` once F-04 makes it fire. |

### Cross-lane cross-references (accepted from other lanes, not re-verified here)

- **`deploy_all_dm_applications.yml` still provisions HML Kinesis/SQS and destroys the deleted `module.kinesis`.** Confirmed from this lane's angle: `scripts/ci/hml_provision.sh:28-36` calls `aws sqs get-queue-url` for `mainnet-mined-blocks-events-hml` / `mainnet-block-txs-hash-id-hml`, which `services/hml/04_peripherals/main.tf` no longer creates (only `s3 ×3`, `dynamodb`, `cloudwatch_logs`); under `set -euo pipefail` the `all-hml-provision` job dies there. Downstream, `deploy_all_dm_applications.yml:307-420` launches the 5 retired producers with `KINESIS_STREAM_TRANSACTIONS`/`FIREHOSE_STREAM_*` env vars, and `:876-889` updates 5 PRD ECS **services** that v0.4.0 destroyed. `scripts/ci/hml_teardown.sh:8` was updated for the retirement; `hml_provision.sh:5-8` was not — the retirement was applied to the teardown half only. **Treat as CRITICAL: the application pipeline is broken end-to-end.**
- **`drift_detection.yml` absent from default branch `master`.** Confirmed: `git ls-tree -r origin/master -- .github/workflows` lists no `drift_detection.yml`, and `gh api .../actions/workflows` does not register it. GitHub schedules `cron` **only** from the default branch, so the Monday 06:00 UTC scan **has never fired and cannot fire** until either the file lands on `master` or the default branch changes. Same mechanism silently disables `plan_on_pr.yml` and `auto-bump-version.yml` registration.
- **2 stale TF locks (`prd/databricks-account`, `hml/peripherals`).** Consistent with `deploy_env.sh:127` / `destroy_env.sh:57` calling `tf_state_lock_check.sh` only at the start of a run — with no run since 2026-04-11, nothing has cleared them.
- **Contradiction: "OIDC cutover done" vs "CI still on static keys".** From the workflow YAML, **the code-side cutover is complete** — zero `secrets.AWS_ACCESS_KEY_ID` references remain in any of the 7 workflows; all 55 `configure-aws-credentials` steps use `role-to-assume: ${{ vars.AWS_DEPLOY_ROLE_* }}` with `id-token: write`. **The platform-side cutover is not** — the 4 `vars` do not exist (F-01) and `services/prd/03_iam/oidc.tf` has never been applied (no run since 2026-04-11, and `master` — the only branch GitHub would schedule from — predates the stack). The static keys survive as unused-but-live secrets (F-02). **Both lanes are right about different halves; the net state is that CI cannot authenticate to AWS at all.**

## 6. Summary

| Severity | Count |
|---|---|
| CRITICAL | 1 (+1 cross-lane) |
| HIGH | 9 |
| MEDIUM | 8 |
| LOW | 5 |
| INFO | 1 |
| **Total** | **24** |

Not covered: `actionlint` on all 7 workflows (F-24); `terraform validate` for `prd/05_databricks`, `prd/06_lambda`, `prd/07_ecs` (3 of 24 dirs); any runtime behaviour (no plan/apply run, no live AWS or GitHub Actions execution); application-layer code under `apps/` and `utils/` (out of lane).

## 7. Recommendation

**REQUEST_CHANGES.**

Nine HIGH and one CRITICAL finding block the v0.4.0 ship. The three that must land before any PR opens: **F-01** (CI cannot authenticate — the entire control plane is inert), **F-04 + no branch protection** (the shipping PR `develop` → `master` passes through zero gates), and the capture-retirement residue in `deploy_all_dm_applications.yml` / `hml_provision.sh` (the release deleted the infrastructure but left the pipeline that provisions and deploys it). F-02, F-14 and F-21 should be routed to `security-reviewer` for a full pass rather than resolved inside this lane.
