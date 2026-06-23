# PLAN — Release v0.4.0 — Capture Layer Retirement

> **Status:** Aprovado
> **Release ID:** v0.4.0
> **Owner:** product-engineer
> **Depends on:** SPEC.md v0.4.0 (Aprovado)

Ordering safety is a **merged-commit property, not a manual run sequence** (architect
review, SPEC §6): every consumer reference to a removed peripherals output is deleted in
the SAME commit, and the ADR-R6-5 re-plan-on-upstream-change + divergence guard in
`deploy_env.sh` keeps the peripherals→consumer transition coherent within one
`deploy_cloud_infra.yml` dispatch (which applies in `stack_map.json` order:
`vpc → peripherals → iam → lambda → ecs → databricks`). All execution is via the repo's
existing CI workflows under OIDC; no raw CLI on prd/hml.

---

## Strategy

1. **One reviewed code change set on `develop`** removes every capture declaration
   (producers, peripherals streaming modules, firehose-from-cloudwatch, orphan modules,
   stack_map/destroy_env edits). The IaC stops declaring the resources so nothing can
   recreate them.
2. **Live removal** then runs as config-diff `terraform apply` via `deploy_cloud_infra.yml`
   in the safe order, with the informed-gate `destroy_ack` review. S3/DynamoDB/log-groups
   are never in the removed config set, so apply preserves them.
3. **CLOSURE** updates memory atoms to describe the product without the AWS capture layer.

Layers affected: Terraform IaC (`services/**`), CI tooling (`scripts/ci/stack_map.json` +
`scripts/ci/destroy_env.sh` + `scripts/ci/hml_teardown.sh`), and operational tooling
(`scripts/prod_resume.sh`, `scripts/prod_standby.sh`, `scripts/prod_ecs_logs.py`,
integration tests). `.github/workflows/*` are read-only here. No application/Databricks
code changes.

---

## WS-A — ECS capture producer removal (one consumer reference set in the merged commit)

**Goal:** remove the 5 capture producer jobs and ALL their references to peripherals
remote-state outputs, in the same merged change set as WS-C, so no stack ever plans
against a vanished output (see SPEC §6 — ordering safety is a merged-commit property, NOT
a manual run sequence).

- **A1** `services/prd/07_ecs/ecs.tf`: delete the 5 `aws_ecs_task_definition`
  (`mined_blocks_watcher`, `orphan_blocks_watcher`, `block_data_crawler`,
  `mined_txs_crawler`, `txs_input_decoder`) and their 5 `aws_ecs_service` resources.
  KEEP `aws_ecs_cluster.dm`, `aws_ecs_cluster_capacity_providers.dm`,
  `aws_cloudwatch_log_group.ecs_apps`, `aws_service_discovery_private_dns_namespace.dm`,
  and both `aws_ecr_repository` resources (OQ-1 resolved: keep).
- **A2** `services/prd/07_ecs/locals.tf`: remove the `common_stream_env` local and the
  `data "terraform_remote_state" "kinesis_sqs"` source; remove the `docs/migrar_kafka.md`
  comment (line 20). Keep `ecr_*`, `common_tags`, `log_config`.
- **A2b** `services/prd/07_ecs/main.tf`: remove the now-orphaned
  `data "terraform_remote_state" "dynamodb"` source (lines 55-62) — it was consumed ONLY
  by `common_stream_env` (`DYNAMODB_TABLE`), which A2 deletes. No survivor in 07_ecs reads
  it. Leaving it dangling keeps a needless peripherals coupling and can confuse plan.
- **A3** `terraform validate` + `terraform fmt -check` clean on `prd/07_ecs`.

> Note: `hml/07_ecs` has no capture producers and no kinesis remote-state reference — it
> is a cluster shell only. No change.

---

## WS-B — Lambda remote-state reference confirmation (survivors keep planning)

**Goal:** ensure the non-capture lambdas still plan after peripherals outputs change.

- **B1** `services/prd/06_lambda/lambda_contracts_ingestion.tf`: the `CLOUDWATCH_LOG_GROUP`
  env var (line 119) reads `data.terraform_remote_state.kinesis_sqs.outputs.
  cloudwatch_log_group_name`. Since the log-group output SURVIVES in peripherals, confirm
  the remote-state alias still resolves; no removal of this reference is required UNLESS
  the alias name changes. `contracts_ingestion` lambda must keep planning clean.
- **B2** `services/dev/02_lambda/main.tf`: references only `dynamodb_table_*` and
  `ingestion_bucket_*` peripherals outputs — none removed. Expected no change; verify a
  clean plan.
- **B3** `terraform validate` clean on both lambda stacks.

---

## WS-C — Peripherals streaming removal

**Goal:** remove kinesis + sqs + firehose-from-cloudwatch from all three peripherals
stacks, in the SAME merged commit as WS-A/WS-B. Keep S3, DynamoDB, and the CloudWatch log
group. (`prd` modules live in `peripherals.tf`; `dev`/`hml` in `main.tf`.)

- **C1** `services/prd/04_peripherals/peripherals.tf`: remove `module "kinesis"` and
  `module "sqs"`; set `firehose_enabled = false` on `module "cloudwatch_logs"`
  (OQ-2 toggle). Keep s3_raw/s3_lakehouse/s3_databricks, dynamodb, log group.
- **C2** `services/prd/04_peripherals/outputs.tf`: remove `kinesis_stream_names`,
  `kinesis_stream_arns`, `firehose_arns`, `firehose_direct_put_stream_names`,
  `sqs_queue_urls`, `sqs_queue_arns`, `sqs_dlq_arns`. KEEP `*_bucket_*`,
  `cloudwatch_log_group_name`/`_arn`, `dynamodb_table_name`/`_arn`.
- **C3** `services/dev/01_peripherals/main.tf` + `outputs.tf`: same module removals +
  firehose toggle. **Remove exactly what dev declares** — `dev/01_peripherals/outputs.tf`
  has NO `firehose_arns`, NO `cloudwatch_log_group_arn`, NO `sqs_dlq_arns`; remove
  `kinesis_stream_names`/`_arns`, `firehose_direct_put_stream_names`, `sqs_queue_urls`/
  `_arns`. KEEP `ingestion_bucket_*`, `dynamodb_table_*`, `cloudwatch_log_group_name`.
- **C4** `services/hml/04_peripherals/main.tf` + `outputs.tf`: same removals — hml declares
  the FULL output set (incl. `firehose_arns`, `cloudwatch_log_group_arn`, `sqs_dlq_arns`);
  remove all kinesis/sqs/firehose outputs. Code-only (nothing live in hml).
- **C5** `terraform validate` + `terraform fmt -check` clean on all three peripherals
  stacks.

---

## WS-D — Orphan modules + CI single-source + operational tooling cleanup

**Goal:** remove unreferenced modules, keep the CI stack map / destroy script honest, and
purge the operational tooling that still references the deleted producers (the concrete
"streams come back" regression vector).

- **D1** Delete `services/modules/kinesis/` (after WS-A/WS-C confirm zero references).
- **D2** Delete `services/modules/sqs/` (same).
- **D3** `scripts/ci/stack_map.json`: drop `kinesis`, `sqs` from the `modules` arrays of
  `dev/peripherals`, `hml/peripherals`, `prd/peripherals`. This file feeds
  `changed_stacks.py` / `plan_on_pr.yml` — editing it makes the post-apply CI idempotency
  gate (AC-7) honest.
- **D4** `scripts/ci/destroy_env.sh`: edit `S3_PRESERVED_TARGETS` (line 73) to remove ONLY
  `-target=module.kinesis -target=module.sqs` (they error once the modules are gone) —
  KEEP `-target=module.dynamodb -target=module.cloudwatch_logs` (OQ-3). Add a warning
  comment: whole-env teardown only; NOT for the capture retirement. Then
  `bash -n scripts/ci/destroy_env.sh` and assert no `module.kinesis`/`module.sqs` target
  remains.
- **D5** `scripts/prod_resume.sh`: remove the 5-producer `ECS_PROD_COUNTS` entries + the
  `aws ecs update-service --desired-count` rescale block (the rescale-up regression
  vector). `scripts/prod_standby.sh`: remove the producer scale-to-0 references.
  `scripts/prod_ecs_logs.py`: remove the 5 producer service references.
- **D6** Strip the 5-producer references from `scripts/ci/hml_teardown.sh` and
  `scripts/{hml_integration_test,hml_integration_test_optimized,dev_integration_test}.sh`
  so the suites do not assert against destroyed resources. `grep -rn` for the 5 service
  names returns nothing post-edit.
- **D7** `actionlint` (if workflows touched — none expected) + `terraform fmt -check
  -recursive` + `terraform validate` (all touched stacks) + `bash -n` on edited shell
  scripts, all clean.

---

## WS-E — Live removal execution (operator-gated)

**Goal:** apply the config-diff destroy via CI under OIDC. Single mutating, irreversible
workstream — gated behind explicit operator go. **There is no manual stack sequence** (see
SPEC §6): one `deploy_cloud_infra.yml` dispatch per env applies the whole merged change set
in `stack_map.json` order (`vpc → peripherals → iam → lambda → ecs → databricks`). Safety
comes from the merged-commit property (every consumer reference removed in the same commit)
+ the ADR-R6-5 re-plan-on-upstream-change + divergence guard, NOT from run ordering.

Per env:

1. **AC-0 producer quiescence** — confirm the 5 producer ECS services are
   `desired=0`/`running=0` (and `prod_resume.sh` is not running) BEFORE dispatch.
2. **prd** — `deploy_cloud_infra.yml` (environment `prd`): the informed pre-gate plan
   shows the peripherals kinesis/sqs/firehose + the 5 producer task-defs/services as
   **destroys**; operator reviews the consolidated add/change/destroy summary and sets
   `destroy_ack = true`; the gated apply runs the saved plans via `deploy_env.sh` in
   stack_map order; downstream stacks (lambda/ecs) re-plan against post-apply peripherals
   state, gated by the divergence guard. S3/DynamoDB/log-group/cluster/ECR preserved.
3. **dev** — same workflow (DEV branch) under `AWS_DEPLOY_ROLE_DEV`; detect-changes flags
   peripherals/lambda changed.
4. **hml** — code-only reconciliation; the pre-gate plan shows no live destroy.

> **Do NOT** use `Destroy Infra Cloud` / `destroy_env.sh` for peripherals — it directly
> destroys `module.dynamodb` (a survivor) and tears down VPC/IAM/Databricks in separate
> steps. The deploy (apply) path is the correct config-diff mechanism.

---

## Technical risks

| Risk | Handling |
|------|----------|
| A stack plans against a removed peripherals output | Single merged commit removes every consumer reference (WS-A incl. A2b, WS-B); ADR-R6-5 re-plan + divergence guard. No manual ordering. |
| A live producer races a destroyed kinesis/sqs target | AC-0 quiescence gate; `prod_resume.sh` rescale block removed (WS-D5). |
| Accidental S3/DynamoDB/log-group destroy | Removed config is only kinesis/sqs/firehose; informed-gate plan review + `destroy_ack`; AC-3 verifies survivors. |
| ECR/cluster shared with batch | WS-A keeps cluster + both ECR repos (OQ-1); AC-5 verifies. |
| `destroy_env.sh` broken target after module delete | WS-D4 removes dead targets + `bash -n` in same commit. |
| Lambda plan breaks on removed remote-state output | Log-group output is KEPT, so `contracts_ingestion` reference stays valid (WS-B1); if alias changes, replace it. |

---

## Validation plan

Per touched stack, after the merged code change set and again after live apply:

1. `terraform fmt -check -recursive` + `bash -n` on edited shell scripts — clean.
2. `terraform validate` — clean on `dev/01_peripherals`, `hml/04_peripherals`,
   `prd/04_peripherals`, `prd/07_ecs`, `prd/06_lambda`, `dev/02_lambda`.
3. `terraform plan` idempotency — second plan post-apply shows `No changes` (AC-2,
   necessary but not sufficient).
4. AWS CLI assertions (AC-1/AC-3/AC-4/AC-5): capture resources + firehose IAM/subscription
   filter absent; S3 + both DynamoDB tables + log groups present; non-capture lambdas
   functionally invoke; batch ECS + both ECR repos intact.
5. **AC-7 (authoritative idempotency):** `drift_detection.yml` zero drift + `plan_on_pr.yml`
   clean on `develop` POST-live-apply.
6. AC-6: `grep -rn` confirms no orphan remote-state ref, no `services/modules/{kinesis,sqs}`,
   no producer reference in tooling/tests.

---

## Rollback note

These resources are being **intentionally destroyed** — there is no "undo apply" once the
streams/queues are gone (in-flight data is already migrated to `dd-chain-capture`).
Rollback is meaningful only if the change is **mis-scoped**.

- **Pre-apply mis-scope** (e.g. an S3 bucket or DynamoDB table appears in a destroy plan):
  ABORT at the informed-gate review — do NOT set `destroy_ack`; revert the offending IaC
  edit from git history (re-add the module) and re-run the plan before any mutating apply.
- **Mid-sequence partial-apply failure** (a downstream stack fails after peripherals
  already applied): the run FAILS CLOSED (no further downstream applies). To recover,
  re-apply the affected stack against its prior git ref (`git checkout <prev-ref> --
  services/<stack>` then `deploy_cloud_infra.yml` for that env), restoring the declaration
  before reattempting. Each peripherals stack's state is isolated by its own remote-state
  key, so a partial apply does not corrupt sibling stacks.

Once the capture streams are correctly destroyed, re-creating them is a deliberate new
release, not a rollback.
