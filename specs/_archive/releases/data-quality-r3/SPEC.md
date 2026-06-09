# SPEC: data-quality-r3 — Pipeline Correctness and Data Contract Enforcement

**Status:** Aprovado
**Owner:** product-engineer
**Priority bucket:** correctness (pipeline operational since R1; security + cost cleared in R1/R2)
**Generated from:** `.dadaia/reports/dd-chain-explorer/project-manager/2026-05-22T150000Z-mediation-index.html` (Part 2: Decision Matrix)
**Issues covered:** ISSUE-003, 015, 016, 028, 031, 032
**Dependency:** pipeline-restart-r1 must be ARCHIVED; cost-and-availability-r2 must be ARCHIVED.

---

## Goal

Fix the correctness technical debt in the DLT pipeline: replace wall-clock windows with
event-time windows in Gold MVs, add data-contract tests, implement schema evolution strategy,
resolve the `transactions_lambda` Lambda Architecture drift, and unblock the dashboard
multi-environment catalog parameterization.

## Scope In

### DLT Pipeline Correctness

- **ISSUE-016** — Replace `current_timestamp()` with event-time windows anchored to `block_time`
  or `tx_timestamp` in all 6 Gold MVs. Makes full-refresh deterministic (DLT idempotency
  contract). (`ethereum_pipeline.py:539,937,1041,1178`)

- **ISSUE-028** — Add `cloudFiles.schemaEvolutionMode: "addNewColumns"` to Auto Loader config.
  Add `_schema_version` metadata column. Add DLT expectation for unknown column alerting.
  (`ethereum_pipeline.py:66–78`)

- **ISSUE-030 (validation)** — Re-verify `expect_or_drop` for `from_address` applied in R1;
  confirm propagation is blocked at Bronze.

### Scalability (already in R1 — verify in R3)

- **ISSUE-003** — Bounded rolling window for `eth_canonical_blocks_index` applied in R1.
  R3 validates correctness under sustained load (DEV pipeline must have run for ≥ 7 days
  since R1 restart before this can be confirmed green).

### Data-Contract Tests

- **ISSUE-015** — Implement pytest + delta-rs data-contract test suite:
  - One schema test per DLT layer (Bronze, Silver, Gold)
  - Row-count smoke test per pipeline run
  - Idempotency test for Gold MVs (full-refresh produces same count ± tolerance)
  - Canonical blocks correctness test (orphan rate within expected range)
  (`find repos/ -name "test_*.py"` — currently empty)

### Lambda Architecture Resolution

- **ISSUE-031** — Resolve `transactions_lambda` Lambda Architecture drift:
  - **If OQ-5 → UNION**: implement `s_apps.popular_contracts_txs_enriched` Silver intermediary
    table (SA requirement for medallion invariant). Then implement UNION in `transactions_lambda`.
  - **If OQ-5 → streaming-only**: update `data-catalog.md` spec to remove UNION, mark
    `contracts_ingestion` Lambda as dead code candidate.
  **BLOCKED-BY-OPERATOR-DECISION: OQ-5**

### Dashboard Catalog Parameterization

- **ISSUE-032** — Implement whichever Lakeview parameterization pattern operator selects (OQ-3):
  - Option a: SQL parameter widget in each dashboard
  - Option b: Separate `.lvdash.json` files per environment
  - Option c: Accept DEV-only and defer to PRD launch
  **BLOCKED-BY-OPERATOR-DECISION: OQ-3**

## Scope Out

- UC column descriptions → Release 4 (ISSUE-018)
- Genie context instruction block → Release 4
- Orphaned Gold MVs decision → Release 4 (ISSUE-027, pending OQ-4)
- PRD catalog name alignment → Release 4 (ISSUE-013, pending OQ-1)
- REST API implementation → not in any release yet

## Blocked Items (operator decision pending)

- **OQ-3** — Lakeview parameterization pattern. Task T-R3-05 is `BLOCKED-BY-OPERATOR-DECISION: OQ-3`.
- **OQ-5** — transactions_lambda direction (UNION vs streaming-only). Tasks T-R3-04 and T-R3-04b are
  `BLOCKED-BY-OPERATOR-DECISION: OQ-5`.

## Success Criteria (Acceptance Gate)

1. All Gold MVs use event-time windows; `current_timestamp()` absent from window filter clauses
   in `ethereum_pipeline.py`. Full-refresh produces identical row counts on two consecutive runs
   on the same data.
2. At least one schema test, one row-count smoke test, and one idempotency test per DLT layer pass
   in CI.
3. `cloudFiles.schemaEvolutionMode: "addNewColumns"` present in Auto Loader config; `_schema_version`
   column present in Bronze tables.
4. `transactions_lambda` implementation aligns with operator intent (UNION with Silver intermediary
   OR streaming-only per OQ-5 decision).
5. Dashboard catalog parameterization implemented per OQ-3 operator selection; dashboards deployable
   to both DEV and (if applicable) HML/PRD targets without hardcoded catalog strings.
6. `eth_canonical_blocks_index` bounded window confirmed running under ≥ 7 days of sustained DEV load
   with no O(N^2) scan warnings.

## Dependencies on Other Releases

- **Depends on:** pipeline-restart-r1 ARCHIVED (pipeline must be operational for test validation).
- **Depends on:** cost-and-availability-r2 ARCHIVED (infrastructure stable before correctness work).
- **Enables:** analytics-enrichment-r4 (Gold data quality required before UC column descriptions
  and Genie context are meaningful).

## Risks

- OQ-5 unresolved before R3 starts: T-R3-04 is fully blocked. The remaining tasks (ISSUE-016,
  028, 015, 032) proceed independently.
- OQ-3 unresolved: T-R3-05 is fully blocked. Workaround: keep DEV-only hardcoded catalogs and
  defer to R4 (Option c default).
- Data-contract tests (ISSUE-015) have L effort — largest task in R3. Risk: DLT test runner
  compatibility with delta-rs version on DBR 15.x. Mitigation: test in DEV first.

## Memory Files Affected at CLOSURE

- `specs/memory/data-catalog.html` — already created in R1 CLOSURE; update to reflect
  OQ-5 decision and any new Silver intermediary table.
- `specs/memory/architecture.html` — already created in R1 CLOSURE; update for schema
  evolution strategy addition.
