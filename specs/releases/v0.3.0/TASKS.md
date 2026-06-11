# TASKS: v0.3.0

**Status:** Aprovado
**Release:** v0.3.0
**Phase:** TASKS
**Branch:** feature/v0.3.0
**Operator waiver (2026-06-11):** plugin-scope waived for v0.3.0 — devops-engineer plugin is a stub and `dadaia plugin install` does not exist (workspace bug on file); software-engineer implements the devops-owned tasks under this approved SPEC. Revisit when the plugin system ships.

Macro-order: WS-A → WS-B1 → WS-B2/B3 → sanitization. Sanitization (T-R6-S*) may run in
parallel with everything — disjoint write sets (`specs/**` only). T-R6-B3 is
hard-sequenced after ALL WS-A tasks (same 7 workflow files). CI-YAML tasks require the
`devops` plugin (`dadaia plugin install devops`) or explicit operator authorization for
software-engineer scope.

---

## WS-A — CI safety

- [x] T-R6-A1 — **Per-stack apply signal in deploy scripts (CI-C2)** | Owner: devops-engineer | Priority: CRITICAL
  Write-set: `scripts/ci/deploy_env.sh`, `scripts/ci/tf_plan.sh`
  Acceptance:
    (a) No `grep`/`tail -1` read of `$GITHUB_OUTPUT` anywhere in `deploy_env.sh`
        (today line 77); apply decision per stack derives from `tf_plan.sh`'s real
        signal (exit code or per-stack temp file).
    (b) The `/dev/null` fallback (`deploy_env.sh:61`) no longer silently skips applies —
        a missing plan signal fails the run loudly. Verification (F-QA-4): run
        `deploy_env.sh` with the per-stack signal absent → exit ≠ 0 + explicit
        `::error::` (PLAN validation table row "Missing-signal fails loudly").
    (c) `tf_state_lock_check.sh || true` (`deploy_env.sh:54`) fails loudly instead.
        Verification (F-QA-4): stub `tf_state_lock_check.sh` to `exit 1` → run fails.
  Parallelism: Wave 1; blocks T-R6-A2.

- [x] T-R6-A2 — **Dependency-chain-aware informed gate for PRD/HML deploys (CI-C1, ADR-R6-4/R6-5)** | Owner: devops-engineer | Priority: CRITICAL
  Write-set: `.github/workflows/deploy_cloud_infra.yml`, `scripts/ci/` (helpers incl.
  `plan_gate_check.sh` + its fixture unit test, single-source stack map file)
  Precondition: T-R6-A1 done.
  Acceptance:
    (a) Pre-gate plan phase: every stack **plannable against current state** uploads its
        `tfplan` binary + full `plan.txt` as artifacts and a consolidated
        add/change/destroy summary per stack is written to the run summary BEFORE the
        environment gate; non-plannable stacks (e.g. prd 05b on bootstrap, upstream
        output absent) appear in the summary as "deferred to post-upstream stage" —
        never silently skipped.
    (b) Post-gate apply (dependency order, per the single-source stack map): a stack
        whose upstreams applied NO in-run changes applies its saved approved plan
        binary only; a stack downstream of an in-run upstream apply (or without a
        pre-gate plan) is RE-PLANNED — apply proceeds iff the re-plan matches the
        approved summary (add/change/destroy counts + resource-address set); otherwise
        the run FAILS CLOSED (exit ≠ 0, no further downstream applies) with the
        approved-vs-re-plan diff published as a run artifact + job summary; re-approval
        = the operator re-triggers the deploy and the re-run (full re-plan) passes the
        NORMAL informed environment gate presenting the new plan (ADR-R6-5 pinned
        mechanism — no second gated job, no new environment). prd 05a→05b
        (`deploy_env.sh:147-184`) is the canonical covered case.
    (c) Destroy acknowledgment (F-QA-2): destroy-detection + ack check implemented in
        `scripts/ci/plan_gate_check.sh`; unit test fed fixture plans asserts exit ≠ 0
        with destroys and no ack, exit 0 with ack, exit 0 for no-destroy plans.
    (d) DEV per-stack auto flow unchanged.
    (e) Lint gate (F-QA-1): `actionlint` exits 0 on every edited workflow.
    (f) Graduation + rollback (F-QA-1/QA-6): one full green hml run through the new
        flow (run URL + artifact list + run-summary evidence showing per-stack counts
        before the gate) is recorded BEFORE the first prd run; rollback path stated in
        the task handoff: `git revert` of the workflow commit restores the previous
        flow (saved-plan artifacts are additive).
    (g) Single-source constraint (F-ARCH-4): the gate's stack list + dependency
        declarations live in the same single data-driven map file consumed by
        `plan_on_pr.yml` (T-R6-A8) — no stack name hardcoded in more than one place.
  Parallelism: Wave 2; same-file edits coordinated with A4/A5/A6 (sequential commits).

- [ ] T-R6-A3 — **hml GitHub environment required_reviewers (OP-R6-3)** | Owner: operator (verification: devops-engineer) | Priority: HIGH
  Write-set: none (GitHub settings; evidence only)
  Acceptance: `gh api repos/:owner/:repo/environments` shows required_reviewers on
  `hml`; evidence captured in the task's handoff. `dev` stays ungated.
  Parallelism: any time; required before rc ship.

- [-] T-R6-A4 — **Concurrency groups on destroy-all + auto-bump + drift (CI-C3, CI-M9)** | Owner: devops-engineer | Priority: CRITICAL
  Write-set: `.github/workflows/destroy_all_cloud_infra.yml`, `.github/workflows/auto-bump-version.yml`, `.github/workflows/drift_detection.yml`
  Acceptance: each file has a workflow-level `concurrency:` group with
  `cancel-in-progress: false`; destroy-all's `confirm` input check verified to block
  before any AWS step runs.
  Parallelism: Wave 2, parallel-safe (disjoint files vs A2).

- [ ] T-R6-A5 — **Error-masking purge (CI-H8, CI-M1, CI-M2)** | Owner: devops-engineer | Priority: HIGH
  Write-set: `.github/workflows/deploy_all_dm_applications.yml`, `.github/workflows/deploy_cloud_infra.yml`, `scripts/ci/tf_plan.sh`
  Acceptance:
    (a) `deploy_all_dm_applications.yml:949-954`: plan exit not masked by `tee`
        (pipefail or no pipe); apply gated on plan-has-changes; `terraform_wrapper: false`
        parity with other jobs.
    (b) `|| true` removed from verify/test/lock-check steps (kept only on genuine
        idempotent teardown; each kept instance justified by an inline comment).
        Verification (F-QA-4): `grep -rn '|| true' .github/workflows/ scripts/ci/` —
        every remaining instance carries the justification comment (PLAN validation
        table row "Error-masking inventory").
    (c) Plan summaries no longer rely on `tail -N` alone — full `plan.txt` artifact +
        `grep '^(Plan:|No changes)'` summary line.
  Parallelism: Wave 2; sequential with A2 in the shared file.

- [ ] T-R6-A6 — **timeout-minutes on every job, all 7 workflows (CI-H4)** | Owner: devops-engineer | Priority: HIGH
  Write-set: all 7 files under `.github/workflows/`
  Acceptance: every `jobs.<id>` has `timeout-minutes` (15 plan/lint; 30–45
  apply/stabilize); `grep -c timeout-minutes` ≥ job count per file.
  Parallelism: Wave 2; trivially mergeable, commit after A2/A5 in shared files.

- [-] T-R6-A7 — **terraform fmt fix + fmt/validate CI gate (CI-H1)** | Owner: devops-engineer | Priority: HIGH
  Write-set: the 15 fmt-failing files under `services/` (mechanical `terraform fmt`
  only), `.github/workflows/plan_on_pr.yml` (gate step)
  Acceptance: `terraform fmt -check -recursive services/` exits 0; `plan_on_pr.yml`
  runs `fmt -check -recursive` + `terraform validate` as a fail-fast gate.
  Parallelism: Wave 2, parallel-safe.

- [ ] T-R6-A8 — **Change-detection correctness (CI-H3, CI-M3)** | Owner: devops-engineer | Priority: HIGH
  Write-set: `scripts/ci/detect_changes.sh`, `.github/workflows/plan_on_pr.yml`
  Acceptance:
    (a) Static stack→module map: a module edit triggers plans only for stacks consuming
        that module (blanket `^services/modules/` clause at `plan_on_pr.yml:67` removed).
        The map lives in the SAME single data-driven file as T-R6-A2's dependency
        declarations (F-ARCH-4) — one file, two consumers, zero duplicated stack lists.
    (b) Unavailable merge-base fails the detection step loudly — no silent `HEAD~1`
        fallback (`detect_changes.sh:21`, `plan_on_pr.yml:60-61`). Verification
        (F-QA-4): run `detect_changes.sh` in a simulated shallow clone (no merge-base)
        → exit ≠ 0 + explicit error.
  Parallelism: Wave 2, parallel-safe (coordinate the shared map file with T-R6-A2).

## WS-B1 — Secret logging

- [x] T-R6-B1 — **Stop logging raw Infura key (SEC-H-01, CWE-532; ADR-R6-2)** | Owner: software-engineer | Priority: HIGH
  Write-set: `apps/docker/onchain-stream-txs/src/4_mined_txs_crawler.py`,
  `apps/docker/onchain-stream-txs/tests/unit/` (new/updated tests)
  Acceptance:
    (a) Lines 66, 107, 114 no longer interpolate `actual_api_key`; replaced with a
        non-reversible identifier (`sha256(key)[:8]` or logical key name).
    (b) Unit test asserts no raw key material appears in captured log output.
    (c) Full streaming suite green: `pytest apps/docker/onchain-stream-txs/tests/unit/
        -p no:cacheprovider`.
    (d) Code fix ONLY — no rotation, no scrubbing (OP-R6-1 is the operator follow-up).
  Parallelism: Wave 1, independent of everything.

## WS-B2/B3 — OIDC migration (ADR-R6-3)

- [-] T-R6-B2 — **Terraform: 4 OIDC IAM roles (account-level — ADR-R6-6)** | Owner: software-engineer | Priority: HIGH
  Write-set: `services/prd/03_iam/**` only (all 4 roles live in the account-level prd
  IAM stack; `services/dev/03_iam` does NOT exist and is NOT created; hml `03_iam`
  untouched)
  Acceptance:
    (a) dev/hml/prd deploy roles with OIDC trust policies; `sub` conditions EXACTLY per
        the SPEC ADR-R6-7 trust matrix: dev → `environment:dev`; hml →
        `environment:hml` AND `environment:hml-apps`; prd → `environment:production`
        (the GitHub environment's real name — NOT `prd`).
    (b) 1 read-only plan role: plan/read permissions + state read; no mutating actions;
        trust covers `repo:<org>/<repo>:pull_request` + the default-branch ref claim
        (`drift_detection.yml`, `all-check-infra`).
    (c) Trust policies reference the account OIDC provider (created by operator,
        OP-R6-2) via data source/ARN — the provider itself is NOT created by this
        terraform (chicken-and-egg, documented in SPEC).
    (d) `terraform validate` + plan reviewed for the touched stack; first apply rides
        the existing static-key deploy path (bootstrap, ADR-R6-6).
  Parallelism: Wave 1–2, parallel with WS-A (disjoint files). Blocks T-R6-B3.

- [ ] T-R6-B3 — **Workflows: static keys → OIDC role-assumption** | Owner: devops-engineer | Priority: HIGH
  Write-set: all 7 files under `.github/workflows/`
  Precondition: ALL T-R6-A* merged (same files); T-R6-B2 applied; OP-R6-2 done.
  Acceptance:
    (a) `git grep -l 'AWS_ACCESS_KEY_ID\|AWS_SECRET_ACCESS_KEY' .github/workflows/` → empty.
    (b) Every `configure-aws-credentials` uses `role-to-assume` per the ADR-R6-7 trust
        matrix; `permissions: id-token: write` present where needed.
    (c) `plan_on_pr.yml` + `drift_detection.yml` + `deploy_all_dm_applications.yml`'s
        `all-check-infra` assume ONLY the read-only plan role (fixes SEC-M-05).
    (d) The 9 named mutating no-environment jobs in `deploy_all_dm_applications.yml`
        (`all-stream-build-rc`, `all-hml-infra-apply`, `all-hml-provision`,
        `all-hml-stream-launch`, `all-hml-lambda-deploy`, `all-hml-test-streaming`,
        `all-hml-test-dabs`, `all-hml-test-lambda`, `all-hml-teardown`) gain
        `environment: hml-apps` (reviewer-less — no required_reviewers ever added) and
        authenticate via the hml deploy role.
    (e) Validation: one PR plan run, one dev deploy, one drift run — all green under
        OIDC.
    (f) Cutover-safety evidence (F-QA-3): a non-mutating role-assumption check
        (`aws sts get-caller-identity` from a workflow run) succeeds under EACH of the
        4 roles — including hml and prd deploy roles — and the 4 evidences (run URLs +
        assumed-role ARNs) are recorded in this task's handoff BEFORE OP-R6-4 is
        triggered.
  Parallelism: strictly last in WS-A/B sequence. OP-R6-4 is blocked on (f).

## Sanitization (parallel-safe — `specs/**` only)

- [x] T-R6-S1 — **session_id frontmatter on all 8 bug files** | Owner: product-engineer | Priority: HIGH
  Write-set: `specs/bugs/*.md` (8 files)
  Acceptance: each file gains `session_id: null` (never fabricate an ID); doctor TREE-7
  ERROR count drops 8 → 0.
  Parallelism: any time.

- [x] T-R6-S2 — **rmdir empty configs/ and schemas/ dirs (drift-04 residue)** | Owner: software-engineer | Priority: LOW
  Write-set: `apps/docker/onchain-stream-txs/src/configs/`, `apps/docker/onchain-stream-txs/src/schemas/` (delete empty dirs)
  Acceptance: both dirs absent from disk.
  Parallelism: any time; blocks drift-04 closure in T-R6-S3.

- [x] T-R6-S3 — **Close the 7 fixed bugs with evidence** | Owner: product-engineer | Priority: MEDIUM
  Write-set: `specs/bugs/{bp-01-streaming-jobs-logger-inconsistency,drift-01-streaming-jobs-zero-tests,drift-02-dadaia-dir-inside-repo,drift-03-specs-bkp-migration-leftover,drift-04-kafka-avro-dead-code,drift-05-release-closure-hygiene,drift-06-08-sdd-structure-gaps}.md`
  Precondition: T-R6-S2 (for drift-04 only).
  Acceptance: for EACH bug, re-run its verification (per `sdd-drift-audit.md` §Bug
  hygiene) against code/git BEFORE closing; then `status: Closed` + `fixed_in: <commit>`
  (bp-01 `c789e9c`, drift-01 `226740e`, others `cb218f7` or as re-verified). `drift-10`
  stays Open until T-R6-S6.
  Parallelism: any time after preconditions.

- [ ] T-R6-S4 — **T-R5-F1: archive specs/domains/ + releases/legacy** | Owner: product-engineer (git mv run by PM/operator) | Priority: LOW
  Write-set: `specs/domains/` → `specs/_archive/legacy-domains/<timestamp>/`;
  `specs/releases/legacy/` → `specs/_archive/`
  Acceptance: `specs/domains/` gone from live tree; doctor SPEC-DOC-007 warnings (8)
  cleared; non-canonical `Implementado` token no longer under live `releases/`.
  Parallelism: any time.

- [ ] T-R6-S5 — **T-R5-F2: token_estimate frontmatter fixes** | Owner: product-engineer | Priority: LOW | Phase: CLOSURE (memory-write window)
  Write-set: `specs/memory/architecture.md`, `specs/memory/product/{aws-resources,capture-layer,data-catalog,medallion-pipelines,serving-layer}.md` (frontmatter only)
  Acceptance: token_estimate within ±10% of computed; doctor LINT-1 token drift cleared;
  regenerate `catalog.json` if estimates change.
  Parallelism: CLOSURE phase only (gate).

- [ ] T-R6-S6 — **T-R5-F3: heading-allowlist evaluation + drift-10 closure** | Owner: product-engineer + ai-engineer | Priority: LOW | Phase: CLOSURE for any heading rewrites
  Write-set: investigation; conditional `specs/memory/*` heading edits (CLOSURE window);
  upstream bug in `repos/dadaia-workspace/specs/bugs/` if allowlist gap (ADDITIVE, any time)
  Acceptance: each non-standard heading either rewritten or justified + upstream bug
  filed; outcome documented in CLOSURE.md; `drift-10` then Closed with evidence.
  Parallelism: any time (investigation); edits in CLOSURE.

---

## Task dependency summary

| Task | Depends on | Blocks |
|------|-----------|--------|
| T-R6-A1 | — | T-R6-A2 |
| T-R6-A2 | T-R6-A1 | T-R6-B3 |
| T-R6-A3 | operator OP-R6-3 | rc ship |
| T-R6-A4..A8 | — (A5/A6 sequence commits with A2 in shared files) | T-R6-B3 |
| T-R6-B1 | — | OP-R6-1 (operator rotation) |
| T-R6-B2 | — (provider ARN from OP-R6-2 at apply time) | T-R6-B3 |
| T-R6-B3 | all T-R6-A*, T-R6-B2, OP-R6-2 | OP-R6-4 (gated on B3(f): 4-role assumption evidence — F-QA-3) |
| T-R6-S1 | — | doctor-clean criterion |
| T-R6-S2 | — | T-R6-S3 (drift-04) |
| T-R6-S3 | T-R6-S2 | — |
| T-R6-S4 | — | — |
| T-R6-S5 | CLOSURE phase | — |
| T-R6-S6 | CLOSURE phase (edits) | drift-10 closure |

---

## rc-1 gate (minimum required for ship)

Must be `[x]` DONE before rc-1 review:
**T-R6-A1, T-R6-A2, T-R6-A3, T-R6-A4, T-R6-A5, T-R6-A6, T-R6-A7, T-R6-A8, T-R6-B1,
T-R6-S1, T-R6-S3** (CI safety complete + key-logging fixed + doctor ERRORs cleared +
bug registry truthful).

T-R6-B2/B3 (OIDC) ship in rc-1 if OP-R6-2 is done in time; otherwise they may graduate
in rc-2 — static keys remain an accepted interim risk only until then (OP-R6-4 pending).
T-R6-S4/S5/S6 may complete at CLOSURE.
