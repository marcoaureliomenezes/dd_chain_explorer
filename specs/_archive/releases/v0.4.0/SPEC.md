# SPEC — Release v0.4.0 — Capture Layer Retirement

> **Status:** Aprovado
> **Release ID:** v0.4.0
> **Owner:** product-engineer
> **Created:** 2026-06-22
> **Approved:** 2026-06-22 (spec review — architect + qa APPROVE-WITH-CHANGES, findings folded)
> **Method (operator-locked):** Through Terraform (SDD) — IaC stops declaring the
> resources; live resources are removed via the informed-gate `terraform apply`
> (config-diff destroy) and a targeted `terraform destroy` for the fully-retired
> producer task-defs. NOT raw CLI.
> **Scope (operator-locked):** Retire the WHOLE capture layer — streaming
> peripherals (Kinesis/Firehose/SQS) + the ECS capture *producer* jobs + the
> CloudWatch→Firehose app-log shipping. S3 stays.

---

## 1. Problem

The data-capture layer has been decoupled out of dd-chain-explorer into the separate
`dd-chain-capture` project (VPS + Docker Swarm + Kafka + Redis). The AWS streaming
capture resources in this repo are now dead weight: they still exist in `dev` and `prd`
live infrastructure, they cost money, and their Terraform declarations invite accidental
recreation.

The operator order is explicit: **"DESTROY ALL KINESIS, FIREHOSE AND SQS FOR DEV, HML
AND PROD. WE SHOULD NOT HAVE IT IN OUR INFRASTRUCTURE ANYMORE."** S3 is the integration
boundary between the two projects and MUST live.

Because the IaC is coupled, retiring the resources requires retiring everything that
references them: the 5 ECS capture *producer* task-definitions/services (which inject
`KINESIS_STREAM_*`, `FIREHOSE_STREAM_*`, `SQS_QUEUE_URL_*`, `CLOUDWATCH_LOG_GROUP` env
vars from the peripherals remote state), and the CloudWatch→Firehose app-log subscription
pipeline (which shares the `cloudwatch_logs` module with the kept log group). Stop
declaring them, plan the destroy, and apply.

---

## 2. Live AWS resources to be destroyed

Region `sa-east-1`, account `016098071081`.

| Type | Names | Env |
|------|-------|-----|
| Kinesis Data Stream (2) | `mainnet-transactions-data-dev`, `mainnet-transactions-data-prd` | dev, prd |
| Firehose (8) | `firehose-mainnet-{blocks,transactions,transactions-decoded}-data-{dev,prd}` + `firehose-app-logs-{dev,prd}` | dev, prd |
| SQS (8) | `mainnet-{mined-blocks-events,block-txs-hash-id}-{dev,prd}` + their 4 DLQs | dev, prd |
| ECS capture producer task-defs + services (5×2) | `dm-{mined-blocks-watcher,orphan-blocks-watcher,block-data-crawler,mined-txs-crawler,txs-input-decoder}` | prd (dev has no ECS) |
| Firehose CW-logs IAM roles/policies (4) | `dm-{dev,prd}-firehose-cw-logs-role`/`-policy`, `dm-{dev,prd}-cw-to-firehose-role`/`-policy` + subscription filters | dev, prd |

**HML has nothing live** — only `dev`/`prd` peripherals were ever applied. The
`hml/04_peripherals` kinesis/sqs/firehose code exists but was never deployed. Code
cleanup still applies to hml so the IaC is internally consistent and cannot be re-applied.

---

## 3. Scope — IN

### 3.1 Terraform code changes

**Streaming peripherals — remove kinesis + sqs, strip firehose from cloudwatch_logs:**

| Stack | Change |
|-------|--------|
| `services/dev/01_peripherals/main.tf` | Remove `module "kinesis"` and `module "sqs"`; set `firehose_enabled = false` on `module "cloudwatch_logs"` (keeps the log group, destroys the firehose stream + 2 IAM roles/policies + subscription filter). |
| `services/hml/04_peripherals/main.tf` | Same removals (code-only; nothing live). |
| `services/prd/04_peripherals/peripherals.tf` | Same removals. |
| `services/{dev/01_peripherals,hml/04_peripherals,prd/04_peripherals}/outputs.tf` | Remove the kinesis/sqs/firehose outputs (`kinesis_stream_*`, `firehose_*`, `sqs_*`). KEEP `cloudwatch_log_group_name`/`_arn`, all `*_bucket_*` (S3), and `dynamodb_table_*`. |

> **Firehose-strip mechanism (recommended).** The `cloudwatch_logs` module already guards
> every firehose resource with `count = var.firehose_enabled ? 1 : 0`. Flipping
> `firehose_enabled = false` at each call site destroys exactly the firehose stream, the
> `firehose_logs`/`cw_to_firehose` IAM roles+policies, and the `to_firehose` subscription
> filter — while keeping `aws_cloudwatch_log_group.this`. This is lower-risk and more
> idempotent than editing the module body. Editing the module to delete the firehose
> resources outright is the alternative; see OQ-2.

**ECS capture producer jobs — surgical removal (NOT whole-stack destroy):**

| Stack | Change |
|-------|--------|
| `services/prd/07_ecs/ecs.tf` | Remove the 5 capture producer `aws_ecs_task_definition` + 5 `aws_ecs_service` resources (`mined_blocks_watcher`, `orphan_blocks_watcher`, `block_data_crawler`, `mined_txs_crawler`, `txs_input_decoder`). KEEP the ECS cluster, capacity providers, `/ecs/...` log group, service-discovery namespace, and **both ECR repositories** (`onchain-stream-txs`, `onchain-batch-txs` — account-level, referenced by surviving batch workload; see OQ-1). |
| `services/prd/07_ecs/locals.tf` + `services/prd/07_ecs/main.tf` | Remove the `common_stream_env` local (consumed only by the 5 removed task-defs) and the `data "terraform_remote_state" "kinesis_sqs"` source it reads. Also remove the now-orphaned `data "terraform_remote_state" "dynamodb"` source in `main.tf` (line 55) — its sole consumer is `common_stream_env` (`locals.tf:36`), so it dangles once the producers go. Remove the stale `docs/migrar_kafka.md` comment reference (file does not exist on disk). |

**Lambda — strip the removed remote-state reference (lambdas survive):**

| Stack | Change |
|-------|--------|
| `services/prd/06_lambda/lambda_contracts_ingestion.tf` | The `CLOUDWATCH_LOG_GROUP` env var (line 119) reads `data.terraform_remote_state.kinesis_sqs.outputs.cloudwatch_log_group_name`. The log-group output SURVIVES (only firehose pieces are removed), so this reference can stay valid IF the peripherals stack keeps exporting `cloudwatch_log_group_name`. Confirm the remote-state alias name still resolves; the `contracts_ingestion` lambda is NOT capture and must keep planning. |
| `services/dev/02_lambda/main.tf` | Reads `data.terraform_remote_state.peripherals.outputs.{dynamodb_table_*,ingestion_bucket_*}` only — none of these are removed. `gold_to_dynamodb` lambda is NOT capture and must keep planning. Expected: no change required; verify plan is clean. |

**Orphaned modules — delete for cleanliness:**

| Path | Change |
|------|--------|
| `services/modules/kinesis/` | Delete the module directory once no stack references it. |
| `services/modules/sqs/` | Delete the module directory once no stack references it. |
| `scripts/ci/stack_map.json` | Update `modules` arrays for `dev/peripherals`, `hml/peripherals`, `prd/peripherals` to drop `kinesis`, `sqs` (and remove firehose coupling). Keeps single-source map honest. This file feeds `changed_stacks.py` / `plan_on_pr.yml` change detection — editing it is what makes the post-apply CI idempotency check (acceptance #2) honest. |
| `scripts/ci/destroy_env.sh` | Update `S3_PRESERVED_TARGETS` (line 73) — it lists `-target=module.kinesis -target=module.sqs`, which will error once those modules are gone. Remove ONLY those two dead targets; KEEP `-target=module.dynamodb -target=module.cloudwatch_logs`. Add a warning comment that this script is a **whole-env teardown only** and is NOT to be used for the capture retirement (OQ-3). |

> **Stale `services/<env>/<n>_peripherals/outputs.tf` are NOT symmetric — remove exactly
> what each declares.** `prd/04_peripherals/outputs.tf` and `hml/04_peripherals/outputs.tf`
> declare the full set (`kinesis_stream_names`, `kinesis_stream_arns`, `firehose_arns`,
> `firehose_direct_put_stream_names`, `sqs_queue_urls`, `sqs_queue_arns`, `sqs_dlq_arns`).
> `dev/01_peripherals/outputs.tf` declares a SMALLER set — it has **no** `firehose_arns`
> and **no** `cloudwatch_log_group_arn`; it has `firehose_direct_put_stream_names`,
> `kinesis_stream_*`, `sqs_queue_*` (no `sqs_dlq_arns`). Each task removes precisely the
> kinesis/sqs/firehose outputs that its own stack declares — see TASKS T-C.2/T-C.3/T-C.4.

> **File-name note:** `prd` peripherals modules live in `peripherals.tf`; `dev` and `hml`
> peripherals modules live in `main.tf`. The TASKS write sets reflect this exactly.

### 3.2 Orphan operational tooling (the "streams come back" regression vector)

Several operator scripts and integration tests still reference the 5 capture producer
ECS services by name. These are the most concrete way the destroyed streams come back or
the change drifts. They must be cleaned in the same change set:

| Path | Change |
|------|--------|
| `scripts/prod_resume.sh` | Contains `ECS_PROD_COUNTS` (`dm-mined-blocks-watcher`=1 … `dm-txs-input-decoder`) and `aws ecs update-service --desired-count` — it **rescales the deleted producers up**. Remove the 5 producer entries / the ECS rescale block (its purpose disappears with the producers). |
| `scripts/prod_standby.sh` | Mirror of resume (scales producers to 0). Remove the producer references. |
| `scripts/prod_ecs_logs.py` | Tails the 5 producer service logs. Remove the producer references. |
| `scripts/{hml_integration_test,hml_integration_test_optimized,dev_integration_test}.sh`, `scripts/ci/hml_teardown.sh` | Reference the 5 producers / streaming flow. Strip the capture-producer references so the suites do not assert against destroyed resources. |

### 3.3 Live-resource removal (execution — operator-gated)

Executed via the repo's existing CI workflows under OIDC role-assumption, per the
mechanism in §6. The final mutating execution is a single operator-gated task (T-4.1).

---

## 4. Scope — OUT (must NOT be touched/destroyed)

- All **S3 buckets** (raw, lakehouse, databricks, dev-ingestion) — the integration boundary.
- All **DynamoDB tables** (`dm-chain-explorer`, `dm-chain-explorer-dev`) and the
  Terraform state lock table `dm-chain-explorer-terraform-lock`.
- All **CloudWatch log GROUPS** (`aws_cloudwatch_log_group.this`, `/ecs/...`).
- The Terraform **state bucket** `dm-chain-explorer-terraform-state`.
- The **non-capture lambdas**: `gold_to_dynamodb` (dev), `contracts_ingestion` (prd).
- The ECS **cluster**, capacity providers, service-discovery namespace, and **ECR repos**.
- **VPC**, **IAM** (OIDC roles), **Databricks** (all stacks), medallion/serving layers.
- The `dd-chain-capture` project (separate repo — not in scope).

---

## 5. Acceptance criteria

All AWS CLI commands below are for an **irreversible production op** — they are written
copy-pasteable with explicit `--region sa-east-1` and the per-env OIDC role context
assumed before running. "Expected" states the exact pass condition.

**AC-0 — Producer quiescence gate (PRE-destroy, mandatory).** Before any apply that
destroys kinesis/sqs in an env, re-verify the 5 capture producer ECS services are scaled
down (no live writer racing a destroyed target):

```bash
aws ecs describe-services --region sa-east-1 --cluster dm-chain-explorer-ecs \
  --services dm-mined-blocks-watcher dm-orphan-blocks-watcher dm-block-data-crawler \
             dm-mined-txs-crawler dm-txs-input-decoder \
  --query 'services[].{n:serviceName,desired:desiredCount,running:runningCount}'
```
Expected: every service `desired=0` and `running=0` (or the service already absent if
07_ecs applied first). Note: `scripts/prod_resume.sh` can rescale these UP — confirm it is
not run during the window (and is cleaned per §3.2).

**AC-1 — Live capture resources GONE** (run under both dev and prd role contexts):

```bash
aws kinesis list-streams --region sa-east-1 \
  --query "StreamNames[?contains(@,'mainnet-transactions-data')]"
aws firehose list-delivery-streams --region sa-east-1 \
  --query "DeliveryStreamNames[?starts_with(@,'firehose-mainnet-') || starts_with(@,'firehose-app-logs-')]"
aws sqs list-queues --region sa-east-1 \
  --queue-name-prefix mainnet- --query 'QueueUrls'
```
Expected: each returns `[]`/null. **Also GONE** (not just the streams): the firehose
CW-logs IAM roles/policies `dm-{dev,prd}-firehose-cw-logs-role`/`-policy`,
`dm-{dev,prd}-cw-to-firehose-role`/`-policy`; the `dm-{dev,prd}-logs-to-firehose`
subscription filter; and the kinesis-module firehose delivery IAM role. Verify:
```bash
aws iam list-roles --query "Roles[?contains(RoleName,'firehose') && contains(RoleName,'dm-')].RoleName"
aws logs describe-subscription-filters --region sa-east-1 \
  --log-group-name /apps/dm-chain-explorer-prd --query 'subscriptionFilters[].name'
```
Expected: no `dm-*firehose*`/`cw-to-firehose` roles; subscription-filter list empty.

**AC-2 — Terraform plan idempotent** on every touched stack: a second `terraform plan`
immediately after apply shows `No changes` for `dev/01_peripherals`, `hml/04_peripherals`,
`prd/04_peripherals`, `prd/07_ecs`, `prd/06_lambda`, `dev/02_lambda`. Local plan-clean is
**necessary but not sufficient** — the real idempotency gate is AC-7.

**AC-3 — S3 / DynamoDB / log-groups intact** post-apply:
```bash
aws s3 ls --region sa-east-1 | grep dm-chain-explorer
aws dynamodb list-tables --region sa-east-1 \
  --query "TableNames[?starts_with(@,'dm-chain-explorer')]"
aws logs describe-log-groups --region sa-east-1 \
  --log-group-name-prefix /apps/dm-chain-explorer --query 'logGroups[].logGroupName'
```
Expected: all S3 buckets present; `dm-chain-explorer` + `dm-chain-explorer-dev` present;
`/apps/dm-chain-explorer-{dev,prd}` + `/ecs/dm-chain-explorer*` log groups present.

**AC-4 — Non-capture lambdas still FUNCTION (not existence-only).** `contracts_ingestion`
(prd) and `gold_to_dynamodb` (dev) plan with no errors AND still invoke successfully:
```bash
aws lambda get-function --region sa-east-1 --function-name dm-chain-explorer-contracts-ingestion
# functional: confirm a recent successful invocation (or run a controlled test invoke)
aws logs filter-log-events --region sa-east-1 \
  --log-group-name /aws/lambda/dm-chain-explorer-contracts-ingestion \
  --start-time $(( ($(date +%s) - 7200) * 1000 )) --query 'events[].message' --max-items 5
```
Expected: function present; a recent successful invocation (or a clean test invoke).
Apply the same to `gold_to_dynamodb`.

**AC-5 — Surviving batch ECS workload still runs.** The batch workload that shares the
cluster + `onchain-batch-txs` ECR is unaffected:
```bash
aws ecs list-services --region sa-east-1 --cluster dm-chain-explorer-ecs
aws ecr describe-repositories --region sa-east-1 \
  --query "repositories[?contains(repositoryName,'onchain-')].repositoryName"
```
Expected: cluster intact; both `onchain-stream-txs` + `onchain-batch-txs` ECR repos
present; the surviving batch service (if any deployed) still RUNNING.

**AC-6 — No orphan refs / modules / tooling.** No `data "terraform_remote_state"` or
`.outputs.<removed>` reference to a deleted kinesis/sqs/firehose output (or the orphaned
07_ecs `dynamodb` remote-state source) remains in any `.tf`; `terraform validate` passes
on every touched stack; `services/modules/{kinesis,sqs}` deleted; `stack_map.json` and
`destroy_env.sh` no longer name them; the `docs/migrar_kafka.md` comment is gone; and the
5 producers are no longer referenced in `scripts/prod_resume.sh`, `scripts/prod_standby.sh`,
`scripts/prod_ecs_logs.py`, or the integration tests (`grep -rn` returns nothing).

**AC-7 — Real CI idempotency POST-live-apply (the authoritative idempotency gate).**
After the live apply, `drift_detection.yml` shows **zero drift** and `plan_on_pr.yml` is
**clean** on `develop`. Because WS-D edits the peripherals `modules` arrays consumed by
`changed_stacks.py`/`stack_map.json`, this is the gate that proves the change is coherent
end-to-end — local `terraform plan` clean alone does not satisfy this AC.

**AC-8 — CI hygiene green.** `terraform fmt -check -recursive`, `terraform validate`,
`actionlint` (if any workflow touched), and `bash -n` on the edited shell scripts pass.

---

## 6. Ordering safety — how it actually works

> **Correction (architect review).** A single `deploy_cloud_infra.yml prd` dispatch does
> NOT let us hand-order stacks ecs-first/peripherals-last. `deploy_env.sh` applies in the
> **`scripts/ci/stack_map.json` dependency order**: `vpc → peripherals → iam → lambda →
> ecs → databricks`. So peripherals is applied **before** ecs/lambda — the inverse of any
> manual "destroy the consumer first" sequence. Ordering safety therefore does NOT come
> from a manual stack sequence. It comes from two structural facts:

1. **Single merged change set removes every consumer's reference in the same commit.**
   Because the producer task-defs + their `common_stream_env`/`kinesis_sqs` remote-state
   source (07_ecs) and the lambda's removed-output references are deleted in the SAME
   merged change set as the peripherals outputs, **no stack ever plans against a vanished
   output**. When peripherals applies first and drops the kinesis/sqs/firehose outputs,
   the only surviving consumer reference (the lambda's `cloudwatch_log_group_name`) still
   resolves because that output is KEPT. The dangling-reference failure mode is eliminated
   at the source-code level, not by run ordering.

2. **ADR-R6-5 re-plan-on-upstream-change + divergence guard.** When an upstream stack
   (peripherals) applies an in-run change, `deploy_env.sh` RE-PLANS its downstream stacks
   (lambda, ecs) against the post-apply state and gates the fresh plan against the
   approved summary via `plan_gate_check.sh plan-diff` — apply proceeds iff the
   add/change/destroy counts and changed-address set match; on any divergence the run
   FAILS CLOSED with no further downstream applies. This is the mechanism that keeps the
   peripherals→consumer transition coherent within a single dispatch.

**Consequence for execution:** the operator does NOT manually sequence ecs-before-
peripherals. One `deploy_cloud_infra.yml` dispatch per env applies the whole merged change
set in stack_map order under the informed gate + `destroy_ack`; the merged-change-set
property (1) and the re-plan guard (2) make it safe. DEV uses the same workflow under
`AWS_DEPLOY_ROLE_DEV`. HML is code-only (nothing live).

Each peripherals stack has its own remote-state key
(`{dev,hml,prd}/peripherals/terraform.tfstate`) in bucket
`dm-chain-explorer-terraform-state`, lock table `dm-chain-explorer-terraform-lock`.

---

## 7. Execution model (per env)

- **PRD/HML** run through **GitHub OIDC role-assumption in CI** — the `Deploy Infra
  Cloud` workflow (`deploy_cloud_infra.yml`, `workflow_dispatch`) with its informed
  environment gate: pre-gate `terraform plan` per stack, operator reviews the
  add/change/**destroy** summary, sets `destroy_ack = true` (ADR-R6-4 destroy-ack gate is
  exactly built for this), and the gated apply runs the saved plans via `deploy_env.sh`.
  This is the correct mechanism — a config-diff apply destroys precisely the removed
  resources while keeping S3/DynamoDB/log-group.
- **DEV** runs through the same `deploy_cloud_infra.yml` (DEV branch) under
  `AWS_DEPLOY_ROLE_DEV`; DEV detect-changes will flag peripherals/lambda changed.
- The local IAM user `dadaia` may lack prd destroy permissions — **execution is via CI
  workflows, not local terraform**, for prd and hml. Local terraform is acceptable for
  dev only if the operator prefers, but CI is the declared path.
- **Do NOT use the `Destroy Infra Cloud` workflow / `destroy_env.sh` for peripherals.**
  That script is a **whole-env teardown**. Precisely: its `S3_PRESERVED_TARGETS`
  (line 73) applies `terraform destroy -target=module.dynamodb -target=module.kinesis
  -target=module.sqs -target=module.cloudwatch_logs` on the peripherals stack — i.e. it
  **directly destroys `module.dynamodb` (a survivor)** along with kinesis/sqs/cloudwatch.
  Separately, `destroy_prd()` / `destroy_hml()` tear down VPC, IAM, and all Databricks
  stacks in their own steps. None of that is what we want. We want a **config-diff
  `terraform apply`** that destroys only the removed kinesis/sqs/firehose config while
  keeping S3, DynamoDB, and the log group. OQ-4: use the apply path, not a targeted
  `terraform destroy` and not `destroy_env.sh`.

---

## 8. Memory files affected at CLOSURE (do NOT write now)

- `specs/memory/product/capture-layer.md` — retire/rewrite: the AWS-streaming capture
  layer no longer exists in this repo; capture now lives in `dd-chain-capture`. Decide
  with operator at CLOSURE whether to (a) rewrite the atom to describe the S3 integration
  boundary + pointer to `dd-chain-capture`, or (b) move the atom to
  `_archive/legacy-memory/<ts>/` and drop it from the catalog. The capture-layer feature
  is currently catalog **rank 2**.
- `specs/memory/tech-stack.md` — remove the Kinesis / Kinesis Firehose / SQS rows and the
  `kinesis`/`sqs` module-inventory rows; adjust the dm-chain-utils handler rows
  (KinesisHandler/SQSHandler/FirehoseHandler) per whether the library keeps them.
- `specs/memory/product/aws-resources.md` — drop the Kinesis/Firehose/SQS inventory; keep
  S3/DynamoDB/Lambda/ECS-cluster/ECR/CloudWatch-log-group/IAM.
- `specs/memory/product/index.md` + `catalog.json` — update the feature catalog if the
  capture-layer atom is retired or its rank changes.

---

## 9. Dependencies & risks

| Risk | Mitigation |
|------|-----------|
| **PRD irreversibility** — destroying prd capture is permanent. | Operator-gated execution (T-4.1); informed-gate pre-plan review + `destroy_ack`; rollback = re-apply the modules from git history if mis-scoped (see PLAN §rollback). |
| **Dangling output references** — a stack planning against a removed peripherals output. | Single merged change set removes every consumer reference in the same commit; ADR-R6-5 re-plan + divergence guard (§6). No manual stack ordering. |
| **Live writer races a destroyed target** — a producer rescaled up mid-window. | AC-0 producer-quiescence gate (desired=0/running=0) before any destroying apply; `prod_resume.sh` rescale block removed (§3.2). |
| **OIDC/CI execution** — local `dadaia` user may lack prd destroy perms. | Execute via `deploy_cloud_infra.yml` under the env-scoped OIDC deploy roles, not local terraform. |
| **Accidental S3/DynamoDB destroy** — a wrong target or a whole-stack destroy would delete the boundary. | Explicit OUT list (§4); forbid `destroy_env.sh` for peripherals (§7, AC verifies it destroys `module.dynamodb` directly); AC-3 verifies S3/DynamoDB/log-groups intact. |
| **ECR/cluster shared with batch workload** — blanket 07_ecs destroy would break surviving batch jobs. | Surgical removal of only the 5 producer task-defs/services (§3.1); OQ-1 confirmed keep cluster + ECR; AC-5 verifies batch + ECR intact. |
| **dd-chain-utils library** still exports Kinesis/SQS/Firehose handlers. | Out of scope (OQ-5 confirmed); follow-up backlog item `dm-chain-utils-capture-handler-cleanup` for project-manager. Does not block this release. |

---

## 10. Decisions resolved (spec review, 2026-06-22)

> Mandatory release-definition grill was run on the picked set during definition. The 5
> open questions raised at Draft were resolved at spec review (both reviewers
> APPROVE-WITH-CHANGES). Recorded here as ADRs:

- **OQ-1 (ECR/cluster fate) — RESOLVED: keep.** Surgical removal of ONLY the 5 capture
  producer task-defs/services. KEEP the ECS cluster, capacity providers,
  service-discovery namespace, and both ECR repos (`onchain-stream-txs`,
  `onchain-batch-txs`) — the surviving batch workload depends on them. AC-5 verifies.
- **OQ-2 (firehose-strip mechanism) — RESOLVED: toggle.** `firehose_enabled = false` at
  each `cloudwatch_logs` call site (count-guarded, idempotent, keeps the log group). Do
  not edit the module body.
- **OQ-3 (`destroy_env.sh`) — RESOLVED: fix dead targets, keep as whole-env-only tool.**
  Remove the dead `module.kinesis`/`module.sqs` targets from `S3_PRESERVED_TARGETS`; KEEP
  `module.dynamodb`/`module.cloudwatch_logs`; add a warning comment that the script is a
  whole-env teardown only and must NOT be used for the capture retirement.
- **OQ-4 (producer removal mechanism) — RESOLVED: config-diff apply.** The deploy
  workflow destroys removed task-defs on apply via the informed gate + `destroy_ack`. NOT
  a targeted `terraform destroy`, NOT `destroy_env.sh`.
- **OQ-5 (dm-chain-utils handlers) — RESOLVED: out of scope.** KinesisHandler /
  SQSHandler / FirehoseHandler library cleanup is a follow-up backlog item
  (`dm-chain-utils-capture-handler-cleanup`) for project-manager to curate. Not in this
  release.
