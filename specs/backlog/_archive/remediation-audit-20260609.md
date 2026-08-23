# Backlog — Audit Remediation (drift audit 20260609T013037Z)

> Owner: project-manager (sole backlog author). Source: project-auditor drift
> audit `specs/audits/20260609T013037Z/audit.md` (score 6.2/10, DRIFT DETECTED)
> plus an operator-mandated security + best-practices pass over the streaming
> code. Refined and ready to fold into a single remediation release. Each item
> below maps 1:1 to a registered bug under `specs/bugs/`.

## Picked set (bug-always-solved)

| Backlog item | Bug file | Sev | Dimension | Workstream |
|---|---|---|---|---|
| BL-01 SDD structure scaffold | drift-06-08-sdd-structure-gaps | MED | Agent-surface | WS-A |
| BL-02 Repo hygiene cleanup | drift-02 + drift-03 + drift-04 | MED/LOW | Security/Arch | WS-B |
| BL-03 Release closure hygiene | drift-05-release-closure-hygiene | MED | Product | WS-C |
| BL-04 Streaming job tests | drift-01-streaming-jobs-zero-tests | HIGH | Tests | WS-D |
| BL-05 Logger/best-practices fix | bp-01-streaming-jobs-logger-inconsistency | MED | Security/BP | WS-D (paired) |
| BL-06 Security + best-practices pass | (operator add-on) | — | Security | WS-E |
| BL-07 Doctor warnings / domains migration | drift-10-doctor-warnings-batch | LOW | Tech/Surface | WS-F |

## Refinement notes (grill-resolved by inspection)

1. **`.dadaia/` files are git-tracked** (not just untracked) — WS-B must `git rm`
   + move + commit, not a plain `mv`. Verified via `git ls-files`.
2. **`specs_bkp/` is untracked** — plain `rm -rf` + `.gitignore`, but it is the
   ONLY copy of the pre-migration tree → operator confirmation required.
3. **All three releases (r2/r3/r4)** have Draft-template CLOSUREs, not just r4 —
   WS-C covers all three; operator decides populate-vs-archive per release.
4. **BL-04 is blocked by BL-05**: the global-`LOGGER` coupling in the job classes
   prevents isolated instantiation, so the logger refactor must land first (or
   in the same task) before contract tests are writable. Sequence BL-05 -> BL-04.
5. **`specs/AGENTS.md` + `specs/memory/AGENTS.md`** are library-projected, not
   hand-authored — WS-A routes through ai-engineer (`dadaia public install`),
   contingent on the library shipping those templates. If it does not, file an
   upstream library gap.
6. **Heading-allowlist warnings** may be a library allowlist gap, not a repo
   defect — do not blindly rewrite valid domain headings; architect/operator call.

## Out of scope / deferred

- DRIFT-09 catalog.json is folded into WS-A (generate command).
- token_estimate + heading normalisation (DRIFT-10) is LOW; WS-F, last, optional.
- No new product features. This is a pure remediation release.
