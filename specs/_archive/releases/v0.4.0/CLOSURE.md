# Closure: Release — v0.4.0

> **Status:** Aprovado
> **Release ID:** v0.4.0
> **Owner:** product-engineer
> **Closed:** 2026-08-23

## Summary

v0.4.0 retired the AWS streaming capture layer. Data capture now lives entirely in the
separate `dd-chain-capture` project on a VPS, and the S3 raw bucket is the whole
integration boundary. Kinesis, Firehose and SQS — plus the five ECS capture producer
services, the CloudWatch→Firehose app-log shipping and the `kinesis`/`sqs` Terraform
modules — no longer exist in AWS or in this repository. S3, DynamoDB, the log groups, the
two non-capture Lambdas, the ECS cluster and both ECR repos were explicitly preserved.

The live destroy ran 2026-06-22 (18 resources in `prd`, 18 in `dev`; `hml` had nothing
live). Closure follows two months later: all sixteen tasks were honestly complete on disk,
but memory still described the pre-v0.4.0 world until today, and three acceptance criteria
were never evidenced. Both facts are stated below rather than smoothed over.

## Tasks completed

All 16 tasks are `[x]`. Per-task SHAs were not recorded individually; the change set landed
as one reviewed sequence (`8bab000`, `f78206a`, `1727e3a`, `7f8cf3c`, `40eadb3`) with review
HEAD `de70033`. Branch head at closure is `c6feb17`.

| Task ID | Description | Final commit |
|---------|-------------|--------------|
| T-A.1 / T-A.2 | Remove 5 producer task-defs+services, `common_stream_env`, `kinesis_sqs`/`dynamodb` remote-state sources from `prd/07_ecs` | `de70033` |
| T-B.1 / T-B.2 | Survivor Lambdas keep planning — `contracts_ingestion` log-group ref confirmed; `dev/02_lambda` no change | `de70033` |
| T-R.1 | Review checkpoint R1 — folded into R2 | `de70033` |
| T-C.1 .. T-C.4 | Peripherals (prd/dev/hml): kinesis+sqs modules removed, `firehose_enabled = false`, kinesis/sqs/firehose outputs dropped | `de70033` |
| T-D.1 / T-D.2 / T-D.3 | Delete `modules/{kinesis,sqs}`; update `stack_map.json`; fix `destroy_env.sh` targets + warning | `de70033` |
| T-D.4 / T-D.5 | Purge producer references from operational scripts, integration tests and hml teardown | `de70033` |
| T-R.2 | Full review — qa + code + security, all green | `de70033` |
| T-4.1 | Live destroy — prd 18 / dev 18 resources; hml code-only | live AWS state only |

## Validations

| Description | Command | Evidence |
|-------------|---------|----------|
| All 16 TASKS markers honest — deliverables exist on disk | `grep -rn` spot-checks across WS-A/WS-C/WS-D | `specs/audits/20260823T145726Z-4db47555/sdd-drift-lane.md` §1.2 — T-A.1/A.2, T-C.1..C.4, T-D.1, T-D.3, T-D.4/D.5 all **CONFIRMED** |
| AC-0 producer quiescence before destroy | `aws ecs describe-services` | T-4.1 row: 0 producer services / 0 tasks on every cluster |
| AC-1 capture resources gone (at destroy) | `aws kinesis list-streams` / `firehose list-delivery-streams` / `sqs list-queues` | T-4.1: prd 18 destroyed, dev 18 destroyed; lists empty post-destroy |
| AC-1 still gone, 2 months later | live re-verification 2026-08-23 | 0 Kinesis streams, 0 Firehose delivery streams, 0 SQS queues live |
| Cost effect of the retirement | AWS cost explorer, monthly | May 62.71 USD → Aug MTD 4.22 USD |
| AC-2 plan idempotency (local) | targeted-destroy preview | T-4.1: preview `0 to add, 0 to change` — no survivor touched |
| AC-3 survivors intact | `aws s3 ls` / `dynamodb list-tables` / `logs describe-log-groups` | T-4.1: 5 S3 buckets, 3 DynamoDB tables, `/apps/dm-chain-explorer-{dev,prd}` present |
| AC-6 no orphan refs/modules/tooling | `grep -rn`, `terraform validate` | Largely met (audit §1.2); **residual**: unconsumed `iam` remote-state source + 4 dead locals in `prd/07_ecs` survive — code-reviewer MEDIUM, handoff `2026-06-23T001115Z` |
| AC-8 CI hygiene | `terraform fmt -check -recursive`, `validate`, `bash -n` | code-reviewer handoff `2026-06-23T001115Z` — 6 stacks validated, 7 scripts `bash -n` clean |
| Security review of the delta | `git diff 6b68c15..de70033 -- services/ scripts/` | security-reviewer handoff `2026-06-23T000518Z` — **APPROVED**, IAM blast radius capture-only, 0 HIGH/MEDIUM |
| Code review of the delta | cumulative diff `6b68c15..de70033` | code-reviewer handoff `2026-06-23T001115Z` — APPROVE-WITH-CHANGES, 0 CRITICAL/HIGH |

**Not evidenced — stated plainly, not waived:**

| AC | Why it carries no evidence |
|----|----------------------------|
| **AC-4** (non-capture Lambdas still *functionally* invoke) | No post-destroy invoke or recent-invocation check was ever run for `contracts_ingestion` or `gold_to_dynamodb`. Existence and plan-cleanliness were confirmed; function was not. |
| **AC-5** (surviving batch ECS workload still runs; both ECR repos intact) | No post-destroy `list-services` / `describe-repositories` assertion was recorded. The audit later found the ECS stacks are empty shells (DRIFT-13), so there is no live batch service to have been broken — but that is a finding, not the evidence AC-5 asked for. |
| **AC-7** (drift_detection zero + plan_on_pr clean post-apply) | **Structurally unsatisfiable.** `drift_detection.yml` is absent from the default branch, so its cron can never fire (audit DRIFT-10). The AC could not have been met by any execution of this release. |

## Size accounting

Aggregate measured from the reviewed diff `6b68c15..de70033` (security-reviewer and
code-reviewer handoffs report identical counts): **+104 / −2 711 across 24 files, net
−2 607.** Per-file largest additions/deletions were **not measured** — this closing session
has no shell and the breakdown was not captured at review time; recorded as a gap rather
than estimated.

Ceilings `C90` and `PLR1702`: `n/a` before and after — no Python ceiling is pinned in this
repo and the delta is Terraform + shell. **Nesting-violation count:** `n/a`.

## Drifts

### architecture-atom-omitted-from-spec-8

**Description:** SPEC §8 pre-declared four memory atoms to rewrite at CLOSURE
(`capture-layer.md`, `tech-stack.md`, `aws-resources.md`, `index.md`+`catalog.json`).
`architecture.md` was not on that list, yet the audit found it was the *most* stale atom —
still asserting 5 live ECS capture jobs, 3 Kinesis streams, 8 Firehose streams and 12 SQS
queues/DLQs.

**Resolution:** The SPEC's memory list was treated as a floor, not a ceiling.
`architecture.md` was rewritten at closure, plus six further atoms once the audit showed
the drift was platform-wide.

**Memory updates:** `specs/memory/architecture.md` (plus the ten atoms listed below).

### t-4-1-mechanism-substitution

**Description:** SPEC §7 and OQ-4 locked the live-removal mechanism to a config-diff
`terraform apply` through `deploy_cloud_infra.yml` under the informed gate + `destroy_ack`.
T-4.1 instead executed an operator-authorized targeted `terraform destroy` against
`module.kinesis`, `module.sqs` and 6 CloudWatch firehose resources.

**Resolution:** Accepted. v0.3.0 was unmerged and `develop`/`master` lagged it, so a
config-diff apply would have bundled unrelated survivor drift into an irreversible
production destroy. The targeted destroy was the surgical fit; its preview showed
`0 to add, 0 to change`. Trade-off: the release's own CI mechanism was never exercised —
one reason AC-7 has no evidence.

**Memory updates:** `specs/memory/product/cicd-pipeline.md` (the deploy gate is written but
has never executed a real apply).

### capture-vectors-outside-every-write-set

**Description:** Three surfaces still provision or grant the retired capture layer and lay
outside every declared write set, so the release's acceptance criteria could not catch
them: `.github/workflows/deploy_all_dm_applications.yml` (builds the stream image,
provisions HML Kinesis/SQS, launches 5 producers, runs `terraform destroy
-target='module.kinesis'` against a deleted module), `scripts/ci/hml_provision.sh`, and the
Kinesis/Firehose/SQS grants in `prd/03_iam` and `hml/03_iam` — exactly the "streams come
back" vector SPEC §3.2 targeted.

**Resolution:** Not fixed here (out of scope by write set; the workflow is inert today
because CI cannot authenticate to AWS — audit DRIFT-01). Routed to v0.5.0 as DRIFT-02/13.

**Memory updates:** `specs/memory/product/cicd-pipeline.md` and
`specs/memory/product/aws-resources.md` record both residues as live gaps.

### promised-backlog-item-never-created

**Description:** SPEC OQ-5 deferred the `dm-chain-utils` Kinesis/SQS/Firehose handler
cleanup to a follow-up backlog item `dm-chain-utils-capture-handler-cleanup`. That item was
never created; the handlers are still exported and shipped in the Lambda layer.

**Resolution:** Superseded by audit DRIFT-12 (16 dead Python modules, ~4 540 LOC), which
covers the same surface more widely and is routed to v0.5.0. No orphan promise survives.

**Memory updates:** `specs/memory/tech-stack.md` (handler rows marked dead-but-shipped).

## Memory updates

Eleven files were written in this CLOSURE phase — paths relative to `specs/memory/`.

- `architecture.md` — rewritten: three owned surfaces, S3 boundary, medallion flow, ADRs.
- `tech-stack.md` — Kinesis/Firehose/SQS and the `kinesis`/`sqs` modules removed; live AWS
  surface, dead-handler rows, two version axes recorded.
- `quality-assurance.md` — new atom: 158 green tests, the CI wiring gap, zero-coverage
  layers, the forward QA contract.
- `product/index.md` — vision, users, capability map and limits rewritten.
- `product/catalog.json` — 6 entries regenerated; `tldr` mirrored to each atom's frontmatter.
- `product/capture-layer.md` — **rewritten in place** as the "Capture Integration" boundary
  atom (decision (a), operator-ratified): the S3 raw bucket is the entire contract. Not
  archived — the boundary is a live product surface though the AWS capture layer is gone.
- `product/aws-resources.md` — Kinesis/Firehose/SQS inventory dropped; every remaining
  resource marked managed, orphan or residue.
- `product/medallion-pipelines.md` — two DLT pipelines, expectations, deploy drift, idle state.
- `product/data-catalog.md` — 29 objects (was an incorrect 30); `popular_contracts_txs` gone.
- `product/serving-layer.md` — dashboards, gold-export chain, never-deployed alerts/Genie.
- `product/cicd-pipeline.md` — seven workflows, the informed gate, the gaps that make the
  control plane inert.

Frontmatter lint fixes in the same phase: eight over-length `tldr` values shortened to the
`memory-frontmatter-v1` ceiling; `cicd-pipeline.md`'s `summary` quoted (an unquoted `: `
made its YAML invalid).

## Dispositions

| Record | Kind | Terminal disposition | Evidence |
|--------|------|-----------------------|----------|
| `specs/bugs/*.jsonl` (`sdd-artifact-linter-mutates-task-markers`) | bug | `superseded` / **misfiled** | This section — a dadaia-workspace tooling bug misfiled in this repo's ledger; re-registration routed upstream to the `dadaia-workspace` context. It **stays open in `bugs.jsonl`** until the operator re-files it; this closure edits no ledger. |
| `drift-01`, `drift-04`, `bp-01-streaming-jobs-logger-inconsistency` | bug | `Closed` (pre-existing) | TASKS Notes — already closed by source-tree fixes; none fixed by this release, none superseded, none dropped |
| backlog | — | none picked | This release consumed no backlog item; no `**Consumes:**` line was declared |

**SPEC open questions (OQ-1..OQ-5):**

| OQ | Status |
|----|--------|
| OQ-1 — keep ECS cluster + both ECR repos | **Honoured** in code; AC-5 verification not evidenced (see Validations) |
| OQ-2 — `firehose_enabled = false` toggle, not module surgery | **Honoured and verified** (audit §1.2, T-C.1..C.4 CONFIRMED) |
| OQ-3 — `destroy_env.sh` kept as whole-env-only, dead targets removed | **Honoured and verified** (audit §1.2, T-D.3 CONFIRMED) |
| OQ-4 — config-diff apply as the destroy mechanism | **Not honoured** — substituted by an operator-authorized targeted destroy (drift 2) |
| OQ-5 — `dm-chain-utils` handler cleanup as a follow-up backlog item | **Not honoured** — item never created; superseded by audit DRIFT-12 (drift 4) |

**Open questions carried by the two memory-update handoffs (2026-08-23):**

| # | Question | Disposition |
|---|----------|-------------|
| 1 | `architecture.md` must be listed in `## Memory updates` despite SPEC §8 | record-only — resolved by drift 1 above |
| 2 | Confirm catalog rank order matches the operator's daily-relevance view | record-only — order kept as authored; no operator objection raised |
| 3 | `g_apps.transactions_lambda` batch-contracts union branch has no backing bronze table | routed to v0.5.0 remediation release (audit DRIFT-12) |
| 4 | Gold-export → S3 → Lambda → DynamoDB CONSUMPTION chain has no verified reader | routed to v0.5.0 remediation release (audit DRIFT-27) |
| 5 | `hml` target — destroy it, or give it a real bucket/external location and redeploy | routed to v0.5.0 remediation release (audit DRIFT-13/DRIFT-18) |

## Test dispositions

| Kind | Deleted/expired test | Replacement / disposition | Evidence |
|------|----------------------|----------------------------|----------|
| tombstone | `scripts/hml_integration_test_optimized.sh` (unconditional `exit 0`, gates a PRD deploy chain) | **deletion owed** — executed in v0.5.0 under a `qa-engineer` verdict; a dead e2e script is deleted, never stubbed | audit DRIFT-02; `specs/memory/quality-assurance.md` |
| demotion/deletion | `utils/tests/unit` (tests for `dm_kinesis`, `dm_sqs`, `dm_firehose` and the other dead modules) | routed to v0.5.0 — deleted with the modules, or demoted if a module is retained | audit DRIFT-12 |

## Record-only observations

| Source (reviewer/handoff) | Observation | Why record-only |
|---|---|---|
| product-engineer `2026-08-23T160000Z` | Field-name compatibility between `dd-chain-capture` deliveries and the DLT Auto Loader schemas is unverified — no delivery has ever been processed end-to-end | No fix surface until the first delivery arrives; recorded in `capture-layer.md` as an open verification |
| security-reviewer `2026-06-23T000518Z` | `destroy_env.sh` remains a whole-env teardown that still targets `module.dynamodb` (a survivor) | LOW, pre-existing; the diff made it safer and the warning is accurate |
| code-reviewer `2026-06-23T001115Z` | `services/dev/00_compose/app_services.yml` still defines local-dev producer containers | Already self-disclosed in the change set; subsumed by the v0.5.0 dead-code lane |

## Intake candidates

All routed via the PM intake report 2026-08-23 (audit `20260823T145726Z-4db47555`) →
v0.5.0. This closure creates no backlog entry.

- **Pre-approved intake** — the audit's remediation lane (DRIFT-02, DRIFT-12, DRIFT-13,
  DRIFT-27 and the unevidenced AC-4/AC-5/AC-7 re-verification), ratified at audit read-out.
- **To be adjudicated** — the `prd/07_ecs` residual `iam` remote-state source and four dead
  locals (AC-6 remainder), and a `DYNAMODB_DESTROY_ACK` guard on `destroy_env.sh`.

## Artifact GC sweep

| Artifact class | Kept (still referenced) | Deleted/archived | Evidence |
|----------------|--------------------------|-------------------|----------|
| `.dadaia/handoff/dd-chain-explorer/*.handoff.json` (this release) | `5` | `0` | This section — the qa/security/code-reviewer v0.4.0 handoffs and both memory-update handoffs are cited by `## Validations`, `## Dispositions` and `## Record-only observations`, so all are KEEP |
| `.dadaia/reports/dd-chain-explorer/**` (this release) | `0` | `0` | This section — no HTML report was produced for v0.4.0 |
| `.dadaia/tmp/**` (this release's captures) | `0` | `not executed` | This section — the closer has no shell; sweep deferred to the coordinator |
| lifecycle run records (this release) | `0` | `not executed` | This section — same |

The sweep is **deferred, not performed** — no file was deleted by this session, and every
handoff named above is referenced by a surviving evidence pointer.

## Archive decision

**MOVE** — archive now to `specs/_archive/releases/v0.4.0/`. This closer has no shell: the
`git mv specs/releases/v0.4.0 specs/_archive/releases/v0.4.0` and the `ACTIVE.md` update
(`phase: ARCHIVED`, then `release: none` or the next release) will be **executed by the
coordinator**. `ACTIVE.md` was deliberately not edited by this session. Expect one
`SPEC-DOC-031` warning per non-terminal slug named by the archived SPEC or this CLOSURE
after the move; the next closer counts them post-move, never before.
