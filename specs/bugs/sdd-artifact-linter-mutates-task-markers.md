---
name: sdd-artifact-linter-mutates-task-markers
status: Open
severity: HIGH
reported: 2026-06-22
surface: SDD artifact post-write linter (editing specs/releases/<id>/{SPEC,PLAN,TASKS}.md via file tools)
session_id: null
---

**Symptom:** While authoring/revising the v0.4.0 release artifacts in
`specs/releases/v0.4.0/`, a post-write linter mutated the markdown between an Edit's
`Read` and its `old_string` apply — repeatedly forcing "File has been modified since
read" errors. Worse, the linter made **semantic** changes to load-bearing content, not
just whitespace normalization:

1. **Flipped a task marker** in `TASKS.md` from `[ ]` (OPEN) to `[-]` and then to `[x]`
   (DONE) on `T-A.1` — a task that has NOT been implemented (the release is in DEFINITION
   phase, no `[-]` reservation, no commit). A false `[x]` is a machine-contract lie that
   would let an implementer skip the work and a closure to proceed on unbuilt scope.
2. **Injected a duplicate, contradictory block** into `PLAN.md` — a second
   "Mid-sequence partial-apply recovery" paragraph that reintroduced a per-stack manual
   ordering narrative the spec review had explicitly corrected (ordering safety is a
   merged-commit property, not a run sequence).
3. **Flipped `**Status:** Em revisão` → `Aprovado`** on SPEC/PLAN/TASKS during editing,
   independent of the authoring agent's explicit status-flip step.

**Repro:**
```
# In a DEFINITION-phase release dir:
1. Write specs/releases/<id>/TASKS.md with all tasks `[ ]` and Status: Em revisão.
2. Apply a small Edit to an unrelated line.
3. Re-read the file: a task marker has been changed to [-]/[x], and/or
   the Status header has been flipped, and/or a duplicate paragraph appended.
```

**Expected:** A linter on SDD markdown may normalize whitespace/formatting only. It MUST
NOT mutate `[ ] / [-] / [x]` task markers (a grep-parsable machine contract,
`dadaia-task-manager` skill), MUST NOT change `**Status:**` tokens
(`Draft`/`Em revisão`/`Aprovado` are author-controlled SDD gate tokens), and MUST NOT
inject or duplicate body content. These are semantic SDD state, not formatting.

**Notes:** Task-marker integrity is the basis of the implement→review→DONE protocol; a
linter flipping markers silently corrupts traceability and the gate's implicit contract.
The authoring agent had to fully rewrite `TASKS.md` to restore the correct all-`[ ]`
state. No operator-local paths/secrets involved. Root cause likely a markdown formatter
hooked on file write that treats list-item checkbox state and frontmatter-like headers as
reformattable. Fix: exclude `specs/releases/**/{SPEC,PLAN,TASKS,CLOSURE}.md` task markers
+ `**Status:**` lines from any auto-formatter, or disable content-mutating linting on
`specs/**` markdown entirely.
