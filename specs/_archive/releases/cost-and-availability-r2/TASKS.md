# TASKS: cost-and-availability-r2

**Status:** Aprovado
**Release:** cost-and-availability-r2
**Phase:** TASKS

Work-Packages A and B run in parallel. A2 must complete before A3 (cluster default
before service override). A1, A4, A5 are independent.

---

## Work-Package A — Terraform Infrastructure (devops-engineer)

<!-- Write-set: services/{dev,hml,prd}/ Terraform modules -->

- [ ] T-R2-01 — **Switch Kinesis to ON_DEMAND in all 3 environments** | Owner: devops-engineer | Effort: S
  Evidence: ISSUE-019, DE-S-001, AWS-02, `kinesis/main.tf:49`
  Write-set: `services/dev/01_peripherals/`, `services/hml/04_peripherals/`, `services/prd/04_peripherals/`
  Done: `stream_mode = "ON_DEMAND"` in all 3 env configs; `terraform apply` succeeds in DEV;
        `aws kinesis describe-stream-summary` confirms ON_DEMAND mode in target env.

- [ ] T-R2-02 — **Change ECS cluster default capacity provider to FARGATE** | Owner: devops-engineer | Effort: S
  Evidence: ISSUE-017, AWS-01, `ecs.tf:15–22`
  Write-set: `services/prd/07_ecs/ecs.tf`
  Done: `default_capacity_provider_strategy` uses `FARGATE` (On-Demand) as default.

- [ ] T-R2-03 — **Align Firehose PRD buffer: 5 MB / 60s** | Owner: devops-engineer | Effort: S
  Evidence: ISSUE-025, AWS-02, `kinesis/variables.tf:68`
  Write-set: `services/prd/04_peripherals/` (Firehose buffer variables)
  Done: PRD Firehose delivery stream configured with `SizeInMBs = 5`, `IntervalInSeconds = 60`;
        confirmed via `aws firehose describe-delivery-stream`.

- [ ] T-R2-04 — **Add S3 lifecycle rules for raw/ prefix** | Owner: devops-engineer | Effort: S
  Evidence: ISSUE-024, DE-C-005, `s3/main.tf:41`
  Write-set: `services/prd/04_peripherals/` (S3 raw bucket config)
  Done: PRD raw bucket has lifecycle rule: INTELLIGENT_TIERING at 30d, GLACIER at 90d for
        `raw/` prefix; confirmed via `aws s3api get-bucket-lifecycle-configuration`.

- [ ] T-R2-05 — **Assign FARGATE_SPOT to ECS Jobs 1, 2, 3** | Owner: devops-engineer | Effort: S
  Evidence: ISSUE-026, AWS-01, cost table §4.4
  Write-set: `services/prd/07_ecs/` (service definitions for jobs 1–3)
  Decision (grill 2026-05-22): Jobs 1,2,3 → FARGATE_SPOT; Jobs 4,5 → FARGATE On-Demand. Job 4 holds DynamoDB semaphore (APIKeysManager) so must remain On-Demand. Job 5 is the gold_to_dynamodb Lambda trigger — keep On-Demand for low-latency consistency.
  Done: Jobs 1–3 service definitions have `capacityProviderStrategy = FARGATE_SPOT`;
        Jobs 4–5 have explicit `FARGATE` (On-Demand) override.

---

## Work-Package B — Application Code (software-engineer-python)

<!-- Write-set: utils/dm_chain_utils/api_keys_manager.py -->

- [ ] T-R2-06 — **Replace unconditional DynamoDB put_item with conditional_put_item** | Owner: software-engineer-python | Effort: S
  Evidence: ISSUE-011, PATTERN-01, `api_keys_manager.py:78–86`
  Write-set: `utils/dm_chain_utils/api_keys_manager.py`
  Done: `put_item` uses `ConditionExpression="attribute_not_exists(pk)"`;
        retry loop with max 3 attempts on `ConditionalCheckFailedException`;
        manual concurrency test (6 goroutines) confirms no duplicate key assignment.

- [ ] T-R2-07 — **Bump dm-chain-utils version, rebuild Docker image, redeploy ECS** | Owner: devops-engineer | Effort: S
  Evidence: ISSUE-011 (follow-on task after T-R2-06)
  Write-set: `VERSION`, Dockerfile (no content change — rebuild trigger), ECS task definition
  Depends on: T-R2-06 complete
  Done: `dm-chain-utils` version bumped; Docker image rebuilt and pushed to ECR;
        ECS tasks running new image version confirmed via `aws ecs describe-tasks`.

---

## Work-Package C — KMS Audit (devops-engineer)

<!-- Write-set: services/prd/ (Terraform only) -->

- [ ] T-R2-NEW-1 — **Audit KMS bill source and enforce Public-Default Encryption policy** | Owner: devops-engineer | Effort: S
  Evidence: OQ-5/OQ-NEW-1 resolved 2026-05-22; operator reports unexpected KMS costs breaking free-tier
  Write-set: `services/prd/` (Terraform only — no KMS keys to create; remove any that exist)
  Decision (grill 2026-05-22): Public-Default Encryption policy adopted — no customer KMS keys; S3=AES256 (SSE-S3); DynamoDB=AWS-owned; Kinesis=SSE disabled (public Ethereum data). Identify and remove any console-created customer KMS keys or CMKs attached to Databricks/Firehose.
  Done: `aws kms list-keys` returns no customer-managed keys in sa-east-1 that are not shared-account keys; KMS line item absent from cost explorer for the following billing period; policy documented in constitution.md.

---

## CLOSURE Tasks (product-engineer — CLOSURE phase only)

- [ ] T-R2-CL-01 — **Convert specs/memory/tech-stack.md to specs/memory/tech-stack.html**
  Owner: product-engineer | Phase: CLOSURE only
  Done: `specs/memory/tech-stack.html` exists; reflects Kinesis ON_DEMAND, ECS Spot strategy,
        Firehose buffer values updated from this release.

---

## Task Summary

| ID | Work-Package | Owner | Effort | Issue | Blocked |
|----|-------------|-------|--------|-------|---------|
| T-R2-01 | A — Terraform | devops-engineer | S | ISSUE-019 | No |
| T-R2-02 | A — Terraform | devops-engineer | S | ISSUE-017 | No |
| T-R2-03 | A — Terraform | devops-engineer | S | ISSUE-025 | No |
| T-R2-04 | A — Terraform | devops-engineer | S | ISSUE-024 | No |
| T-R2-05 | A — Terraform | devops-engineer | S | ISSUE-026 | No (OQ-6 resolved) |
| T-R2-06 | B — Code | software-engineer-python | S | ISSUE-011 | No |
| T-R2-07 | B — Redeploy | devops-engineer | S | ISSUE-011 follow-on | T-R2-06 |
| T-R2-NEW-1 | C — KMS Audit | devops-engineer | S | OQ-NEW-1 | No |
| T-R2-CL-01 | CLOSURE | product-engineer | M | Memory migration | CLOSURE phase |

**Total implementation tasks:** 8
**Total CLOSURE tasks:** 1
**Grand total:** 9
