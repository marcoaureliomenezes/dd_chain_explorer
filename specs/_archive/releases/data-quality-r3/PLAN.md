# PLAN: data-quality-r3

**Status:** Aprovado
**Release:** data-quality-r3
**Owner:** product-engineer
**Source:** SPEC.md (this release) + PM mediation matrix Part 2

---

## Strategy

All tasks are in the data layer (DLT pipeline code and test suite). data-engineer owns
the pipeline fixes and test suite. data-analyst owns the dashboard parameterization.
Blocked tasks (OQ-3, OQ-5) are documented inline and can be parallelized once operator
decisions are received.

```
Work-Package A: DLT pipeline correctness (data-engineer)
  ├── A1: event-time windows in Gold MVs (ISSUE-016)
  ├── A2: schema evolution strategy (ISSUE-028)
  └── A3: transactions_lambda resolution (ISSUE-031) — BLOCKED-BY-OPERATOR-DECISION: OQ-5

Work-Package B: Data-contract tests (data-engineer)
  └── B1: pytest + delta-rs test suite (ISSUE-015)

Work-Package C: Dashboard parameterization (data-analyst)
  └── C1: Lakeview catalog parameterization (ISSUE-032) — BLOCKED-BY-OPERATOR-DECISION: OQ-3
```

---

## Work-Package A: DLT Pipeline Correctness

**Owner:** data-engineer
**File:** `apps/dabs/dlt_ethereum/src/*/ethereum_pipeline.py`

### A1 — Event-time windows in Gold MVs (ISSUE-016)

Lines: `ethereum_pipeline.py:539,937,1041,1178` (and any others with `current_timestamp()`)
Replace pattern:
```python
# Before (non-idempotent — wall-clock)
WHERE timestamp >= current_timestamp() - INTERVAL 1 HOUR

# After (idempotent — event-time)
WHERE block_time >= (SELECT max(block_time) FROM s_apps.eth_blocks) - INTERVAL 1 HOUR
# or equivalently using tx_timestamp where block_time is unavailable
```

Apply to all 6 Gold MVs using `current_timestamp()` in window filter clauses.
After change, run two consecutive full-refresh DLT runs and confirm row counts are identical.

### A2 — Schema evolution strategy (ISSUE-028)

File: `ethereum_pipeline.py:66–78` (Auto Loader config)
Add to `cloudFiles` options:
```python
"cloudFiles.schemaEvolutionMode": "addNewColumns"
```
Add `_schema_version` as a metadata column populated via `input_file_name()` or a constant
tied to the pipeline version.
Add DLT expectation for schema drift alerting:
```python
@dlt.expect_or_warn("no_unknown_columns", ...)
```

### A3 — transactions_lambda Lambda Architecture (ISSUE-031) — BLOCKED-BY-OPERATOR-DECISION: OQ-5

**If OQ-5 → UNION:**
1. Create Silver intermediary table `s_apps.popular_contracts_txs_enriched`:
   - Sources: `b_ethereum.popular_contracts_txs` (batch Bronze)
   - Applies same enrichment as `transactions_ethereum` (type_cast, decode_type labeling)
2. Update `transactions_lambda` Gold MV to UNION:
   - `transactions_ethereum` (streaming, decode_type priority 1–3)
   - `s_apps.popular_contracts_txs_enriched` (batch, decode_type priority 4)
   - Deduplicate by `tx_hash`, priority by decode_type ascending
3. Update `data-catalog.md` (or its HTML replacement) to reflect new Silver table.

**If OQ-5 → streaming-only:**
1. Remove UNION from `transactions_lambda` spec (it is already the implementation).
2. Update architecture ADR-005 note to say "UNION is archived intent — streaming-only as of R3".
3. Add `contracts_ingestion` Lambda to dead code candidates in `backlog/candidates.md`.

---

## Work-Package B: Data-Contract Tests (ISSUE-015)

**Owner:** data-engineer
**New directory:** `apps/dabs/dlt_ethereum/tests/` (or equivalent test path)

### B1 — Test suite implementation

Test framework: `pytest` + `delta` Python library (delta-rs compatible with DBR 15.x)

Required tests:
1. **Bronze schema test** — verify Bronze tables have required columns (`block_number`, `tx_hash`,
   `from_address`, `to_address`, `value`, etc.) with expected types.
2. **Silver row-count smoke** — after a DLT trigger run, Silver tables have row count > 0
   and Bronze row count is ≥ Silver (no row inflation).
3. **Gold MV idempotency** — run `dm-ethereum` full-refresh twice; compare
   `g_apps.popular_contracts_ranking` row count. Expect count_run2 == count_run1 ± 5% tolerance.
4. **Canonical blocks correctness** — `eth_canonical_blocks_index` has orphan rate < 1% for
   last 1,000 blocks (validates bounded window correctness).
5. **from_address drop enforcement** — verify no rows with NULL `from_address` in Silver
   `transactions_ethereum` (validates R1 T-R1-19 fix).

CI integration: add test step to DABs deploy workflow for DEV target only.

---

## Work-Package C: Dashboard Catalog Parameterization (ISSUE-032)

**Owner:** data-analyst
**BLOCKED-BY-OPERATOR-DECISION: OQ-3**

Awaiting operator selection:
- **Option a** — SQL parameter widget: each dashboard gets a catalog parameter widget at the
  top; default = `dev`. Users can switch to `hml` or `dd_chain_explorer` (PRD).
- **Option b** — Separate `.lvdash.json` per env: maintain `01_network_overview_dev.lvdash.json`,
  `01_network_overview_prd.lvdash.json`, etc. Deployed per target.
- **Option c** — Accept DEV-only; defer multi-env to R4 launch prep. No changes in R3.

Once operator decides, implement chosen pattern for all 4 dashboards.

---

## Architecture Decisions (this release)

- **Event-time over wall-clock in MVs** — Gold MVs become idempotent, enabling reliable
  backfill and deterministic testing. The `max(block_time)` anchor uses the latest ingested
  block as the reference point — aligned with how the streaming pipeline actually delivers data.
- **addNewColumns schema evolution** — safe default: new fields from Ethereum protocol upgrades
  (e.g. EIP-4844 blob fields) flow through without pipeline failure; old consumers see NULLs
  for new columns until they adopt them.
- **transactions_lambda direction** — pending OQ-5. Architecture decision record ADR-005 will
  be updated to reflect the chosen path.

## BLOCKED-BY-OPERATOR-DECISION Items

| OQ | Impact | Default |
|----|--------|---------|
| OQ-3 | Dashboard parameterization pattern | Option c (DEV-only, defer to R4) |
| OQ-5 | transactions_lambda: UNION vs streaming-only | None — operator must decide |

## Validation Plan

1. Full-refresh DLT run × 2 — verify Gold MV row counts identical.
2. `pytest apps/dabs/dlt_ethereum/tests/ -v` — all 5 tests green.
3. `grep -n "current_timestamp()" apps/dabs/dlt_ethereum/src/*/ethereum_pipeline.py` — no matches
   in window filter clauses (only allowed in non-window contexts).
4. Bronze table has `_schema_version` column: `SELECT _schema_version FROM dev.b_ethereum.eth_transactions LIMIT 1`.
5. transactions_lambda row count validation (depends on OQ-5 decision).
