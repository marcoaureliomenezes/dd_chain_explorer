# TASKS — Release v0.7.0 — Market-data restart: batch capture runtime + medallion landing

> **Status:** Aprovado
> **Release ID:** v0.7.0
> **Owner:** product-engineer (authoring) → software-engineer / security-reviewer / qa-engineer / code-reviewer / **operator** (execution, per task) — approved under the operator standing order of 2026-09-13 after ratifying R1-R17
> **Depends on:** SPEC.md + PLAN.md v0.7.0 (`Aprovado`)
> **Lifecycle:** pre-staged — no task is reserved before v0.6.0 closes and v0.7.0 turns ACTIVE.
> **Marker contract:** `[ ]` OPEN → `[-]` IN PROGRESS → `[x]` DONE. Reserve with an isolated `chore(tasks): start <id>` commit **before** writing. One `[-]` per owner; WS-I and WS-X have disjoint write sets (one repo each) and may each hold one `[-]`. All tasks below are `[ ]`.

**Write-set law.** WS-I writes only inside `dd-chain-infrastructure` (+ its state keys and the live dev resources it declares); WS-X only inside the new `dd-chain-explorer` (+ this bundle's live Databricks `dev` resources); WS-O writes settings and live operator acts only. `specs/**` is written only in the authoritative tree of the moment (SPEC O-9). `In`/`Xn` = SPEC §2; `AC-n` = SPEC §4; `O-n` = SPEC §5; `Kn` = PLAN §2. **OPERATOR-ONLY** = holds a secret value, applies `prd/00_bootstrap`, dispatches a first live apply, or amends the constitution — agents author inputs and verify outcomes, never run it.

---

## WS-I — `dd-chain-infrastructure` (`feature/0.7.0`)

- [x] **T-I7.1** — Register bug `deploy-roles-lack-scheduler-grants-for-declared-schedule` (HIGH, `caused_by: none`, shape-1 commit) in the authoritative ledger; then add the namespace-coverage test (I1, PLAN §3.4) and commit it **RED** (O-2). — landed: bug registered; test with fix 31f372c
  - software-engineer · write set: `specs/bugs/BUGS.jsonl` (authoritative tree), `scripts/ci/tests/` · blocked by: none · delivers: the suite names every namespace `services/**` needs and the bootstrap lacks · AC-1

- [x] **T-I7.2** — Bootstrap delta (I2, PLAN §3.2) + `publish_oidc_vars.sh --target`: role, statements, PassRole services, locals, output, `capture_images` default; delete `s3:HeadObject`; extend the pinned tests, add publish-role minimality + images equality; output-name test covers 5 pairs. Namespace test GREEN. — landed 31f372c
  - software-engineer · write set: `services/prd/00_bootstrap/**`, `services/prd/06_lambda/lambda_contracts_ingestion.tf`, `scripts/ci/publish_oidc_vars.sh`, `scripts/ci/tests/**` · blocked by: T-I7.1 · delivers: plan = 1 role added, documents changed, 0 destroyed; one publisher for three repos · AC-1, AC-2

- [ ] **T-I7.3** — Security verdict on the bootstrap delta before any apply (O-3).
  - security-reviewer · write set: handoff only · blocked by: T-I7.2 · delivers: APPROVED handoff naming the sha, publish-role minimality, the one conditioned boundary PassRole, the retained deny · AC-2

- [x] **T-I7.4** — ECR ×3 + lifecycle + outputs in `prd/04_peripherals` (I3); `empty_s3_and_ecr.sh` → `empty_s3_buckets.sh` (3 callers); `AGENTS.md`/`README.md` capture sentence; root `VERSION` `0.7.0` (I9). Applied via the prd lane's informed gate (operator click). — landed d6de196 (+d241b95)
  - software-engineer · write set: `services/prd/04_peripherals/**`, `scripts/ci/empty_s3_buckets.sh`, `.github/workflows/**` (callers), `AGENTS.md`, `README.md`, `VERSION` · blocked by: T-O7.1 · delivers: three repositories capture CI can push to · AC-4, AC-10

- [x] **T-I7.5** — Dev raw landing in `dev/01_peripherals` (I4, PLAN §3.3): `module.s3_raw_data`, MFA-gated writer role + policy, `databricks_dev_s3_policy` widened, outputs; CI dev lane applies. — landed 0360b2a
  - software-engineer · write set: `services/dev/01_peripherals/**` · blocked by: T-O7.1 · delivers: a bucket the smoke can land in and Databricks can read · AC-5

- [x] **T-I7.6** — New stack `dev/03_capture` (I5, PLAN §3.3), `schedules_enabled = false`; `stack_map.json` `dev.capture` + `$comment` edge; tests: schedules default disabled, task-role prefix scope, schedule ↔ container name; runbook `docs/runbooks/capture-backfill.md`. — landed c798ffa
  - software-engineer · write set: `services/dev/03_capture/**`, `scripts/ci/stack_map.json`, `scripts/ci/tests/**`, `docs/runbooks/` · blocked by: T-I7.4, T-I7.5, T-O7.4(a) · delivers: seven disabled schedules, three runnable task definitions · AC-6

- [x] **T-I7.7** — UC stack relocated and completed (I6, O-5): `git mv services/databricks services/dev/04_unity_catalog`, docs updated, README §"Not in stack_map" deleted, external location + two singular `databricks_grant`, `var.databricks_dev_sp_application_id` (no default), `stack_map.json` `dev.unity_catalog`. — landed cddf2c0
  - software-engineer · write set: `services/dev/04_unity_catalog/**`, `scripts/ci/stack_map.json` · blocked by: v0.6.0 `T-I.12` (`No changes` after import), T-I7.5, T-O7.2 · delivers: a plan of exactly 3 adds; after T-O7.3 the SP reads the bucket and writes catalog `dev` · AC-7

- [x] **T-I7.8** — Map-driven dev lane (I7, PLAN §3.5): `deploy_env.sh dev` → `deploy_dev()`, one `dev-deploy` job, **delete `detect_changes.sh`**; `plan_on_pr.yml` +2 (`plan-dev-unity-catalog` with `environment: dev`), `drift_detection.yml` +2, `destroy_all_cloud_infra.yml` +2; dev-lane case in `test_deploy_apply_path.py`; fresh-clone `0/0/0` proof on six stacks. — landed d55d2d1 + d241b95 (142 tests)
  - software-engineer (lane) · qa-engineer (proof) · write set: `scripts/ci/deploy_env.sh`, `scripts/ci/tests/**`, `.github/workflows/**` · blocked by: T-I7.6, T-I7.7 · delivers: every dev stack planned, applied, drift-checked and destroyable from the map alone · AC-8, AC-9

## WS-X — `dd-chain-explorer` (`feature/0.7.0`)

- [x] **T-X7.1** — Bundle skeleton `apps/dabs/dlt_market_data/` (X1, PLAN §4.1): `databricks.yml` (dev real, prod declared), pipeline + PAUSED trigger job, a `pipeline.py` that validates with zero tables; `test_bundle_targets_contract.py` → 8; seam 3 in `docs/cross-repo-contract.md` (K7); `apps/dabs/README.md` 8 bundles + Ethereum parked; version axis `0.7.0` (X6 docs half). — landed 30f6fd5/f447c4d
  - software-engineer · write set: `apps/dabs/dlt_market_data/**`, `tests/dabs/test_bundle_targets_contract.py`, `docs/**`, `apps/dabs/README.md`, `VERSION`, `apps/dabs/*/VERSION`, `utils/pyproject.toml` + `__init__.py` · blocked by: none · delivers: an eighth bundle validating in both targets; the image seam stated once · AC-11, AC-12, AC-15

- [x] **T-X7.2** — Pure-Python parsers (X2, PLAN §4.2) + `tests/dabs/test_market_data_parsers.py` with small public-grade fixtures; no `pyspark` import. — landed 30f6fd5 (41 tests)
  - software-engineer · write set: `apps/dabs/dlt_market_data/src/market_data/parsers/**`, `tests/dabs/**` · blocked by: T-X7.1 · delivers: every raw format parses off-cluster, RED/GREEN per AC-11 · AC-11

- [x] **T-X7.3** — Bronze `b_market` (X3, PLAN §4.3): 11 `binaryFile` streaming tables + `raw_manifests`; derived columns; no decoding. — landed ccb436d
  - software-engineer · write set: `apps/dabs/dlt_market_data/src/market_data/pipeline.py`, `resources/dlt/**` · blocked by: T-X7.1 · delivers: `bundle validate` green with 12 bronze tables declared · AC-14 (bronze half)

- [x] **T-X7.4** — Silver `s_market` (X4, PLAN §4.3): 8 streaming tables calling the parsers; expectations (parse success, manifest sha, `versao`); max-`VERSAO` dedupe; `ORDEM_EXERC = ÚLTIMO`; FRE/IPE untouched. — landed ccb436d
  - software-engineer · write set: `apps/dabs/dlt_market_data/src/**` · blocked by: T-X7.2, T-X7.3 · delivers: `test_dlt_expectations_contract` green (silver-only); validate green · AC-11, AC-14

- [x] **T-X7.5** — Gold `g_market` first cut (X5, PLAN §4.3): `company_daily_price`, `ibov_constituents_daily`, `company_fundamentals_snapshot`; NULL-never-fabricate; D&A mapping recorded; Makefile `dabs_run_dlt_market_data`; `make check` green on a fresh checkout without `pyspark` (X6). — landed ccb436d/f447c4d
  - software-engineer · write set: `apps/dabs/dlt_market_data/src/**`, `Makefile`, `tests/**` · blocked by: T-X7.4 · delivers: the three MVs declared and validated; ratio formulas readable in source · AC-11, AC-14

- [ ] **T-X7.6** — Deploy **this bundle only** to `dev` and run one update (X7, O-6, O-10): `databricks bundle deploy -t dev`; `make dabs_run_dlt_market_data`; verify 12/8/3 objects and `bcb/sgs` rows with matching sha; trigger job PAUSED; no Ethereum resource deployed.
  - software-engineer · write set: live Databricks `dev` (this bundle) · blocked by: T-X7.5, T-O7.3, T-O7.4 · delivers: the first market-data rows in `dev.s_market` · AC-13, AC-14

- [ ] **T-X7.7** — Release gates: alpha-1 qa review (AC-1..AC-15 evidence table); rc-1 trio (`qa-engineer`, `code-reviewer`, `security-reviewer`) APPROVED in **both** repos; ship — memory update (SPEC §9) → CLOSURE → disposition sweep (`market-data-medallion-restart`, the bug) → `feature/0.7.0 → develop` PRs in both repos, CI watched to green → promote-or-continue asked.
  - reviewers (trio) · product-engineer (memory, CLOSURE) · coordinator (PRs) · write set: `specs/memory/**`, `specs/releases/v0.7.0/**` in the authoritative tree; handoffs · blocked by: T-I7.8, T-X7.6, T-O7.5, v0.6.0 candidate merge (O-1) · delivers: the release closed and merged · AC-18

## WS-O — **OPERATOR-ONLY**

- [ ] **T-O7.1** — Apply `services/prd/00_bootstrap` with operator credentials (MFA; the sole ADR-6 exception), then run `publish_oidc_vars.sh --target capture` → `AWS_CAPTURE_PUBLISH_ROLE` in `dd-chain-capture` (envs `dev`, `production`).
  - **operator** · write set: live IAM, `prd/bootstrap` key, `dd-chain-capture` variables · blocked by: T-I7.3 · delivers: capture CI can assume its role; deploy roles hold the runtime grants · AC-2, AC-3

- [ ] **T-O7.2** — Infra repo `dev` GitHub environment: secrets `DATABRICKS_HOST` / `DATABRICKS_CLIENT_ID` / `DATABRICKS_CLIENT_SECRET` (Free-Edition SP), variable `TF_VAR_databricks_dev_sp_application_id`; agents reference names only (O-8).
  - **operator** · write set: GitHub environment settings · blocked by: none · delivers: `plan-dev-unity-catalog` can authenticate · AC-7

- [ ] **T-O7.3** — Dispatch the first dev-lane apply of `unity_catalog` (K3, K5): confirm exactly 3 adds, approve, verify `grants get-effective` and `external-locations validate`.
  - **operator** (dispatch) · software-engineer (evidence) · write set: live UC objects, the UC state key · blocked by: T-I7.7, T-I7.8 · delivers: the SP reads the raw bucket and writes catalog `dev` · AC-7

- [ ] **T-O7.4** — First real landing (K2, K6): (a) push `dd-chain-capture` `develop` → `publish-images.yml` green, 3 images `:dev` in ECR; (b) `make batch-smoke-real` from the operator machine assuming `dm-chain-explorer-capture-dev-writer` with MFA; (c) one `aws ecs run-task` of `bcb-sgs macro_series` per `docs/runbooks/capture-backfill.md`. Schedules remain `DISABLED`.
  - **operator** · write set: ECR images, `raw/bcb/sgs/…` objects, one Fargate task run · blocked by: (a) T-O7.1, T-I7.4; (b) T-I7.5; (c) T-I7.6 · delivers: real partitions with valid manifests, one from Fargate · AC-16

- [ ] **T-O7.5** — Constitution amendment, **explicit operator confirmation before writing**: §1 third seam (the image seam; capture runtime hosted in the infra repo); §6 UC stack path; §7 batch raw layout + `Market data` medallion row (`b_market` / `s_market` / `g_market`); §10 classification row (CVM/B3/BCB public regulatory and market data; FRE `posicao_acionaria` reserved). `dadaia specs doctor` 0 errors.
  - product-engineer (author) · **operator** (confirmation) · write set: `specs/constitution.md` (authoritative tree) · blocked by: T-X7.1 · delivers: the constitution describes three seams and the new data source · AC-17
