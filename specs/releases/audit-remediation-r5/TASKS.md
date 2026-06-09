# TASKS: audit-remediation-r5

**Status:** Aprovado
**Release:** audit-remediation-r5
**Phase:** TASKS
**Branch:** feature/specs-first-docs-cleanup

WS-A and WS-B are fully parallelizable and may start simultaneously.
WS-C is independent (product-engineer owned) and may begin immediately.
WS-D: T-R5-D1 (logger fix) must complete before T-R5-D2 (tests).
WS-E: T-R5-E1 gates on T-R5-D1 + T-R5-D2 both done.
WS-F: lowest priority; does not block rc-1.

---

## WS-A — SDD Structure Scaffold

Owner: ai-engineer (projection path) or product-engineer (fallback stub path)
Parallelizable with WS-B and WS-C.

Fixes: DRIFT-06, DRIFT-07, DRIFT-08 (bugs/), DRIFT-09 (catalog.json)
Doctor warnings cleared: TREE-5, TREE-5M, CAT-1

- [x] T-R5-A1 — **Scaffold specs/AGENTS.md and specs/memory/AGENTS.md** | Owner: ai-engineer | Priority: HIGH
  Write-set: `specs/AGENTS.md`, `specs/memory/AGENTS.md`
  Precondition: None.
  Done criterion:
    (a) Verify whether `dadaia-workspace` library has source templates for `specs/AGENTS.md`
        and `specs/memory/AGENTS.md` under `repos/dadaia-workspace/dadaia_workspace/public/data/`.
    (b) If templates exist: project via `dadaia public install` targeting `dd-chain-explorer`;
        both files present with correct ownership contract content.
    (c) If templates absent: hand-author minimal stubs (SDD workflow contract for specs/AGENTS.md;
        memory ownership contract for memory/AGENTS.md); file upstream bug against dadaia-workspace.
    (d) `dadaia specs doctor` no longer reports TREE-5 or TREE-5M.
  Parallelism: safe to run concurrently with T-R5-B1, T-R5-C1.

- [x] T-R5-A2 — **Generate specs/memory/product/catalog.json** | Owner: ai-engineer | Priority: HIGH
  Write-set: `specs/memory/product/catalog.json`
  Precondition: 5 feature atom `.md` files already present in `specs/memory/product/`.
  Done criterion:
    Run `dadaia memory catalog generate` with `DADAIA_CONTEXT=dd-chain-explorer`.
    `specs/memory/product/catalog.json` present and contains entries for all 5 feature atoms.
    `dadaia specs doctor` no longer reports CAT-1.
  Parallelism: safe to run concurrently with T-R5-A1, T-R5-B1, T-R5-C1.

---

## WS-B — Repo Hygiene

Owner: software-engineer
Parallelizable with WS-A and WS-C.

Fixes: DRIFT-02 (.dadaia/ in repo), DRIFT-03 (specs_bkp/), DRIFT-04 (Kafka dead code)

- [-] T-R5-B1 — **Remove .dadaia/ from repo working tree** | Owner: software-engineer | Priority: HIGH
  Write-set: `repos/dd-chain-explorer/.gitignore`, git index (git rm tracked files)
  Precondition: Operator confirmed migration applied and backup not needed (done in dispatch).
  Done criterion:
    (a) `git ls-files repos/dd-chain-explorer/.dadaia` returns empty.
    (b) Files previously tracked under `.dadaia/` moved to workspace-level paths:
        - Report HTML → `/home/marco/workspace/dadaia/.dadaia/reports/dd-chain-explorer/data-analyst/`
        - Handoff JSON → `/home/marco/workspace/dadaia/.dadaia/handoff/dd-chain-explorer/`
    (c) `repos/dd-chain-explorer/.dadaia/` directory absent from filesystem.
    (d) `.dadaia/` entry added to `repos/dd-chain-explorer/.gitignore`.
  Parallelism: safe to run concurrently with T-R5-A1, T-R5-A2, T-R5-C1.

- [-] T-R5-B2 — **Delete specs_bkp/ and add to .gitignore** | Owner: software-engineer | Priority: MEDIUM
  Write-set: `repos/dd-chain-explorer/.gitignore`; filesystem delete of `specs_bkp/`
  Precondition: T-R5-B1 commit may be in same commit or separate; operator already confirmed.
  Done criterion:
    (a) `specs_bkp/` directory absent from `repos/dd-chain-explorer/`.
    (b) `specs_bkp/` entry present in `repos/dd-chain-explorer/.gitignore`.
  Parallelism: safe to combine into same commit as T-R5-B1.

- [-] T-R5-B3 — **Delete Kafka/Avro dead code artifacts** | Owner: software-engineer | Priority: LOW
  Write-set: `apps/docker/onchain-stream-txs/src/configs/` (delete 3 files),
             `apps/docker/onchain-stream-txs/src/schemas/` (delete 7 files)
  Precondition: Confirm no importer:
    `grep -r "topics.ini\|consumers.ini\|producers.ini" apps/docker/onchain-stream-txs/src/*.py`
    `grep -r "schemas/" apps/docker/onchain-stream-txs/src/*.py`
    Both must return empty.
  Done criterion:
    (a) No `.ini` files under `apps/docker/onchain-stream-txs/src/configs/` related to Kafka.
    (b) No `*avro*.json` files under `apps/docker/onchain-stream-txs/src/schemas/`.
    (c) `find apps/docker/onchain-stream-txs/src -name "*.ini"` returns empty.
    (d) `find apps/docker/onchain-stream-txs/src/schemas -name "*.json"` returns empty.
  Parallelism: safe to run concurrently with all other tasks.

---

## WS-C — Release Closure Forensics

Owner: product-engineer
Independent of WS-A, WS-B, WS-D. May start immediately.

Fixes: DRIFT-05 (three stale CLOSURE.md templates)
Operator mandate: forensic verification — evidence-based verdicts, no fabrication.

- [x] T-R5-C1 — **Forensic closure: cost-and-availability-r2** | Owner: product-engineer | Priority: HIGH
  Write-set: `specs/releases/cost-and-availability-r2/CLOSURE.md`
             (optional: `git mv` to `specs/_archive/releases/cost-and-availability-r2` if ABANDONED)
  Precondition: None.
  Done criterion:
    For each of T-R2-01 through T-R2-07 and T-R2-NEW-1:
    (a) Run `git log --oneline --all -- <write-set-files-for-task>` and check current file state.
    (b) Assign per-task verdict: IMPLEMENTED (commit found, file reflects change) or ABANDONED
        (no commit evidence; file does not reflect done criterion).
    (c) Release verdict:
        - IMPLEMENTED: populate CLOSURE.md with real commit SHAs and validation evidence;
          set `**Status:** Aprovado`.
        - ABANDONED: document reason in CLOSURE.md; set `**Status:** Aprovado` with ABANDONED
          verdict; propose `git mv` to `_archive/`.
    (d) CLOSURE.md status is `Aprovado` with documented forensic verdict.
    Note: Do NOT fabricate SHAs. "No commit evidence found" is a valid and honest finding.
  Parallelism: safe to run concurrently with T-R5-A1, T-R5-B1.

- [x] T-R5-C2 — **Forensic closure: data-quality-r3** | Owner: product-engineer | Priority: HIGH
  Write-set: `specs/releases/data-quality-r3/CLOSURE.md`
             (optional: `git mv` to `specs/_archive/releases/data-quality-r3` if ABANDONED)
  Precondition: None (may run in parallel with T-R5-C1).
  Done criterion:
    For each of T-R3-01 through T-R3-05 and T-R3-NEW-1:
    (a) Run `git log --oneline --all -- <write-set-files-for-task>` and check current file state
        for done criteria (event-time windows, schema evolution, orphaned MV drop, data-contract
        tests).
    (b) Assign per-task verdict: IMPLEMENTED or ABANDONED with evidence.
    (c) Release verdict documented; CLOSURE.md status `Aprovado`.
  Parallelism: safe to run concurrently with T-R5-C1.

- [x] T-R5-C3 — **Forensic closure: analytics-enrichment-r4** | Owner: product-engineer | Priority: HIGH
  Write-set: `specs/releases/analytics-enrichment-r4/CLOSURE.md`
             (optional: `git mv` to `specs/_archive/releases/analytics-enrichment-r4` if ABANDONED)
  Precondition: None (may run in parallel with T-R5-C1, T-R5-C2).
  Done criterion:
    For each of T-R4-01 through T-R4-09 and T-R4-NEW-1, T-R4-NEW-2:
    (a) Run `git log --oneline --all -- <write-set-files-for-task>` and check current file state
        for done criteria (Genie context, freshness tiles, analyst GRANTs, column comments,
        daily export schedule, PRD catalog alignment, alerting).
    (b) Assign per-task verdict: IMPLEMENTED or ABANDONED with evidence.
    (c) Release verdict documented; CLOSURE.md status `Aprovado`.
    (d) Note: T-R4-CL-01/02/03 were CLOSURE-phase memory migration tasks from a pre-Markdown-memory
        era; these are superseded by the current Markdown memory format — document as SUPERSEDED.
  Parallelism: safe to run concurrently with T-R5-C1, T-R5-C2.

---

## WS-D — Streaming Job Logger Fix + Tests

Owner: software-engineer (D1 + D2 impl) + qa-engineer (D2 plan)
T-R5-D1 must complete before T-R5-D2. Both must complete before WS-E.

Fixes: BP-01 (logger wiring), DRIFT-01 (streaming job zero tests)

- [x] T-R5-D1 — **Fix module-global LOGGER references in all 5 streaming job classes** | Owner: software-engineer | Priority: HIGH
  Write-set: `apps/docker/onchain-stream-txs/src/1_mined_blocks_watcher.py`,
             `apps/docker/onchain-stream-txs/src/2_orphan_blocks_watcher.py`,
             `apps/docker/onchain-stream-txs/src/3_block_data_crawler.py`,
             `apps/docker/onchain-stream-txs/src/4_mined_txs_crawler.py`,
             `apps/docker/onchain-stream-txs/src/5_txs_input_decoder.py`
  Precondition: None. May start after WS-B completes or in parallel.
  Done criterion:
    (a) `grep -nE '\bLOGGER\b' apps/docker/onchain-stream-txs/src/*.py | grep -v "__main__"`
        returns empty for all 5 files (no LOGGER references inside class methods).
    (b) All class methods that previously referenced global `LOGGER` now reference `self.logger`.
    (c) Each job class `__init__` sets `self.logger` before any method can be invoked.
    (d) `if __name__ == "__main__":` blocks may still configure a module-level logger for the
        process entry point — this is acceptable.
    (e) Instantiating each job class without calling `main()` does not raise `NameError`.
  Parallelism: may start concurrently with WS-A, WS-B, WS-C. T-R5-D2 depends on this task.

- [-] T-R5-D2 — **Define and implement unit tests for the 5 streaming job classes** | Owner: qa-engineer (plan) + software-engineer (impl) | Priority: HIGH
  Write-set: `apps/docker/onchain-stream-txs/tests/unit/` (create directory + test files)
  Precondition: T-R5-D1 complete (logger fix landed; classes instantiable without NameError).
  Done criterion:
    (a) Test plan authored by qa-engineer covering per-job:
        - Constructor + logger injection (no NameError on instantiation).
        - Main processing loop with mocked boto3/web3 clients.
        - At least one error path per job.
    (b) software-engineer implements tests in `apps/docker/onchain-stream-txs/tests/unit/`.
    (c) `pytest apps/docker/onchain-stream-txs/tests/unit/ -p no:cacheprovider` passes (all green).
    (d) Minimum: 1 test file per job (5 files total); minimum 3 tests per job (constructor, happy
        path, error path).
  Parallelism: sequential after T-R5-D1. T-R5-E1 depends on this task.

---

## WS-E — Security + Best-Practices Pass

Owner: security-reviewer
Gates on T-R5-D1 + T-R5-D2 both complete.

Covers: operator-mandated security pass over streaming/production code

- [ ] T-R5-E1 — **Security and best-practices review of 5 streaming job files** | Owner: security-reviewer | Priority: HIGH
  Write-set: None (read-only audit; findings in handoff JSON / report).
  Precondition: T-R5-D1 and T-R5-D2 both `[x]` DONE.
  Done criterion:
    (a) security-reviewer reviews all 5 job files post-logger-fix for:
        - Any remaining module-global references inside class methods.
        - Bare `except` clauses (recommend `except SpecificException`).
        - Secret material sourcing: all API keys, SSM paths, and credentials must come from
          ParameterStoreClient or environment variables; no hardcoded strings.
        - Job 5 (`5_txs_input_decoder.py`): confirm ParameterStoreClient used for API key
          retrieval.
    (b) A handoff JSON report emitted under `.dadaia/handoff/dd-chain-explorer/`.
    (c) No CRITICAL or HIGH unresolved findings. MEDIUM findings documented with recommended fix.
  Parallelism: sequential after T-R5-D1 + T-R5-D2. Does not block WS-F.

---

## WS-F — Doctor Warnings / Legacy specs/domains/ Migration

Owner: product-engineer (domains migration + token_estimate fixes)
       ai-engineer (heading-allowlist library gap, if any)
LOW PRIORITY — may defer past rc-1 if time constrained.

Covers: DRIFT-10 (SPEC-DOC-007, LINT-1)

- [ ] T-R5-F1 — **Migrate or archive specs/domains/ legacy specs** | Owner: product-engineer | Priority: LOW
  Write-set: `specs/domains/` (move to `specs/_archive/legacy-domains/` or `specs/_archive/releases/`),
             `specs/_archive/` (new subdirectory)
  Precondition: None. May start at any time after WS-C is done (to avoid conflict with CLOSURE work).
  Done criterion:
    (a) `specs/domains/` no longer exists at `specs/domains/`.
    (b) Legacy specs moved to `specs/_archive/legacy-domains/<timestamp>/` or archived release dirs.
    (c) `dadaia specs doctor` no longer reports SPEC-DOC-007 for `specs/domains/` entries.
  Note: If any `specs/domains/` spec represents work that was actually implemented, reference it
  from the appropriate forensic CLOSURE (WS-C) before archiving.
  Parallelism: safe to run concurrently with WS-E or after.

- [ ] T-R5-F2 — **Fix token_estimate frontmatter in drifted memory atoms** | Owner: product-engineer | Priority: LOW
  Write-set: `specs/memory/architecture.md`, `specs/memory/product/aws-resources.md`,
             `specs/memory/product/capture-layer.md`, `specs/memory/product/data-catalog.md`,
             `specs/memory/product/medallion-pipelines.md`, `specs/memory/product/serving-layer.md`
  Precondition: None.
  Done criterion:
    (a) `token_estimate` frontmatter in each of the 6 listed atoms updated to match actual token
        count (within ±10%).
    (b) `dadaia specs doctor` no longer reports LINT-1 token_estimate drift for these atoms.
  Parallelism: safe to run at any time (CLOSURE phase authorized for PE memory writes).

- [ ] T-R5-F3 — **Evaluate and address heading-allowlist warnings** | Owner: product-engineer + ai-engineer | Priority: LOW
  Write-set: investigation only; changes conditional on operator/architect decision.
  Precondition: None.
  Done criterion:
    (a) Evaluate each non-standard heading name (e.g. `## AWS Infrastructure`, `## S3 Buckets`,
        `## Schema: ...`) — does it warrant rewriting or is it a valid domain-specific heading?
    (b) If heading rewrite is appropriate: update affected atom files.
    (c) If a library allowlist extension is appropriate: file the gap as an upstream bug against
        `repos/dadaia-workspace/specs/bugs/`; do NOT modify library source from within this release.
    (d) Outcome documented in CLOSURE.md.
  Parallelism: safe to run at any time.

---

## Task dependency summary

| Task | Depends on | Blocks |
|------|-----------|--------|
| T-R5-A1 | — | — |
| T-R5-A2 | — | — |
| T-R5-B1 | — | — |
| T-R5-B2 | — | — |
| T-R5-B3 | — (confirm no importer first) | — |
| T-R5-C1 | — | — |
| T-R5-C2 | — | — |
| T-R5-C3 | — | — |
| T-R5-D1 | — | T-R5-D2, T-R5-E1 |
| T-R5-D2 | T-R5-D1 | T-R5-E1 |
| T-R5-E1 | T-R5-D1, T-R5-D2 | — |
| T-R5-F1 | WS-C done (recommended) | — |
| T-R5-F2 | — | — |
| T-R5-F3 | — | — |

---

## rc-1 gate (minimum required for ship)

The following tasks must be `[x]` DONE before rc-1 review:
T-R5-A1, T-R5-A2, T-R5-B1, T-R5-B2, T-R5-B3, T-R5-C1, T-R5-C2, T-R5-C3, T-R5-D1, T-R5-D2, T-R5-E1.

WS-F tasks (T-R5-F1, T-R5-F2, T-R5-F3) may be completed before or deferred to a subsequent release.
