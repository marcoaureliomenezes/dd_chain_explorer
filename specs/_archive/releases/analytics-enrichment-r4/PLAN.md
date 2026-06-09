# PLAN: analytics-enrichment-r4

**Status:** Aprovado
**Release:** analytics-enrichment-r4
**Owner:** product-engineer
**Source:** SPEC.md (this release) + PM mediation matrix Part 2

---

## Strategy

Two parallel work-packages: data-analyst (dashboards, Genie, GRANT DDL) and data-engineer
(Gold column descriptions DDL, orphaned MV decision, export schedule). PRD catalog alignment
(OQ-1) is a cross-cutting concern that must be applied to all 9 bundles before PRD launch.

```
Work-Package A: Analytics enrichment (data-analyst)
  ├── A1: Genie context instruction block (DA-009)
  ├── A2: Freshness KPI tile — all 4 dashboards (DA-010)
  ├── A3: Analyst GRANT DDL (DA-012)
  ├── A4: Dashboard filter UI improvements (DA-014)
  └── A5: Orphaned Gold MV surface — if OQ-4 → surface (ISSUE-027)

Work-Package B: Gold column descriptions + pipeline (data-engineer)
  ├── B1: COMMENT ON COLUMN for Gold tables (ISSUE-018)
  ├── B2: Orphaned Gold MV removal — if OQ-4 → drop (ISSUE-027)
  └── B3: Export schedule for Gold tables (DA-015)

Work-Package C: PRD catalog name alignment (devops-engineer + data-engineer)
  └── C1: Align catalog name per OQ-1 decision (ISSUE-013)
  BLOCKED-BY-OPERATOR-DECISION: OQ-1
```

---

## Work-Package A: Analytics Enrichment (data-analyst)

### A1 — Genie context instruction block (DA-009)

File: `apps/dabs/genie_ethereum/genie_ethereum.yml`
Add `instructions:` block to Genie space configuration:
```yaml
instructions: |
  This space contains Ethereum mainnet on-chain data from block ~18,000,000 to present.
  Key schemas:
  - g_apps: application-level transaction analytics (popular contracts, P2P transfers, gas)
  - g_network: network-level metrics (TPS, block production, burn rate, orphan rate)
  - g_api_keys: API key consumption health (Etherscan, Infura/Alchemy)
  
  Key entities: block (eth_blocks), transaction (transactions_ethereum), contract (popular_contracts_ranking)
  Block time is stored as Unix timestamp in 'block_time' column.
  'tx_hash' is the unique identifier for transactions.
  Preferred queries: use Gold schema tables (g_* prefix), not Silver (s_*).
```

### A2 — Freshness KPI tile on all 4 dashboards (DA-010)

Files: all 4 `.lvdash.json` files
Add a `Text/Counter` widget per dashboard:
- Network overview: `SELECT max(block_time) as last_block FROM g_network.network_metrics_hourly`
- Hot contracts: `SELECT max(event_date) as last_update FROM g_apps.popular_contracts_ranking`
- Gas analytics: `SELECT max(block_hour) as last_hour FROM g_apps.gas_price_distribution_hourly`
- API health: `SELECT max(last_call_at) as last_api_call FROM g_api_keys.etherscan_consumption`

### A3 — Analyst GRANT DDL (DA-012)

File: `apps/dabs/dlt_ethereum/src/*/setup_ddl.py` (or DDL setup file)
Add at end of DDL setup:
```sql
GRANT SELECT ON SCHEMA g_apps TO analysts;
GRANT SELECT ON SCHEMA g_network TO analysts;
GRANT SELECT ON SCHEMA g_api_keys TO analysts;
```
(Syntax varies by Unity Catalog version; adjust for service principal group name.)

### A4 — Dashboard date-range filter (DA-014)

Files: dashboards where `event_date` partition column is queryable
Add date-range filter widget linked to `event_date` parameter.
Priority: `network_overview` and `gas_analytics` (have event_date in their queries).

### A5 — Orphaned Gold MV surface (ISSUE-027, if OQ-4 → surface)

If operator selects "surface":
Create new `dashboard_contract_intelligence` DABs bundle with two widgets:
- Hourly deployment rate chart from `g_apps.contract_deploy_metrics_hourly`
- Top method call ranking from `g_apps.contract_method_activity`
Alternatively, add to Genie context instructions referencing both tables.

---

## Work-Package B: Gold Column Descriptions + Pipeline (data-engineer)

### B1 — COMMENT ON COLUMN for Gold tables (ISSUE-018)

File: `apps/dabs/dlt_ethereum/src/*/setup_ddl.py`
Add `COMMENT ON COLUMN <schema>.<table>.<column> IS '<description>'` for all Gold MV columns.
Priority order:
1. `g_apps.*` — application-facing, Genie-critical
2. `g_network.*` — network health, dashboard-critical
3. `g_api_keys.*` — operational, lower Genie usage

Total estimated: ~80 column descriptions across all Gold MVs.

### B2 — Orphaned Gold MV removal (ISSUE-027, if OQ-4 → drop)

**BLOCKED-BY-OPERATOR-DECISION: OQ-4**

If operator selects "drop":
File: `apps/dabs/dlt_ethereum/src/*/ethereum_pipeline.py`
Remove `@dlt.table` decorators and function bodies for:
- `g_apps.contract_deploy_metrics_hourly`
- `g_apps.contract_method_activity`
Drop tables: `DROP TABLE dev.g_apps.contract_deploy_metrics_hourly`
Update `specs/memory/data-catalog.*` to remove entries.

### B3 — Export schedule for Gold tables (DA-015)

File: `apps/dabs/job_export_gold/databricks.yml` (or create if not exists)
Configure daily export job:
- Source: `g_apps.popular_contracts_ranking`, `g_network.network_metrics_hourly`
- Destination: `s3://dm-chain-explorer-lakehouse/exports/{table_name}/year=Y/month=M/day=D/`
- Format: JSON
- Schedule: daily 02:00 UTC

---

## Work-Package C: PRD Catalog Name Alignment (ISSUE-013)

**Owner:** devops-engineer + data-engineer
**BLOCKED-BY-OPERATOR-DECISION: OQ-1**

**If OQ-1 → `prd` (bundles are canonical):**
Update specs:
- `specs/memory/tech-stack.md` Catalog Convention: change `prod` row from `dd_chain_explorer` to `prd`
- `specs/memory/constitution.md` Databricks/DABs Rules: update catalog target table

**If OQ-1 → `dd_chain_explorer` (specs are canonical):**
Update 9 DABs bundle prod targets:
```yaml
# All 9 databricks.yml prod target blocks
targets:
  prod:
    catalog: dd_chain_explorer  # was: prd
```
Files: `apps/dabs/*/databricks.yml` (9 files)
Test in HML first; apply to PRD after HML validation.

---

## Architecture Decisions (this release)

- **Genie context instruction** — added as a static YAML string. If the Genie API adds
  dynamic context injection, migrate to that. Current approach is idempotent (redeploy replaces).
- **Column descriptions via COMMENT ON COLUMN** — Unity Catalog-native. No code change to DLT
  pipeline logic; only DDL setup script additions.
- **Orphaned MV decision** — either path is architecturally correct per the chosen intent.
  Drop reduces DLT compute cost; surface provides analytical value.

## BLOCKED-BY-OPERATOR-DECISION Items

| OQ | Impact | Default |
|----|--------|---------|
| OQ-1 | PRD catalog name canonical source | None — operator must decide |
| OQ-4 | Orphaned Gold MVs: surface or drop | None — operator must decide |

## Validation Plan

1. `SELECT column_name, comment FROM information_schema.columns WHERE table_schema = 'g_apps'` —
   verify all Gold columns have non-NULL comments.
2. Genie NL query test: "What are the top 5 contracts by transaction volume today?" —
   verify correct Gold table reference in generated SQL.
3. Each dashboard freshness tile shows a timestamp within the last 30 minutes (if pipeline active).
4. `SHOW GRANTS ON SCHEMA g_apps` — verify analysts group has SELECT.
5. PRD bundle deploy test (HML target): `databricks bundle deploy --target prod` — verify
   catalog name resolves correctly per OQ-1 decision.
