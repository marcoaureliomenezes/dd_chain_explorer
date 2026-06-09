# Closure: Release — cost-and-availability-r2

> **Status:** Aprovado
> **Release ID:** cost-and-availability-r2
> **Forensic verdict:** ABANDONED
> **Owner:** product-engineer
> **Closed (forensic):** 2026-06-08
> **Authored by:** T-R5-C1 forensic investigation

---

## Summary

This release was planned to reduce recurring cloud costs and eliminate availability risks
in the streaming capture layer. Based on forensic evidence — file state in the current
working tree and absence of any implementation commits in git history — **none of the
eight implementation tasks (T-R2-01 through T-R2-07, T-R2-NEW-1) was implemented**.

The CLOSURE.md was previously a blank template with literal `<sha>` placeholders. This
document records the ground truth for each task based on evidence gathered during
audit-remediation-r5 (T-R5-C1).

The release is classified ABANDONED in full. No Terraform changes, no application code
changes, and no KMS audit were applied. The infrastructure remains in its pre-r2 state:
Kinesis PROVISIONED, ECS cluster FARGATE_SPOT default, Firehose at default buffers,
S3 lifecycle without the required `raw/` prefix and using STANDARD_IA instead of
INTELLIGENT_TIERING, DynamoDB semaphore still using unconditional `put_item`.

This release should be moved to `specs/_archive/releases/cost-and-availability-r2/`.
The open issues (ISSUE-011, 017, 019, 024, 025, 026, and OQ-NEW-1) remain unresolved
and should be promoted to `specs/backlog/candidates.md` for the next planning round.

---

## Tasks completed

None. All tasks are ABANDONED (no implementation evidence found).

| Task ID | Description | Forensic verdict | Evidence |
|---------|-------------|-----------------|---------|
| T-R2-01 | Switch Kinesis to ON_DEMAND in all 3 environments | ABANDONED | `services/dev/01_peripherals/main.tf`, `services/hml/04_peripherals/main.tf`, `services/prd/04_peripherals/peripherals.tf` all still declare `stream_mode = "PROVISIONED"`. No git commit evidence found. |
| T-R2-02 | Change ECS cluster default capacity provider to FARGATE | ABANDONED | `services/prd/07_ecs/ecs.tf` lines 19–22 still declare `capacity_provider = "FARGATE_SPOT"` as default. No commit found. |
| T-R2-03 | Align Firehose PRD buffer: 5 MB / 60s | ABANDONED | `services/prd/04_peripherals/peripherals.tf` kinesis module call has no `firehose_buffer_size_mb` or `firehose_buffer_interval_seconds` overrides; module defaults apply (64 MB / 300s). The cloudwatch_logs Firehose in the same file has `firehose_buffer_size_mb = 5` but `firehose_buffer_interval_seconds = 300` (not 60s) and targets log delivery, not the Kinesis data-stream Firehose. |
| T-R2-04 | Add S3 lifecycle rules for raw/ prefix | ABANDONED (diverged) | `services/prd/04_peripherals/peripherals.tf` `module.s3_raw` has lifecycle rules: STANDARD_IA at 30d and GLACIER at 90d on prefix `""` (entire bucket). Spec required INTELLIGENT_TIERING (not STANDARD_IA) on prefix `raw/` specifically. Origin of these rules is unknown; they may predate r2 planning or be a partial manual change. No git commit attributable to this task. |
| T-R2-05 | Assign FARGATE_SPOT to ECS Jobs 1, 2, 3 | ABANDONED | All 5 ECS services in `services/prd/07_ecs/ecs.tf` use `launch_type = "FARGATE"` with no per-service capacity_provider_strategy overrides. No commit found. |
| T-R2-06 | Replace unconditional DynamoDB put_item with conditional_put_item | ABANDONED | `utils/src/dm_chain_utils/api_keys_manager.py` `check_api_key_request()` (line 37) still calls `self.dynamodb.put_item(...)` unconditionally — no `ConditionExpression` parameter. No retry loop present. |
| T-R2-07 | Bump dm-chain-utils version, rebuild Docker image, redeploy ECS | ABANDONED | Depends on T-R2-06 which was not implemented. No version bump or rebuild evidence. |
| T-R2-NEW-1 | Audit KMS bill source and enforce Public-Default Encryption policy | ABANDONED | No Terraform changes to `services/prd/` related to KMS policy. No policy documentation in `specs/memory/constitution.md`. No commit found. |

---

## Validations

No validations are possible: no implementation was done. The table below records the
expected validation commands from the original template alongside the forensic finding.

| Description | Command | Forensic finding |
|-------------|---------|-----------------|
| Kinesis ON_DEMAND active | `aws kinesis describe-stream-summary --stream-name ...` | Not applicable — Kinesis still PROVISIONED in Terraform |
| ECS cluster default FARGATE | `aws ecs describe-clusters --clusters dm-chain-explorer` | Not applicable — ecs.tf still declares FARGATE_SPOT default |
| Firehose buffer 5MB/60s | `aws firehose describe-delivery-stream ...` | Not applicable — no override in Terraform config |
| S3 lifecycle rule active | `aws s3api get-bucket-lifecycle-configuration ...` | Partial: lifecycle rules exist but use STANDARD_IA on `""` prefix, not INTELLIGENT_TIERING on `raw/` |
| Semaphore no race condition | Manual concurrency test | Not applicable — conditional put_item not implemented |
| Cost reduction >= 80% | AWS Cost Explorer | Not applicable — no infrastructure changes applied |

---

## Drifts

### drift-r2-s3-lifecycle-partial

**Description:** The PRD raw S3 bucket (`services/prd/04_peripherals/peripherals.tf`,
`module.s3_raw`) has lifecycle rules (STANDARD_IA at 30d, GLACIER at 90d) on the entire
bucket (prefix `""`). The spec required INTELLIGENT_TIERING on the `raw/` prefix. It is
unknown whether these rules were pre-existing or partially applied outside the r2
lifecycle. They do not match the acceptance criterion.

**Resolution:** The divergence is documented here. The correct configuration (INTELLIGENT_TIERING
at 30d on `raw/` prefix) should be applied in a future release. The current rules provide
some cost benefit but differ from the spec.

**Memory updates:** None — r2 was abandoned; memory was not updated.

---

## Memory updates

No memory updates were made during this release. T-R2-CL-01 (create `specs/memory/tech-stack.html`)
was not executed.

- `specs/memory/tech-stack.md` — no change: r2 was abandoned; tech-stack reflects pre-r2 state.

---

## Backlog returns

The following open issues from r2 remain unresolved and should be promoted to
`specs/backlog/candidates.md` for the next planning round:

- `backlog/candidates.md` ← ISSUE-019: Switch Kinesis `mainnet-transactions-data` to ON_DEMAND
- `backlog/candidates.md` ← ISSUE-017: Change ECS cluster default capacity provider to FARGATE
- `backlog/candidates.md` ← ISSUE-025: Align Firehose PRD buffer to 5 MB / 60s
- `backlog/candidates.md` ← ISSUE-024: Add S3 lifecycle rules for `raw/` prefix (INTELLIGENT_TIERING)
- `backlog/candidates.md` ← ISSUE-026: FARGATE_SPOT per-service override for ECS Jobs 1–3
- `backlog/candidates.md` ← ISSUE-011: Replace unconditional DynamoDB put_item with conditional_put_item
- `backlog/candidates.md` ← OQ-NEW-1: KMS audit and Public-Default Encryption policy

Note: promotion to backlog is the responsibility of project-manager, not product-engineer.

---

## Archive decision

**MOVE** — this release is fully abandoned. Move to archive:

```
git mv specs/releases/cost-and-availability-r2 specs/_archive/releases/cost-and-availability-r2
```

`specs/releases/ACTIVE.md` currently points at `audit-remediation-r5` — do not modify it.
This release is not referenced by ACTIVE.md and can be archived independently.
