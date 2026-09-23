# TASKS — Release v0.7.0 — Market-data restart: batch capture runtime + batch medallion; us-east-1 serverless platform

> **Status:** Aprovado
> **Release ID:** v0.7.0
> **Owner:** product-engineer (R1-R17) · software-engineer (amendments, ADR 0019) → implementers / code-reviewer (six lenses) / **operator**
> **Depends on:** SPEC.md (53d9a7f) + PLAN.md v0.7.0 (`Aprovado`)
> **Amended:** 2026-09-23 (2) — R27-R36: removed T-O7.7, B1, B2, seed S4-S7; T-X7.12(a) dropped; T-I7.15-T-I7.21, T-V7.2, T-V7.3 added. Order: A code/CI → B sa-east-1 teardown → C us-east-1 bring-up → D proofs.
> **Markers:** `[ ]`→`[-]` (isolated `chore(tasks): start <id>`)→`[x]`; one `[-]` per repo. Repos: **infra** `dd-chain-infrastructure`, **explorer** the new `dd-chain-explorer`, **capture** `dd-chain-capture`. **OP** = operator act. §n = PLAN §9.n.

## Done (R1-R17)

- [x] T-I7.1..T-I7.8 — 31f372c, a26ce6d, 55e1853, d6de196, d241b95, 0360b2a, c798ffa, cddf2c0, d55d2d1 (T-I7.5/7.6/7.7 content is rebuilt for us-east-1 by T-I7.16/T-I7.18)
- [x] T-X7.2 parsers + 41 tests — 30f6fd5 (moved unchanged by T-X7.9)
- [x] T-X7.1, T-X7.3..T-X7.6 — **SUPERSEDED (R19) → T-X7.9/T-X7.12**, not evidence
- [x] T-O7.1 bootstrap apply + capture var — OP, 09-21
- [x] T-O7.2 → `*/06_github` (T-I7.17) · T-O7.3 → UC stacks (T-I7.18) + lanes (T-I7.9) · T-O7.4 (a) done run 35546515532, (b,c) → `capture_run` (T-I7.14) — **SUPERSEDED**
- [x] T-O7.7 Free Edition restore — **REMOVED (R27)**

## Phase A — code, tests, CI (nothing live)

- [ ] **T-I7.9** Plan-as-detector lanes (§9.6): push `develop` + dispatch; every map stack `plan -detailed-exitcode`, apply on 2; `account` group in the prd lane behind `production`; delete `changed_files_since_base`, `FORCE`, `force_apply`, `destroy_ack`, the `raw/` object-count drift check; tests rewritten.
  - infra · `scripts/ci/**`, `.github/workflows/**` · blocked: — · AC-8, AC-24
- [ ] **T-I7.10** Bootstrap delta 2 (§9.5, §9.6): teardown grants (sa-east-1 bucket delete, `capture/ecr` whole: ECR, KMS schedule-deletion/alias, Roles Anywhere); us-east-1 grants (ECS RunTask/Describe for `capture_run`, `raw/*/_manifest.json` read, UC IAM roles `dm-chain-explorer-*-uc` incl. PutRolePolicy); lock-table grants kept until T-I7.16. Tests extended. **Security verdict before any apply.**
  - infra · `services/prd/00_bootstrap/**`, `scripts/ci/tests/**` · blocked: — · AC-2, AC-23, AC-26
- [ ] **T-I7.12** PR-α destroy commit (§9.5.1): dev/01, dev/02, dev/03, prd/04, prd/06 → backend+provider; `prevent_destroy` lifted; dev/04 (Free Edition) out of the map; `retire.sh` + `retired_objects.json` (empty buckets by exact name; whole destroy of `capture/ecr` via `services/retired/capture_ecr/`); stub tests (idempotent, absent = pass).
  - infra · `services/**`, `scripts/ci/**` · blocked: T-I7.9, T-I7.10 · AC-23, AC-26
- [ ] **T-I7.16** PR-β region move (§9.3, §9.5.3): backends → `dm-chain-explorer-tfstate-use1`, `use_lockfile`, no region/`dynamodb_table`; `var.aws_region` (no default) + workflow `AWS_REGION` single source; names `dm-chain-explorer-{dev,prd}-{raw,lakehouse}`; SSE-S3, no KMS; dev/01, dev/03 (default VPC), prd/04 (ECR + prd buckets) rebuilt; `prd/01_tf_state` rewritten; deletes: dev/02, prd/06, `services/retired/`, `retire.sh`, `resolve_*`, modules `dynamodb`/`lambda`, `tf_state_lock_check.sh`, lock/Lambda/DynamoDB/artifacts/KMS grants, `--target explorer`; region-pin + grep tests.
  - infra · `services/**`, `scripts/**`, `.github/workflows/**` · blocked: T-I7.12 (stacked on it) · AC-9, AC-23, AC-25, AC-27
- [ ] **T-I7.19** Capture region literal: `publish-images.yml` `AWS_REGION: us-east-1` + `tests/ci/test_publish_images_contract.py`.
  - capture · those 2 files · blocked: — · AC-25
- [ ] **T-I7.15** Account stack `services/account/databricks` (§9.3): account provider OAuth M2M; metastore us-east-1 (optional `import` id var); SPs `dm-chain-explorer-{dev,prd}-deploy` + secrets; budget alert; map entry; `validate` + contract test.
  - infra · `services/account/**`, `scripts/ci/stack_map.json`, tests · blocked: T-I7.16 · AC-28, AC-30
- [ ] **T-I7.18** Per-env units (§9.3-9.4): `services/{dev,prd}/05_workspace` (SERVERLESS workspace, metastore assignment, permission assignments, dev warehouse 2X-Small/1 min/1 cluster; outputs host, workspace id, warehouse id) + `services/{dev,prd}/04_unity_catalog` rewritten (UC role, credential, file-event locations, ISOLATED catalog `force_destroy=false`, binding, schemas b/s/g_market + `ops`, volume, grants).
  - infra · `services/{dev,prd}/0{4,5}_*/**`, map, tests · blocked: T-I7.15 · AC-7, AC-28, AC-29
- [ ] **T-I7.17** GitHub stacks `services/{dev,prd}/06_github` (§9.6): App auth; env secrets/vars; `production` imported; default branch `develop` (prd).
  - infra · `services/{dev,prd}/06_github/**`, map, tests · blocked: T-I7.18 · AC-28
- [ ] **T-I7.14** Chain, infra half (§9.6 steps 2, 4): `signal-explorer`; `capture_run.yml`; App tokens `CI_APP_*` scoped per job; actionlint + zizmor clean.
  - infra · `.github/workflows/**`, `scripts/ci/**` · blocked: T-I7.9 · AC-22, AC-24
- [ ] **T-I7.20** `rebuild_drill.yml` (§9.6): snapshot → destroy `dev/05_workspace` → dev lane → explorer signal → compare → `capture_run`; contract test (dev only, never a prd path).
  - infra · `.github/workflows/**`, `scripts/ci/**` · blocked: T-I7.14, T-I7.18 · AC-29
- [ ] **T-I7.11** Trust seed S1-S3 (§9.7): `scripts/seed/trust_seed.sh` (`--step`), `docs/runbooks/trust-seed.md` replaces `00-bootstrap-apply.md`; stub tests (run 2 = 0 mutating calls, no secret in argv/output); shellcheck.
  - infra · `scripts/seed/**`, `docs/runbooks/**` · blocked: T-I7.10, T-I7.16 · AC-24, AC-28
- [ ] **T-X7.8** Explorer chain CI: `deploy-dev` on push `develop` + `infra-dev-applied`, bundle filter deleted, host from environment; `validate-prod`; `signal-infra`.
  - explorer · `.github/workflows/ci.yml`, `tests/**` · blocked: — · AC-20, AC-21
- [ ] **T-X7.9** Bundle `job_market_data` (§9.2): parsers `git mv`; tasks; job + file-arrival YAML; tables by `LOCATION`; no schemas resource; `artifact_path` volume; `performance_target: STANDARD`; helper + contract + no-`dlt` tests; `bundle validate -t dev/-t prod` in CI.
  - explorer · `apps/dabs/job_market_data/**`, `tests/**`, `Makefile` · blocked: T-X7.8 (merge order) · AC-19, AC-20
- [ ] **T-X7.10** Delete (X8): the 8 bundle dirs, `apps/lambda/`, `utils/`, `publish-artifacts.yml`, dashboard tooling, tests; contract = exactly 1 bundle; `docs/cross-repo-contract.md`, README, versions `0.7.0`; grep AC-23 = 0.
  - explorer · `apps/**`, `utils/**`, `.github/**`, `docs/**`, `tests/**` · blocked: T-X7.9 · AC-15, AC-19, AC-23
- [ ] **T-X7.11** `e2e-verify` on `capture-landed` (§9.6 step 6).
  - explorer · `.github/workflows/ci.yml`, `scripts/**` · blocked: T-X7.9 · AC-22

## Phase B — sa-east-1 teardown (old backend)

- [ ] **T-O7.8** **OP** Apply the T-I7.10 delta after its verdict, at the PR-α head (old backend), per the still-present `00-bootstrap-apply.md`.
  - live IAM · blocked: T-I7.10 verdict, T-I7.12 · AC-2
- [ ] **T-I7.13** Merge PR-α → dev apply + `production`-approved prd apply destroy every sa-east-1 stack; `retire` destroys `capture/ecr` whole; cite run ids; AC-26 probes (except the state bucket).
  - infra · live · blocked: T-I7.12, T-O7.8, O-1 · AC-23, AC-26

## Phase C — us-east-1 bring-up

- [ ] **T-O7.6** **OP** Seed S1-S3 (real terminal): new state bucket, bootstrap migrate + apply, OIDC vars, account BPA, old state bucket + lock table deleted; App + `CI_APP_*` + `production`; account SP secret; metastore check. Confirms name probes.
  - live AWS/GitHub/Databricks · blocked: T-I7.13, T-I7.11 verdict · AC-3, AC-24, AC-26, AC-28
- [ ] **T-I7.21** Merge PR-β (T-I7.14..T-I7.20 on top) → one `develop` push applies account → buckets/ECR → workspaces → UC → GitHub → capture (approvals only); capture push `develop` publishes 3 images to us-east-1 ECR; probes AC-4..7, 25, 27, 28.
  - infra + capture · live · blocked: T-O7.6, T-I7.19 · AC-4..7, AC-25, AC-27, AC-28
- [ ] **T-X7.12** Explorer live: `bundle deploy -t dev` via chain; `bundle summary`, `jobs get` (3 tasks, serverless, `file_arrival` `UNPAUSED`), SP `.bundle/` = this bundle only.
  - explorer · live dev · blocked: T-I7.21, T-X7.8..T-X7.11 · AC-20, AC-21

## Phase D — proofs and closure

- [ ] **T-V7.1** Chain proof: one `develop` merge → infra → explorer → capture → file arrival → `e2e-verify` green; events ∈ push/workflow_run/repository_dispatch/file arrival; second fire = no count change; drift 0; seed run 2 = no changes, no secret echoed; M-ledger table.
  - software-engineer (evidence) · blocked: T-X7.12 · AC-22, AC-24
- [ ] **T-V7.2** Rebuild drill: pre-drill binding probe (§9.9 row 1); dispatch `rebuild_drill.yml`; equal counts, lakehouse intact, next arrival fires.
  - software-engineer (evidence) · OP dispatch · blocked: T-V7.1, T-I7.20 · AC-29
- [ ] **T-V7.3** Cost evidence: list-price table sa-east-1 vs us-east-1 per line item; `system.billing.usage` × list price, 7 days after T-I7.21; measured %.
  - software-engineer · blocked: T-I7.21 + 7 days · AC-30
- [ ] **T-O7.5** **OP** Constitution amendment, confirmed before writing (AC-17): §1 image seam in, lambda seam out; §2 DynamoDB out + serverless DEV/PRD clause (Free Edition, hml out); §6 UC path; §7 batch raw layout + `Market data` row, Ethereum + `@dlt` out; §10 row.
  - product-engineer · `specs/constitution.md` · blocked: T-X7.9 · AC-17
- [ ] **T-X7.7** Release gates: AC table (AC-1..10, 15, 17..30) + M1..M15 map (§9.8); reviewer APPROVED per repo; memory → CLOSURE → sweep → `feature/0.7.0 → develop` PRs, CI green → promote-or-continue.
  - code-reviewer · product-engineer · coordinator · blocked: T-V7.1..T-V7.3, T-O7.5, O-1 · AC-18
