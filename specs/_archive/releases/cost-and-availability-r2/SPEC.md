# SPEC: cost-and-availability-r2 — Cloud Cost Reduction and Availability Hardening

**Status:** Aprovado
**Owner:** product-engineer
**Priority bucket:** cost > availability (security cleared in R1)
**Generated from:** `.dadaia/reports/dd-chain-explorer/project-manager/2026-05-22T150000Z-mediation-index.html` (Part 2: Decision Matrix)
**Issues covered:** ISSUE-011, 017, 019, 024, 025, 026
**Dependency:** pipeline-restart-r1 must be ARCHIVED before this release begins.

---

## Goal

Reduce recurring cloud costs and eliminate availability risks in the streaming capture layer
by switching Kinesis to ON_DEMAND mode, applying FARGATE Spot strategy for eligible jobs,
fixing the DynamoDB semaphore race condition, aligning Firehose buffer parameters, and adding
S3 lifecycle rules.

## Scope In

### Cost Reduction

- **ISSUE-019** — Switch Kinesis `mainnet-transactions-data` from PROVISIONED 1-shard to
  ON_DEMAND in all 3 environment Terraform configs. Remove PROVISIONED override in PRD
  peripherals. Expected: ~92% cost reduction on Kinesis (~$22/mo → ~$2/mo at current volume).
  (`kinesis/main.tf:49`)

- **ISSUE-024** — Configure S3 Intelligent-Tiering at 30 days + Glacier at 90 days for `raw/`
  prefix on `dm-chain-explorer-raw-data` bucket. Expected: ~60% reduction on aged raw data
  storage cost.
  (`s3/main.tf:41`)

- **ISSUE-025** — Override Firehose buffer in PRD peripherals:
  `firehose_buffer_size_mb = 5`, `firehose_buffer_interval_seconds = 60`.
  Current defaults: 64 MB / 300s cause up to 5-min worst-case latency; spec claims 60s.
  (`kinesis/variables.tf:68`)

- **ISSUE-026** — Migrate ECS Jobs 1, 2, 3 to FARGATE_SPOT capacity provider per-service.
  Jobs 4 and 5 remain On-Demand (semaphore-holding; Spot interruption would cause data loss).
  Expected: ~70% reduction on ECS compute cost for eligible jobs.
  **BLOCKED-BY-OPERATOR-DECISION: OQ-6** — operator must confirm Spot eligibility assignment.

### Availability Hardening

- **ISSUE-011** — Replace unconditional `put_item` in DynamoDB semaphore election with
  `conditional_put_item(ConditionExpression="attribute_not_exists(pk)")` to prevent race
  condition at 6 concurrent replicas. Max 3 retry attempts on collision.
  (`api_keys_manager.py:78–86`)

- **ISSUE-017** — Change ECS cluster default capacity provider from FARGATE_SPOT to FARGATE
  (on-demand). Only Jobs 1–3 get explicit FARGATE_SPOT override (per ISSUE-026 / OQ-6).
  (`ecs.tf:15–22`)

## Scope Out

- Event-time windows in Gold MVs → Release 3 (ISSUE-016)
- Data-contract tests → Release 3 (ISSUE-015)
- Schema evolution strategy → Release 3 (ISSUE-028)
- transactions_lambda Lambda Architecture → Release 3 (ISSUE-031, pending OQ-5)
- UC column descriptions, Genie context → Release 4
- PRD catalog name alignment → Release 4 (pending OQ-1)
- Memory HTML migration for tech-stack.md → CLOSURE of this release

## Blocked Items (operator decision pending)

- **OQ-6** — FARGATE Spot assignment confirmation. SA recommendation: Jobs 1, 2, 3 on Spot;
  Jobs 4, 5 on On-Demand. This SPEC adopts the SA recommendation as default.
  Tasks T-R2-05 and T-R2-06 are `BLOCKED-BY-OPERATOR-DECISION: OQ-6`.

## Success Criteria (Acceptance Gate)

1. Kinesis ON_DEMAND active in all 3 environments; Terraform plan shows `stream_mode = "ON_DEMAND"`.
2. ECS cluster default capacity provider is FARGATE (On-Demand); Jobs 1–3 have explicit
   FARGATE_SPOT service override; Jobs 4–5 have explicit FARGATE override.
3. Firehose PRD buffer: `buffering_size = 5` MB, `buffering_interval = 60` s confirmed in
   Terraform state.
4. S3 lifecycle rule for `raw/` prefix: Intelligent-Tiering at 30d, Glacier at 90d active.
5. DynamoDB semaphore: `conditional_put_item` in `api_keys_manager.py`; manual concurrency test
   with 6 goroutines confirms no race condition.
6. Cost analysis (AWS Cost Explorer): Kinesis line item reduced ≥ 80% month-over-month.

## Dependencies on Other Releases

- **Depends on:** pipeline-restart-r1 ARCHIVED.
- **Enables:** data-quality-r3 (correctness work requires a running pipeline to validate fixes).

## Risks

- OQ-6 unresolved: if operator adjusts Spot eligibility, T-R2-05/T-R2-06 task scope changes.
  Fallback: skip Spot migration entirely (Jobs remain On-Demand); still delivers ISSUE-017 safety fix.
- Kinesis ON_DEMAND switch requires a brief stream interruption (~1 min). Schedule during
  low-traffic window.
- DynamoDB semaphore fix (ISSUE-011) touches `dm-chain-utils` library. Requires library version
  bump + Docker image rebuild + ECS redeploy.

## Memory Files Affected at CLOSURE

- `specs/memory/tech-stack.html` — to be created from `tech-stack.md` during CLOSURE;
  reflect Kinesis ON_DEMAND, ECS Spot strategy, Firehose buffer values.
