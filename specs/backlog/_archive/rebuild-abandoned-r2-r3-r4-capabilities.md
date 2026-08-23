# Backlog — CANDIDATE Epic: Rebuild Abandoned r2/r3/r4 Capabilities

> **Status:** CANDIDATE — NOT picked into any release.
> **Owner:** project-manager (sole backlog author).
> **Created:** 2026-06-09
> **Operator decision:** backlog for later. Do NOT scope a rebuild release now.
> **Source:** audit-remediation-r5 forensics (T-R5-C1/C2/C3). The three releases
> below were forensically verified ABANDONED in full (zero implementation commits)
> and archived under `specs/_archive/releases/`. Their CLOSURE.md "Backlog returns"
> sections are the authoritative evidence for each item.

This epic re-captures the ~16 never-built capabilities from the three abandoned
releases so they survive archival and remain available for a future planning round.
Nothing here is committed scope. Grill + SPEC are required before any of this is
picked. Grouped by the originating release / domain.

---

## Group A — Cost & Availability (from `cost-and-availability-r2`)

Evidence: `specs/_archive/releases/cost-and-availability-r2/CLOSURE.md` (all tasks
ABANDONED; one S3 partial-drift documented).

| Candidate | Original task / issue | Forensic evidence | Sev/Size |
|---|---|---|---|
| CAND-R2-01 Switch Kinesis `mainnet-transactions-data` to ON_DEMAND (3 envs) | T-R2-01 / ISSUE-019 | dev/hml/prd peripherals `.tf` still `stream_mode = "PROVISIONED"` | MED |
| CAND-R2-02 ECS cluster default capacity provider → FARGATE | T-R2-02 / ISSUE-017 | `services/prd/07_ecs/ecs.tf:19-22` still `FARGATE_SPOT` default | MED |
| CAND-R2-03 Align Firehose PRD buffer to 5 MB / 60s | T-R2-03 / ISSUE-025 | prd peripherals kinesis module has no buffer overrides (defaults 64MB/300s) | LOW |
| CAND-R2-04 S3 lifecycle on `raw/` prefix (INTELLIGENT_TIERING) | T-R2-04 / ISSUE-024 | `module.s3_raw` has STANDARD_IA/GLACIER on `""` prefix, not IT on `raw/` — see drift-r2-s3-lifecycle-partial | LOW |
| CAND-R2-05 FARGATE_SPOT per-service override for ECS Jobs 1–3 (4,5 On-Demand) | T-R2-05 / ISSUE-026 / OQ-6 | all 5 services `launch_type = "FARGATE"`, no per-service strategy | MED |
| CAND-R2-06 Replace unconditional DynamoDB `put_item` with conditional put | T-R2-06 / ISSUE-011 | `api_keys_manager.py:37` `put_item` has no `ConditionExpression` | MED |
| CAND-R2-07 Bump dm-chain-utils, rebuild Docker image, redeploy ECS | T-R2-07 | depends on CAND-R2-06; no version bump/rebuild evidence | LOW |
| CAND-R2-08 KMS bill audit + Public-Default Encryption policy | T-R2-NEW-1 / OQ-NEW-1 | no KMS policy Terraform or constitution doc | MED |

**Known drift to reconcile:** the existing S3 lifecycle rules (STANDARD_IA@30d,
GLACIER@90d on `""`) diverge from the r2 spec (INTELLIGENT_TIERING@30d on `raw/`).
A rebuild must reconcile, not blindly re-apply. (drift-r2-s3-lifecycle-partial.)

---

## Group B — Data Quality / DLT Correctness (from `data-quality-r3`)

Evidence: `specs/_archive/releases/data-quality-r3/CLOSURE.md` (all tasks ABANDONED).

| Candidate | Original task / issue | Forensic evidence | Sev/Size |
|---|---|---|---|
| CAND-R3-01 Replace `current_timestamp()` with event-time windows in Gold MVs | T-R3-01 / ISSUE-016 | `ethereum_pipeline.py` `current_timestamp()` in window filters at lines 607, 1005, 1109, 1247 | HIGH |
| CAND-R3-02 Add Auto Loader schema-evolution (`schemaEvolutionMode: addNewColumns`) | T-R3-02 / ISSUE-028 | no `schemaEvolutionMode`/`addNewColumns`/`_schema_version` in pipeline | MED |
| CAND-R3-03 Validate `eth_canonical_blocks_index` bounded window under ≥7d DEV load | T-R3-03 / ISSUE-003 | read-only validation; never executed/signed-off | LOW |
| CAND-R3-04 Implement `transactions_lambda` UNION with Silver intermediary | T-R3-04 / ISSUE-031 / OQ-5 | Gold `g_apps.transactions_lambda` exists (line 736) but no `s_apps.transactions_from_lambda` Silver UNION | MED |
| CAND-R3-05 Drop orphaned Gold MVs `contract_deploy_metrics_hourly` + `contract_method_activity` | T-R3-NEW-1 / ISSUE-027 / OQ-4 | both DLT defs still present (lines 985-1042, 1044-1070) | LOW |
| CAND-R3-06 Implement data-contract test suite (Bronze schema + Silver row-count + Gold idempotency) | T-R3-05 / ISSUE-015 | `apps/dabs/dlt_ethereum/tests/` does not exist | MED |

---

## Group C — Analytics Enrichment / PRD Readiness (from `analytics-enrichment-r4`)

Evidence: `specs/_archive/releases/analytics-enrichment-r4/CLOSURE.md` (implementation
tasks ABANDONED; the three CLOSURE memory tasks T-R4-CL-01/02/03 are SUPERSEDED by the
Markdown-memory migration and are intentionally NOT re-captured here).

| Candidate | Original task / issue | Forensic evidence | Sev/Size |
|---|---|---|---|
| CAND-R4-01 Lakeview dashboard catalog/env parameterization | T-R4-NEW-1 / OQ-3 | blocked by INV-1 catalog parity; no per-env `.lvdash.json` | MED (blocked) |
| CAND-R4-02 Add Genie context `instructions:` block | T-R4-01 / DA-009 | `genie_ethereum.yml` has `sample_questions` but no `instructions:` | MED |
| CAND-R4-03 Add freshness KPI tile to all 4 dashboards | T-R4-02 / DA-010 | no `freshness`/`max(block_time)`/KPI tile in any `*.lvdash.json` | MED |
| CAND-R4-04 Add analyst GRANT DDL for all Gold schemas | T-R4-03 / DA-012 | no `GRANT`/`analysts` in `setup_ddl.py` | MED |
| CAND-R4-05 Add date-range filter widget to applicable dashboards | T-R4-05 / DA-014 | no `dateRange`/date filter widget in dashboard JSONs | LOW |
| CAND-R4-06 Add `COMMENT ON COLUMN` for all Gold MV columns | T-R4-06 / ISSUE-018 | no `COMMENT ON` in `setup_ddl.py` | MED |
| CAND-R4-07 Configure daily Gold export schedule (`schedule` block) | T-R4-08 / DA-015 | `workflow_dm_export_gold.yml` exists but has no `schedule`/cron block | MED |
| CAND-R4-08 Add 50%/1h pre-warn alert for API keys threshold | T-R4-NEW-2 / OQ-7 | only 80%/24h alert (`alert_api_keys_threshold.yml`) exists | LOW |
| CAND-R4-09 Record OQ-1 decision (`prd` canonical catalog) in memory atoms | T-R4-09 / ISSUE-013 | bundle prod targets already use `catalog: "prd"` but memory atoms (`tech-stack.md`, `constitution.md`) not updated | LOW |

**Cross-release dependency:** CAND-R4 dashboard/Genie cleanup of the orphaned Gold MVs
(was T-R4-04/T-R4-07) is downstream of CAND-R3-05 (drop from DLT). Sequence
CAND-R3-05 → the R4 residual-reference cleanup if both are picked.

---

## Notes for a future planning round

- **Bug-always-solved does not apply yet** — these are backlog candidates, not picked
  bugs; no release fixes them until the operator picks them.
- **Grill is mandatory** before any of this reaches a SPEC (release-governance rule):
  the cost/availability Terraform items and the DLT correctness items have non-trivial
  ambiguity (S3-lifecycle drift reconciliation, event-time semantics, blocked INV-1).
- **Do not delete the archived releases.** They are the evidence source; this epic only
  forwards their "Backlog returns" lists into live backlog.
