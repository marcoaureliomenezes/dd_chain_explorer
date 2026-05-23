# PLAN: cost-and-availability-r2

**Status:** Aprovado
**Release:** cost-and-availability-r2
**Owner:** product-engineer
**Source:** SPEC.md (this release) + PM mediation matrix Part 2

---

## Strategy

Two parallel work-packages: Terraform infrastructure changes (devops-engineer) and
application code changes (software-engineer-python). Terraform changes require apply
in order per PRD module dependency. Code changes to `dm-chain-utils` require library
version bump and image rebuild.

```
Work-Package A: Terraform infra changes (devops-engineer)
  ├── A1: Kinesis ON_DEMAND (all envs)
  ├── A2: ECS cluster capacity provider default fix
  ├── A3: ECS Jobs 1–3 FARGATE_SPOT service override (post OQ-6)
  ├── A4: Firehose PRD buffer alignment
  └── A5: S3 raw/ lifecycle rules

Work-Package B: Application code changes (software-engineer-python)
  └── B1: DynamoDB semaphore conditional put (dm-chain-utils + ECS redeploy)
```

---

## Work-Package A: Terraform Infrastructure Changes

**Owner:** devops-engineer

### A1 — Kinesis ON_DEMAND (ISSUE-019)

Files: `services/{dev,hml,prd}/*/kinesis/main.tf` (or `kinesis/variables.tf:49`)
Change `stream_mode` to `"ON_DEMAND"` in all 3 environment configurations.
Remove any `shard_count` or PROVISIONED override in PRD peripherals.

Apply order:
1. DEV: `make tf_apply_dev_peripherals` (local state, safe)
2. HML: Applied in CI run (ephemeral — no persistent impact)
3. PRD: `terraform apply` via CI/CD with `production` approval gate

**Cost impact:** ~$22/mo → ~$2/mo on Kinesis data stream costs.

### A2 — ECS cluster default to On-Demand (ISSUE-017)

File: `services/prd/07_ecs/ecs.tf:15–22`
Change `default_capacity_provider_strategy`:
```hcl
default_capacity_provider_strategy {
  capacity_provider = "FARGATE"
  weight            = 1
}
```
Rationale: Jobs 4 and 5 hold DynamoDB semaphore — Spot interruption during lock
hold causes semaphore orphan, stalling all 6 Job-4 replicas.

### A3 — FARGATE_SPOT for Jobs 1, 2, 3 (ISSUE-026) — BLOCKED-BY-OPERATOR-DECISION: OQ-6

Files: ECS service definitions for `mined-blocks-watcher`, `orphan-blocks-watcher`,
`block-data-crawler` in `services/prd/07_ecs/`.
Add per-service capacity provider override:
```hcl
capacity_provider_strategy {
  capacity_provider = "FARGATE_SPOT"
  weight            = 1
}
```
Rationale: Jobs 1–3 are stateless watchers/crawlers. SQS provides durability; if a Spot
instance is reclaimed, the job restarts and resumes from SQS. No semaphore held.

**BLOCKED-BY-OPERATOR-DECISION: OQ-6** — Confirm Jobs 1, 2, 3 may use Spot.

### A4 — Firehose PRD buffer alignment (ISSUE-025)

File: `services/prd/04_peripherals/` or `kinesis/variables.tf:68`
For PRD target, override:
```hcl
firehose_buffer_size_mb       = 5
firehose_buffer_interval_seconds = 60
```
Rationale: Current 64 MB / 300s defaults mean worst-case 5-min latency, violating the
60s latency spec. 5 MB / 60s delivers data within spec at acceptable cost.

### A5 — S3 raw/ lifecycle rules (ISSUE-024)

File: `services/{prd,dev,hml}/*/s3/main.tf` (raw bucket)
Add lifecycle rule for `raw/` prefix:
```hcl
transition {
  days          = 30
  storage_class = "INTELLIGENT_TIERING"
}
transition {
  days          = 90
  storage_class = "GLACIER"
}
```
This does not affect DEV/HML (small volumes; cost-neutral). Apply to PRD raw bucket only.

---

## Work-Package B: DynamoDB Semaphore Fix (ISSUE-011)

**Owner:** software-engineer-python
**File:** `utils/dm_chain_utils/api_keys_manager.py:78–86`

Replace unconditional `put_item`:
```python
# Before (race condition)
table.put_item(Item={"pk": "SEMAPHORE", "sk": key_name, "ttl": ttl})

# After (conditional — atomic)
table.put_item(
    Item={"pk": "SEMAPHORE", "sk": key_name, "ttl": ttl},
    ConditionExpression="attribute_not_exists(pk)"
)
```
Add retry loop: max 3 attempts with 100ms backoff on `ConditionalCheckFailedException`.

After code change:
1. Bump `dm-chain-utils` version (patch release)
2. Rebuild Docker image: `make build_stream`
3. Update Lambda layer if `api_keys_manager` is used in Lambda
4. ECS redeploy: `make deploy_prd_stream` (or CI workflow)

---

## Architecture Decisions (this release)

- **Kinesis ON_DEMAND vs PROVISIONED** — ON_DEMAND eliminates idle shard cost at low volume.
  The pipeline currently runs below 1 MB/s (1-shard capacity). If PRD throughput exceeds
  2 shards equivalent (2 MB/s), consider reverting with explicit shard count.
- **ECS Spot strategy** — cluster default stays FARGATE (safe). Only Jobs 1–3 opt into Spot
  via explicit service-level override. This allows gradual rollback per service.
- **Semaphore conditional put** — `attribute_not_exists(pk)` is atomic in DynamoDB. A lost
  race (another replica claimed the key) returns `ConditionalCheckFailedException` which is
  handled by the retry loop. After 3 failures the replica backs off and tries the next key.

## BLOCKED-BY-OPERATOR-DECISION Items

| OQ | Impact | Default |
|----|--------|---------|
| OQ-6 | Confirm FARGATE_SPOT eligibility for Jobs 1, 2, 3 | SA recommendation (adopt) |

## Validation Plan

1. `terraform plan` on PRD kinesis module — confirm `stream_mode = "ON_DEMAND"` in diff.
2. `aws kinesis describe-stream-summary --stream-name dm-chain-explorer-mainnet-transactions` —
   confirm `StreamModeDetails.StreamMode = ON_DEMAND` after apply.
3. `aws ecs describe-services` — confirm Jobs 4+5 `capacityProviderStrategy = FARGATE`.
4. `aws ecs describe-services` — confirm Jobs 1–3 `capacityProviderStrategy = FARGATE_SPOT`
   (only if OQ-6 approved).
5. `aws firehose describe-delivery-stream` — confirm `BufferingHints.SizeInMBs = 5`,
   `IntervalInSeconds = 60`.
6. `aws s3api get-bucket-lifecycle-configuration --bucket dm-chain-explorer-raw-data` —
   confirm Intelligent-Tiering and Glacier rules present.
7. Semaphore test: run 6 concurrent `api_keys_manager.acquire()` calls in DEV; verify
   no duplicate key assignment and no crash on collision.
