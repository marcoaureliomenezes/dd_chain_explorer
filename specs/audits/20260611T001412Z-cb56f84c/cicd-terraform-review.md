# CI/CD + Terraform Code-Quality Review — dd-chain-explorer

**Reviewer:** code-reviewer (dadaia Tier-3)
**Target:** working tree on `feature/specs-first-docs-cleanup` (audit of code on disk, not a PR diff)
**Date (UTC):** 2026-06-11T00:14:12Z
**Scope:** A — `.github/workflows/` (7 files); B — `services/` Terraform; C — `Makefile` + `scripts/`
**Tooling:** `terraform v1.15.2` available — `terraform fmt -check -recursive services/` was run.

> This is a **verdict report**, not a fix. The implementing agent owns the fix.
> Every finding cites `file:line`. Findings outside the reviewed scope are marked `[pre-existing]` where relevant.

---

## Summary — counts by severity

| Severity | Count |
|---|---|
| CRITICAL | 3 |
| HIGH | 8 |
| MEDIUM | 11 |
| LOW | 7 |
| **Total** | **29** |

**Recommendation: REQUEST_CHANGES** — 3 CRITICAL + 8 HIGH findings block.

---

## CRITICAL

### C1 — PRD/HML production `terraform apply` runs with **no per-stack approval gate**; the entire prod infra applies under a single environment approval, auto-approved
- **Files:** `.github/workflows/deploy_cloud_infra.yml:181-210` (`prd-deploy` job), `:248-273` (`hml-deploy`); `scripts/ci/deploy_env.sh:79` (`terraform apply -input=false -auto-approve tfplan`)
- **What it does:** PRD and HML deploy *all* Terraform stacks (VPC, IAM, peripherals, ECS, Lambda, Databricks) inside **one** GitHub job (`prd-deploy` / `hml-deploy`) that shells out to `deploy_env.sh`. The GitHub `environment: production` gate fires **once** at job start; after a human clicks approve, the wrapper loops through every stack and `terraform apply -auto-approve` each one with zero further human review of the actual plan diff. The plan output is only tailed into the step summary *after* the run.
- **Why CRITICAL:** A reviewer approving the job cannot see any plan before approving — the approval is blind. A destructive plan (e.g. VPC replacement forcing ECS/Databricks teardown) applies automatically. This defeats the purpose of an environment protection rule.
- **Contrast:** DEV uses the *correct* pattern — one GitHub job per stack with `if: steps.plan.outputs.plan_has_changes == 'true'` gating apply (`deploy_cloud_infra.yml:107-111`). PRD/HML abandon it.
- **Fix direction:** Either (a) split PRD/HML into per-stack GitHub jobs each behind `environment: production` so each apply is independently approvable, or (b) adopt a two-phase plan→manual-approval→apply pattern (upload `tfplan` artifact on plan job, gate the apply job on environment approval, apply the saved plan). Do not collapse all stacks behind one blind approval.

### C2 — `deploy_env.sh` reads `plan_has_changes` from a **shared append-only `$GITHUB_OUTPUT` file with `tail -1`**, so apply decisions cross-contaminate between stacks
- **File:** `scripts/ci/deploy_env.sh:77` — `PLAN_HAS_CHANGES=$(grep "plan_has_changes=" "${GITHUB_OUTPUT}" 2>/dev/null | tail -1 | cut -d= -f2 || echo "false")`; written by `scripts/ci/tf_plan.sh:43-45`
- **What it does:** Every stack's `tf_plan.sh` *appends* `plan_has_changes=...` to the same `$GITHUB_OUTPUT` file. `deploy_env.sh` then greps the whole file and takes `tail -1`. Across a multi-stack run the file accumulates one line per stack; `tail -1` happens to read the most-recent stack's value, but the file is never truncated between stacks, and the `|| echo "false"` swallows any grep failure.
- **Why CRITICAL:** This is a correctness landmine. If `tf_plan.sh` writes to `/dev/null` (the fallback set at `deploy_env.sh:61` when `GITHUB_OUTPUT` is unset locally) the grep returns nothing → `false` → **apply silently skipped** even when changes exist. In CI the value is read positionally and is fragile to any reordering or an added output line. Apply/skip should never be inferred by string-scraping a shared accumulator file.
- **Fix direction:** Have `tf_plan.sh` return a real exit code (it already computes `PLAN_EXIT`); let `deploy_module()` branch on that exit code directly instead of grepping `$GITHUB_OUTPUT`. Or write the flag to a per-module temp file. Remove the `tail -1` scrape entirely.

### C3 — "Nuclear" destroy-all workflow has **no concurrency group**, so two operators can race a full multi-env teardown concurrently
- **File:** `.github/workflows/destroy_all_cloud_infra.yml` — no top-level `concurrency:` block (confirmed: file absent from `grep -l concurrency`)
- **What it does:** This workflow destroys *every* resource across PRD+HML+DEV, including the `01_tf_state` S3 bucket and the DynamoDB lock table (header lines 8-13). Two concurrent dispatches (or a re-dispatch while one is mid-flight) will both try to empty/delete the same buckets and remove the shared state lock table.
- **Why CRITICAL:** Concurrent destroys of the shared state backend can corrupt or orphan remote state for *all* stacks, and racing on the lock-table deletion removes the very mechanism preventing concurrent state writes. The single most dangerous workflow in the repo is the one missing the guard.
- **Fix direction:** Add `concurrency: { group: destroy-all, cancel-in-progress: false }` at workflow level. Also gate the `confirm` input check (`destroy_all_cloud_infra.yml:19-22`) before any AWS step runs (it currently relies on a downstream safety job — verify it actually blocks).

---

## HIGH

### H1 — `terraform fmt -check` fails on 15 files (formatting drift, not CI-gated)
- **Files:** `services/dev/01_peripherals/main.tf`, `services/dev/02_lambda/main.tf`, `services/hml/03_iam/main.tf`, `services/hml/04_peripherals/main.tf`, `services/hml/05b_databricks_workspace/databricks.tf`, `services/modules/kinesis/variables.tf`, `services/modules/sqs/variables.tf`, `services/prd/02_vpc/locals.tf`, `services/prd/03_iam/locals.tf`, `services/prd/03_iam/main.tf`, `services/prd/05_databricks/databricks.tf`, `services/prd/05a_databricks_account/databricks.tf`, `services/prd/05b_databricks_workspace/databricks.tf`, `services/prd/07_ecs/ecs.tf`, `services/prd/07_ecs/locals.tf`
- **Evidence:** `terraform fmt -check -recursive services/` lists all 15. No workflow runs `fmt -check`; the closest is `scripts/tf_validate_all.sh` (validate only, no fmt gate).
- **Fix direction:** Run `terraform fmt -recursive services/` and add a `terraform fmt -check -recursive` step to `plan_on_pr.yml` as a fail-fast lint gate.

### H2 — Inconsistent Terraform version floors across stacks (three different constraints in one repo)
- **Files:** `services/dev/01_peripherals/main.tf:9` & `services/hml/02_vpc/main.tf:9` pin `required_version >= 1.5` + `aws >= 5.0`; `services/prd/02_vpc/main.tf:2` & `services/prd/07_ecs/main.tf:2` pin `required_version >= 1.3.0` + `aws >= 4.60.0`; `services/prd/01_tf_state/main.tf:2` pins `>= 1.7.0`. CI pins `TF_VERSION: 1.7.0` everywhere.
- **Why HIGH:** The PRD stacks accept AWS provider 4.60 while DEV/HML demand 5.0 — provider behaviour diverges silently between envs that are supposed to mirror each other, defeating the "HML validates what PRD will get" model. The wide `>= 4.60.0` floor allows a stale lockfile to resolve an old provider in PRD only.
- **Fix direction:** Standardise on one `required_version` and one `aws` constraint across all stacks (e.g. `>= 1.7.0`, `~> 5.0`). Commit `.terraform.lock.hcl` per stack (currently gitignored) so provider versions are reproducible.

### H3 — `plan_on_pr.yml` change-detection marks **every** stack changed whenever any shared module changes
- **File:** `.github/workflows/plan_on_pr.yml:67` — `grep -qE "(^services/${path}/|^services/modules/)"`
- **What it does:** The `^services/modules/` alternative is shared by all 10 `set_out` calls, so a one-line edit to *any* module (e.g. `modules/s3`) flips **all 10** stack outputs to `true`, spinning up 10 plan jobs regardless of which stacks actually consume that module.
- **Why HIGH:** Wasteful (10 AWS-authenticated jobs per trivial module edit) and noisy, and it trains reviewers to ignore the plan output. The detection is not module-aware.
- **Fix direction:** Map each module to the stacks that reference it, or run a real `terraform plan` only for stacks whose `terraform graph`/`init` shows the changed module. At minimum, drop the blanket `^services/modules/` OR-clause and scope per consuming stack.

### H4 — Zero `timeout-minutes` on **any** job in **any** of the 7 workflows
- **Files:** all of `.github/workflows/*.yml` (`grep -c timeout-minutes` = 0 for every file)
- **Why HIGH:** Jobs that wait on ECS service stabilization (`deploy_all_dm_applications.yml:841 all-prod-stream-deploy`), Databricks cluster creation, or `aws ecs wait` can hang up to the 6-hour GitHub default. A hung PRD apply holds the Terraform state lock for hours, blocking all other deploys and drift detection.
- **Fix direction:** Add `timeout-minutes:` to every job (e.g. 15 for plan/lint, 30-45 for apply/stabilize jobs).

### H5 — Three deploy strategies for DEV vs HML vs PRD inside the same workflow — unmaintainable divergence
- **File:** `.github/workflows/deploy_cloud_infra.yml` — DEV = per-stack GH jobs with `detect_changes.sh` + plan-gated apply (`:54-156`); PRD = single job → `deploy_env.sh prd` (`:181-210`); HML = single job → `deploy_env.sh hml` (`:248-273`)
- **Why HIGH:** Each env has different change-detection, gating, and plan-visibility semantics. A reviewer must understand three code paths to reason about one workflow. The DEV path uses GH-native `plan_has_changes` gating; PRD/HML bury it in a bash wrapper (see C2). Behaviour drift between envs is guaranteed.
- **Fix direction:** Pick one strategy. Recommended: per-stack matrix job (see also H8) with consistent plan→gate→apply across all three envs; delete `deploy_env.sh` as the parallel implementation.

### H6 — Massive copy-paste in `plan_on_pr.yml`: 10 near-identical 25-line plan jobs differing only by `working-directory` + `MODULE_NAME`
- **File:** `.github/workflows/plan_on_pr.yml:87-359` (jobs `plan-dev-peripherals` … `plan-prd-ecs`)
- **Why HIGH:** ~270 lines of duplicated checkout/setup-terraform/configure-aws/init/plan boilerplate. Any change (e.g. new TF version, OIDC migration, a fmt step) must be edited in 10 places — exactly the kind of drift that produces the inconsistencies in this report.
- **Fix direction:** Collapse into a single `strategy.matrix` job over `{dir, name}` pairs, gated by per-entry `if` on the detect-changes output. The same applies to the 8 per-stack jobs in `deploy_cloud_infra.yml` DEV section and the destroy workflows.

### H7 — Same-stack HML↔PRD Terraform has structural drift (file layout differs, not just values)
- **Evidence:** `diff -rq services/hml/<stack> services/prd/<stack>`:
  - `02_vpc`: PRD has `locals.tf` + `network.tf`; HML folds everything into `main.tf` (`Only in services/prd/02_vpc: locals.tf`, `network.tf`)
  - `03_iam`: PRD has `iam.tf` + `locals.tf`; HML does not
  - `04_peripherals`: PRD has `locals.tf` + `peripherals.tf`; HML does not
  - `07_ecs`: PRD has `ecs.tf` + `locals.tf`; HML does not
  - `05b_databricks_workspace`: PRD has `locals.tf`; all `.tf` differ
- **Why HIGH:** The two environments that are supposed to mirror each other have *diverged file structures*, meaning HML cannot faithfully validate PRD changes. Copy-paste-then-edit drift is exactly what this audit was asked to find. The `required_version`/provider mismatch (H2) is a symptom of the same divergence.
- **Fix direction:** Collapse each duplicated stack into a **single reusable stack module + per-env `tfvars`** (e.g. `services/stacks/vpc/` consumed by `services/envs/{hml,prd}/vpc/` passing a tfvars file). This is the highest-leverage refactor: it eliminates H2, H7, and most of H5/H6 at once.

### H8 — PRD Lambda apply pipes `terraform plan` through `tee`, masking the plan exit code, then applies unconditionally
- **File:** `.github/workflows/deploy_all_dm_applications.yml:949-954` — `terraform plan ... 2>&1 | tee plan.txt` followed immediately by `terraform apply -input=false -auto-approve tfplan` with **no `plan_has_changes` gate**
- **Why HIGH:** The pipe to `tee` means the step's success is determined by `tee`'s exit (0), not `terraform plan`'s — a failing plan still proceeds to apply. And unlike DEV (`deploy_cloud_infra.yml:108`), there is no `if plan_has_changes` guard, so apply runs even with an empty diff. Note also `setup-terraform` here does **not** set `terraform_wrapper: false` (contrast every other job, e.g. `plan_on_pr.yml:100`), so exit-code preservation is already inconsistent.
- **Fix direction:** Use `set -o pipefail` or drop the pipe; reuse `tf_plan.sh` for consistent detailed-exitcode handling; gate apply on changes. Add `terraform_wrapper: false` for parity.

---

## MEDIUM

### M1 — `|| true` / `2>/dev/null || true` error-masking pervasive in teardown and test steps
- **Files (sample):** `deploy_all_dm_applications.yml:395-398` (`aws ecs ... || true`), `:423-425`, `:647-649`, `:669-677`, `:716-727` (Lambda/DynamoDB cleanup all `|| true`), `:733-745`; `scripts/ci/deploy_env.sh:54` (`tf_state_lock_check.sh || true`)
- **Why MEDIUM:** Acceptable for best-effort *teardown*, but several of these mask failures in *test* and *verify* steps (`:423` HML verify, `:649` lambda invoke response), so a broken deployment can report green. The state-lock check being best-effort (`deploy_env.sh:54`) means a stale lock is silently ignored before a multi-stack apply.
- **Fix direction:** Restrict `|| true` to genuine idempotent-cleanup steps; remove it from verify/test/lock-check steps and let them fail loudly (or assert explicitly).

### M2 — `tf_plan.sh` summary uses `tail -N plan.txt` — truncates the plan, can hide the resource-change summary
- **File:** `scripts/ci/tf_plan.sh:31` (`tail -"${TAIL_LINES}" plan.txt`), invoked with `TAIL_LINES: "20"`/`"30"` throughout
- **Why MEDIUM:** Tailing the last 20-30 lines of a plan usually captures the `Plan: X to add` footer, but a plan with a long post-footer warning block, or many resources, will push the critical create/destroy lines out of view. Combined with C1 (blind approval) this means the only plan a reviewer sees may be truncated. Exit code is preserved here (good — `set +e`/`PLAN_EXIT`), so this is masking *visibility*, not exit status.
- **Fix direction:** Upload the full `plan.txt` (and binary `tfplan`) as a build artifact; in the summary show `grep -E '^(Plan:|No changes)'` plus a tail, not tail alone.

### M3 — `git diff origin/<base>...HEAD` change-detection silently falls back to `HEAD~1` and can misclassify on shallow/squash checkouts
- **Files:** `scripts/ci/detect_changes.sh:21`, `plan_on_pr.yml:60-61` (`git diff ... || git diff --name-only HEAD~1 HEAD`)
- **Why MEDIUM:** `detect_changes.sh` uses `origin/develop...HEAD` while the PR workflow uses `origin/${base_ref}...HEAD`; both fall back to `HEAD~1` when the base ref is unavailable. On a squash-merge or shallow clone the fallback compares only the last commit and can mark a changed stack as unchanged → apply skipped. `actions/checkout` fetch-depth is `0` in detect jobs (good) but the fallback remains a foot-gun.
- **Fix direction:** Fetch the base ref explicitly and fail loudly if the merge-base cannot be computed, rather than silently degrading to `HEAD~1`.

### M4 — Hardcoded S3 backend bucket / region / lock table duplicated in every stack's `backend "s3"` block
- **Files:** all 16 `backend "s3"` blocks, e.g. `services/dev/01_peripherals/main.tf:17-23`, `services/prd/07_ecs/main.tf:11-17` — each repeats `bucket = "dm-chain-explorer-terraform-state"`, `region = "sa-east-1"`, `dynamodb_table = "dm-chain-explorer-terraform-lock"`
- **Why MEDIUM:** 16-way duplication of backend config; the only field that varies is `key`. Changing the backend bucket/lock table is a 16-file edit. Region `sa-east-1` is also hardcoded in workflow `env:` and `provider` blocks.
- **Fix direction:** Use partial backend config — keep only `key` in code, pass `bucket`/`region`/`dynamodb_table` via `-backend-config=` (a shared `backend.hcl`) at `terraform init`. Centralises the backend identity.

### M5 — Hardcoded account-derived and resource names baked into workflow `env:`
- **File:** `deploy_all_dm_applications.yml:29-41` — `ECS_CLUSTER`, `HML_ECS_CLUSTER`, `ECR_REPO`, `PRD_LAMBDA_ROLE`, `HML_LAMBDA_ROLE`, etc. all hardcoded; account id is resolved at runtime via `sts get-caller-identity` (`:126`, good) but role/cluster names are literal.
- **Why MEDIUM:** Renaming any resource requires editing the workflow; names can drift from the Terraform that creates them (no single source of truth). Memory `aws-resources.md` lists account `016098071081` — verify no account id is literally embedded anywhere in tf/scripts (none found in this pass, but the coupling is fragile).
- **Fix direction:** Read resource names from Terraform outputs / SSM at runtime instead of hardcoding, or generate the workflow env from a shared config.

### M6 — `dm-chain-utils` pinned `==0.2.9` in CI guard but tech-stack/memory says `>= 0.2.9`
- **File:** `deploy_all_dm_applications.yml:87` (`REQUIRED="dm-chain-utils==0.2.9"`) vs `specs/memory/tech-stack.md` (`dm-chain-utils >= 0.2.9`)
- **Why MEDIUM:** The CI hard-fails any artifact not pinned to *exactly* 0.2.9, but the documented contract is `>=`. Every utils version bump silently breaks this gate until someone edits the literal in the workflow. Source-of-truth mismatch.
- **Fix direction:** Derive the expected pin from the repo `VERSION`/utils version at runtime, or align memory and CI on one pinning policy.

### M7 — Modules lack `required_providers` / version constraints (only root stacks have them)
- **Files:** `services/modules/*/` — `required_providers` present only in stack roots; child modules (e.g. `services/modules/kinesis/`, `services/modules/ecs/`) declare resources without their own `required_providers` version floor.
- **Why MEDIUM:** Reusable modules should declare provider source/version requirements so they are portable and version-safe independent of caller. Without it, a module silently inherits whatever floor the caller sets (which itself is inconsistent — H2).
- **Fix direction:** Add a `versions.tf` with `required_providers` to each module under `services/modules/*`.

### M8 — Variable hygiene: missing `description`/`validation` and inconsistent typing across modules
- **Files:** `services/modules/kinesis/variables.tf`, `services/modules/sqs/variables.tf` (both flagged by `fmt`), and module `variables.tf` generally
- **Why MEDIUM:** Spot-check shows variables without `description` or `validation` blocks, and `environment`/`region` repeated as free-form strings with no `validation` to constrain to `dev|hml|prd` / `sa-east-1`. This is how the env-naming drift in the tech-stack ("dm-{env}-" vs "dm-dd-chain-explorer-{env}-") creeps in.
- **Fix direction:** Add `description` to every variable; add `validation` blocks for `environment` (allowed set) and other enumerated inputs.

### M9 — `auto-bump-version.yml` and `drift_detection.yml` lack concurrency groups
- **Files:** `auto-bump-version.yml` (no `concurrency:`), `drift_detection.yml` (no `concurrency:`)
- **Why MEDIUM:** Two PRs merging to `develop` near-simultaneously can race the VERSION bump (lost update / push conflict). Concurrent drift-detection runs across the same state can collide on the lock.
- **Fix direction:** Add `concurrency: { group: version-bump, cancel-in-progress: false }` and a per-state group for drift.

### M10 — `prd-create-tag` checks out and tags `master` while the deploy ran from `develop` — branch model ambiguity
- **File:** `deploy_cloud_infra.yml:228-242` — `git checkout master` then tag, but `branch_guard.sh` enforces deploys run from `develop` (`:42-48`)
- **Why MEDIUM:** The infra version that was actually applied came from `develop`'s `VERSION`, but the tag is placed on `master`'s HEAD, which may not equal what was deployed. The tag can point at a different tree than the applied infra.
- **Fix direction:** Tag the exact deployed commit SHA, not the tip of `master`.

### M11 — Leftover commented-out / dead code in tf and Makefile
- **Files:** `Makefile:315-318` (commented `docker push` lines in `publish_apps`), `Makefile:328,330` (commented compose lines in `deploy_dev_all`); also scan `services/prd/05*/databricks.tf` for commented blocks (flagged by fmt).
- **Why MEDIUM:** Commented-out commands mislead operators about what a target actually does (`publish_apps` only pushes `spark-batch-jobs`, the rest are commented — name implies "all apps").
- **Fix direction:** Delete dead commented commands or convert to documented optional targets.

---

## LOW

### L1 — `Makefile` `deploy_dev_all` references a non-existent directory `services/compose/`
- **File:** `Makefile:327-330` — `docker compose -f services/compose/airflow_orchestration_layer.yml ...` (and two commented siblings). `services/compose/` does not exist; the real compose file is `services/dev/00_compose/app_services.yml`.
- **Impact:** `make deploy_dev_all` fails immediately. Dead target.
- **Fix direction:** Point at `services/dev/00_compose/app_services.yml` or remove the target.

### L2 — `Makefile` `prod_destroy_infra` calls undefined target `tf_destroy_free_resources`
- **File:** `Makefile:394` calls `$(MAKE) tf_destroy_free_resources`, but that target is **never defined** (only `tf_apply_free_resources` exists at `:320`).
- **Impact:** `make prod_destroy_infra` fails at the last step with "No rule to make target". Broken target.
- **Fix direction:** Define `tf_destroy_free_resources` (mirror of `tf_apply_free_resources` with `destroy`) or fix the call.

### L3 — `Makefile` has no `.PHONY` declarations
- **File:** `Makefile` (`grep -c PHONY` = 0)
- **Impact:** All 60+ targets are non-phony; a file named like a target (e.g. `build_stream`) would shadow it. Minor but standard hygiene gap.
- **Fix direction:** Add `.PHONY` for all action targets.

### L4 — `Makefile` references a non-existent workflow filename in comments
- **File:** `Makefile:363` — "veja .github/workflows/deploy_infrastructure.yml" — no such file (actual: `deploy_cloud_infra.yml`).
- **Fix direction:** Update the comment to the real filename.

### L5 — `Makefile` tf targets hardcode `TF_DIR := services/prd` — duplicate of CI deploy logic, PRD-only
- **File:** `Makefile:312` and all `tf_apply_*`/`tf_destroy_*` targets
- **Impact:** The Makefile re-implements the CI deploy ordering (VPC→peripherals→IAM→ECS→Lambda→Databricks) for PRD only, with `-auto-approve`. It duplicates `deploy_env.sh` and drifts from it (different ordering than `deploy_env.sh:128-136`). A local `make prod_deploy_infra` bypasses every CI guard.
- **Fix direction:** Either delete the local apply targets (force deploys through CI) or have them call the same `deploy_env.sh` to avoid two sources of truth.

### L6 — Local `.terraform/` dirs and `.terraform.lock.hcl` present on disk in `prd/03_iam`, `prd/04_peripherals` (not git-tracked)
- **Evidence:** `diff -rq` shows `Only in services/prd/03_iam: .terraform` / `.terraform.lock.hcl`; `git ls-files | grep .terraform` returns nothing → **not committed** (gitignored), local artifacts only.
- **Impact:** None in VCS, but per workspace repo-cleanliness policy these init artifacts should not linger in the working tree. The *flip side*: because lockfiles are gitignored, provider versions are **not** reproducible in CI (reinforces H2).
- **Fix direction:** Clean local `.terraform/`; reconsider committing `.terraform.lock.hcl` for reproducibility.

### L7 — Region `sa-east-1` hardcoded in workflow `env:` blocks across all 7 workflows
- **Files:** every workflow `env: AWS_REGION: sa-east-1`; also every `backend "s3"` block (see M4).
- **Impact:** Single-region assumption baked everywhere; a region migration is a repo-wide find/replace.
- **Fix direction:** Centralise region as a repo/organization variable (`vars.AWS_REGION`).

---

## Findings index by axis

| Axis | Findings |
|---|---|
| Architecture conformance (env parity, layering) | H5, H7, H2, M4, L5 |
| CI gating / approval quality | C1, C2, C3, H8, M3, M10, M9 |
| Copy-paste / duplication | H6, H7, M4, L5 |
| Error masking / exit-code | C2, H8, M1, M2 |
| Dead code / broken refs | L1, L2, L4, M11 |
| Module / variable hygiene | H1, M7, M8, M6 |
| Version pinning | H2, M6, L6 |
| Timeouts / concurrency | H4, C3, M9 |
| Hardcoding | M5, L7, M4 |

---

## Recommendation

**REQUEST_CHANGES.**

Blocking set: **C1, C2, C3** (blind/auto-approved prod apply; fragile cross-stack apply gating; unguarded nuclear destroy) and **H1–H8**. The single highest-leverage remediation is **H7/H5** — collapse the duplicated per-env stacks into one reusable stack + per-env tfvars, which dissolves H2, H7, most of H5/H6, M4, and M7 in one move, and makes the C1/C2 gating rewrite tractable.

This is a recommendation, not a merge gate — the operator/project-manager decides. No source files were modified by this review.
