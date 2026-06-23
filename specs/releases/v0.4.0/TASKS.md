# TASKS — Release v0.4.0 — Capture Layer Retirement

> **Status:** Aprovado
> **Release ID:** v0.4.0
> **Owner:** product-engineer (authoring) → software-engineer (implementation)
> **Marker contract:** `[ ]` OPEN → `[-]` IN PROGRESS → `[x]` DONE. Max one `[-]` per
> owner unless a task declares a disjoint write set. Reserve before writing; flip to
> `[x]` only after review approval (see review checkpoints). All tasks below are `[ ]` —
> no implementation has started.

All IaC + tooling edits (WS-A..WS-D) land in ONE merged change set so no stack ever plans
against a vanished output (ordering safety is a merged-commit property, not a manual run
sequence — SPEC §6). The single mutating, irreversible live-apply is the final
operator-gated task (T-4.1).

---

## WS-A — ECS capture producer removal

- [x] **T-A.1** — Remove the 5 capture producer task-defs + services from `prd/07_ecs`.
  - Owner: software-engineer
  - Write set: `services/prd/07_ecs/ecs.tf`
  - Precondition: SPEC + PLAN `Aprovado`; OQ-1 resolved (keep cluster + ECR).
  - Done: the 5 `aws_ecs_task_definition` + 5 `aws_ecs_service` (mined_blocks_watcher,
    orphan_blocks_watcher, block_data_crawler, mined_txs_crawler, txs_input_decoder) are
    gone; cluster, capacity providers, `/ecs/...` log group, service-discovery namespace,
    and both ECR repos remain; `terraform validate` + `fmt -check` clean.
  - Parallelism: disjoint write set from T-A.2 (same stack, different file) — sequence
    A.1 then A.2 to keep one `[-]` per owner.

- [x] **T-A.2** — Remove `common_stream_env` local, `kinesis_sqs` remote-state source, the
  now-orphaned `dynamodb` remote-state source, and the stale `docs/migrar_kafka.md` comment
  from `prd/07_ecs`.
  - Owner: software-engineer
  - Write set: `services/prd/07_ecs/locals.tf`, `services/prd/07_ecs/main.tf`
  - Precondition: T-A.1 done.
  - Done: `common_stream_env` and `data "terraform_remote_state" "kinesis_sqs"` removed;
    the `data "terraform_remote_state" "dynamodb"` source (`main.tf:55`) — orphaned once the
    5 producer task-defs + `common_stream_env` go, its sole consumer being `locals.tf:36` —
    is also removed; the line-20 `docs/migrar_kafka.md` comment removed; surviving `ecr_*`/
    `common_tags`/`log_config` intact; `grep -rn "remote_state.dynamodb\|kinesis_sqs"
    services/prd/07_ecs/` returns nothing; `terraform validate` clean on `prd/07_ecs`.

---

## WS-B — Lambda remote-state confirmation (survivors)

- [x] **T-B.1** — Confirm/strip the `contracts_ingestion` lambda's log-group remote-state
  reference so the lambda keeps planning.
  - Owner: software-engineer
  - Write set: `services/prd/06_lambda/lambda_contracts_ingestion.tf`
  - Precondition: T-A.2 done (kinesis_sqs source removed from ecs only — peripherals still
    exports `cloudwatch_log_group_name`).
  - Done: `CLOUDWATCH_LOG_GROUP` env var resolves against the surviving peripherals
    log-group output (alias confirmed) OR the reference is replaced with a valid one; no
    reference to a removed kinesis/sqs/firehose output remains; `terraform validate` clean.

- [x] **T-B.2** — Verify `dev/02_lambda` plans clean (expected: no change).
  - Owner: software-engineer
  - Write set: `services/dev/02_lambda/main.tf` (only if a change proves necessary)
  - Precondition: T-B.1 done.
  - Done: `gold_to_dynamodb` lambda references only surviving outputs
    (`dynamodb_table_*`, `ingestion_bucket_*`); `terraform validate` clean; if no edit
    needed, record "no change required" in the commit.

### Review checkpoint R1 (after WS-A + WS-B)
- [x] **T-R.1** — Review checkpoint: `qa-engineer` + `code-reviewer` confirm the
  dependents (07_ecs producers removed, lambdas still plan, no orphan remote-state source)
  are correct and no survivor reference dangles. Owner: reviewers. Done: green review
  handoff for the WS-A/WS-B commit. **DONE — covered by the combined R2 full review at
  HEAD de70033: code-reviewer APPROVE-WITH-CHANGES + qa-engineer APPROVE (both legs green).**

---

## WS-C — Peripherals streaming removal

> Note: `prd` peripherals modules live in `peripherals.tf`; `dev`/`hml` in `main.tf`. The
> three `outputs.tf` are NOT symmetric — each task removes exactly what its stack declares.

- [x] **T-C.1** — Remove kinesis + sqs modules and disable firehose on cloudwatch_logs in
  `prd/04_peripherals`.
  - Owner: software-engineer
  - Write set: `services/prd/04_peripherals/peripherals.tf`
  - Precondition: T-R.1 green.
  - Done: `module "kinesis"` + `module "sqs"` removed; `firehose_enabled = false` on
    `module "cloudwatch_logs"`; S3 (3 modules), dynamodb, log group intact; validate clean.

- [x] **T-C.2** — Remove kinesis/sqs/firehose outputs from `prd/04_peripherals/outputs.tf`.
  - Owner: software-engineer
  - Write set: `services/prd/04_peripherals/outputs.tf`
  - Precondition: T-C.1 done.
  - Done: `kinesis_stream_names`/`_arns`, `firehose_arns`, `firehose_direct_put_stream_names`,
    `sqs_queue_urls`/`_arns`, `sqs_dlq_arns` removed; `*_bucket_*`,
    `cloudwatch_log_group_name`/`_arn`, `dynamodb_table_*` kept; validate clean.

- [x] **T-C.3** — Same removals on `dev/01_peripherals` (main + outputs).
  - Owner: software-engineer
  - Write set: `services/dev/01_peripherals/main.tf`, `services/dev/01_peripherals/outputs.tf`
  - Precondition: T-C.2 done.
  - Done: kinesis/sqs modules removed + firehose toggle-off in `main.tf`. **dev outputs are
    a SMALLER set** — it has NO `firehose_arns`, NO `cloudwatch_log_group_arn`, NO
    `sqs_dlq_arns`; remove only what it declares (`kinesis_stream_names`/`_arns`,
    `firehose_direct_put_stream_names`, `sqs_queue_urls`/`_arns`). KEEP `ingestion_bucket_*`,
    `dynamodb_table_*`, `cloudwatch_log_group_name`; validate clean.

- [x] **T-C.4** — Same removals on `hml/04_peripherals` (main + outputs) — code-only.
  - Owner: software-engineer
  - Write set: `services/hml/04_peripherals/main.tf`, `services/hml/04_peripherals/outputs.tf`
  - Precondition: T-C.3 done.
  - Done: kinesis/sqs modules + firehose toggle-off; hml declares the FULL output set
    (incl. `firehose_arns`, `cloudwatch_log_group_arn`, `sqs_dlq_arns`) — remove all
    kinesis/sqs/firehose outputs; S3/dynamodb/log-group kept; validate clean. (Nothing
    live in hml — code consistency only.)

---

## WS-D — Orphan modules + CI single-source + operational tooling cleanup

- [x] **T-D.1** — Delete `services/modules/kinesis/` and `services/modules/sqs/`.
  - Owner: software-engineer
  - Write set: `services/modules/kinesis/**`, `services/modules/sqs/**` (deletion)
  - Precondition: T-C.4 done (zero references remain across all stacks).
  - Done: both module dirs removed; `grep -rn "modules/kinesis\|modules/sqs" services/`
    returns nothing.

- [x] **T-D.2** — Update `stack_map.json` modules arrays (drop `kinesis`, `sqs`).
  - Owner: software-engineer
  - Write set: `scripts/ci/stack_map.json`
  - Precondition: T-D.1 done.
  - Done: `dev/peripherals`, `hml/peripherals`, `prd/peripherals` `modules` arrays no
    longer list `kinesis`/`sqs`; JSON valid. (This file feeds `changed_stacks.py` /
    `plan_on_pr.yml` — the edit is what makes AC-7 honest.)

- [x] **T-D.3** — Fix `destroy_env.sh` `S3_PRESERVED_TARGETS` (remove dead kinesis/sqs targets).
  - Owner: software-engineer
  - Write set: `scripts/ci/destroy_env.sh`
  - Precondition: T-D.1 done; OQ-3 resolved.
  - Done: line-73 `S3_PRESERVED_TARGETS` no longer references `module.kinesis`/`module.sqs`
    (`grep -n 'module.kinesis\|module.sqs' scripts/ci/destroy_env.sh` returns nothing) AND
    the kept targets remain (`grep -n 'module.dynamodb'` and `grep -n 'module.cloudwatch_logs'`
    each match); the whole-env-teardown-only warning comment (OQ-3) is present;
    `bash -n scripts/ci/destroy_env.sh` clean.

- [x] **T-D.4** — Purge the deleted-producer references from operational tooling (the
  rescale-up "streams come back" regression vector).
  - Owner: software-engineer
  - Write set: `scripts/prod_resume.sh`, `scripts/prod_standby.sh`, `scripts/prod_ecs_logs.py`
  - Precondition: T-A.1 done.
  - Done: `prod_resume.sh` no longer carries the 5-producer `ECS_PROD_COUNTS` entries or the
    `aws ecs update-service --desired-count` rescale block for them; `prod_standby.sh` no
    longer references the producers; `prod_ecs_logs.py` no longer tails the 5 producer
    services; `bash -n` (sh) / `python -m py_compile` (py) clean.

- [x] **T-D.5** — Strip producer references from integration tests + hml teardown.
  - Owner: software-engineer
  - Write set: `scripts/ci/hml_teardown.sh`, `scripts/hml_integration_test.sh`,
    `scripts/hml_integration_test_optimized.sh`, `scripts/dev_integration_test.sh`
  - Precondition: T-A.1 done.
  - Done: none of the 5 producer service names remain
    (`grep -rn 'mined-blocks-watcher\|orphan-blocks-watcher\|block-data-crawler\|mined-txs-crawler\|txs-input-decoder' scripts/`
    returns nothing); suites do not assert against destroyed resources; `bash -n` clean.

### Review checkpoint R2 (after WS-C + WS-D — full code change set)
- [x] **T-R.2** — Full review: `qa-engineer` + `code-reviewer` + `security-reviewer` on the
  complete merged change set. Confirm AC-2/AC-5/AC-6/AC-8 (validate clean, batch/ECR intact,
  no orphan refs/modules/tooling, fmt/actionlint/`bash -n` green) and that
  S3/DynamoDB/log-group declarations are untouched. Owner: reviewers. Done: green review
  handoffs for the merge commit. **DONE — 3× green at HEAD de70033: code-reviewer
  APPROVE-WITH-CHANGES (safe to apply), qa-engineer APPROVE (execution-ready),
  security-reviewer APPROVE (IAM blast radius capture-only). Non-blocking CLOSURE cleanups:
  drop unconsumed `iam` remote-state source + 4 unused locals in 07_ecs; rename
  `kinesis_sqs` alias in 06_lambda. Handoffs under .dadaia/handoff/dd-chain-explorer/.**

---

## WS-E — Live removal execution (operator-gated, irreversible)

- [x] **T-4.1** — Execute the live destroy. **DONE 2026-06-22 — operator-authorized
  surgical targeted destroy** (chosen over the CI config-diff apply to avoid bundling the
  unmerged-v0.3.0 survivor drift seen in the dev plan). Mechanism: `terraform destroy
  -target=module.kinesis -target=module.sqs -target=<6 cloudwatch firehose resources>` on
  `prd/04_peripherals` then `dev/01_peripherals`. **prd: 18 destroyed; dev: 18 destroyed
  (preview 0-add/0-change — no survivor touched).** AC-0 verified (0 producer services/tasks
  on every cluster). AC-1 verified: Kinesis/Firehose/SQS list empty post-destroy. AC-3
  verified: all 5 S3 buckets + all 3 DynamoDB tables + `/apps/dm-chain-explorer-{dev,prd}`
  log groups remain. hml had nothing live (code-only). Note: the SPEC's `deploy_cloud_infra.yml`
  CI mechanism was not used because v0.3.0 (PR #28 → master) is unmerged and develop/master
  lag it, which would have bundled unrelated changes; targeted destroy was the surgical fit.
  - Owner: operator (triggers `deploy_cloud_infra.yml`); devops-engineer assists if
    dispatched. product-engineer does NOT run CLI.
  - Write set: none in-repo (AWS live state only).
  - Precondition: T-R.2 green; change set merged to `develop`; **AC-0 producer quiescence
    verified** (5 producer ECS services `desired=0`/`running=0`, `prod_resume.sh` not
    running); operator reviewed each informed-gate pre-plan and set `destroy_ack = true`
    where the plan shows destroys.
  - Steps: (1) AC-0 quiescence check; (2) `deploy_cloud_infra.yml` env `prd` — informed gate
    + `destroy_ack`; (3) `deploy_cloud_infra.yml` DEV branch under `AWS_DEPLOY_ROLE_DEV`;
    (4) `deploy_cloud_infra.yml` env `hml` (code-only, no live destroy).
  - Done: AC-1 (capture resources + firehose IAM/subscription filter absent) + AC-3
    (S3/DynamoDB/log-groups present) + AC-4 (non-capture lambdas functionally invoke) + AC-5
    (batch ECS + both ECR repos intact) + AC-7 (drift_detection zero + plan_on_pr clean
    post-apply) verified; run URLs recorded for CLOSURE.

---

## Notes

- **No picked bugs.** All capture-related bugs (`drift-01`, `drift-04`,
  `bp-01-streaming-jobs-logger-inconsistency`) are already `Closed` (source-tree fixes,
  not the live AWS resources) — none are fixed by this release, none are silently dropped.
  Record this in CLOSURE Dispositions as a no-op confirmation. `drift-04`
  (kafka/avro dead code) is conceptually adjacent but already resolved; do NOT mark
  `superseded_by` — it is not superseded, it is independently closed.
- **dm-chain-utils** Kinesis/SQS/Firehose handlers remain in the shared library — a
  follow-up library-cleanup backlog item `dm-chain-utils-capture-handler-cleanup` (OQ-5)
  for project-manager to curate, out of scope here.
- Memory atom updates (`capture-layer.md`, `tech-stack.md`, `aws-resources.md`,
  `index.md`, `catalog.json`) happen in CLOSURE, not during implementation.
