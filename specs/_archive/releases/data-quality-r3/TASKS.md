# TASKS: data-quality-r3

**Status:** Aprovado
**Release:** data-quality-r3
**Phase:** TASKS

Work-Packages A and B are independent and may run in parallel. T-R3-04 and T-R3-NEW-1 are unblocked (OQ-4 and OQ-5 resolved 2026-05-22).

---

## Work-Package A — DLT Pipeline Correctness (data-engineer)

<!-- Write-set: apps/dabs/dlt_ethereum/src/*/ethereum_pipeline.py -->

- [ ] T-R3-01 — **Replace current_timestamp() with event-time windows in 6 Gold MVs** | Owner: data-engineer | Effort: M
  Evidence: ISSUE-016, DE-L-002, `ethereum_pipeline.py:539,937,1041,1178`
  Write-set: `apps/dabs/dlt_ethereum/src/*/ethereum_pipeline.py`
  Done: No `current_timestamp()` in window filter clauses; two consecutive full-refresh runs
        produce identical row counts in all affected Gold MVs.

- [ ] T-R3-02 — **Add schema evolution strategy to Auto Loader config** | Owner: data-engineer | Effort: M
  Evidence: ISSUE-028, DE-L-001, LAKEHOUSE-05, `ethereum_pipeline.py:66–78`
  Write-set: `apps/dabs/dlt_ethereum/src/*/ethereum_pipeline.py`
  Done: `cloudFiles.schemaEvolutionMode: "addNewColumns"` in all Auto Loader sources;
        `_schema_version` metadata column present in Bronze; DLT expectation for unknown columns added.

- [ ] T-R3-03 — **Confirm eth_canonical_blocks_index bounded window under sustained load** | Owner: data-engineer | Effort: S
  Evidence: ISSUE-003 (validation follow-up from R1 T-R1-20)
  Write-set: none (read-only validation)
  Precondition: DEV pipeline has been running ≥ 7 days since R1 restart
  Done: DLT run log shows no O(N^2) scan warning for at least 2 consecutive runs with ≥ 7 days
        of data; `eth_canonical_blocks_index` row count is bounded.

- [ ] T-R3-04 — **Implement transactions_lambda UNION (Lambda Architecture ADR-005)** | Owner: data-engineer | Effort: L
  Evidence: ISSUE-031, DE-L-003, LAKEHOUSE-04; ADR-005 specifies UNION of Silver streaming + Bronze batch
  Write-set: `apps/dabs/dlt_ethereum/src/streaming/ethereum_pipeline.py`
  Decision (grill 2026-05-22): Keep Lambda Architecture (Path A). Operator confirmed this will be used for future product evolution.
  Implementation: (a) Create Silver intermediary `s_apps.transactions_from_lambda` from Bronze batch source (contracts_ingestion Lambda); (b) Rewrite `g_apps.transactions_lambda` as UNION ALL of Silver streaming + Silver intermediary; (c) Validate in DEV that UNION produces rows from both sources.
  Done: `g_apps.transactions_lambda` is a UNION of two Silver sources; DEV DLT run completes without error; both source paths produce rows.

- [ ] T-R3-NEW-1 — **Drop orphaned Gold MVs from DLT pipeline** | Owner: data-engineer | Effort: S
  Evidence: ISSUE-027, DA-008; OQ-4 resolved 2026-05-22 (operator: "Dropar da DLT")
  Write-set: `apps/dabs/dlt_ethereum/src/streaming/ethereum_pipeline.py`
  Decision (grill 2026-05-22): Drop `g_apps.contract_deploy_metrics_hourly` and `g_apps.contract_method_activity` — no dashboard/Genie consumer; saves DBU on every DLT run.
  Done: Both orphaned Gold MV functions removed from `ethereum_pipeline.py`; DLT run completes without reference to these tables; no dashboard/Genie YAML references them.

---

## Work-Package B — Data-Contract Tests (data-engineer)

<!-- Write-set: apps/dabs/dlt_ethereum/tests/ (new directory) -->

- [ ] T-R3-05 — **Implement data-contract test suite (Bronze schema + Silver row-count + Gold idempotency)** | Owner: data-engineer | Effort: L
  Evidence: ISSUE-015, DE-P-002, `find repos/ -name "test_*.py"` (currently empty)
  Write-set: `apps/dabs/dlt_ethereum/tests/` (create), CI workflow (test step)
  Done: 5 tests defined and passing in DEV environment (Bronze schema, Silver smoke,
        Gold idempotency, canonical blocks correctness, from_address NULL enforcement);
        test step added to DABs CI workflow for DEV target.

---

## CLOSURE Tasks (product-engineer — CLOSURE phase only)

- [ ] T-R3-CL-01 — **Update specs/memory/data-catalog.html to reflect OQ-5 decision**
  Owner: product-engineer | Phase: CLOSURE only
  Precondition: T-R3-04 complete (OQ-5 resolved)
  Done: `data-catalog.html` reflects current `transactions_lambda` implementation;
        Silver intermediary table present if UNION path chosen.

- [ ] T-R3-CL-02 — **Update specs/memory/architecture.html to reflect schema evolution addition**
  Owner: product-engineer | Phase: CLOSURE only
  Done: `architecture.html` includes `cloudFiles.schemaEvolutionMode` in Auto Loader section.

---

## Task Summary

| ID | Work-Package | Owner | Effort | Issue | Blocked |
|----|-------------|-------|--------|-------|---------|
| T-R3-01 | A — DLT | data-engineer | M | ISSUE-016 | No |
| T-R3-02 | A — DLT | data-engineer | M | ISSUE-028 | No |
| T-R3-03 | A — Validation | data-engineer | S | ISSUE-003 follow-on | Precondition: 7d DEV run |
| T-R3-04 | A — DLT | data-engineer | L | ISSUE-031 | No (OQ-5 resolved) |
| T-R3-NEW-1 | A — DLT | data-engineer | S | ISSUE-027 | No (OQ-4 resolved) |
| T-R3-05 | B — Tests | data-engineer | L | ISSUE-015 | No |
| T-R3-CL-01 | CLOSURE | product-engineer | S | Memory update | CLOSURE phase |
| T-R3-CL-02 | CLOSURE | product-engineer | S | Memory update | CLOSURE phase |

**Total implementation tasks:** 6
**Total CLOSURE tasks:** 2
**Grand total:** 8
