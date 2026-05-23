# Closure: Release — cost-and-availability-r2

> **Status:** Draft (template — populate when all TASKS.md tasks are [x] DONE)
> **Release ID:** cost-and-availability-r2
> **Owner:** product-engineer
> **Closed:** YYYY-MM-DD

---

## Summary

<!-- 1–3 paragraphs from the product owner's perspective. -->

## Tasks completed

| Task ID | Description | Final commit |
|---------|-------------|--------------|
| T-R2-01 | Switch Kinesis to ON_DEMAND in all 3 environments | `<sha>` |
| T-R2-02 | Change ECS cluster default capacity provider to FARGATE | `<sha>` |
| T-R2-03 | Align Firehose PRD buffer: 5 MB / 60s | `<sha>` |
| T-R2-04 | Add S3 lifecycle rules for raw/ prefix | `<sha>` |
| T-R2-05 | Assign FARGATE_SPOT to ECS Jobs 1, 2, 3 (if OQ-6 approved) | `<sha>` |
| T-R2-06 | Replace unconditional DynamoDB put_item with conditional_put_item | `<sha>` |
| T-R2-07 | Bump dm-chain-utils version, rebuild Docker image, redeploy ECS | `<sha>` |

---

## Validations

| Description | Command | Evidence |
|-------------|---------|----------|
| Kinesis ON_DEMAND confirmed | `aws kinesis describe-stream-summary --stream-name dm-chain-explorer-mainnet-transactions` | `StreamMode: ON_DEMAND` in stdout |
| ECS cluster default is FARGATE | `aws ecs describe-clusters --clusters dm-chain-explorer` | `defaultCapacityProviderStrategy: FARGATE` |
| Firehose buffer 5MB/60s | `aws firehose describe-delivery-stream --delivery-stream-name dm-chain-explorer-mainnet-transactions-data` | `SizeInMBs: 5, IntervalInSeconds: 60` |
| S3 lifecycle rule active | `aws s3api get-bucket-lifecycle-configuration --bucket dm-chain-explorer-raw-data` | rules for INTELLIGENT_TIERING + GLACIER |
| Semaphore no race condition | Manual concurrency test script | `<sha or stdout>` |
| Cost reduction ≥ 80% on Kinesis | AWS Cost Explorer Kinesis line item | `<screenshot path>` |

---

## Drifts

<!-- Fill in during CLOSURE. -->

---

## Memory updates

- [ ] **T-R2-CL-01** — `specs/memory/tech-stack.html` — create from `tech-stack.md`; reflect:
  - Kinesis `stream_mode = ON_DEMAND` (was PROVISIONED, 1 shard)
  - ECS cluster default: FARGATE (was FARGATE_SPOT)
  - ECS Jobs 1–3: FARGATE_SPOT per-service override (if OQ-6 approved)
  - Firehose PRD buffer: 5 MB / 60s

Memory files NOT migrated in this CLOSURE:
- `specs/memory/constitution.md` — deferred to R4 CLOSURE (OQ-1, OQ-3 pending).
- `specs/memory/product.md` — deferred to R4 CLOSURE.

After HTML atom written:
```bash
mkdir -p specs/_archive/legacy-memory/<UTC-timestamp>
git mv specs/memory/tech-stack.md specs/_archive/legacy-memory/<UTC-timestamp>/
```

---

## Backlog returns

<!-- Items discovered during implementation. -->

---

## Archive decision

**MOVE** — after CLOSURE.md complete and memory atom written:

```bash
git mv specs/releases/cost-and-availability-r2 specs/_archive/releases/cost-and-availability-r2
```

Update `specs/releases/ACTIVE.md`:
```
release: data-quality-r3
phase: TASKS
```
