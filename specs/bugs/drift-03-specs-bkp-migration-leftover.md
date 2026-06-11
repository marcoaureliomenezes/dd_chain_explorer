---
name: drift-03-specs-bkp-migration-leftover
status: Closed
severity: MEDIUM
reported: 2026-06-08
surface: repos/dd-chain-explorer/specs_bkp/ (migration leftover)
session_id: null
fixed_in: cb218f7
closed: 2026-06-11
audit_ref: specs/audits/20260609T013037Z/audit.md#DRIFT-03
---

**Symptom:** `specs_bkp/0→1-20260609T002529Z/` (520 KB) sits at the repo root —
a backup written by a `dadaia specs upgrade` run. It is a full copy of the old
specs tree (backlog/, domains/, memory/, releases/, SPEC.md) and is not a
canonical repo directory.

**Repro:**
```
ls repos/dd-chain-explorer/specs_bkp/0→1-20260609T002529Z/
du -sh repos/dd-chain-explorer/specs_bkp/   # ~520K
git ls-files | grep '^specs_bkp/'           # untracked (no output)
```

**Expected:** Repo working trees must not carry migration/state backup
directories. The upgrade has already been applied (current specs tree is the
v1 layout), so the backup is redundant.

**Notes:** Untracked, so deletion is a plain `rm -rf` + add `specs_bkp/` to
`.gitignore`. **Operator must confirm deletion** before it is removed — it is
the only copy of the pre-migration tree. Possible upstream library bug: `specs
upgrade` leaving the backup inside the repo working tree rather than under
`.dadaia/`; consider filing against dadaia-workspace.

**Closure evidence (2026-06-11, T-R6-S3):** re-verified — `specs_bkp/` is absent from
disk (path probe: does not exist). Fixed in commit `cb218f7`.
