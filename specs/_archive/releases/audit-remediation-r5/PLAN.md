# PLAN: audit-remediation-r5

**Status:** Aprovado
**Release ID:** audit-remediation-r5
**Phase:** PLAN
**Owner:** product-engineer
**Date:** 2026-06-09

---

## Strategy

Six workstreams executed in a single implementation sprint on `feature/specs-first-docs-cleanup`.
WS-A and WS-B are fully parallelizable. WS-C depends on no workstream but is product-engineer
owned and may begin immediately. WS-D requires logger fix (BP-01) to land before tests are
written. WS-E gates on WS-D code landing. WS-F is low priority and may slip past rc-1.

```
WS-A  ─────────────────────────────────────────── [ai-engineer / PE]
WS-B  ─────────────────────────────────────────── [software-engineer]
WS-C  ─────────────────────────────────────────── [product-engineer]
WS-D  [logger fix] ──── [tests] ──────────────── [SE + QA]
WS-E                         ──── [sec pass] ──── [security-reviewer]
WS-F  (defer if needed) ──────────────────────── [PE + ai-engineer]
```

---

## Layers affected

| Layer | Workstream | Files |
|-------|-----------|-------|
| SDD scaffold | WS-A | `specs/AGENTS.md`, `specs/memory/AGENTS.md`, `specs/memory/product/catalog.json` |
| Repo hygiene | WS-B | `.dadaia/` (tracked files + dir), `specs_bkp/`, Kafka artifacts, `.gitignore` |
| Spec governance | WS-C | `specs/releases/{r2,r3,r4}/CLOSURE.md`, optional `_archive/` moves |
| Streaming app | WS-D | `apps/docker/onchain-stream-txs/src/*.py`, new test files |
| Security review | WS-E | Read-only audit of WS-D output; report only |
| Doctor warnings | WS-F | `specs/domains/` migration, memory atom frontmatter |

---

## Execution order

### Wave 1 — Parallel (no dependencies)

**WS-A: SDD structure scaffold** (ai-engineer + product-engineer)

1. Verify whether `dadaia-workspace` library ships a `specs/AGENTS.md` template for consumer
   repos (check `repos/dadaia-workspace/dadaia_workspace/public/data/`).
2. If library template exists: run `dadaia public install --target dd-chain-explorer` or
   equivalent to project `specs/AGENTS.md` and `specs/memory/AGENTS.md`.
3. If library template absent: hand-author minimal stubs (one paragraph each, ownership contract);
   file upstream bug against dadaia-workspace for the missing template.
4. Run `dadaia memory catalog generate` (with `DADAIA_CONTEXT=dd-chain-explorer`) to produce
   `specs/memory/product/catalog.json`.
5. Verify `dadaia specs doctor` clears TREE-4, TREE-5, TREE-5M, CAT-1.

**WS-B: Repo hygiene** (software-engineer)

1. Confirm two files are git-tracked under `repos/dd-chain-explorer/.dadaia/` with
   `git ls-files repos/dd-chain-explorer/.dadaia`.
2. `git rm` the tracked files; move (copy) to workspace-level paths:
   - `.dadaia/reports/dd-chain-explorer/data-analyst/`
   - `.dadaia/handoff/dd-chain-explorer/` (for the `.handoff.json`)
3. Delete `repos/dd-chain-explorer/.dadaia/` from filesystem (untracked remainder).
4. Add `.dadaia/` and `specs_bkp/` to `repos/dd-chain-explorer/.gitignore` (create or append).
5. Delete `specs_bkp/0→1-20260609T002529Z/` after operator confirmation that migration is applied
   (operator already confirmed in dispatch).
6. Confirm no importer of Kafka artifacts: `grep -r "topics.ini\|consumers.ini\|producers.ini\|avro" apps/docker/onchain-stream-txs/src/*.py`.
7. Delete: `apps/docker/onchain-stream-txs/src/configs/topics.ini`, `consumers.ini`,
   `producers.ini` and all 7 `src/schemas/*.json` files.
8. Commit with: `chore(hygiene): remove .dadaia/ from repo, delete kafka/avro dead code, add gitignore`.

**WS-C: Release closure forensics** (product-engineer)

For each of r2, r3, r4 — in that order — perform a **forensic verification**:

*For each release and each of its tasks/workstreams:*
1. Read the TASKS.md to understand what each task was supposed to change.
2. Run `git log --oneline --all -- <write-set-files>` for the declared write-set files.
3. Cross-check: does any commit in git history implement the described change? Does the current
   file state on disk reflect the task's done criterion?
4. Verdict per task: `IMPLEMENTED` (code matches, commit found) or `ABANDONED` (no evidence).
5. Aggregate verdict per release: if all implementation tasks are `IMPLEMENTED` → populate
   CLOSURE evidence (real SHAs, validation commands); if majority or critical tasks are
   `ABANDONED` → write CLOSURE as ABANDONED with documented reason; move to `_archive/`.
6. Update each CLOSURE.md status to `Aprovado` once the verdict is documented.
7. Do NOT fabricate SHAs. If a commit cannot be found, state "no commit evidence found" explicitly.

### Wave 2 — WS-D (unblocked after Wave 1 starts; logger fix is independent)

**WS-D: Logger fix + streaming job tests** (software-engineer + qa-engineer)

Step D1 — Logger refactor (software-engineer, must complete before D2):
1. For each of the 5 job files, audit: `grep -nE '\bLOGGER\b|self\.logger' <file>`.
2. For each class method that references module-global `LOGGER`:
   - Replace `LOGGER.<method>` with `self.logger.<method>`.
   - Remove any `global LOGGER` statement inside class methods.
3. Ensure `self.logger` is always set in `__init__` before any method can be called.
4. Keep the `if __name__ == "__main__":` block intact; the module-level `LOGGER` there is fine
   (it configures logging for the process entry point).
5. Confirm: `grep -nE '\bLOGGER\b' apps/docker/onchain-stream-txs/src/*.py | grep -v "__main__"`
   returns empty (no LOGGER inside class methods).

Step D2 — Unit tests (qa-engineer defines plan; software-engineer implements):
1. QA defines a test plan for each of the 5 job classes covering:
   - Constructor + logger injection (no NameError on instantiation without running main).
   - Main processing loop with mocked dependencies (boto3 clients, web3 client).
   - Key error paths (connection errors, malformed data).
2. Software-engineer implements tests under `apps/docker/onchain-stream-txs/tests/unit/`.
3. Tests run with `pytest apps/docker/onchain-stream-txs/tests/unit/ -p no:cacheprovider`.
4. All tests green.

### Wave 3 — WS-E (after WS-D code lands)

**WS-E: Security + best-practices pass** (security-reviewer)

1. Review all 5 job files post-logger-fix for:
   - Any remaining module-global references inside class methods.
   - Bare `except` clauses (should be `except SpecificException`).
   - Secret material: confirm Etherscan keys, SSM names, API keys sourced from
     ParameterStoreClient or environment variables only — no hardcoded strings.
   - Job 5 (`5_txs_input_decoder.py`) specifically: confirm ParameterStoreClient usage for
     API key retrieval.
2. Issue a security report (handoff JSON). Any CRITICAL/HIGH findings block rc-1.

### Wave 4 — WS-F (low priority, may defer)

**WS-F: Doctor warnings / domains migration** (product-engineer + ai-engineer)

1. Move `specs/domains/` tree to `specs/_archive/legacy-domains/` or incorporate active specs.
2. Update `token_estimate` frontmatter in drifted atoms (6 atoms noted in DRIFT-10).
3. For heading-allowlist warnings: evaluate whether to rewrite headings or file library gap.
   Do NOT blindly rewrite valid domain-specific headings.
4. Re-run `dadaia specs doctor` — target zero SPEC-DOC-007 and LINT-1 warnings.

---

## Technical risks

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Library missing `specs/AGENTS.md` template | WS-A falls back to hand-authoring | File upstream bug; use minimal stub |
| Git history sparse for r2/r3/r4 | WS-C verdict may be "no evidence" | Document honestly; do not fabricate |
| Logger fix exposes wider coupling in jobs 2–5 | WS-D scope expansion | Cap at `self.logger` fix only; broader refactor deferred |
| WS-F heading rewrite breaks valid domain headings | Memory accuracy regression | Operator/architect decision before any heading changes |

---

## Validation plan

| Check | Command | Pass criterion |
|-------|---------|---------------|
| SDD doctor clean | `DADAIA_CONTEXT=dd-chain-explorer dadaia specs doctor` | 0 errors; TREE-4/5/5M/CAT-1 cleared |
| No .dadaia in repo | `git ls-files repos/dd-chain-explorer/.dadaia` | empty |
| No Kafka artifacts | `find apps/docker/onchain-stream-txs/src -name "*.ini"` | empty |
| Logger fix | `grep -nE '\bLOGGER\b' src/*.py \| grep -v "__main__"` | empty |
| Tests pass | `pytest apps/docker/onchain-stream-txs/tests/unit/ -p no:cacheprovider` | all green |
| r2/r3/r4 CLOSURE verdict | manual review of each CLOSURE.md | status Aprovado, verdict documented |
