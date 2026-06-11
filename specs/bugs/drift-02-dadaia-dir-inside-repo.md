---
name: drift-02-dadaia-dir-inside-repo
status: Closed
severity: MEDIUM
reported: 2026-06-08
surface: repos/dd-chain-explorer/.dadaia/ (workspace-boundary violation)
session_id: null
fixed_in: cb218f7
closed: 2026-06-11
audit_ref: specs/audits/20260609T013037Z/audit.md#DRIFT-02
---

**Symptom:** A `.dadaia/` directory exists INSIDE the repo working tree at
`repos/dd-chain-explorer/.dadaia/`. Per workspace law, `.dadaia/` is
workspace-level ONLY; inside a repo it corrupts workspace-vs-repo boundary
detection. It holds two 2026-05-23 orphan files (data-analyst serving-layer
report + handoff) and — critically — both files are **git-tracked / committed**,
not merely untracked.

**Repro:**
```
ls repos/dd-chain-explorer/.dadaia/reports/dd-chain-explorer/data-analyst/
git ls-files | grep '^.dadaia/'   # returns 2 tracked files (.html + .handoff.json)
```

**Expected:** No repo contains `.dadaia/`. The two artifacts belong at the
workspace level under `.dadaia/reports/dd-chain-explorer/data-analyst/` and
`.dadaia/handoff/dd-chain-explorer/`.

**Notes:** Because the files are tracked, remediation needs `git rm` + move +
`.gitignore` add `.dadaia/`, in a committed change — not a plain `mv`. This is
the security/hygiene dimension (scored 7/10). Confirm the workspace-level copy
does not already exist before overwriting.

**Closure evidence (2026-06-11, T-R6-S3):** re-verified — `.dadaia/` is absent from the
repo working tree (path probe: does not exist); audit `20260611T001412Z-cb56f84c`
confirmed `git ls-files` returns no `.dadaia/` entries. Fixed in commit `cb218f7`.
