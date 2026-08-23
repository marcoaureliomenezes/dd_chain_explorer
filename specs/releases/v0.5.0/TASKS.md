# TASKS — Release v0.5.0 — Remediation: clean restart of infra, CI and Databricks artifacts

> **Status:** Aprovado
> **Release ID:** v0.5.0
> **Owner:** product-engineer (authoring) → software-engineer / qa-engineer / security-reviewer / coordinator / product-engineer (execution, per task)
> **Depends on:** SPEC.md + PLAN.md v0.5.0 (`Aprovado`)
> **Marker contract:** `[ ]` OPEN → `[-]` IN PROGRESS → `[x]` DONE. Reserve with an isolated `chore(tasks): start <id>` commit **before** writing. Max one `[-]` per owner; the five workstreams have disjoint write sets, so four implementers plus the closer may each hold one `[-]` in parallel. Flip to `[x]` only after the review boundary covering the task clears (`dd-release-implement` §4). All tasks below are `[ ]`.

**Write-set law.** WS-A owns `.github/**`, `scripts/ci/**`, `services/prd/00_bootstrap/**` and the **version-axis carve-out** (`VERSION`, `apps/dabs/*/VERSION`, `apps/dabs/deploy_all.sh`); WS-B owns `services/**` except `00_bootstrap` — the whole of `prd/03_iam` included; WS-C owns `apps/dabs/**` except the carve-out; WS-D owns application/library/docs/test paths, `utils/**` **wholly** (the one ordered-not-disjoint seam: `T-D.7` sets the library version after `T-A.9`, K3); WS-E owns `specs/**`. No task writes outside its workstream's set; no Terraform stack has two appliers. Live-resource write sets are named per task. `AC-n` = SPEC §4 acceptance criterion.

---

## WS-A — CI authentication, workflow purge, governance, version axis

- [ ] **T-A.1** — Author the operator-applied bootstrap stack `services/prd/00_bootstrap/` (A1, D14): backend key `prd/bootstrap`; the OIDC provider reference; the four roles `dm-chain-explorer-gha-deploy-{dev,hml,prd}` + `dm-chain-explorer-gha-readonly-plan`, each with prefix-scoped allow statements (project prefixes, state bucket + lock table, SSM path prefixes, Lambda/S3/DynamoDB/Logs/Events/`iam:PassRole` on project roles only), an explicit `Deny` on `iam:*` against `arn:aws:iam::*:role/dm-chain-explorer-gha-*` and on `iam:CreateAccessKey`/`AttachUserPolicy`/`PutUserPolicy`, and `token.actions.githubusercontent.com:sub` trust conditions — `repo:<owner>/<repo>:environment:<env>` per deploy role, `pull_request` + `refs/heads/develop` + `refs/heads/main` for the read-only role (which gets **no** lock-table write, T-A.7's `-lock=false`).
  - Owner: software-engineer · Write set: `services/prd/00_bootstrap/**`
  - Deps: — · AC-2, AC-2b · Findings: DRIFT-01, DRIFT-08, SEC-H-02, SEC-I-01
  - Evidence: explicit statement list, no managed-policy attachment, no `iam:*` on `"*"`; `terraform validate`/`fmt -check` clean on the new stack.

- [ ] **T-A.2** — Security verdict on the bootstrap IAM policy delta before any apply.
  - Owner: security-reviewer · Write set: `.dadaia/handoff/dd-chain-explorer/` (handoff only)
  - Deps: T-A.1 · AC-2, AC-2b · Findings: DRIFT-08
  - Evidence: APPROVED handoff naming the `00_bootstrap` commit sha and confirming the self-mutation `Deny` and the trust `sub` pinning.

- [ ] **T-A.3** — Apply `prd/00_bootstrap` — coordinator-local with operator credentials, the only non-CI apply, and the only stack CI may never apply (O-1).
  - Owner: coordinator (operator credentials) · Write set: live AWS IAM (the four `gha` roles) + the `prd/bootstrap` state key
  - Deps: T-A.2, T-B.1 (O-2), T-B.5 (`00_bootstrap` lock file, O-5) · AC-2 · Findings: DRIFT-01
  - Evidence: apply summary; `aws iam list-roles` + `list-attached-role-policies` + `get-role-policy` for all four roles.

- [ ] **T-A.3b** — Prove least privilege negatively: `aws iam simulate-principal-policy` per `gha` role on a forbidden action (`iam:UpdateAssumeRolePolicy` against a `dm-chain-explorer-gha-*` role ARN) and on one representative allowed action; plus a `scripts/ci/tests` case over `terraform show -json` asserting every `Allow` resource matches a project prefix or the state bucket/lock table.
  - Owner: software-engineer · Write set: `scripts/ci/tests/**`
  - Deps: T-A.3 · AC-2, AC-2b · Findings: DRIFT-08
  - Evidence: `implicitDeny`/`explicitDeny` for the forbidden action on all four roles, `allowed` for the permitted one; the assertion test green in CI.

- [ ] **T-A.4** — Bootstrap-as-code and the credential surface (A2): check in `scripts/ci/publish_oidc_vars.sh` (reads the `00_bootstrap` outputs, runs `gh variable set` for the four names), add the fail-fast preflight step to every role-assuming workflow with a `scripts/ci/tests` case asserting its presence, write the one-time-apply runbook entry (`docs/`, executed by WS-D's `T-D.6`), then publish the four variables and delete the static + capture-era secrets.
  - Owner: software-engineer (script, preflight, test) · coordinator (variables + secrets, operator credentials) · Write set: `scripts/ci/publish_oidc_vars.sh`, `scripts/ci/tests/**`, `.github/workflows/**` (preflight step), GitHub repository variables + secrets
  - Deps: T-A.3 (roles must exist first, O-9) · AC-1, AC-3, AC-3b · Findings: DRIFT-01, DRIFT-09, SEC-M-05, SEC-I-01
  - Evidence: `gh variable list`, `gh secret list` (generic names only — public repo); a deliberate empty-variable run failing **at the preflight step** with an explicit message.

- [ ] **T-A.5** — Deactivate the CI IAM user's 2025-vintage access key (A2).
  - Owner: coordinator (operator credentials) · Write set: live AWS IAM (that access key)
  - Deps: T-A.4 · AC-3 · Findings: DRIFT-09, SEC-H-02
  - Evidence: `aws iam list-access-keys --user-name <ci-user>` → `Inactive`.

- [ ] **T-A.6** — Purge the capture lane from the application deploy workflow; reduce the HML lane scripts; delete the tombstoned gate call (A3).
  - Owner: software-engineer · Write set: `.github/workflows/deploy_all_dm_applications.yml`, `scripts/ci/hml_provision.sh`, `scripts/ci/hml_teardown.sh`
  - Deps: — · AC-5 · Findings: DRIFT-02, CI-M1
  - Evidence: job graph = Lambda + DABs only; `grep -rniE 'kinesis|firehose|sqs|ecs|onchain-stream' .github/workflows/ scripts/ci/` → 0; `actionlint` + `bash -n` clean.

- [ ] **T-A.7** — CI safety batch: per-environment `concurrency`, PR trigger on both long-lived branches, the three test suites + `pip-audit` + the from-source layer build wired into `plan_on_pr`, `destroy_all` covering every live stack, Terraform and actionlint installer pinned (version + checksum), `auto-bump-version.yml` deleted, every `hml-apps` reference removed (A4, A5).
  - Owner: software-engineer · Write set: `.github/workflows/**`
  - Deps: T-A.6; T-D.4 (layer-build inputs, PLAN K6) · AC-4, AC-6, AC-21 · Findings: DRIFT-07, DRIFT-14, DRIFT-15, DRIFT-26, CI-M9, ARCH-H6
  - Evidence: `gh workflow list`; per-workflow `concurrency:` grep; `actionlint` clean; a green `plan_on_pr` run URL from a fresh clone.

- [ ] **T-A.8** — Make `scripts/ci/` truthful and the plan path lock-free: `stack_map.json` declares dev module edges and drops phantom prd edges, the four hard-coded stack lists read it, `check_prd_version.sh` reads `VERSION`, `tf_plan.sh` passes **`-lock=false`** on the read-only plan path (F-04); new `scripts/ci/tests` cases assert the map, the `-lock=false` flag, and that `destroy_all`'s stack set equals `stack_map.json`'s survivors (A4, A6).
  - Owner: software-engineer · Write set: `scripts/ci/**` except the three files of T-A.6
  - Deps: T-A.7 · AC-4b, AC-9 · Findings: DRIFT-14, DRIFT-15
  - Evidence: `pytest scripts/ci/tests -p no:cacheprovider` green **and** the CI job log proving the suite ran; `grep -n 'lock=false' scripts/ci/tf_plan.sh`; the read-only role's policy carries no `dynamodb:PutItem`/`DeleteItem`.

- [x] **T-A.9** — One version axis = the SDD release id (A6). **Lands before any WS-C/WS-D edit (O-4, K3).**
  - Owner: software-engineer · Write set: `VERSION`, `apps/dabs/*/VERSION`, `apps/dabs/deploy_all.sh`, `scripts/ci/check_prd_version.sh`
  - Deps: — · AC-8 · Findings: DRIFT-11, CI-M10
  - Evidence: `cat VERSION`; `cat apps/dabs/*/VERSION | sort -u` → `0.5.0`; tag-skip gone from `deploy_all.sh`. The library declarations are `T-D.7`'s, ordered after this task — the one ordered-not-disjoint seam.

- [ ] **T-A.10** — Governance settings: protection on `main` (PR + the `plan_on_pr` required check named after its **first** run on the cut-over PR, no force-push/deletion) and `develop` (no force-push/deletion); operator as required reviewer on `production` and `hml`; no `hml-apps` environment; stale remote branches **listed only**, as a committed artifact (A5).
  - Owner: coordinator (operator credentials) · Write set: GitHub branch-protection rules + environments; the stale-branch listing artifact
  - Deps: T-A.7, T-A.11 steps (3)–(5) — a required check cannot be named before it has run once · AC-7, AC-7b · Findings: DRIFT-10, SEC-I-03
  - Evidence: `gh api repos/{owner}/{repo}/branches/{main,develop}/protection` and `.../environments`; the committed stale-branch list (no deletion).

- [ ] **T-A.11** — Execute steps (3)–(5) of the O-8 `main` cut-over: rename the default branch `master`→`main` via `gh api --method POST repos/{o}/{r}/branches/master/rename` (redirects preserved), open the PR `develop` → `main`, and capture the check name from that PR's first `plan_on_pr` run. **Only after T-A.7 is merged and pushed (O-8 steps 1–2).** Steps (6)–(9) are `T-A.10` + `T-R.3`.
  - Owner: coordinator (operator credentials) · Write set: GitHub repository settings; the cut-over PR
  - Deps: T-A.7 merged to `develop` and pushed · AC-7 · Findings: DRIFT-10, CI-M10
  - Evidence: `gh repo view --json defaultBranchRef` → `main`; the PR URL; the `plan_on_pr` run and its check name (feeds AC-4 and T-A.10).

---

## WS-B — Terraform purge, HML reduction, live AWS cleanup

- [ ] **T-B.1** — Force-unlock the two state locks stuck since April (B3). **First live task — O-2 blocks every plan/apply behind it.**
  - Owner: software-engineer (operator-gated) · Write set: live DynamoDB lock table
  - Deps: — · AC-13 · Findings: DRIFT-16
  - Evidence: `gh run list --status in_progress` empty beforehand; `terraform force-unlock` output; `aws dynamodb scan --table-name <lock-table> --select COUNT` → 0.

- [ ] **T-B.2** — Delete the capture-era and never-applied stacks and modules (B1).
  - Owner: software-engineer · Write set: `services/prd/{02_vpc,05_databricks,05a_databricks_account,05b_databricks_workspace,07_ecs}`, `services/hml/{02_vpc,03_iam,05_databricks,05b_databricks_workspace,07_ecs}`, `services/modules/{ecs,vpc}` (deletion)
  - Deps: T-B.1 · AC-11 · Findings: DRIFT-13, ARCH-C1, CI-M11
  - Evidence: `ls services/prd services/hml services/modules`; `terraform validate` clean on every survivor.

- [ ] **T-B.3** — Module, grant and dead-IaC surgery: firehose branch + `[0]` index out of `modules/cloudwatch_logs`; capture grants out of `modules/iam` and `prd/03_iam/iam.tf`; the **E2 cross-account/cluster role set** (dead since the PRD workspace was destroyed 2026-04-11 — the load-bearing UC credential is `dm-databricks-dev-s3-role`, not these); the hard-coded `databricks_account_uuid` **default** (variable kept, default removed — public repo); the `kinesis_sqs` **and `prd/vpc`** remote-state aliases and every consumer of them; 6 unused variables and the ignored `prevent_destroy` variable (B1, F-07).
  - Owner: software-engineer · Write set: `services/modules/{cloudwatch_logs,iam,s3}/**`, `services/prd/03_iam/**` (except `oidc.tf`, removed by T-B.3a), `services/prd/06_lambda/**`
  - Deps: T-B.2 · AC-16 · Findings: DRIFT-13, DRIFT-26, ARCH-M6, ARCH-H4
  - Evidence: `grep -rniE 'kinesis|firehose|sqs' services/` → 0; no account uuid literal in `git grep`; `terraform validate` clean. **Applied before `T-B.11` deletes the `prd/vpc` state key (O-1b/K9).**

- [ ] **T-B.3a** — Remove `oidc.tf` from `prd/03_iam` and apply, once `prd/00_bootstrap` holds the roles (O-1, D14). One plan/apply event together with T-B.3's purge — `prd/03_iam` has exactly one applier.
  - Owner: software-engineer (apply operator-gated) · Write set: `services/prd/03_iam/oidc.tf` (deletion); the `prd/03_iam` state
  - Deps: T-B.3, T-A.3, T-A.3b (the bootstrap roles must be proven working first) · AC-2, AC-10 · Findings: DRIFT-01, DRIFT-08
  - Evidence: plan showing only the `oidc.tf` resources leaving `03_iam` state (no role deletion — they are `00_bootstrap`'s now); post-apply plan 0/0/0; the four `gha` roles still present.

- [ ] **T-B.4** — Reduce HML to the minimal lane with the **names pinned in SPEC §2.2 B2**: `hml/04_peripherals` keeps `dm-chain-explorer-hml-raw-data` + `dm-chain-explorer-hml-lakehouse` and declares `dm-databricks-hml-s3-role` granting only those two buckets; every other HML stack is destroyed (B2, F-05).
  - Owner: software-engineer (live destroy operator-gated) · Write set: `services/hml/**`; live AWS HML peripherals resources
  - Deps: T-B.3, T-C.3 (bundle variables aligned to the same names), T-C.5 (PLAN K5) · AC-10, AC-11, AC-18b · Findings: DRIFT-22, ARCH-C2
  - Evidence: informed-gate plan reviewed before `destroy_ack`; post-apply plan 0/0/0; `aws s3api head-bucket` → 200 on both canonical names.

- [ ] **T-B.5** — Commit `.terraform.lock.hcl` for every surviving root stack; declare `required_providers` in every module (B5). **Before the first apply (O-5) — `prd/00_bootstrap` included.**
  - Owner: software-engineer · Write set: `services/**/.terraform.lock.hcl`, `services/modules/**/versions.tf`
  - Deps: T-B.2, T-A.1 (the `00_bootstrap` directory must exist) · AC-15 · Findings: DRIFT-15, ARCH-H6, CI-H2, CI-M7
  - Evidence: `git ls-files 'services/**/.terraform.lock.hcl' | wc -l` = the surviving root-stack count (**8**, `00_bootstrap` included).

- [ ] **T-B.6** — Services hardening: stop persisting the Databricks bootstrap token in state; drop the ECR `MUTABLE`/`force_delete` and VPC-CIDR all-protocol ingress declarations with their stacks; encode or drop the manual post-apply `.keep` step (B5).
  - Owner: software-engineer · Write set: `services/prd/**`, `services/dev/**` (the named declarations)
  - Deps: T-B.3 · AC-10 · Findings: DRIFT-26, SEC-M-03, SEC-L-02, ARCH-L7
  - Evidence: no state-persisted token in the diff; plan clean.

- [ ] **T-B.7** — Disable the hourly PRD `contracts-ingestion` schedule **through Terraform**; keep the Lambda and the `job_export_gold → gold_to_dynamodb → DynamoDB` chain (B4).
  - Owner: software-engineer (apply operator-gated) · Write set: `services/prd/06_lambda/**`; live EventBridge rule state
  - Deps: T-B.5 · AC-14 · Findings: DRIFT-21, DRIFT-27, DRIFT-N01, DRIFT-N02, DRIFT-N03
  - Evidence: `aws events describe-rule` → `State: DISABLED`; the AC-10 clean plan proves it is declared, not clicked.

- [ ] **T-B.8** — Live network cleanup: delete the 24 `dm-hml-sg-*` security groups, then the unmanaged legacy VPC with its subnets and internet gateway (B3; order fixed by O-3).
  - Owner: software-engineer (operator-gated) · Write set: live AWS EC2/VPC
  - Deps: T-B.1, T-B.4 · AC-12 · Findings: DRIFT-17
  - Evidence: pre-delete `describe-security-groups|vpcs|subnets` snapshots in `.dadaia/tmp/software-engineer/<date>/`; zero-attached-ENI check; post-delete probes → 0.

- [ ] **T-B.9** — Live compute/registry cleanup: the empty ECS cluster, the two empty ECR repositories, the HML log groups, the ACTIVE `dm-*` task-definition revisions (B3).
  - Owner: software-engineer (operator-gated) · Write set: live AWS ECS/ECR/CloudWatch Logs
  - Deps: T-B.8 · AC-12 · Findings: DRIFT-22, DRIFT-24, ARCH-L3
  - Evidence: `ecr list-images` empty before deletion; `ecs list-clusters`, `ecr describe-repositories`, `logs describe-log-groups --log-group-name-prefix /hml` empty after.

- [ ] **T-B.10** — Live orphan cleanup: the legacy dev `gold-to-dynamodb` lambda with its role and log group, and the orphan firehose role (B3). **Log-group retention is not set here** — the kept groups are declared and imported by `T-B.14` so Terraform owns it (F-09).
  - Owner: software-engineer (operator-gated) · Write set: live AWS Lambda/IAM/CloudWatch Logs
  - Deps: T-B.9 · AC-12, AC-16 · Findings: DRIFT-24
  - Evidence: pre-delete `get-function` + role-policy snapshots; `lambda list-functions` and `iam list-roles --query "Roles[?contains(RoleName,'firehose')]"` absent.

- [ ] **T-B.11** — State-bucket hygiene: remove the orphan 0-resource state keys and the phantom `hml/peripherals` bucket entries (B3).
  - Owner: software-engineer (operator-gated) · Write set: the Terraform state bucket key space
  - Deps: T-B.2, T-B.4 · AC-11 · Findings: DRIFT-24
  - Evidence: per-key resource count 0 recorded before deletion; bucket versioning confirmed ON; `aws s3api list-objects-v2 --bucket <state-bucket> --query 'Contents[].Key'` after. **State files are never copied to local disk** (`DADAIA.md` §8).

- [ ] **T-B.12** — Import the live `dm-databricks-dev-s3-role` into `dev/01_peripherals` — load-bearing, never deleted (B2/B3, F-05).
  - Owner: software-engineer (operator-gated) · Write set: `services/dev/01_peripherals/**`; that stack's Terraform state
  - Deps: T-B.4 · AC-10, AC-18b · Findings: DRIFT-22
  - Evidence: `terraform import` output; post-import plan 0 diff; the dev Databricks storage credential still resolves.

- [ ] **T-B.14** — Artifact store and layer inputs (B6, D15): create `dm-chain-explorer-artifacts` (versioned, private, block-public-access) in `prd/04_peripherals` — dev consumes it under a `dev/` prefix; rewire `prd/06_lambda` and `dev/02_lambda` to read the layer from `s3_bucket`/`s3_key`/`source_code_hash` supplied as `layer_s3_key`/`layer_sha256` **variables** (no `filebase64sha256` on a working-tree path) and to build the handler zips with `data "archive_file"` over `apps/lambda/<fn>/src`; declare and **import** the kept Lambda log groups with their retention.
  - Owner: software-engineer (apply operator-gated) · Write set: `services/prd/04_peripherals/**`, `services/prd/06_lambda/**`, `services/dev/02_lambda/**`
  - Deps: T-D.4 (build script + lock exist), T-B.6 · AC-10, AC-12, AC-21 · Findings: DRIFT-07, DRIFT-24
  - Evidence: `aws s3api head-bucket` on the artifacts bucket; a fresh-clone plan with **no** local `.lambda_zip/` resolving the layer from the variables; `logs describe-log-groups` retention matching the declaration. **The bucket exists before the first CI upload, and an object exists at the key before any consuming plan (O-1c).**

- [ ] **T-B.13** — Prove the surviving tree: plan clean on every kept stack, **from a fresh clone**.
  - Owner: software-engineer · Write set: none (verification)
  - Deps: T-B.3a, T-B.4..T-B.12, T-B.14 · AC-10 · Findings: DRIFT-13, DRIFT-22
  - Evidence: `deploy_cloud_infra` plan phase for `dev` and `prd` — `0 to add, 0 to change, 0 to destroy` on all **eight** kept stacks (`00_bootstrap` included); run URL recorded.

---

## WS-C — Databricks artifacts

- [ ] **T-C.1** — Drop the no-op `alert_*` and `genie_ethereum` bundles and `job_reconcile_orphans` (C1).
  - Owner: software-engineer · Write set: `apps/dabs/**` (the named bundles/jobs)
  - Deps: T-A.9 (O-4) · AC-17, AC-18 · Findings: DRIFT-19, ARCH-M3, ARCH-M5
  - Evidence: `databricks bundle validate -t dev` per survivor; alert/Genie reinstatement recorded as a deferred intake candidate (T-E.7).

- [ ] **T-C.2** — **Delete `apps/dabs/job_trigger_all` and `apps/dabs/job_full_refresh` entirely** (C2, F-06): the DLT bundles already own per-pipeline trigger jobs with native ids, and full refresh is `databricks pipelines start-update --full-refresh <id>` — documented in `apps/dabs/README.md` by T-C.4. No cross-bundle reference and no display-name `lookup` is introduced; the ADR-004 corollary "no bundle references another bundle's resource" is recorded by `T-E.4`. Remove the silently-dropped DLT `schedule:` blocks.
  - Owner: software-engineer · Write set: `apps/dabs/job_trigger_all/**`, `apps/dabs/job_full_refresh/**` (deletion), the DLT bundles' `schedule:` blocks
  - Deps: T-C.1 · AC-17, AC-18 · Findings: DRIFT-19, ARCH-M3
  - Evidence: both directories absent from disk; `databricks bundle summary -t dev` with no empty `pipeline_id`; the in-bundle trigger job of each DLT bundle validated.

- [ ] **T-C.3** — Guard the workspace host on **every** target (`dev`, `hml`, `prod` all read it from a `DATABRICKS_HOST`-style env var or bundle variable; prod's has no default, so `validate -t prod` fails unset and no `cloud.databricks.com` literal survives); parametrise the dashboard catalog; align the published embed setting; set `run_as` to the service principal; align every hml bundle variable to SPEC §2.2 B2's pinned bucket names (C3, PLAN K5, F-06).
  - Owner: software-engineer · Write set: `apps/dabs/**` (targets, variables, dashboards)
  - Deps: T-C.2 · AC-17, AC-19 · Findings: DRIFT-09, DRIFT-25, ARCH-M3
  - Evidence: `databricks bundle validate -t prod` non-zero with the host unset; `grep -rniE '@|cloud.databricks.com|"dev\."' apps/dabs/` → 0; `databricks service-principals list` contains `dm_spn_user`.

- [ ] **T-C.7** — Create or update the `hml` Unity-Catalog **storage credential** and **external location** via `databricks storage-credentials` / `databricks external-locations`, pointing at `dm-databricks-hml-s3-role` and the two canonical hml buckets (C6, F-05).
  - Owner: software-engineer (operator-gated) · Write set: the live Databricks `hml` storage credential + external location
  - Deps: T-B.4, T-B.12, T-C.3 · AC-18b · Findings: DRIFT-22
  - Evidence: `databricks external-locations get <hml>` — `url` matches the canonical bucket names and its credential is the hml role; `aws s3api head-bucket` ×2 → 200; `databricks bundle validate -t hml` clean.

- [ ] **T-C.4** — Scope or remove `job_ddl_setup` / `job_delta_maintenance`; remove the f-string SQL construction; retarget the app-logs silver filter off the retired producers' logger names; rewrite `apps/dabs/README.md` (C4).
  - Owner: software-engineer · Write set: `apps/dabs/**` (the named jobs, notebooks, `README.md`)
  - Deps: T-C.3 · AC-18, AC-24 · Findings: DRIFT-25, DRIFT-26, DRIFT-27
  - Evidence: job definitions scoped to non-DLT objects; no f-string SQL in the diff; `validate -t dev` clean.

- [ ] **T-C.5** — Validate every surviving bundle in `dev` and `hml` before any deploy (O-6).
  - Owner: software-engineer · Write set: none (verification)
  - Deps: T-C.4 · AC-17 · Findings: DRIFT-18
  - Evidence: exit-0 `databricks bundle validate -t dev` and `-t hml`, captured per bundle name.

- [ ] **T-C.6** — Deploy `dev` and `hml` so live == repo (incl. the never-deployed Fluent-Bit app-logs reader and the pre-R1 hml ethereum pipeline); remove the stale `.bundle/dd-chain-explorer` roots and the orphan dashboard (C5). **No prod deploy.**
  - Owner: software-engineer (operator-gated) · Write set: the live Databricks `dev` and `hml` targets
  - Deps: T-C.5, T-B.4 · AC-18 · Findings: DRIFT-18
  - Evidence: `databricks bundle summary` per target; `pipelines get <id>` showing the repo-revision notebook; `jobs list`; no stale `.bundle` root or orphan dashboard.

---

## WS-D — Dead code, supply chain, quality gates, tests, docs

- [ ] **T-D.1** — Write the live-surface pyramid **before** any deletion (O-7): both Lambda handlers, the DABs job scripts, the DLT expectation functions (local PySpark), and the CI-script cases the suite lacks; intent and size declared on every test (D4).
  - Owner: software-engineer · Write set: `tests/**` (new)
  - Deps: T-A.9 (O-4) · AC-23 · Findings: DRIFT-20, DRIFT-N08
  - Evidence: `pytest -p no:cacheprovider` green; per-test intent/size declarations.

- [ ] **T-D.2** — `qa-engineer` verdict on the deletion/demotion map for the capture-era tests — no deletion without it (test-stewardship).
  - Owner: qa-engineer · Write set: `.dadaia/handoff/dd-chain-explorer/` (handoff only)
  - Deps: T-D.1 · AC-20, AC-23 · Findings: DRIFT-20
  - Evidence: APPROVED handoff listing every test to delete/demote with its replacement — copied into CLOSURE `## Test dispositions`.

- [ ] **T-D.3** — Delete the capture-era code and tests and the `img/` slop (D1).
  - Owner: software-engineer · Write set: `apps/docker/**` (deletion), the 6 dead `dm_chain_utils` modules + re-exports under `utils/**`, `scripts/prod_ecs_logs.py`, the unreferenced operator scripts, `scripts/hml_integration_test_optimized.sh`, `img/`, the tests named in T-D.2
  - Deps: T-D.2 · AC-20 · Findings: DRIFT-12, DRIFT-20, ARCH-M6, ARCH-L1, ARCH-L2, ARCH-L4
  - Evidence: `ls apps/docker`; `grep -rn 'dm_kinesis|dm_sqs|dm_firehose|dm_web3_client|dm_cloudwatch_logger|api_keys_manager' --include='*.py' .` → 0; the verdict handoff path.

- [ ] **T-D.4** — Close the supply chain (D2, D15): write `scripts/build_lambda_layer.sh` — `pip install --require-hashes -r apps/lambda/requirements.lock -t build/` for the third-party deps **plus** `pip install ./utils -t build/ --no-deps` for the library as a **path** requirement (the path install closes dependency confusion; `--no-index` is **wrong** here, the transitive deps do come from the index, hash-pinned) — and the `requirements.lock` it consumes; zip to `.lambda_zip/` (untracked + gitignored). Drop the public `==0.2.9` pin, untrack the tracked binaries, pin every lambda/utils requirement with `==`. CI upload + `-var` pass-through is `T-A.7`; the bucket and Terraform variables are `T-B.14` (PLAN K6).
  - Owner: software-engineer · Write set: `scripts/build_lambda_layer.sh`, `apps/lambda/**` (incl. `requirements.lock`), `utils/**` (version declarations only in T-D.7), `scripts/**` except `scripts/ci/**`, `.gitignore`
  - Deps: T-D.3 · AC-21 · Findings: DRIFT-06, DRIFT-07, CI-M6, DRIFT-N07, DRIFT-N09
  - Evidence: `grep -rn 'dm-chain-utils==' .` → 0; `git ls-files '*.zip' '*.whl'` → 0; `git check-ignore .lambda_zip/`; `pip-audit -r apps/lambda/requirements.lock` clean or every finding covered by an ignore recorded in AC-21.

- [ ] **T-D.7** — Set the library version declarations to `0.5.0` (`utils/pyproject.toml`, `utils/src/dm_chain_utils/__init__.py`) — **the one ordered-not-disjoint seam: runs after `T-A.9`** (O-4, K3).
  - Owner: software-engineer · Write set: `utils/pyproject.toml`, `utils/src/dm_chain_utils/__init__.py`
  - Deps: T-A.9, T-D.4 · AC-8 · Findings: DRIFT-11, CI-M6
  - Evidence: `grep -n version utils/pyproject.toml utils/src/dm_chain_utils/__init__.py` → `0.5.0`; `grep -rn '0\.2\.9' -- . ':!specs'` → 0.

- [ ] **T-D.5** — Quality gates and a clean worktree: `ruff` + `mypy` configured and passing; state directories gitignored; duplicate test tree removed; residual key-tail logging and the bulk parameter-listing helper removed; the scanner-ignore blind spot closed (D3).
  - Owner: software-engineer · Write set: root `pyproject.toml`/ruff/mypy config, `.gitignore`, `.gitguardian.yml`, the kept modules under `apps/lambda/**` and `utils/**`
  - Deps: T-D.4 · AC-22 · Findings: DRIFT-26, DRIFT-29, ARCH-M7, CI-L6, SEC-H-01 (residual), SEC-L-05
  - Evidence: `ruff format --check . --no-cache`, `ruff check . --no-cache`, `mypy`, `git status --porcelain` — all clean.

- [ ] **T-D.6** — Docs to the post-capture truth: the Makefile reduced to thin wrappers over the scripts CI runs (the 16 broken targets fixed); `README.md`, `docs/**`, app READMEs, DLT notebook headers, DDL comments and integration-test prerequisites rewritten (D5).
  - Owner: software-engineer · Write set: `Makefile`, `README*`, `docs/**`, repo-local `AGENTS.md`, app READMEs and notebook/DDL headers outside `apps/dabs/**`
  - Deps: T-D.5 · AC-24 · Findings: DRIFT-28, ARCH-H2, CI-L1, CI-L2, CI-L3, CI-L4, CI-L5, DRIFT-N10
  - Evidence: `make -n <target>` for every documented target; `grep -rniE 'kinesis|firehose|ECS producer' README* docs/ apps/**/README*` → 0.

---

## WS-E — Governance documents, dispositions, memory truth

- [ ] **T-E.1** — Author `specs/constitution.md` from the archived 231-line version, scoped to the infra / CI / Databricks reality (E1).
  - Owner: product-engineer · Write set: `specs/constitution.md`
  - Deps: — · AC-26 · Findings: DRIFT-31
  - Evidence: `wc -l specs/constitution.md` (not the 33-byte stub); `dadaia specs doctor`.

- [ ] **T-E.2** — Bug-ledger repair (E4): a terminal event for the misfiled tooling bug, and the resolved-before-reported timestamp anomaly.
  - Owner: product-engineer · Write set: `specs/bugs/bugs.jsonl`
  - Deps: — · AC-28 · Findings: DRIFT-31
  - Evidence: exact command — `dadaia bugs append --bug-id sdd-artifact-linter-mutates-task-markers --event rejected --reported-by product-engineer --reason "not a bug of this context: workspace-library tooling, re-registered upstream in the dadaia-workspace context"`. `rejected` is the terminal kind for a misfiled record; `superseded` is reserved for supersession by a slug in **this** context's picked set. Then correct the migration-synthesized `reported` timestamp of `drift-04-kafka-avro-dead-code` so it precedes its `resolved` event. Then `dadaia bugs status` → 0 open and `dadaia specs doctor` SPEC-DOC-032/033 clean.

- [ ] **T-E.3** — SDD-tree verification (E4 residual): confirm no release SPEC lives outside `_archive/` — at authoring time every `SPEC.md` other than the active release is already archived — and `git mv` any survivor; confirm the v0.4.0 archive and the single-source backlog are intact.
  - Owner: product-engineer · Write set: `specs/_archive/**` via `git mv` only
  - Deps: — · AC-25 · Findings: DRIFT-03, DRIFT-30, ARCH-L8, ARCH-M8
  - Evidence: the file listing; `dadaia specs doctor` + `dadaia backlog doctor` output.

- [ ] **T-E.4** — **(CLOSURE)** Author the capture-deprecation ADR (supersession by `dd-chain-capture`, S3 as the sole boundary, parked-until-delivery posture, sunset criteria) and rewrite the ADR-005 lambda-union claim to the streaming-only reality (E2).
  - Owner: product-engineer · Write set: `specs/memory/architecture.md`
  - Deps: T-R.2, `ACTIVE.md` phase `CLOSURE` (memory is gate-writable in DEFINITION/CLOSURE only) · AC-26 · Findings: DRIFT-04, ARCH-H5, DRIFT-N01, DRIFT-N02, DRIFT-N03
  - Evidence: the ADR sections in `architecture.md`; `dadaia specs doctor` clean.

- [ ] **T-E.5** — **(CLOSURE)** Update the memory atoms to the post-release truth (E5, SPEC §8): `product/cicd-pipeline.md`, `product/aws-resources.md`, `architecture.md`, `product/medallion-pipelines.md`, `product/serving-layer.md`, `product/data-catalog.md` (only if the object inventory changed), `product/capture-layer.md`, `quality-assurance.md`, `tech-stack.md`, and `product/index.md` + `catalog.json` only if a rank changed or an atom was added/removed.
  - Owner: product-engineer · Write set: `specs/memory/**`
  - Deps: T-E.4 · AC-25 · Findings: DRIFT-04, DRIFT-23 (state-key documentation), DRIFT-27, ARCH-H3, ARCH-M1, ARCH-M2, ARCH-M4, DRIFT-N06
  - Evidence: the file list reproduced in CLOSURE `## Memory updates`; no changelog section; `dadaia specs doctor` 0 errors.

- [ ] **T-E.6** — **(CLOSURE)** Write `CLOSURE.md`: summary, tasks + commit shas, validations, size accounting, drifts, memory updates, `## Dispositions` with one terminal row per DRIFT-01..31 and per 2026-06-11 finding id (SPEC §7 is the source), test dispositions (T-D.2's map), record-only observations, artifact GC sweep, archive decision.
  - Owner: product-engineer · Write set: `specs/releases/v0.5.0/CLOSURE.md`
  - Deps: T-E.5 · AC-25, AC-27 · Findings: DRIFT-05, DRIFT-30
  - Evidence: `dadaia specs doctor` 0 errors; `dadaia backlog doctor` clean; every disposition row carries a CLOSURE section or commit sha.

- [ ] **T-E.7** — **(CLOSURE)** Compile the residuals into CLOSURE `## Intake candidates` for the PM's intake report — `terraform-single-stack-tree-per-env-tfvars`, `capture-ecr-state-and-kms-ownership-transfer`, `rest-api-public-endpoint`, `encryption-at-rest-posture-decision`, alert/Genie reinstatement. **No backlog entry is authored by this release.**
  - Owner: product-engineer · Write set: `specs/releases/v0.5.0/CLOSURE.md` (that section)
  - Deps: T-E.6 · AC-25 · Findings: DRIFT-19, DRIFT-23, ARCH-M8, SEC-M-04, ARCH-H1, CI-H5, CI-H6, CI-H7, CI-M4, CI-M5, CI-M8, CI-L7
  - Evidence: each residual listed under "To be adjudicated" or "Pre-approved intake" (SPEC §3 deferrals are operator-ratified → pre-approved).

- [ ] **T-E.8** — **(CLOSURE, O-10 last)** Archive both audit directories with a `DISPOSITION.md` naming v0.5.0; then archive the release and repoint `ACTIVE.md`.
  - Owner: product-engineer · Write set: `specs/audits/**` and `specs/releases/v0.5.0/` via `git mv`; `specs/releases/ACTIVE.md`
  - Deps: T-E.6, T-E.7 · AC-27 · Findings: DRIFT-05
  - Evidence: `ls specs/audits/_archive/`; `git mv specs/releases/v0.5.0 specs/_archive/releases/v0.5.0`; `ACTIVE.md` → `release: none` or the next release.

---

## Review checkpoints

- [ ] **T-R.1** — **alpha-1**: all WS-A..WS-E implementation tasks review-ready → `qa-engineer` review committed to the branch.
  - Owner: qa-engineer · Write set: `.dadaia/handoff/dd-chain-explorer/` + the qa artifact on `feature/0.5.0`
  - Deps: T-A.1..T-A.11 (incl. T-A.3b), T-B.1..T-B.14 (incl. T-B.3a), T-C.1..T-C.7, T-D.1..T-D.7, T-E.1..T-E.3 · AC-1..AC-26 evidence assembled
  - Evidence: `APPROVE`/`REQUEST_CHANGES` handoff. Unlocks `[x]` on the implementation tasks — **not** push, PR, merge or CLOSURE.

- [ ] **T-R.2** — **rc-1**: `qa-engineer` + `code-reviewer` (six-axis on the delta) + `security-reviewer` (diff-based) all APPROVE the **same** commit.
  - Owner: qa-engineer, code-reviewer, security-reviewer · Write set: `.dadaia/handoff/dd-chain-explorer/`
  - Deps: T-R.1 green · the full AC set
  - Evidence: three APPROVED handoffs naming one commit sha. Unlocks memory → CLOSURE → archive (T-E.4..T-E.8), then ship.

- [ ] **T-R.3** — **ship + the O-8 `main` cut-over**, in this exact order: (1) merge `feature/0.5.0` → local `develop` (milestone b), security push verdict on `origin/develop..develop`, push `develop` — every workstream now on `develop`; (2) confirm `plan_on_pr` already triggers on `main` (landed by T-A.7); (3) the `master`→`main` rename and (4) the PR `develop` → `main` are `T-A.11`'s; (5) that PR's **first** `plan_on_pr` run names the required check; (6) `T-A.10` sets `main` + `develop` protection; (7) merge the PR with a **merge commit — never squash** — so `master`'s 4 unique commits are reconciled rather than orphaned; (8) merge `main` back into `develop` locally and push `develop`; (9) verify `drift_detection.yml` on the default branch and the workflow **enabled** — its next cron is the first real run, recorded as **pending**, not as evidence. Tag `v0.5.0`.
  - Owner: software-engineer (merge/push/CI) · security-reviewer (push verdict) · coordinator (rename, PR, protection, merge)
  - Write set: `develop`, `main` via the PR, GitHub settings, the `v0.5.0` tag · Deps: T-E.8 (order is review → closure → archive → ship), T-A.10, T-A.11 · AC-4, AC-7, AC-8
  - Evidence: APPROVED security handoff covering the pushed delta; the merge-commit sha with two parents; `gh api …/contents/.github/workflows/drift_detection.yml?ref=main` → 200; `gh workflow view drift_detection` enabled; green CI run URLs; `git tag --list 'v0.5.0'`.

- [ ] **T-R.4** — **re-audit**: `project-auditor` re-scores against the ship gate. **Score ≥ 7 with no dimension < 5** — any dimension below 5 blocks the release.
  - Owner: project-auditor · Write set: `specs/audits/<new-audit-id>/**`
  - Deps: T-R.3 · SPEC §4 ship gate
  - Evidence: the audit report with its dimension table; residuals routed to the PM's intake report, never silently dropped.

---

## Finding → task index (makes the CLOSURE disposition sweep mechanical)

| Finding | Task(s) | Finding | Task(s) |
|---|---|---|---|
| DRIFT-01 | T-A.1, T-A.2, T-A.3, T-A.4, T-B.3a | DRIFT-17 | T-B.8 |
| DRIFT-02 | T-A.6 | DRIFT-18 | T-C.5, T-C.6 |
| DRIFT-03 | T-E.3 (re-verification) | DRIFT-19 | T-C.1, T-C.2, T-E.7 |
| DRIFT-04 | T-E.4, T-E.5 | DRIFT-20 | T-D.1, T-D.2, T-D.3 |
| DRIFT-05 | T-E.6, T-E.8 | DRIFT-21 | T-B.7 |
| DRIFT-06 | T-D.4 | DRIFT-22 | T-B.4, T-B.9, **T-B.12**, T-C.7 |
| DRIFT-07 | T-D.4, T-A.7, **T-B.14** | DRIFT-23 | T-E.5 (docs), T-E.7 (deferred) |
| DRIFT-08 | T-A.1, T-A.2, T-A.3b, T-B.3a | DRIFT-24 | T-B.10, T-B.11, T-B.14 |
| DRIFT-09 | T-A.4, T-A.5, T-C.3 | DRIFT-25 | T-C.3, T-C.4 |
| DRIFT-10 | T-A.10, T-A.11, T-R.3 | DRIFT-26 | T-A.7, T-B.6, T-C.4, T-D.5 |
| DRIFT-11 | T-A.9, T-D.7 | DRIFT-27 | T-B.7, T-C.4, T-E.5 |
| DRIFT-12 | T-D.3 | DRIFT-28 | T-D.6 |
| DRIFT-13 | T-B.2, T-B.3, T-B.13 | DRIFT-29 | T-D.5 |
| DRIFT-14 | T-A.7, T-A.8 | DRIFT-30 | T-E.3, T-E.6 |
| DRIFT-15 | T-A.7, T-A.8, T-B.5 | DRIFT-31 | T-E.1, T-E.2 |
| DRIFT-16 | T-B.1 | — | — |

New tasks from the 2026-08-23 architecture review, and the June lane ids they carry:
`T-A.3b` (SEC-H-02 negative proof), `T-B.3a` (ARCH-C1 residual — one applier per stack),
`T-B.14` (ARCH-H6 reproducibility, D15), `T-C.7` (ARCH-C2 hml lane), `T-D.7` (CI-M6).
`ARCH-L8` is dispositioned **already relocated at intake**, re-verified by `T-E.3`.

The 2026-06-11 audit's 82 lane ids route through SPEC §7.2's groups; every task above lists the lane ids it carries, and `T-E.6` re-asserts each one with evidence.

---

## Notes

- **No picked bugs.** The only live record in this context's ledger is the misfiled tooling bug (T-E.2, `rejected`) — nothing is fixed-in-release, nothing is silently dropped.
- Memory atoms are written in CLOSURE only (T-E.4, T-E.5) — never during implementation; stale memory found while implementing becomes a CLOSURE note.
- Live-mutating tasks (`T-A.3`, `T-A.4`, `T-A.5`, `T-A.10`, `T-A.11`, `T-B.1`, `T-B.3a`, `T-B.4`, `T-B.7`..`T-B.12`, `T-B.14`, `T-C.6`, `T-C.7`) are operator-gated and each carries a rollback row in PLAN §9. Evidence uses generic resource names — the repository is public.
