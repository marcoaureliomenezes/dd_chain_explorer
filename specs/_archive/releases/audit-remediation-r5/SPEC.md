# SPEC: audit-remediation-r5

**Status:** Aprovado
**Release ID:** audit-remediation-r5
**Phase:** SPEC
**Owner:** product-engineer
**Branch:** feature/specs-first-docs-cleanup
**Date:** 2026-06-09

---

## Objective

Close all open drift items from the project-auditor report (2026-06-09T01:30:37Z, score 6.2/10).
This is a **pure remediation release** — no new product features. The release brings the
dd-chain-explorer repo into SDD compliance, removes workspace-boundary violations, resolves
three stale release closures via forensic evidence, adds the first unit tests to the streaming
jobs, and applies a security/best-practices pass to the production capture layer.

---

## Product deltas

None — no user-facing functionality changes.

---

## Architecture deltas

- Logger coupling removed from 5 streaming job classes (BP-01): each class will log exclusively
  through its injected `self.logger`; module-global `LOGGER` references inside class methods
  eliminated. This is a structural correctness fix, not a behavioral change.

---

## Tech-stack deltas

- No new dependencies added.
- Dead Kafka/Avro artifacts deleted: 7 Avro schema JSON files and 3 Kafka `.ini` config files
  removed from `apps/docker/onchain-stream-txs/src/`. These were unreferenced stale artifacts
  from a pre-ADR-001 era; no importer exists in the active codebase.

---

## Security / operations deltas

- `.dadaia/` directory removed from inside the repo working tree (workspace-boundary violation).
  Two git-tracked files moved to workspace-level paths; directory deleted; `.dadaia/` added to
  `.gitignore`.
- `specs_bkp/` leftover from `dadaia specs upgrade` migration deleted and added to `.gitignore`.
- Security + best-practices pass (WS-E) reviews all 5 streaming job modules for: latent
  global/closure references, bare `except` clauses, secret material sourcing (SSM-only — no
  hardcoded keys), and any additional `NameError`-risk patterns exposed by the logger fix.

---

## Memory files affected at closure

- `specs/memory/quality-assurance.md` — update test coverage section to reflect streaming job
  tests added.
- `specs/memory/product/capture-layer.md` — update to reflect logger refactor and test coverage.
- No other memory atoms change (no functional or architectural change).

---

## Acceptance criteria

1. `dadaia specs doctor` exits with 0 errors and clears TREE-4, TREE-5, TREE-5M, CAT-1 warnings
   (WS-A complete).
2. `git ls-files repos/dd-chain-explorer/.dadaia` returns empty; `.dadaia/` present in repo
   `.gitignore` (WS-B complete).
3. `specs_bkp/` directory absent from working tree; `specs_bkp/` in `.gitignore` (WS-B complete).
4. Dead Kafka artifacts absent: `find apps/docker/onchain-stream-txs/src -name "*.ini" -o -name
   "*avro*.json"` returns empty (WS-B complete).
5. For each of r2, r3, r4: CLOSURE.md contains a forensic verdict (`IMPLEMENTED` or `ABANDONED`)
   with code/git evidence or a documented reason, and either populated CLOSURE evidence or an
   archive action taken (WS-C complete).
6. Unit tests exist for all 5 streaming job classes; `pytest` (or equivalent runner) passes for
   the streaming-job test suite (WS-D complete).
7. All 5 job classes reference only `self.logger` inside methods; no module-global `LOGGER`
   referenced from within class methods (WS-D complete).
8. Security reviewer issues no CRITICAL or HIGH findings against the streaming jobs post-fix
   (WS-E complete).
9. `dadaia specs doctor` clears or explicitly defers SPEC-DOC-007 and LINT-1 warnings (WS-F
   attempted; may defer past rc-1 if blocking).

---

## Out of scope

- No new product features.
- No Databricks DLT, dashboard, or Lakeview changes.
- No Terraform infrastructure changes.
- No dm-chain-utils library version bump.
- `token_estimate` frontmatter drift in memory atoms (LINT-1 part) — address in WS-F if time
  allows; not blocking.
- Heading-allowlist library extension — flagged to ai-engineer/operator as upstream library gap;
  not remediated in this release.
- Releases r2/r3/r4 directory archiving via `git mv` is performed as part of WS-C only if
  forensic verdict is `ABANDONED`. If `IMPLEMENTED`, the operator decides archive timing.

---

## Dependencies and risks

| Risk | Mitigation |
|------|-----------|
| `specs/AGENTS.md` + `specs/memory/AGENTS.md` require library source templates that may not yet exist in dadaia-workspace | ai-engineer verifies library support first; if absent, files upstream gap bug and falls back to hand-authoring minimal stubs |
| Forensic closure (WS-C) may find r2/r3/r4 were genuinely implemented — `git log` evidence may be sparse | PE documents what is found; verdict is evidence-based, even if incomplete; does not fabricate SHAs |
| Logger refactor (BP-01) may expose additional coupling in jobs 2–5 beyond the documented `1_mined_blocks_watcher.py` | software-engineer scans all 5 job files as part of WS-D task |
| Heading-allowlist warnings in WS-F may require a library change outside this context's scope | Flag to operator; do not modify library source from within this release |
