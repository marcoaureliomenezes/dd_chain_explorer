---
name: drift-10-doctor-warnings-batch
status: Open
severity: LOW
reported: 2026-06-08
surface: specs/domains/ (legacy specs) + specs/memory atoms (token_estimate + headings)
session_id: null
audit_ref: specs/audits/20260609T013037Z/audit.md#DRIFT-10
---

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
