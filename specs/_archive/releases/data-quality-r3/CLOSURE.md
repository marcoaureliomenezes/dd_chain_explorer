# Closure: Release — data-quality-r3

> **Status:** Aprovado
> **Release ID:** data-quality-r3
> **Forensic verdict:** ABANDONED
> **Owner:** product-engineer
> **Closed (forensic):** 2026-06-08
> **Authored by:** T-R5-C2 forensic investigation

---

## Summary

This release was planned to fix correctness technical debt in the DLT pipeline: replace
wall-clock windows with event-time windows in Gold MVs, add data-contract tests, implement
schema evolution strategy, resolve the `transactions_lambda` Lambda Architecture, and
drop orphaned Gold MVs.

Based on forensic evidence — file state in the current working tree and absence of
implementation commits in git history — **none of the six implementation tasks
(T-R3-01 through T-R3-05, T-R3-NEW-1) was implemented**.

The CLOSURE.md was previously a blank template with literal `<sha>` placeholders. This
document records the ground truth for each task based on evidence gathered during
audit-remediation-r5 (T-R5-C2).

Key findings: `ethereum_pipeline.py` still uses `current_timestamp()` in window filter
clauses (confirmed at lines 607, 1005, 1109, 1247 of the streaming pipeline). No
`schemaEvolutionMode` or `_schema_version` additions. `contract_deploy_metrics_hourly`
and `contract_method_activity` Gold MVs still present in the pipeline. No `transactions_from_lambda`
Silver intermediary. The `apps/dabs/dlt_ethereum/tests/` directory does not exist.

This release should be moved to `specs/_archive/releases/data-quality-r3/`.

---

## Tasks completed

None. All tasks are ABANDONED (no implementation evidence found).

| Task ID | Description | Forensic verdict | Evidence |
|---------|-------------|-----------------|---------|
| T-R3-01 | Replace current_timestamp() with event-time windows in 6 Gold MVs | ABANDONED | `apps/dabs/dlt_ethereum/src/streaming/ethereum_pipeline.py` still contains `current_timestamp()` in window filter contexts at lines 607 (INTERVAL 1 HOUR), 1005 (INTERVAL 24 HOURS), 1109 (INTERVAL 24 HOURS), 1247 (INTERVAL 24 HOURS). Event-time windows not applied. |
| T-R3-02 | Add schema evolution strategy to Auto Loader config | ABANDONED | Grep for `schemaEvolutionMode`, `addNewColumns`, `_schema_version` in `ethereum_pipeline.py` returns no matches. Auto Loader configuration unchanged. |
| T-R3-03 | Confirm eth_canonical_blocks_index bounded window under sustained load | ABANDONED | Read-only validation task; precondition requires DEV pipeline running ≥ 7 days since r1 restart. No evidence of validation execution or sign-off recorded. Classified as never completed. |
| T-R3-04 | Implement transactions_lambda UNION (Lambda Architecture ADR-005) | ABANDONED | `ethereum_pipeline.py` contains `g_apps.transactions_lambda` (line 736) as a Gold MV, but no Silver intermediary `s_apps.transactions_from_lambda` or `s_apps.popular_contracts_txs_enriched` was added. UNION of two Silver sources not implemented. |
| T-R3-NEW-1 | Drop orphaned Gold MVs from DLT pipeline | ABANDONED | `contract_deploy_metrics_hourly` (lines 1044–1070) and `contract_method_activity` (lines 985–1042) DLT function definitions still present in `ethereum_pipeline.py`. Neither was removed. |
| T-R3-05 | Implement data-contract test suite | ABANDONED | `apps/dabs/dlt_ethereum/tests/` directory does not exist. No test files found under the dlt_ethereum app. |

---

## Validations

No validations possible. The table below records expected validation commands alongside
the forensic finding.

| Description | Command | Forensic finding |
|-------------|---------|-----------------|
| No current_timestamp() in window clauses | `grep -n "current_timestamp()" ethereum_pipeline.py` | Present at lines 607, 1005, 1109, 1247 in filter/window contexts |
| Gold MV idempotency | Run DLT full-refresh × 2; compare row counts | Not applicable — event-time windows not implemented |
| Schema evolution mode set | `grep "schemaEvolutionMode" ethereum_pipeline.py` | No matches — not implemented |
| Data-contract tests pass | `pytest apps/dabs/dlt_ethereum/tests/ -v` | Directory does not exist |
| Orphaned MVs removed | `grep "contract_deploy_metrics_hourly\|contract_method_activity" ethereum_pipeline.py` | Both functions still present |

---

## Drifts

No implementation was done in this release; no drifts from PLAN occurred. The release
was simply never implemented.

---

## Memory updates

No memory updates were made during this release. T-R3-CL-01 and T-R3-CL-02 were not
executed.

- `specs/memory/data-catalog.md` — no change: r3 was abandoned.
- `specs/memory/architecture.md` — no change: r3 was abandoned; Auto Loader section not updated.

---

## Backlog returns

The following open issues from r3 remain unresolved and should be promoted to
`specs/backlog/candidates.md` for the next planning round:

- `backlog/candidates.md` ← ISSUE-016: Replace `current_timestamp()` with event-time windows in 6 Gold MVs
- `backlog/candidates.md` ← ISSUE-028: Add `cloudFiles.schemaEvolutionMode: "addNewColumns"` to Auto Loader config
- `backlog/candidates.md` ← ISSUE-031: Implement `transactions_lambda` UNION with Silver intermediary
- `backlog/candidates.md` ← ISSUE-027: Drop orphaned Gold MVs `contract_deploy_metrics_hourly` and `contract_method_activity`
- `backlog/candidates.md` ← ISSUE-015: Implement data-contract test suite (Bronze schema + Silver row-count + Gold idempotency)
- `backlog/candidates.md` ← ISSUE-003: Validate `eth_canonical_blocks_index` bounded window under ≥ 7 days sustained DEV load

Note: promotion to backlog is the responsibility of project-manager, not product-engineer.

---

## Archive decision

**MOVE** — this release is fully abandoned. Move to archive:

```
git mv specs/releases/data-quality-r3 specs/_archive/releases/data-quality-r3
```

`specs/releases/ACTIVE.md` currently points at `audit-remediation-r5` — do not modify it.
This release is not referenced by ACTIVE.md and can be archived independently.
