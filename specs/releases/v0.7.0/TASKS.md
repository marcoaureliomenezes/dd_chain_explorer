# TASKS — Release v0.7.0 — Market-data restart: batch capture runtime + batch medallion; Ethereum lane retired

> **Status:** Aprovado
> **Release ID:** v0.7.0
> **Owner:** product-engineer (R1-R17 authoring) · software-engineer (2026-09-23 amendment, ADR 0019) → implementers / code-reviewer (six lenses) / **operator**
> **Depends on:** SPEC.md + PLAN.md v0.7.0 (`Aprovado`)
> **Amended:** 2026-09-23 — R18-R26: T-X7.1/3/4/5/6 superseded (DLT → batch job); T-O7.2-7.4 folded into the seed and the chain; new tasks below, ordered so code, tests, CI and AWS teardown come before any Databricks-live step (PLAN §9).
> **Markers:** `[ ]` → `[-]` (isolated `chore(tasks): start <id>`) → `[x]`. One `[-]` per repo. `In`/`Xn` SPEC §2 · `AC-n` §4 · `O-n` §5 · `§9.n` PLAN. **Blockers:** **B1** Databricks org inactive (no compute; jobs create 403) — operator account act; **B2** SP lacks metastore `CREATE_EXTERNAL_LOCATION` — seed S6. **PR-α/β** = the two ordered `develop` merges of a teardown (O-10).

## Done (R1-R17)

- [x] **T-I7.1** bug + RED namespace test (AC-1) — 31f372c
- [x] **T-I7.2** bootstrap delta + publisher (AC-1, AC-2) — 31f372c
- [x] **T-I7.3** security verdict on the delta — a26ce6d, 55e1853
- [x] **T-I7.4** ECR ×3 in `prd/04` (AC-4, AC-10) — d6de196, d241b95
- [x] **T-I7.5** dev raw landing (AC-5) — 0360b2a
- [x] **T-I7.6** `dev/03_capture`, 7 schedules `DISABLED` (AC-6) — c798ffa
- [x] **T-I7.7** UC stack relocated + completed (AC-7) — cddf2c0; infra #8/#9
- [x] **T-I7.8** map-driven dev lane (AC-8, AC-9) — d55d2d1, d241b95
- [x] **T-X7.1** DLT bundle skeleton — **SUPERSEDED (R19) → T-X7.9**; closed by supersession, not evidence
- [x] **T-X7.2** pure parsers + 41 tests — 30f6fd5; **kept**, moved unchanged by T-X7.9
- [x] **T-X7.3** DLT bronze — **SUPERSEDED (R19) → T-X7.9**
- [x] **T-X7.4** DLT silver — **SUPERSEDED (R19) → T-X7.9**
- [x] **T-X7.5** DLT gold — **SUPERSEDED (R19) → T-X7.9**
- [x] **T-X7.6** deploy DLT + one update — **SUPERSEDED (R19) → T-X7.12**; never passed (09-21 org refusal = B1); closed by supersession, not evidence
- [x] **T-O7.1** bootstrap apply + capture var — operator, 09-21 (M1, M3; AC-2, AC-3)

## Phase A — code, tests, CI (no Databricks org needed)

- [ ] **T-I7.9** Plan-as-detector lanes (M11, §9.4): `deploy_cloud_infra` on `push: develop` + dispatch; every map stack planned `-detailed-exitcode`, applied on exit 2; `prd-apply` behind `production` only when a prd plan changes; delete `changed_files_since_base`, `FORCE`, `force_apply`, `destroy_ack`; `test_deploy_apply_path.py` rewritten; drift counts `raw/` objects, fails at 8,000.
  - infra · `scripts/ci/**`, `.github/workflows/**` · blocked by: none · AC-8, AC-24
- [ ] **T-I7.10** Bootstrap delta 2 (§9.3-9.4): dev deploy role `ecs:RunTask/DescribeTasks` on capture task defs + cluster, `s3:GetObject` on `raw/*/_manifest.json`; exact-ARN retire grant for `dd-chain-capture-{stream,connect}` (policy + boundary, temporary); tests extended. **Security-lens verdict before any apply.**
  - infra · `services/prd/00_bootstrap/**`, `scripts/ci/tests/**` · blocked by: none · AC-2, AC-23
- [ ] **T-I7.11** Trust seed S1-S7 (§9.5): `scripts/seed/trust_seed.sh`, `docs/runbooks/trust-seed.md` (replaces `00-bootstrap-apply.md`); stub-binary tests: run 2 = zero mutating calls, no secret in argv/output; shellcheck.
  - infra · `scripts/seed/**`, `docs/runbooks/**` · blocked by: T-I7.10 · AC-24
- [ ] **T-I7.12** Teardown destroy commit, infra PR-α (§9.3 step 1): empty `dev/02_lambda`, `prd/06_lambda` to backend+provider; drop modules `s3_ingestion`/`dynamodb` (dev/01), `s3_artifacts`/`dynamodb` (prd/04); narrow `databricks_dev_s3_policy`; `retire.sh` + `retired_objects.json` (empty the two buckets; targeted destroy of ECR stream/connect in state `capture/ecr` via `services/retired/capture_ecr/`, fallback delete + `state rm`); tests (idempotent retire with stubs).
  - infra · `services/{dev,prd,retired}/**`, `scripts/ci/**` · blocked by: T-I7.9, T-I7.10 · AC-23
- [ ] **T-I7.14** Chain, infra half (§9.4 steps 2, 4): `signal-explorer` (App token → `infra-dev-applied`); `capture_run.yml` on `explorer-dev-deployed`: one Fargate task per image, wait, manifest check, `capture-landed`; actionlint + zizmor clean.
  - infra · `.github/workflows/**`, `scripts/ci/**` · blocked by: T-I7.9, T-I7.10 · AC-22, AC-24
- [ ] **T-X7.8** Retire lane, explorer PR-α (§9.3 step 3): `apps/dabs/RETIRED` (8 bundles); `ci` `deploy-dev` on `push: develop` + `infra-dev-applied`, bundle filter deleted; retire step (`bundle destroy -t dev`, then location `dm-dev-ingestion` + 7 schemas, idempotent) before deploy; `signal-infra`; bundle contract admits RETIRED dirs.
  - explorer · `.github/workflows/ci.yml`, `apps/dabs/RETIRED`, `tests/**` · blocked by: none · AC-21, AC-23
- [ ] **T-X7.9** Bundle `job_market_data` (X1-X7, §9.2): `git mv` parsers byte-identical; `bronze.py`/`silver.py`/`gold.py`/`_spark.py`; job + trigger + schemas YAML; `raw_manifests` bookkeeping; key/rejection helpers unit-tested; job contract + no-`dlt` tests; Makefile; `bundle validate -t dev/-t prod` in CI.
  - explorer · `apps/dabs/job_market_data/**`, `tests/**`, `Makefile` · blocked by: T-X7.8 (merge order only) · AC-19, AC-20
- [ ] **T-X7.10** Teardown delete, explorer PR-β (§9.3 step 4): the 8 bundle dirs, `apps/lambda/`, `utils/`, `publish-artifacts.yml`, dashboard tooling, their tests, `RETIRED` + retire step; contract = exactly 1 bundle; `docs/cross-repo-contract.md` (seam 3 once, lambda seam out), README, versions `0.7.0`; grep AC-23 = 0.
  - explorer · `apps/**`, `utils/**`, `.github/**`, `docs/**`, `tests/**` · blocked by: T-X7.9; merge after T-X7.12(a) run id · AC-15, AC-19, AC-23
- [ ] **T-X7.11** `e2e-verify` on `capture-landed` (§9.4 step 6): waits for the `FILE_ARRIVAL` run, reads task values, fails on 0 gold rows or sha rejections.
  - explorer · `.github/workflows/ci.yml`, `scripts/**` · blocked by: T-X7.9 · AC-22

## Phase B — live AWS and GitHub (no Databricks compute needed)

- [ ] **T-O7.6** Run the trust seed (S1-S7) after the T-I7.10 verdict; confirm the App install and the default branch `develop`. Clears B2.
  - **operator** · live IAM, GitHub settings, UC grants · blocked by: T-I7.10 verdict, T-I7.11 · AC-3, AC-7, AC-24
- [ ] **T-I7.13** Infra teardown live + delete (§9.3 steps 1-2): merge PR-α → dev apply + `production`-approved prd apply destroy the Ethereum/lambda-seam AWS objects (cite run ids); then PR-β deletes both stacks, map entries, `resolve_*`, `retire.sh`, `services/retired/`, `gha_artifacts_publish` + Lambda/DynamoDB/artifacts/retire statements, `--target explorer`.
  - infra · the T-I7.12 write set + `services/prd/00_bootstrap/**` · blocked by: T-I7.12, T-O7.6, O-1 · AC-9, AC-23

## Phase C — Databricks-live (last)

- [ ] **T-O7.7** Restore the Databricks Free Edition org to active with compute (B1); record in the M-ledger as an account act.
  - **operator** · blocked by: none · unblocks T-X7.12, T-V7.1
- [ ] **T-X7.12** Explorer live: (a) PR-α merged → retire step destroys the 8 bundles + stateless UC objects (run id; 0 pipelines); (b) PR-β merged → `bundle deploy -t dev` of `job_market_data`; `bundle summary`, `jobs get` (3 tasks, serverless, `file_arrival` `UNPAUSED`), SP `.bundle/` holds this bundle only.
  - explorer · live Databricks `dev` · blocked by: (a) T-X7.8, (b) T-X7.9, T-X7.10; both T-O7.6, T-O7.7, O-1 · AC-20, AC-21, AC-23
- [ ] **T-V7.1** Chain proof: one `develop` merge → infra → explorer → capture run → file-arrival run → `e2e-verify` green; every event ∈ push/workflow_run/repository_dispatch/file arrival; second fire = no count change; drift on `develop` = 0; seed re-run after T-I7.13 removes the retired grants, the next run = no changes, no secret echoed; M-ledger table drafted.
  - software-engineer (evidence) · blocked by: T-I7.13, T-I7.14, T-X7.11, T-X7.12 · AC-22, AC-24

## Superseded operator tasks

- [x] **T-O7.2** hand secrets — **SUPERSEDED → seed S5 (T-O7.6)**
- [x] **T-O7.3** hand first UC apply — **SUPERSEDED → push-triggered lane (T-I7.9) + seed S6**
- [x] **T-O7.4** first landing — (a) DONE 09-21, run 35546515532; (b, c) **SUPERSEDED → `capture_run` (T-I7.14, M14)**

## Governance and closure

- [ ] **T-O7.5** Constitution amendment, operator-confirmed before writing (AC-17): §1 image seam in, lambda seam out; §2 DynamoDB clause out; §6 UC path; §7 batch raw layout + `Market data` row in, Ethereum row + `@dlt` rule out; §10 classification row.
  - product-engineer · **operator** · `specs/constitution.md` · blocked by: T-X7.9
- [ ] **T-X7.7** Release gates: AC evidence table (AC-1..10, 15, 17..24) + M1..M15 → replacement table (PLAN §9.6); reviewer APPROVED per repo (six lenses); memory (SPEC §9) → CLOSURE → sweep (4 consumed entries, 5 `REJECTED · obsolete-by-R21`, the bug) → `feature/0.7.0 → develop` PRs per repo, CI watched green → promote-or-continue.
  - code-reviewer · product-engineer · coordinator · blocked by: T-V7.1, T-O7.5, v0.6.0 merge (O-1) · AC-18
