# Closure: Release — analytics-enrichment-r4

> **Status:** Draft (template — populate when all TASKS.md tasks are [x] DONE)
> **Release ID:** analytics-enrichment-r4
> **Owner:** product-engineer
> **Closed:** YYYY-MM-DD

---

## Summary

<!-- 1–3 paragraphs from the product owner's perspective. -->

## Tasks completed

| Task ID | Description | Final commit |
|---------|-------------|--------------|
| T-R4-01 | Add Genie context instruction block | `<sha>` |
| T-R4-02 | Add freshness KPI tile to all 4 dashboards | `<sha>` |
| T-R4-03 | Add analyst GRANT DDL for all Gold schemas | `<sha>` |
| T-R4-04 | Resolve orphaned Gold MVs (per OQ-4) | `<sha>` |
| T-R4-05 | Add date-range filter widget to applicable dashboards | `<sha>` |
| T-R4-06 | Add COMMENT ON COLUMN for all Gold MV columns | `<sha>` |
| T-R4-07 | Remove orphaned Gold MVs from pipeline (if OQ-4 → drop) | `<sha>` |
| T-R4-08 | Configure daily Gold export schedule | `<sha>` |
| T-R4-09 | Align PRD catalog name across all bundles and specs (per OQ-1) | `<sha>` |

---

## Validations

| Description | Command | Evidence |
|-------------|---------|----------|
| All Gold columns have COMMENT | `SELECT column_name, comment FROM information_schema.columns WHERE table_schema IN ('g_apps','g_network')` | no NULL comments |
| Genie NL query works | 3 domain queries in Genie space | screenshots or stdout |
| Freshness tile renders | Visual inspection, 4 dashboards | `<sha or screenshot>` |
| Analyst GRANT in place | `SHOW GRANTS ON SCHEMA g_apps` | analysts group has SELECT |
| PRD catalog consistent | `grep -r 'catalog:' apps/dabs/*/databricks.yml \| grep prod` | all use same catalog |
| Export job scheduled | `databricks jobs get --job-id <id>` | schedule confirmed |

---

## Drifts

<!-- Fill in during CLOSURE. -->

---

## Memory updates

- [ ] **T-R4-CL-01** — `specs/memory/constitution.html` — create from `constitution.md`; reflect
  OQ-1 canonical catalog name decision; LGPD classification section added in R1.

- [ ] **T-R4-CL-02** — `specs/memory/product.html` — create from `product.md`; reflect
  resolved OQ-4 (orphaned MVs), expanded analytics surface (Genie context, freshness tiles,
  analyst GRANTs, export schedule).

- [ ] **T-R4-CL-03** — Archive remaining legacy Markdown atoms:
  ```bash
  mkdir -p specs/_archive/legacy-memory/<UTC-timestamp>
  git mv specs/memory/constitution.md specs/_archive/legacy-memory/<UTC-timestamp>/
  git mv specs/memory/product.md specs/_archive/legacy-memory/<UTC-timestamp>/
  git mv specs/SPEC.md specs/_archive/
  git mv specs/domains specs/_archive/
  ```

After all HTML atoms exist (architecture, aws-resources, data-catalog from R1; tech-stack from R2;
constitution, product from R4), all 6 memory atoms are HTML and the legacy Markdown tree is archived.

---

## Backlog returns

<!-- Items discovered during implementation. -->

---

## Archive decision

**MOVE** — after CLOSURE.md complete and memory atoms written:

```bash
git mv specs/releases/analytics-enrichment-r4 specs/_archive/releases/analytics-enrichment-r4
```

Update `specs/releases/ACTIVE.md`:
```
release: none
phase: none
```
