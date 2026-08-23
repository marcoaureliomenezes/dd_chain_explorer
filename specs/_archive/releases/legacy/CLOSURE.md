# CLOSURE: legacy (forensic)

**Status:** Aprovado
**Release:** legacy (pre-SDD grab-bag — not a versioned release)
**Closed:** 2026-06-11 (forensic closure during v0.3.0, task T-R6-S4)

## Summary

`specs/releases/legacy/` predates the repo's SDD onboarding (2026-06-09). It held
pre-pattern spec fragments with non-canonical status tokens (`Implementado`) and no
SPEC/PLAN/TASKS lifecycle. It was never an executed release under the current canon.

## Validations

| Description | Command | Evidence |
|-------------|---------|----------|
| Archived verbatim, no edits | `git log --follow specs/_archive/releases/legacy/` | single move commit 0a5d513 (T-R6-S4) |
| Non-canonical token gone from live tree | `grep -r "Implementado" specs/releases/` | 0 matches after the move |
| Legacy-token warnings cleared | `dadaia specs doctor` | SPEC-DOC-007 warnings absent post-archive (doctor run 2026-06-11) |

## Drifts

- None introduced: this directory was never an executed release; its non-canonical
  fragments are superseded by `specs/memory/` atoms. Residual knowledge gaps are
  tracked as GAP-LD-1..6 in `specs/backlog/candidates.md`.

## Memory updates

- None in this forensic closure (IMPLEMENTATION phase). GAP-LD-1..6 feed the
  v0.3.0 CLOSURE-phase memory pass (T-R6-S5/S6).

## Forensic disposition

- Archived verbatim to `specs/_archive/releases/legacy/` by T-R6-S4 (commit 0a5d513),
  fulfilling deferred task T-R5-F1 (audit-remediation-r5 CLOSURE deferral).
- Current product truth lives in `specs/memory/`; content-loss review recorded gaps
  GAP-LD-1..6 in `specs/backlog/candidates.md` for the v0.3.0 CLOSURE-phase pass
  (T-R6-S5/S6).
- No evidence triple applies: nothing was implemented under this directory's authority.

This file exists to satisfy SPEC-DOC-006 (archived release must carry a CLOSURE.md)
with an honest record rather than a fabricated lifecycle.
