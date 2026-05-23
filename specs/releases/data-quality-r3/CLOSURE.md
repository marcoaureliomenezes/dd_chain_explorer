# Closure: Release — data-quality-r3

> **Status:** Draft (template — populate when all TASKS.md tasks are [x] DONE)
> **Release ID:** data-quality-r3
> **Owner:** product-engineer
> **Closed:** YYYY-MM-DD

---

## Summary

<!-- 1–3 paragraphs from the product owner's perspective. -->

## Tasks completed

| Task ID | Description | Final commit |
|---------|-------------|--------------|
| T-R3-01 | Replace current_timestamp() with event-time windows in 6 Gold MVs | `<sha>` |
| T-R3-02 | Add schema evolution strategy to Auto Loader config | `<sha>` |
| T-R3-03 | Confirm eth_canonical_blocks_index bounded window under sustained load | `<sha>` |
| T-R3-04 | Resolve transactions_lambda Lambda Architecture (per OQ-5) | `<sha>` |
| T-R3-05 | Implement data-contract test suite | `<sha>` |
| T-R3-06 | Implement Lakeview catalog parameterization (per OQ-3) | `<sha>` |

---

## Validations

| Description | Command | Evidence |
|-------------|---------|----------|
| No current_timestamp() in window clauses | `grep -n "current_timestamp()" ethereum_pipeline.py` | empty output for filter contexts |
| Gold MV idempotency | Run DLT full-refresh × 2; compare row counts | stdout row count match |
| Schema evolution mode set | `grep "schemaEvolutionMode" ethereum_pipeline.py` | `addNewColumns` |
| Data-contract tests pass | `pytest apps/dabs/dlt_ethereum/tests/ -v` | all green |
| No hardcoded dev. catalog in lvdash | `grep -r '"dev\.' apps/dabs/dashboard_*/` | empty output |

---

## Drifts

<!-- Fill in during CLOSURE. -->

---

## Memory updates

- [ ] **T-R3-CL-01** — `specs/memory/data-catalog.html` — update to reflect OQ-5 decision:
  if UNION, add `s_apps.popular_contracts_txs_enriched` Silver table entry.
  if streaming-only, remove UNION references from `transactions_lambda` description.

- [ ] **T-R3-CL-02** — `specs/memory/architecture.html` — update Auto Loader section to
  include `cloudFiles.schemaEvolutionMode: "addNewColumns"` and `_schema_version` column note.

Memory files NOT migrated in this CLOSURE:
- `specs/memory/constitution.md` — deferred to R4 CLOSURE.
- `specs/memory/product.md` — deferred to R4 CLOSURE.

---

## Backlog returns

<!-- Items discovered during implementation. -->
<!-- Note: if OQ-5 → streaming-only, add contracts_ingestion Lambda to backlog/candidates.md as dead code candidate. -->

---

## Archive decision

**MOVE** — after CLOSURE.md complete and memory atoms updated:

```bash
git mv specs/releases/data-quality-r3 specs/_archive/releases/data-quality-r3
```

Update `specs/releases/ACTIVE.md`:
```
release: analytics-enrichment-r4
phase: TASKS
```
