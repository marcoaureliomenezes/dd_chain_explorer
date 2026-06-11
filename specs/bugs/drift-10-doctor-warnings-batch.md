---
name: drift-10-doctor-warnings-batch
status: Closed
severity: LOW
reported: 2026-06-08
closed: 2026-06-11
fixed_in: v0.3.0 (T-R6-S4/S5/S6, feature/v0.3.0)
surface: specs/domains/ (legacy specs) + specs/memory atoms (token_estimate + headings)
session_id: null
audit_ref: specs/audits/20260609T013037Z/audit.md#DRIFT-10
---

**Closure evidence (2026-06-11, v0.3.0 CLOSURE):**
- SPEC-DOC-007 (legacy `specs/domains/` + `specs/releases/legacy/`): archived by
  T-R6-S4 — both gone from the live tree under `specs/_archive/`.
- token_estimate drift: T-R6-S5 recomputed all drifted atoms with the doctor's own
  formula (body `words × 1.35`) and fixed frontmatter: architecture 2400→1950,
  aws-resources 1200→1860, capture-layer 800→740, data-catalog 1400→1830,
  medallion-pipelines 900→580, serving-layer 600→435, tech-stack 1200→1910 (after
  v0.3.0 content update); `product/catalog.json` synced.
- Heading allowlist: T-R6-S6 evaluated every non-standard heading — all are valid
  domain-specific section names (renaming them to the library's dadaia-internal
  Group B/C strings would corrupt meaning); justified and kept. Upstream library bug
  filed: `repos/dadaia-workspace/specs/bugs/memory-heading-allowlist-not-consumer-extensible.md`
  (allowlist hardcoded + not consumer-extensible; library's own scaffold violates it).
  New atoms authored in v0.3.0 (`cicd-pipeline.md`) use Group-A canonical headings only.
- Full outcome documented in `specs/releases/v0.3.0/CLOSURE.md` §Drifts.

**Symptom:** `dadaia specs doctor` reports a batch of non-blocking warnings
(0 errors):
- **SPEC-DOC-007**: 8 legacy SPEC/PLAN/TASKS under `specs/domains/`
  (applications, infrastructure, devops, data-engineering, data-analytics +
  applications/rest-api) live outside `releases/` or `_archive/`.
- **token_estimate drift** on 6 memory atoms (architecture 25%, aws-resources
  50%, capture-layer 25%, data-catalog 30%, medallion-pipelines 35%,
  serving-layer 28%).
- **Non-standard heading names** in several atoms not on the curated allowlist
  (e.g. `## AWS Infrastructure`, `## S3 Buckets`, `## Schema: ...`).

**Repro:**
```
DADAIA_CONTEXT=dd-chain-explorer dadaia specs doctor
# Summary: 0 OK, 8 WARN-only, 0 ERROR (memory) + SPEC-DOC-007 (domains)
```

**Expected:** Legacy `specs/domains/` specs migrated/archived; atom
`token_estimate` frontmatter matches computed counts; headings normalised or
the allowlist extended.

**Notes:** Lowest priority, zero blocking impact. `domains/` migration is
product-engineer (spec ownership); token_estimate + heading fixes are
product-engineer for atoms (memory write-locked to PE in DEFINITION/CLOSURE).
The heading-allowlist warnings may instead warrant extending the library's
`lint-memory-atoms.py` allowlist (ai-engineer) rather than rewriting valid
domain-specific headings — operator/architect call.
