# Closure: Release — v0.3.0

> **Status:** Aprovado
> **Release ID:** v0.3.0
> **Owner:** product-engineer
> **Closed:** 2026-06-11
> **Branch:** feature/v0.3.0 (pushed; PR #28 open, merge is operator's)
> **Operator decision:** ship now; defer all operator-pending work to the next release.

## Summary

v0.3.0 removed the two catastrophic-failure modes of the CI/CD surface and the standing
secret exposures. Production and HML infrastructure applies are no longer a blind
single-approval `-auto-approve` loop: every plannable stack's plan is uploaded and
summarized (add/change/destroy) before the informed environment gate, the post-gate
apply uses the saved approved plan binary, and any re-plan divergence fails closed with
the diff published (ADR-R6-4/5). The raw Infura API key is no longer logged — Job 4
references keys only via `sha256(key)[:8]` (ADR-R6-2; rotation is operator follow-up
OP-R6-1, accepted risk until done). CI identity moved from static AWS keys to a 4-role
GitHub OIDC model (ADR-R6-3/6/7) — code-complete; the live cutover (provider creation,
role apply, evidence runs, key deletion) is explicitly deferred to the operator.

The SDD registry was fully sanitized: all 8 bugs closed with evidence, legacy
`specs/domains/` + `specs/releases/legacy/` archived, the three r5 deferrals
(T-R5-F1/F2/F3) executed, and `dadaia specs doctor` reports 0 ERRORs. Ship-trio
approved (qa alpha after 2 reject/fix rounds; code-reviewer; security-reviewer).

## Tasks completed

| Task ID | Description | Final commit |
|---------|-------------|--------------|
| T-R6-A1 | Per-stack apply signal in deploy scripts (CI-C2) | feature/v0.3.0 (PR #28) |
| T-R6-A2 | Dependency-chain-aware informed gate (CI-C1, ADR-R6-4/5) — (a)–(e),(g) complete; (f) live hml graduation deferred to operator | feature/v0.3.0 (PR #28) |
| T-R6-A4 | Concurrency groups on destroy-all/auto-bump/drift | feature/v0.3.0 (PR #28) |
| T-R6-A5 | Error-masking purge (`tee`/`\|\| true`/`tail -N`) | feature/v0.3.0 (PR #28) |
| T-R6-A6 | `timeout-minutes` on every job, all 7 workflows | feature/v0.3.0 (PR #28) |
| T-R6-A7 | terraform fmt fix (15 files) + fmt/validate CI gate | feature/v0.3.0 (PR #28) |
| T-R6-A8 | Change-detection correctness (stack→module map, loud merge-base failure) | feature/v0.3.0 (PR #28) |
| T-R6-B1 | Stop logging raw Infura key (SEC-H-01, ADR-R6-2) | feature/v0.3.0 (PR #28) |
| T-R6-S1 | `session_id` frontmatter on all 8 bug files | feature/v0.3.0 (PR #28) |
| T-R6-S2 | rmdir empty `configs/`/`schemas/` dirs | feature/v0.3.0 (PR #28) |
| T-R6-S3 | Close the 7 fixed bugs with evidence (`c789e9c`, `226740e`, `cb218f7` et al.) | feature/v0.3.0 (PR #28) |
| T-R6-S4 | Archive `specs/domains/` + `specs/releases/legacy/` (T-R5-F1) | feature/v0.3.0 (PR #28) |
| T-R6-S5 | token_estimate frontmatter fixes, 7 atoms + catalog sync (T-R5-F2) | this CLOSURE commit |
| T-R6-S6 | Heading-allowlist evaluation + drift-10 closure (T-R5-F3) | this CLOSURE commit |

Not completed in-release (deferral authority: operator "ship now" decision, this
CLOSURE): **T-R6-A3** (`[ ]`, operator GitHub setting), **T-R6-B2** (`[-]`,
code-complete, apply blocked on OP-R6-2), **T-R6-B3** (`[-]`, code-complete, live
evidence blocked on OP-R6-2/B2). See §Deferred — none silently dropped.

## Validations

| Description | Command | Evidence |
|-------------|---------|----------|
| Streaming + utils unit suites green | `pytest apps/docker/onchain-stream-txs/tests/unit/ utils/tests/unit/ -p no:cacheprovider` | `123 passed` |
| Workflow lint clean on all 7 workflows | `actionlint -shellcheck= .github/workflows/*.yml` | exit 0 on all 7 files |
| Terraform hygiene | `terraform fmt -check -recursive services/` + `terraform validate` (touched stacks) | exit 0 / 0 findings |
| No raw key in logs | unit test asserting no key material in captured log output (T-R6-B1(b)) | included in the 123-passed run |
| No static AWS keys in workflows | `git grep -l 'AWS_ACCESS_KEY_ID\|AWS_SECRET_ACCESS_KEY' .github/workflows/` | empty output |
| SDD registry health | `DADAIA_CONTEXT=dd-chain-explorer dadaia specs doctor` | 0 ERROR |
| QA approval (alpha, after 2 reject/fix rounds) | qa-engineer review | `.dadaia/handoff/dd-chain-explorer/2026-06-11T030500Z-qa-engineer-v030-alpha1-delta-review.handoff.json` |
| Code review approval (rc ship) | code-reviewer review | `.dadaia/handoff/dd-chain-explorer/2026-06-11T021500Z-code-reviewer-v030-rc1-ship-review.handoff.json` |
| Security review approval (rc ship) | security-reviewer review | `.dadaia/handoff/dd-chain-explorer/2026-06-11T013000Z-security-reviewer-v030-rc1-ship.handoff.json` |

## Drifts

### operator-era-cutover-split

**Description:** SPEC acceptance 2(f), 3, and 10 require live runs (hml graduation, hml
required_reviewers, 4-role assumption evidence) that depend on operator one-time actions
(OP-R6-2/3). The operator decided to ship rc now and execute the cutover afterwards.

**Resolution:** WS-A + B1 + sanitization ship fully validated; B2/B3 ship code-complete
with markers annotated DEFERRED-TO-OPERATOR in TASKS.md; static keys remain the interim
auth (accepted risk) until OP-R6-4. All deferrals are tracked as verification tasks in
`specs/backlog/v0.3.0-operator-cutover-and-next.md`.

**Memory updates:** none beyond the planned ones — memory describes the OIDC model as
the CI auth model (current truth of the code); the cicd-pipeline atom marks hml
required_reviewers as operator-pending.

### code-reviewer-non-blocking-residue

**Description:** code-reviewer approved with 3 non-blocking findings: dead
`local root=` assignments at `scripts/ci/deploy_env.sh:275,318`; stale comment at
`scripts/ci/plan_env.sh:112-114`; deploy roles attach `PowerUserAccess` (least-privilege
tightening belongs to epic WS-D).

**Resolution:** accepted as shipped; queued as cleanup items in
`specs/backlog/v0.3.0-operator-cutover-and-next.md`.

**Memory updates:** none (no behavior impact).

### heading-allowlist-upstream-gap

**Description:** T-R6-S6 found that the doctor's memory heading allowlist is hardcoded
with dadaia-workspace-internal strings and not consumer-extensible — the domain headings
in this repo's atoms (e.g. `## S3 Buckets`, `## Schema: ...`) are valid and renaming
them to allowlisted strings would corrupt meaning.

**Resolution:** all non-standard headings justified and kept; upstream library bug filed
at `repos/dadaia-workspace/specs/bugs/memory-heading-allowlist-not-consumer-extensible.md`;
new atoms authored in this release use Group-A canonical headings only. Residual
heading WARNs are accepted until the library ships an extension mechanism.

**Memory updates:** none (headings unchanged by design).

## Memory updates

- `specs/memory/tech-stack.md` — CI/CD section rewritten to current truth: OIDC 4-role
  model + trust matrix, actionlint + fmt/validate gates, single-source
  `scripts/ci/stack_map.json` convention, job hygiene (timeouts/concurrency);
  token_estimate 1200→1910.
- `specs/memory/cicd-pipeline.md` — **NEW atom** (category: ops, GAP-LD-1): the 7
  workflows, informed-gate semantics (ADR-R6-4/5: pre-gate plan artifacts, saved-plan
  apply, deferred 05b, fail-closed divergence), OIDC trust matrix summary, scripts/ci
  toolbox. release_origin: v0.3.0.
- `specs/memory/product/capture-layer.md` — key-redaction behavior added (Job 4 logs
  only `_key_ref()` = `sha256(key)[:8]`, CWE-532 posture); token_estimate 800→740.
- `specs/memory/product/aws-resources.md` — token_estimate 1200→1860 (frontmatter only).
- `specs/memory/product/data-catalog.md` — token_estimate 1400→1830 (frontmatter only).
- `specs/memory/product/medallion-pipelines.md` — token_estimate 900→580 (frontmatter only).
- `specs/memory/product/serving-layer.md` — token_estimate 600→435 (frontmatter only).
- `specs/memory/architecture.md` — token_estimate 2400→1950 (frontmatter only;
  **content explicitly NOT rewritten** — fidelity rewrite stays epic WS-F1).
- `specs/memory/product/catalog.json` — token_estimates synced (regenerate with
  `generate-memory-catalog.py` if preferred; values match frontmatter).
- `specs/memory/product/index.md` — no change: catalog order unchanged; the new atom is
  top-level ops memory, not a product feature.
- `specs/memory/quality-assurance.md` — no change this closure (updated in r5; CI wiring
  of the 71 tests stays epic WS-F5).

## Deferred (operator handover — explicit, none silently dropped)

Deferral authority: operator decision at this CLOSURE ("ship now, defer all
operator-pending work to the next release"). Every item is a verification task with an
evidence criterion in `specs/backlog/v0.3.0-operator-cutover-and-next.md`.

| # | Item | What remains | Interim state |
|---|---|---|---|
| 1 | **OP-R6-1** Infura key rotation | Rotate the exposed key(s); update SSM | **ACCEPTED RISK (ADR-R6-2)**: key valid + readable in historical CloudWatch/S3/Databricks logs until rotated |
| 2 | **OP-R6-2** OIDC provider creation | Create `token.actions.githubusercontent.com` provider in the AWS account (one-time) | static keys remain CI auth |
| 3 | **OP-R6-2 follow-on / T-R6-B2** | Apply `services/prd/03_iam` (4 OIDC roles, code-complete + validated) and set `AWS_DEPLOY_ROLE_{DEV,HML,PRD,READONLY}` repo vars | roles exist only in code |
| 4 | **A3 / OP-R6-3** hml required_reviewers | `gh api -X PUT repos/:owner/:repo/environments/hml -f "reviewers[][type]=User" -F "reviewers[][id]=42839553"` | hml applies human-ungated |
| 5 | **T-R6-B3(f)** 4-role assumption evidence | `aws sts get-caller-identity` evidence runs under ALL 4 roles (run URLs + ARNs) — hard precondition for OP-R6-4 | no live OIDC proof yet |
| 6 | **OP-R6-4** static-key deletion | Delete/deactivate static IAM keys + repo secrets AFTER item 5 evidence | standing secret persists |
| 7 | **T-R6-A2(f)** live hml graduation | One full green hml run through the new gate flow BEFORE the first prd run | new flow unproven live (code + hermetic tests green) |

TASKS.md markers: A3 left `[ ]`, B2/B3 left `[-]`, each annotated
`DEFERRED-TO-OPERATOR (2026-06-11)` — this CLOSURE records the deferral authority.

## Dispositions

| File | Kind | Terminal status | Evidence |
|------|------|-----------------|----------|
| `specs/bugs/bp-01-streaming-jobs-logger-inconsistency.md` | bug | `Closed` | `fixed_in: c789e9c` (T-R6-S3) |
| `specs/bugs/drift-01-streaming-jobs-zero-tests.md` | bug | `Closed` | `fixed_in: 226740e` (T-R6-S3) |
| `specs/bugs/drift-02-dadaia-dir-inside-repo.md` | bug | `Closed` | T-R6-S3 re-verified |
| `specs/bugs/drift-03-specs-bkp-migration-leftover.md` | bug | `Closed` | T-R6-S3 re-verified |
| `specs/bugs/drift-04-kafka-avro-dead-code.md` | bug | `Closed` | T-R6-S3 (after T-R6-S2 rmdir) |
| `specs/bugs/drift-05-release-closure-hygiene.md` | bug | `Closed` | T-R6-S3 re-verified |
| `specs/bugs/drift-06-08-sdd-structure-gaps.md` | bug | `Closed` | T-R6-S3 re-verified |
| `specs/bugs/drift-10-doctor-warnings-batch.md` | bug | `Closed` | this CLOSURE (T-R6-S4/S5/S6 evidence in the bug file) |
| `specs/backlog/platform-audit-remediation-20260611.md` | backlog | non-terminal (CANDIDATE) — WS-A + B1/B2/B3 slice CONSUMED by v0.3.0; WS-B4/B5/B6, WS-C/D/E/F/G remain candidate | SPEC §Sources; pointer kept in `specs/backlog/v0.3.0-operator-cutover-and-next.md` (accepted SPEC-DOC-031 WARN until the epic terminates) |

## Backlog returns

- `specs/backlog/v0.3.0-operator-cutover-and-next.md` ← **NEW CANDIDATE**: the 6
  operator cutover/verification items (OP-R6-1..4, A3, B3(f), A2(f)), the 3
  code-reviewer non-blocking cleanups, and memory gaps GAP-LD-2..6 (see file).

## Archive decision

**MOVE** — release directory moves to `specs/_archive/releases/v0.3.0/` via `git mv`
(run by coordinator/operator; PE has no shell). `ACTIVE.md` is then freed to
`release: none` — the operator has not picked the next release.
