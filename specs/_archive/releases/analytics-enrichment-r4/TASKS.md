# TASKS: analytics-enrichment-r4

**Status:** Aprovado
**Release:** analytics-enrichment-r4
**Phase:** TASKS

Work-Packages A and B run in parallel. Work-Package C unblocked (OQ-1 resolved 2026-05-22).
T-R4-04 unblocked (OQ-4 resolved 2026-05-22). T-R4-NEW-1 moved from R3.

---

## Work-Package D — Lakeview Parameterization (data-analyst)

<!-- Moved from R3 T-R3-06; deferred per OQ-3 resolution 2026-05-22 -->
<!-- BLOCKED-BY: INV-1 (catalog parity investigation) -->

- [ ] T-R4-NEW-1 — **Lakeview dashboard catalog parameterization (env parity)** | Owner: data-analyst | Effort: M
  Evidence: ISSUE-032, OQ-DA-01; OQ-3 resolved 2026-05-22 (operator: "DEV-only agora, diferir para R4/pós-INV-1")
  Write-set: `apps/dabs/dashboard_*/resources/dashboards/*.lvdash.json`
  Decision (grill 2026-05-22): Accept DEV as only active dashboard env now; implement env parity (separate .lvdash.json per env or dashboard SQL parameter widget) as part of R4 launch prep, after INV-1 completes.
  BLOCKED-BY: INV-1 (catalog parity investigation)
  Done: Each dashboard env (dev/hml/prd) has a validated .lvdash.json with correct catalog FQNs; dashboards render data in DEV and PRD.

---

## Work-Package A — Analytics Enrichment (data-analyst)

<!-- Write-set: apps/dabs/genie_ethereum/, apps/dabs/dashboard_*/, apps/dabs/dlt_ethereum/src/*/setup_ddl.py -->

- [ ] T-R4-01 — **Add Genie context instruction block** | Owner: data-analyst | Effort: S
  Evidence: DA-009, `genie_ethereum.yml`
  Write-set: `apps/dabs/genie_ethereum/genie_ethereum.yml`
  Done: `instructions:` block present in Genie YAML; at least 3 domain NL queries return
        correct Gold table SQL (verified in DEV Genie space).

- [ ] T-R4-02 — **Add freshness KPI tile to all 4 dashboards** | Owner: data-analyst | Effort: M
  Evidence: DA-010, all 4 `.lvdash.json` files
  Write-set: `apps/dabs/dashboard_*/resources/dashboards/*.lvdash.json`
  Done: Each of the 4 dashboards has a Counter/Text widget showing max timestamp from the
        relevant Gold table; tile renders with recent timestamp when pipeline is running.

- [ ] T-R4-03 — **Add analyst GRANT DDL for all Gold schemas** | Owner: data-analyst | Effort: S
  Evidence: DA-012, `setup_ddl.py`
  Write-set: `apps/dabs/dlt_ethereum/src/*/setup_ddl.py`
  Done: `GRANT SELECT ON SCHEMA g_apps TO analysts` and analogous for `g_network`, `g_api_keys`
        present in DDL setup; verified with `SHOW GRANTS ON SCHEMA g_apps`.

- [ ] T-R4-04 — **Resolve orphaned Gold MVs** | Owner: data-analyst (if surface) | Effort: M
  Evidence: ISSUE-027, DA-008, `data-catalog.md §g_apps`
  Write-set: depends on OQ-4 decision
  Decision (grill 2026-05-22): Drop from DLT — handled by T-R3-NEW-1 (data-quality-r3). This task covers dashboard/Genie surface cleanup only if residual references exist after R3.
  Done (if surface): new "Contract Intelligence" dashboard or Genie context entry references both MVs.
  Done (if drop): MVs removed from pipeline and catalog; compute savings confirmed.

- [ ] T-R4-05 — **Add date-range filter widget to applicable dashboards** | Owner: data-analyst | Effort: S
  Evidence: DA-014, `*.lvdash.json`
  Write-set: `apps/dabs/dashboard_network_overview/resources/dashboards/01_network_overview.lvdash.json`,
             `apps/dabs/dashboard_gas_analytics/resources/dashboards/03_gas_analytics.lvdash.json`
  Done: Date-range filter widget linked to `event_date` column present in at least 2 dashboards;
        filtering a date range reduces returned data to that range only.

---

## Work-Package B — Gold DDL + Pipeline (data-engineer)

<!-- Write-set: apps/dabs/dlt_ethereum/src/*/setup_ddl.py, ethereum_pipeline.py -->

- [ ] T-R4-06 — **Add COMMENT ON COLUMN for all Gold MV columns** | Owner: data-engineer | Effort: M
  Evidence: ISSUE-018, DA-007, `setup_ddl.py` (no COMMENT ON COLUMN currently)
  Write-set: `apps/dabs/dlt_ethereum/src/*/setup_ddl.py`
  Done: All columns in `g_apps.*` and `g_network.*` have non-NULL COMMENT in Unity Catalog;
        verified via `SELECT column_name, comment FROM information_schema.columns WHERE table_schema IN ('g_apps', 'g_network')`.

- [ ] T-R4-07 — **Remove orphaned Gold MVs from DLT pipeline** | Owner: data-engineer | Effort: M
  Evidence: ISSUE-027 (follow-on if OQ-4 → drop)
  Write-set: `apps/dabs/dlt_ethereum/src/*/ethereum_pipeline.py`
  Decision (grill 2026-05-22): OQ-4 resolved — drop path confirmed. DLT removal is covered by T-R3-NEW-1 (data-quality-r3). This task is superseded by T-R3-NEW-1; skip unless T-R3-NEW-1 is not yet complete by R4.
  Done: `contract_deploy_metrics_hourly` and `contract_method_activity` DLT definitions removed;
        tables dropped from DEV catalog; DLT pipeline run completes without referencing them.

- [ ] T-R4-08 — **Configure daily Gold export schedule** | Owner: data-engineer | Effort: S
  Evidence: DA-015
  Write-set: `apps/dabs/job_export_gold/databricks.yml`
  Done: `job_export_gold` DABs job has daily schedule configured; S3 `exports/` path receives
        files on next scheduled run.

---

## Work-Package C — PRD Catalog Alignment (devops-engineer + data-engineer)

<!-- Write-set: apps/dabs/*/databricks.yml (all 9 prod targets) OR specs/memory/*.md -->
<!-- OQ-1 resolved 2026-05-22: PRD catalog = "prd" is canonical -->

- [ ] T-R4-09 — **Align PRD catalog name across all bundles and specs** | Owner: devops-engineer | Effort: S
  Evidence: ISSUE-013, UC-01, `dlt_ethereum/databricks.yml:63`
  Write-set: `apps/dabs/*/databricks.yml` (all 9) OR `specs/memory/tech-stack.md` + `specs/memory/constitution.md`
  Decision (grill 2026-05-22): PRD catalog = "prd" — confirmed canonical. Specs memory update deferred to pipeline-restart-r1 CLOSURE.
  Done: All 9 bundle prod targets and all memory atom references use the same catalog name;
        `databricks bundle deploy --target prod --dry-run` succeeds with resolved catalog name.

---

## Work-Package E — Alerting (devops-engineer)

<!-- Write-set: apps/dabs/alert_api_keys/resources/alerts/ -->

- [ ] T-R4-NEW-2 — **Add 50%/1h pre-warn alert for API keys threshold** | Owner: devops-engineer | Effort: S
  Evidence: OQ-7 resolved 2026-05-22; existing 80%/24h alert kept
  Write-set: `apps/dabs/alert_api_keys/resources/alerts/`
  Decision (grill 2026-05-22): Add pre-warn at 50% threshold / 1h retrigger alongside existing 80%/24h critical alert.
  Done: New alert YAML at 50% threshold with `seconds_to_retrigger: 3600` deployed and triggers correctly in DEV.

---

## CLOSURE Tasks (product-engineer — CLOSURE phase only)

- [ ] T-R4-CL-01 — **Create specs/memory/constitution.html from constitution.md**
  Owner: product-engineer | Phase: CLOSURE only
  Done: `specs/memory/constitution.html` exists; reflects OQ-1 catalog name decision and
        LGPD classification added in R1.

- [ ] T-R4-CL-02 — **Create specs/memory/product.html from product.md**
  Owner: product-engineer | Phase: CLOSURE only
  Done: `specs/memory/product.html` exists; reflects resolved OQ-4 (orphaned MVs decision),
        updated analytics surface (freshness tiles, Genie context, analyst GRANTs).

- [ ] T-R4-CL-03 — **Deprecate remaining legacy memory Markdown atoms**
  Owner: product-engineer | Phase: CLOSURE only
  Done: `constitution.md` and `product.md` moved to `specs/_archive/legacy-memory/<timestamp>/`.
        All 6 original memory atoms now have HTML equivalents; Markdown versions archived.
        Legacy `specs/SPEC.md` and `specs/domains/` tree moved to `specs/_archive/`.

---

## Task Summary

| ID | Work-Package | Owner | Effort | Issue / Source | Blocked |
|----|-------------|-------|--------|----------------|---------|
| T-R4-NEW-1 | D — Lakeview | data-analyst | M | ISSUE-032 | INV-1 |
| T-R4-01 | A — Analytics | data-analyst | S | DA-009 | No |
| T-R4-02 | A — Analytics | data-analyst | M | DA-010 | No |
| T-R4-03 | A — Analytics | data-analyst | S | DA-012 | No |
| T-R4-04 | A/B — MV Decision | data-analyst or data-engineer | M | ISSUE-027 | No (OQ-4 resolved) |
| T-R4-05 | A — Analytics | data-analyst | S | DA-014 | No |
| T-R4-06 | B — DDL | data-engineer | M | ISSUE-018 | No |
| T-R4-07 | B — Pipeline | data-engineer | M | ISSUE-027 (drop path) | No (OQ-4 resolved) |
| T-R4-08 | B — Pipeline | data-engineer | S | DA-015 | No |
| T-R4-09 | C — PRD | devops-engineer | S | ISSUE-013 | No (OQ-1 resolved) |
| T-R4-NEW-2 | E — Alerting | devops-engineer | S | OQ-7 | No |
| T-R4-CL-01 | CLOSURE | product-engineer | M | Memory migration | CLOSURE phase |
| T-R4-CL-02 | CLOSURE | product-engineer | M | Memory migration | CLOSURE phase |
| T-R4-CL-03 | CLOSURE | product-engineer | M | Legacy archive | CLOSURE phase |

**Total implementation tasks:** 11
**Total CLOSURE tasks:** 3
**Grand total:** 14
