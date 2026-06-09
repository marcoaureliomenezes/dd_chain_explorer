# Closure: Release — analytics-enrichment-r4

> **Status:** Aprovado
> **Release ID:** analytics-enrichment-r4
> **Forensic verdict:** ABANDONED
> **Owner:** product-engineer
> **Closed (forensic):** 2026-06-08
> **Authored by:** T-R5-C3 forensic investigation

---

## Summary

This release was planned to enrich the analytics surface and achieve PRD deployment
readiness: add Unity Catalog column descriptions, add a Genie context instruction block,
add freshness KPI tiles to dashboards, add analyst SQL GRANTs, configure daily export
schedule, and align PRD catalog name.

Based on forensic evidence — file state in the current working tree and absence of
implementation commits in git history — **none of the eleven implementation tasks
(T-R4-NEW-1, T-R4-01 through T-R4-09, T-R4-NEW-2) was implemented**.

The CLOSURE.md was previously a blank template with literal `<sha>` placeholders. This
document records the ground truth for each task based on evidence gathered during
audit-remediation-r5 (T-R5-C3).

Key findings: the Genie YAML (`genie_ethereum.yml`) has table descriptions and
`sample_questions` but no `instructions:` block; no `COMMENT ON COLUMN` or GRANT
statements exist in `setup_ddl.py`; no freshness KPI tile in any dashboard JSON;
`workflow_dm_export_gold.yml` exists but has no `schedule` block; only one alert exists
(80%/24h threshold) with no 50%/1h pre-warn counterpart; no per-env dashboard
parameterization (`lvdash.json` per env) was implemented.

The three CLOSURE-phase memory migration tasks (T-R4-CL-01, T-R4-CL-02, T-R4-CL-03)
are SUPERSEDED — they referenced a legacy HTML memory format (`constitution.html`,
`product.html`) that the workspace has since migrated away from (memory is now Markdown
atoms under `specs/memory/`). They are documented as superseded rather than abandoned.

This release should be moved to `specs/_archive/releases/analytics-enrichment-r4/`.

---

## Tasks completed

None of the implementation tasks were completed. CLOSURE-phase memory tasks are
superseded by the Markdown memory migration.

| Task ID | Description | Forensic verdict | Evidence |
|---------|-------------|-----------------|---------|
| T-R4-NEW-1 | Lakeview dashboard catalog parameterization | ABANDONED | Blocked by INV-1 (catalog parity investigation). No per-env `.lvdash.json` files found under `apps/dabs/dashboard_*/`. Only DEV dashboard JSONs present. |
| T-R4-01 | Add Genie context instruction block | ABANDONED | `apps/dabs/genie_ethereum/resources/genie/genie_ethereum.yml` has `sample_questions` and table descriptions but no `instructions:` block. No commit evidence for an `instructions:` addition. |
| T-R4-02 | Add freshness KPI tile to all 4 dashboards | ABANDONED | Grep for `freshness`, `max.*block_time`, `max.*event_date`, `Counter`, `kpi` in all 4 `*.lvdash.json` files returned no matches. No freshness tile present. |
| T-R4-03 | Add analyst GRANT DDL for all Gold schemas | ABANDONED | Grep for `GRANT`, `analysts` in `apps/dabs/job_ddl_setup/src/dd_chain_explorer/ddl/setup_ddl.py` returned no matches. No GRANT statements present. |
| T-R4-04 | Resolve orphaned Gold MVs (dashboard/Genie surface cleanup) | ABANDONED | This task was to clean up dashboard/Genie residual references after T-R3-NEW-1 (drop from DLT). T-R3-NEW-1 was itself abandoned (r3 was abandoned). The MVs `contract_deploy_metrics_hourly` and `contract_method_activity` are still in the DLT pipeline; no cleanup of residual references was done. |
| T-R4-05 | Add date-range filter widget to applicable dashboards | ABANDONED | Grep for `dateRange`, `date.*range`, `filter.*widget`, `event_date.*filter` in dashboard JSONs returned no matches. No date-range filter widgets present. |
| T-R4-06 | Add COMMENT ON COLUMN for all Gold MV columns | ABANDONED | Grep for `COMMENT ON` in `setup_ddl.py` returned no matches. Column comments not added. |
| T-R4-07 | Remove orphaned Gold MVs from DLT pipeline | ABANDONED | `contract_deploy_metrics_hourly` and `contract_method_activity` DLT function definitions still present in `ethereum_pipeline.py`. This is noted as superseded by T-R3-NEW-1 in TASKS.md, but T-R3-NEW-1 was also abandoned. Both paths abandoned. |
| T-R4-08 | Configure daily Gold export schedule | ABANDONED | `apps/dabs/job_export_gold/resources/workflows/workflow_dm_export_gold.yml` exists but has no `schedule` block — no cron/trigger configuration found. The job is defined but not scheduled. |
| T-R4-09 | Align PRD catalog name across all bundles and specs | ABANDONED (pre-existing) | All 10 bundle prod targets already use `catalog: "prd"`, consistent with the OQ-1 decision. However, no commit evidence attributes this to r4 work. The state appears to be pre-existing. Memory atoms (`specs/memory/tech-stack.md`, `specs/memory/constitution.md`) were not updated to reflect the decision. Task not completed. |
| T-R4-NEW-2 | Add 50%/1h pre-warn alert for API keys threshold | ABANDONED | Only one alert exists: `apps/dabs/alert_api_keys/resources/alerts/alert_api_keys_threshold.yml` (80%/24h, `seconds_to_retrigger: 86400`). No second alert at 50%/1h (`seconds_to_retrigger: 3600`) was created. |
| T-R4-CL-01 | Create specs/memory/constitution.html from constitution.md | SUPERSEDED | The workspace migrated from HTML memory atoms to Markdown memory atoms (`memory-markdown-source-v1`). `constitution.html` was never the target format for new memory; the current canonical is `specs/memory/` Markdown atoms. This task is superseded by the memory format migration and need not be executed. |
| T-R4-CL-02 | Create specs/memory/product.html from product.md | SUPERSEDED | Same reason as T-R4-CL-01. Markdown is the current memory format. `product.html` is not the target. |
| T-R4-CL-03 | Deprecate remaining legacy memory Markdown atoms | SUPERSEDED | The memory migration went in a different direction than planned: Markdown was retained as the canonical format; HTML was deprecated. The Markdown files referenced (constitution.md, product.md) remain in `specs/memory/` as the live atoms, which is correct under the current memory model. No archival needed. |

---

## Validations

No validations possible. The table below records expected validation commands alongside
the forensic finding.

| Description | Command | Forensic finding |
|-------------|---------|-----------------|
| All Gold columns have COMMENT | `SELECT column_name, comment FROM information_schema.columns WHERE table_schema IN ('g_apps','g_network')` | Not applicable — COMMENT ON COLUMN never added to setup_ddl.py |
| Genie NL query works | 3 domain queries in Genie space | Not applicable — no `instructions:` block added |
| Freshness tile renders | Visual inspection, 4 dashboards | Not applicable — no freshness tile in any dashboard JSON |
| Analyst GRANT in place | `SHOW GRANTS ON SCHEMA g_apps` | Not applicable — no GRANT added |
| PRD catalog consistent | `grep -r 'catalog:' apps/dabs/*/databricks.yml \| grep prod` | Pre-existing: all prod targets use `"prd"` but no commit from r4 |
| Export job scheduled | `databricks jobs get --job-id <id>` | Not applicable — no schedule block in workflow YAML |
| 50%/1h alert active | Alert definition in `resources/alerts/` | Not applicable — only 80%/24h alert exists |

---

## Drifts

No implementation was done in this release; no drifts from PLAN occurred. The release
was simply never implemented.

### drift-r4-cl-memory-format-superseded

**Description:** The CLOSURE-phase memory tasks (T-R4-CL-01, T-R4-CL-02, T-R4-CL-03)
were designed around a planned migration from Markdown to HTML memory atoms. The
workspace instead migrated to Markdown as the canonical format, making the HTML creation
tasks obsolete.

**Resolution:** The CLOSURE memory tasks are marked SUPERSEDED. No action required.
The existing `specs/memory/*.md` atoms are the correct current state.

**Memory updates:** None required for this drift.

---

## Memory updates

No memory updates were made during this release. The three CLOSURE-phase memory tasks
(T-R4-CL-01, T-R4-CL-02, T-R4-CL-03) are SUPERSEDED.

- `specs/memory/constitution.md` — no change from this release; atom is current Markdown.
- `specs/memory/product/index.md` — no change from this release.
- `specs/memory/tech-stack.md` — no change; OQ-1 catalog name decision (`prd` canonical) not yet recorded here.
- `specs/memory/architecture.md` — no change from this release.

Open memory debt: the OQ-1 decision (`prd` is the canonical PRD catalog name) should be
reflected in `specs/memory/tech-stack.md` and `specs/memory/constitution.md` in a future
release.

---

## Backlog returns

The following open work from r4 remains unresolved and should be promoted to
`specs/backlog/candidates.md` for the next planning round:

- `backlog/candidates.md` ← DA-009: Add Genie context `instructions:` block
- `backlog/candidates.md` ← DA-010: Add freshness KPI tile to all 4 dashboards
- `backlog/candidates.md` ← DA-012: Add analyst GRANT DDL for Gold schemas
- `backlog/candidates.md` ← DA-014: Add date-range filter widget to applicable dashboards
- `backlog/candidates.md` ← DA-015: Configure daily Gold export schedule (add `schedule` block to `workflow_dm_export_gold.yml`)
- `backlog/candidates.md` ← ISSUE-018: Add COMMENT ON COLUMN for all Gold MV columns in setup_ddl.py
- `backlog/candidates.md` ← OQ-7: Add 50%/1h pre-warn alert for API keys threshold
- `backlog/candidates.md` ← ISSUE-013: Record OQ-1 decision in memory atoms (tech-stack.md, constitution.md)
- `backlog/ideas.md` ← T-R4-NEW-1: Lakeview dashboard env parameterization (blocked on INV-1)

Note: promotion to backlog is the responsibility of project-manager, not product-engineer.

---

## Archive decision

**MOVE** — this release is fully abandoned. Move to archive:

```
git mv specs/releases/analytics-enrichment-r4 specs/_archive/releases/analytics-enrichment-r4
```

`specs/releases/ACTIVE.md` currently points at `audit-remediation-r5` — do not modify it.
This release is not referenced by ACTIVE.md and can be archived independently.
