# SPEC: v0.3.0

**Status:** Em revisão
**Release ID:** v0.3.0
**Phase:** SPEC
**Owner:** product-engineer
**Branch:** feature/specs-first-docs-cleanup
**Date:** 2026-06-11
**Sources:** backlog epic `specs/backlog/platform-audit-remediation-20260611.md`
(WS-A + WS-B1/B2/B3 slice + sanitization); consolidated audit
`specs/audits/20260611T001412Z-cb56f84c/` (cicd-terraform-review.md, security-review.md,
sdd-drift-audit.md); grill report
`.dadaia/reports/dd-chain-explorer/project-manager/2026-06-11T004812Z-refine-specs.html`
(ADR-R6-1..4).

---

## Objective

Stop the catastrophic-failure modes in the CI/CD surface and remove the standing-secret
exposure: (1) make every production `terraform apply` an **informed, gated, per-stack-
signaled** operation instead of today's blind single-approval auto-apply; (2) stop
logging the raw Infura key; (3) replace long-lived static AWS keys with GitHub OIDC
role-assumption; (4) sanitize the SDD registry (bug closures, doctor ERRORs, and the
three tasks deferred from audit-remediation-r5).

No product features. No data-pipeline changes.

---

## Embedded decisions (from the mandatory grill, 2026-06-11)

- **ADR-R6-1** — r5 closed with deferral; T-R5-F1/F2/F3 fold into this release's
  sanitization workstream (never dropped).
- **ADR-R6-2** — Infura key leak (SEC-H-01): **code fix only**. Key rotation is an
  **operator follow-up** (see Named operator actions). Log scrubbing rejected.
- **ADR-R6-3** — OIDC topology = **4 IAM roles**: dev/hml/prd deploy roles, each
  trust-bound to its GitHub environment via OIDC `sub` claims, plus **1 read-only plan
  role** used by `plan_on_pr.yml` and `drift_detection.yml`.
- **ADR-R6-4** — Apply gating = **one informed gate per env-deploy**: all stack plans
  uploaded as artifacts + a consolidated add/change/destroy summary visible to the
  approver; destroy-containing plans require explicit acknowledgment; `hml` GitHub
  environment gains required_reviewers; `dev` stays automatic.

---

## Product deltas

None — no user-facing functionality changes.

---

## Architecture deltas

None to the data platform. The CI control plane changes shape:

- PRD/HML deploys move from "one blind environment approval → loop of
  `terraform apply -auto-approve`" to a two-phase **plan → informed gate → apply-saved-
  plan** flow with per-stack plan artifacts (CI-C1, ADR-R6-4).
- CI identity moves from one static IAM key pair (repo secrets) to federated OIDC
  role-assumption with per-env blast radius (CI/SEC-H-02, ADR-R6-3).

---

## Tech-stack deltas

- No new application dependencies.
- New Terraform resources: 4 IAM roles with OIDC trust policies (see Security deltas).
- GitHub Actions workflows gain `permissions: id-token: write`, `concurrency:` groups,
  `timeout-minutes`, and a `terraform fmt -check`/`validate` gate.

---

## Security / operations deltas

### WS-A — CI safety (CRITICAL set from cicd-terraform-review.md)

| Item | Findings | Delta |
|---|---|---|
| A1 per-stack apply signal | CI-C2 | `scripts/ci/deploy_env.sh:77` stops grepping `tail -1` over the shared `$GITHUB_OUTPUT`; apply decision derives from `tf_plan.sh`'s real exit signal per stack; the silent `/dev/null` skip path (`deploy_env.sh:61`) is removed — a missing signal fails loudly |
| A2 plan-visible informed gate | CI-C1 + ADR-R6-4 | `deploy_cloud_infra.yml` PRD (`:181-210`) and HML (`:248-273`) restructured: plan phase uploads every stack's plan (`tfplan` + full `plan.txt`) as artifacts and posts a consolidated add/change/destroy summary to the run summary; environment-gated apply phase applies the **saved** plans; any plan containing destroys requires an explicit acknowledgment input; `dev` keeps its existing auto per-stack gating |
| A3 hml environment gate | CI-C1 | `hml` GitHub environment gains required_reviewers (operator one-time GitHub setting — see Named operator actions); `dev` stays auto |
| A4 concurrency groups | CI-C3, CI-M9 | `destroy_all_cloud_infra.yml`, `auto-bump-version.yml`, `drift_detection.yml` gain `concurrency:` groups with `cancel-in-progress: false` |
| A5 error-masking purge | CI-H8, CI-M1, CI-M2 | `deploy_all_dm_applications.yml:949-954` plan no longer piped through `tee` without `pipefail`; apply gated on plan changes; `terraform_wrapper: false` parity; `\|\| true` removed from verify/test/lock-check steps (kept only for genuine idempotent teardown); plan summaries stop truncating via `tail -N` — full plan uploaded as artifact (CI-M2) |
| A6 timeouts | CI-H4 | `timeout-minutes` on **every** job in all 7 workflows |
| A7 fmt/validate gate | CI-H1 | `terraform fmt -check -recursive` + `terraform validate` CI gate added; the 15 currently-failing files mechanically fixed with `terraform fmt` |
| A8 change-detection correctness | CI-H3, CI-M3 | module change triggers plans only for **dependent** stacks via a static stack→module map (replacing the blanket `^services/modules/` clause at `plan_on_pr.yml:67`); the `HEAD~1` fallback in `scripts/ci/detect_changes.sh:21` / `plan_on_pr.yml:60-61` fails loudly instead of silently degrading |

### WS-B1 — Stop logging the raw Infura key (SEC-H-01, CWE-532)

`apps/docker/onchain-stream-txs/src/4_mined_txs_crawler.py:66,107,114` stop emitting
`actual_api_key` (the raw secret) into logs; replaced with a non-reversible identifier
(e.g. `sha256(key)[:8]` or the key's logical name). Code fix **only** (ADR-R6-2).

**Accepted residual risk (operator decision, recorded):** the current key remains valid
and readable in historical CloudWatch (`/apps/dm-chain-explorer`, `/ecs/dm-chain-explorer`),
S3 `raw/app_logs/`, and Databricks `b_app_logs`/gold log tables **until the operator
rotates it**. No log scrubbing will be performed.

### WS-B2/B3 — OIDC migration (SEC-H-02/M-05, CWE-798; ADR-R6-3)

- **Terraform-owned (this release):** 4 IAM roles —
  - `dev`/`hml`/`prd` deploy roles, defined in the respective `services/<env>/03_iam`
    stacks, each with an OIDC trust policy whose `sub` condition binds to this repo's
    corresponding GitHub **environment**;
  - 1 read-only plan role (account-level; defined alongside the prd IAM stack) with
    read/plan permissions + state-bucket read, used by `plan_on_pr.yml` and
    `drift_detection.yml`.
- **Operator one-time setup (NOT terraform in this release):** the AWS GitHub OIDC
  identity provider (`token.actions.githubusercontent.com`) — chicken-and-egg: CI cannot
  terraform its own identity provider while still authenticating with the keys being
  retired. See Named operator actions.
- **Workflows:** static `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` removed from **all 7
  workflows**; `aws-actions/configure-aws-credentials` switches to `role-to-assume`;
  `permissions: id-token: write` added per job/workflow as required; PR plans and drift
  detection assume only the read-only role (fixes SEC-M-05's deploy-creds-on-PR exposure).
- **Sequencing:** OIDC workflow edits land **after** the WS-A gate redesign — same 7
  workflow files; sequencing avoids churn (grill priority table).

### Sanitization workstream (ADR-R6-1 fold + audit recommendation 4)

- Add `session_id: null` frontmatter to all 8 `specs/bugs/` files (clears the 8 doctor
  TREE-7 ERRORs; never fabricate an ID).
- Close the 7 fixed-but-Open bugs with `status: Closed` + `fixed_in:` commit evidence,
  re-verifying each against code/git per `sdd-drift-audit.md` §Bug hygiene before
  closing: `bp-01` (`c789e9c`), `drift-01` (`226740e`), `drift-02`, `drift-03`,
  `drift-04` (after rmdir of the empty `configs/`/`schemas/` dirs), `drift-05`,
  `drift-06-08`. `drift-10` closes only when T-R6-S4/S5/S6 complete its remaining scope.
- Deferred r5 tasks executed here: T-R5-F1 → archive `specs/domains/` (+
  `specs/releases/legacy/`); T-R5-F2 → fix `token_estimate` frontmatter in the 6 drifted
  memory atoms; T-R5-F3 → evaluate heading-allowlist warnings (rewrite vs upstream
  library bug).

---

## Bug-always-solved check

`specs/bugs/` contains exactly 8 bug files; **all 8 are picked** into this release's
sanitization workstream. 7 are verified-fixed and will be closed with evidence; `drift-10`
is completed by T-R6-S4/S5/S6 and then closed. No bug is superseded
(`superseded_by:` not used), none is silently dropped, and no Open bug remains
picked-but-unsolved. There are no unpicked Open bugs.

---

## Named operator actions (recorded follow-ups, not release tasks)

| ID | Action | Trigger | Accepted interim risk |
|---|---|---|---|
| OP-R6-1 | **Rotate the exposed Infura API key(s)** | after WS-B1 merges/deploys | key remains valid + readable in historical CloudWatch/S3/Databricks logs until rotated (ADR-R6-2) |
| OP-R6-2 | **Create the GitHub OIDC identity provider** in AWS account (one-time) | before T-R6-B3 (workflow cutover) | static keys remain in use until cutover |
| OP-R6-3 | **Add required_reviewers to the `hml` GitHub environment** | with WS-A A3 | hml applies remain human-ungated until set |
| OP-R6-4 | **Delete/deactivate the static IAM access keys + repo secrets** | after OIDC cutover validated | standing secret persists until deleted |

---

## Memory files affected at closure

- `specs/memory/tech-stack.md` — CI/CD section: OIDC auth model, fmt/validate gate,
  concurrency/timeout posture (current-state description only).
- `specs/memory/*` token_estimate frontmatter fixes (T-R6-S5) and any heading rewrites
  (T-R6-S6) land in the CLOSURE memory-write window.
- `specs/memory/architecture.md` — **explicitly NOT rewritten** in this release (WS-F1 of
  the epic; deferred until architectural decisions E1/E3/D5 land).
- No product atom changes expected (WS-B1 is a non-functional log-statement fix).

---

## Acceptance criteria

1. **A1:** `deploy_env.sh` contains no `grep`/`tail -1` over `$GITHUB_OUTPUT`; apply
   decision is per-stack from the plan's real exit signal; missing signal fails the run.
2. **A2:** PRD and HML deploys upload every stack's plan artifact + consolidated
   add/change/destroy summary before the environment gate; apply uses the saved plans;
   destroy-containing plans require explicit acknowledgment; dev unchanged (auto).
3. **A3:** `gh api` shows required_reviewers on `hml` (operator OP-R6-3 done); recorded
   in the task evidence.
4. **A4:** `destroy_all_cloud_infra.yml`, `auto-bump-version.yml`, `drift_detection.yml`
   each have a `concurrency:` group with `cancel-in-progress: false`.
5. **A5:** no `tee`-masked plan exits (pipefail or no pipe); no `|| true` on
   verify/test/lock-check steps; full plan artifacts replace `tail -N` summaries.
6. **A6:** `grep -c timeout-minutes` ≥ number of jobs, in each of the 7 workflows.
7. **A7:** `terraform fmt -check -recursive services/` exits 0 (15 files fixed); a CI
   gate runs fmt-check + validate and fails on drift.
8. **A8:** a module-only change triggers plans solely for stacks mapped to that module;
   unavailable merge-base fails the detection step loudly (no `HEAD~1` silent fallback).
9. **B1:** no log statement in `4_mined_txs_crawler.py` emits raw key material (lines
   66/107/114 fixed); a unit test asserts log output contains no key value.
10. **B2/B3:** `git grep -l 'AWS_ACCESS_KEY_ID\|AWS_SECRET_ACCESS_KEY' .github/workflows/`
    returns empty; every AWS job uses `role-to-assume` + `id-token: write`; 4 roles exist
    in Terraform (3 env-bound via OIDC `sub` to their GitHub environments + 1 read-only
    plan role); `plan_on_pr.yml` and `drift_detection.yml` assume only the read-only role.
11. **Sanitization:** `DADAIA_CONTEXT=dd-chain-explorer dadaia specs doctor` reports 0
    ERRORs; all 8 bugs carry `session_id:`; 7+1 bugs Closed with `fixed_in:` evidence;
    `specs/domains/` and `specs/releases/legacy/` archived; token_estimates within ±10%;
    heading warnings resolved or filed upstream.

---

## Out of scope

- WS-B4/B5/B6 (encryption-at-rest CMK posture, Databricks token in TF state, low-sev
  hardening batch) — stay in the backlog epic.
- WS-C (stale PRD Databricks monolith / HML-validates-PRD / Makefile retirement),
  WS-D (single stack tree / provider pinning), WS-E (capture-layer deprecation ADR),
  WS-G — backlog epic.
- `specs/memory/architecture.md` fidelity rewrite (epic WS-F1) and ADR-005 /
  `popular_contracts_txs` resolution (epic WS-F2/E3).
- Wiring the 71 streaming tests into CI (epic WS-F5).
- Infura key **rotation** and historical **log scrubbing** (OP-R6-1; scrubbing rejected —
  ADR-R6-2).
- Per-stack approval clicks (9 gates per deploy) — rejected by ADR-R6-4 in favor of one
  informed gate per env.

---

## Dependencies and risks

| Risk | Mitigation |
|------|-----------|
| OIDC cutover depends on operator one-time provider setup (OP-R6-2); if delayed, B3 blocks | B2 (terraform roles) can land first; workflows keep static keys until cutover; rc gate may ship WS-A+B1 without B3 |
| WS-A and WS-B3 touch the same 7 workflow files | hard sequencing: WS-A merges before B3 edits begin (grill priority table) |
| `devops` plugin required for CI-YAML ownership (`devops-engineer`) | if not installed: `dadaia plugin install devops`, or operator explicitly authorizes software-engineer scope for workflow files |
| Plan-artifact gate redesign could break the working dev flow | dev path explicitly unchanged (ADR-R6-4); validation runs `plan_on_pr` + a dev deploy before hml/prd cutover |
| Closing bugs without re-verification risks registry lies | T-R6-S3 acceptance requires re-running each bug's verification command before flipping status |
| `hml` required_reviewers adds friction to hml iteration | accepted by operator in grill Problem #4 (informed single gate per env) |
