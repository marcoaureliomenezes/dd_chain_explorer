---
name: drift-05-release-closure-hygiene
status: Open
severity: MEDIUM
reported: 2026-06-08
surface: specs/releases/{analytics-enrichment-r4,cost-and-availability-r2,data-quality-r3}
audit_ref: specs/audits/20260609T013037Z/audit.md#DRIFT-05
---

**Symptom:** Three releases each have SPEC/PLAN/TASKS marked `Aprovado` but a
`CLOSURE.md` that is still the empty Draft template
(`> **Status:** Draft (template — populate when all TASKS.md tasks are [x] DONE)`,
literal `<sha>` placeholders, no validation evidence). `ACTIVE.md` shows
`release: none / phase: DEFINITION`, so no release is active — yet three named
releases sit in an unfinished, unverifiable state.

**Repro:**
```
grep -H "Status:" specs/releases/*/CLOSURE.md
# all three: Draft template
cat specs/releases/ACTIVE.md   # release: none / phase: DEFINITION
```

**Expected:** Each release is either (a) genuinely closed with populated CLOSURE
evidence (commit SHAs, validation, [x] tasks) or (b) archived to
`specs/_archive/releases/` as incomplete. SDD governance must not leave
Aprovado-TASKS releases with empty closures and no active release pointer.

**Notes:** Audit confirmed r4 explicitly; r2 and r3 CLOSURE.md show the same
Draft template (verified). Operator decision required: were these releases
actually implemented (→ populate CLOSURE) or abandoned (→ archive)? Owner:
product-engineer (sole CLOSURE/ACTIVE/memory author).
