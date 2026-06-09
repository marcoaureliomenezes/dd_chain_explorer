# SPEC: analytics-enrichment-r4 — Analytics Enrichment and PRD Readiness

**Status:** Aprovado
**Owner:** product-engineer
**Priority bucket:** efficiency > correctness (security cleared R1, cost cleared R2, correctness cleared R3)
**Generated from:** `.dadaia/reports/dd-chain-explorer/project-manager/2026-05-22T150000Z-mediation-index.html` (Part 2: Decision Matrix)
**Issues covered:** ISSUE-013, 018, 027, plus DA-009, DA-010, DA-012, DA-014, DA-015 from DA report
**Dependency:** data-quality-r3 must be ARCHIVED before this release begins.

---

## Goal

Enrich the analytics surface for users and achieve PRD deployment readiness: add Unity Catalog
column descriptions to all Gold tables (improving Genie NL-to-SQL accuracy), add a Genie
context instruction block, add freshness KPI tiles to all dashboards, resolve orphaned Gold MVs
(OQ-4), add analyst SQL GRANT DDL, and align PRD catalog name across all bundles (OQ-1).

## Scope In

### Analytics Enrichment

- **ISSUE-018** — Add `COMMENT ON COLUMN` DDL for all Gold MV columns in `setup_ddl.py`.
  Priority: `g_apps.*` and `g_network.*`. Column descriptions enable Genie NL-to-SQL to
  interpret field names correctly.

- **DA-009** — Add a Genie context instruction block in `genie_ethereum.yml`: describe the
  Ethereum data domain, the key entities (block, transaction, contract), and preferred query
  patterns. Genie uses this to improve NL response quality.

- **DA-010** — Add freshness KPI tile to each of the 4 dashboards: a widget showing
  `max(block_time)` or `max(event_date)` from the most critical Gold table for that dashboard.
  Helps users identify stale data before acting on it.

- **DA-012** — Add analyst GRANT statements to `setup_ddl.py` for all Gold schemas:
  `GRANT SELECT ON SCHEMA g_apps TO analysts_group` (and analogously for `g_network`,
  `g_api_keys`). Required for non-admin users to query Gold tables.

- **DA-014** — Dashboard filter UI improvements: add date-range filter widget to dashboards
  where event_date partitioning is exploitable.

- **DA-015** — Export schedule for Gold tables: add a scheduled `job_export_gold` configuration
  to export `g_apps.popular_contracts_ranking` and `g_network.network_metrics_hourly` daily
  to S3 `exports/` for external consumers.

### Orphaned Gold MVs Decision

- **ISSUE-027** — Resolve `contract_deploy_metrics_hourly` and `contract_method_activity`:
  - **If OQ-4 → surface**: add both MVs to a new "Contract Intelligence" dashboard or Genie
    context. Assign to data-analyst for dashboard implementation.
  - **If OQ-4 → drop**: remove both MVs from DLT pipeline. Assign to data-engineer.
  **BLOCKED-BY-OPERATOR-DECISION: OQ-4**

### PRD Readiness

- **ISSUE-013** — Align PRD catalog name: update non-authoritative source once operator decides.
  - **If OQ-1 → `prd`**: update `specs/memory/tech-stack.md` Catalog Convention table;
    update `specs/memory/constitution.md` Databricks/DABs Rules.
  - **If OQ-1 → `dd_chain_explorer`**: update all 9 DABs bundle prod targets that currently
    use `catalog: "prd"`.
  **BLOCKED-BY-OPERATOR-DECISION: OQ-1**

## Scope Out

- REST API implementation — not in any current release (see backlog/candidates.md)
- Multi-chain support — not in scope
- User authentication for dashboard viewers — not in scope

## Blocked Items (operator decision pending)

- **OQ-1** — PRD catalog name: `prd` (bundles) vs `dd_chain_explorer` (specs). Task T-R4-07
  is `BLOCKED-BY-OPERATOR-DECISION: OQ-1`.
- **OQ-4** — Orphaned Gold MVs: surface or drop. Task T-R4-04 is
  `BLOCKED-BY-OPERATOR-DECISION: OQ-4`.

## Success Criteria (Acceptance Gate)

1. All Gold columns in `g_apps.*` and `g_network.*` have non-empty `COMMENT` in Unity Catalog.
2. Genie context instruction block present in `genie_ethereum.yml`; Genie responds to at least
   3 natural language domain questions with correct SQL.
3. Each of the 4 dashboards has a freshness KPI tile showing `max(block_time)` or equivalent.
4. `GRANT SELECT` statements for analyst group present in `setup_ddl.py` for all Gold schemas.
5. PRD catalog name consistent between all 9 bundle prod targets and `specs/memory/` atoms
   (per OQ-1 decision).
6. Orphaned Gold MVs resolved per OQ-4 decision (surfaced or removed).

## Dependencies on Other Releases

- **Depends on:** data-quality-r3 ARCHIVED (Gold data quality required before descriptions
  and Genie context are meaningful; also OQ-3 resolved, so catalog parameterization done).
- This release has no successors currently planned.

## Risks

- OQ-1 unresolved: if `dd_chain_explorer` is canonical, all 9 bundle prod targets need update.
  High change surface — coordinate carefully with devops-engineer and test in HML first.
- OQ-4 unresolved: orphaned MV removal has performance improvement benefit; surfacing has
  analytical benefit. No default — operator must decide.
- DA-015 export schedule depends on PRD infrastructure being live (PRD deploy itself not in
  any release — requires separate operator action).

## Memory Files Affected at CLOSURE

- `specs/memory/constitution.html` — to be created from `constitution.md` during CLOSURE;
  reflect OQ-1 catalog name decision and LGPD classification added in R1.
- `specs/memory/product.html` — to be created from `product.md` during CLOSURE;
  reflect resolved OQ-4 (orphaned MVs) and updated analytics surface.
- All prior memory HTML atoms should already exist from R1/R2/R3 CLOSURE phases.
