---
slug: quality-assurance
title: Quality Assurance
category: core
tldr: 158 green pytest tests in three suites, only one wired into CI; the intended pyramid for Lambdas, DABs, DLT and Terraform is largely unbuilt.
summary: Documents the current test inventory (35 utils unit, 78 streaming-job unit, 45 CI-script tests — all green, sub-3s), the wiring gap that leaves two of three suites out of CI, the layers with zero coverage (Lambdas, DABs/DLT, Terraform policy), the shell integration scripts including one tombstoned no-op, the review-gate cadence, and the QA contract this platform is committed to going forward.
tags:
  - quality-assurance
  - testing
  - test-pyramid
  - anti-slop
last_updated: "2026-08-23"
release_origin: v0.4.0
---

## Padrões de qualidade

### Review gates

- End of each `alpha-N` → `qa-engineer`-only review, committed to the branch.
- End of each `rc-N` / at ship → full trio (`qa-engineer` + `code-reviewer` + `security-reviewer`) must APPROVE before push/PR.
- Security reviews are diff-based read-only verdicts; remediation is implemented by `software-engineer` under its own task.

### Anti-slop discipline

- No fabricated tests, commands or SHAs — every validation cites a real command and real evidence.
- Root cause always: reproduce on the executed path, RED test, fix the cause, prove GREEN. Symptom patches are not acceptable outcomes.
- Tests run with `-p no:cacheprovider`; no cache, coverage or result directory may land in the repo tree.
- The implementer never prunes a test to go green — deleting, skipping or disabling a test is a `qa-engineer` verdict with evidence.
- Bugs close only with resolution evidence, never silently.

## Disciplina de testes

### Inventário atual

| Suite | Location | Tests | Kind | Runs in CI? |
|---|---|---|---|---|
| Shared library | `utils/tests/unit/` | 35 | unit | **yes — the only suite CI runs** |
| Streaming producer jobs | `apps/docker/onchain-stream-txs/tests/unit/` | 78 | unit | no (gap) |
| CI/CD script logic | `scripts/ci/tests/` | 45 | hermetic integration (stub-binary subprocess) | no (gap) |

**158 tests, 158 green**, total runtime under 5 seconds, no skips, no xfail, no quarantine markers, no sleep-based flake patterns.

The suite that exists is small, hermetic and honest. The problem is breadth and wiring, not quality:

- **CI runs one suite of three** (gap — see audit `20260823T145726Z-4db47555`). The 45 CI-script tests are the guards for the deploy gate, the plan-divergence check and the stack map — the very mechanisms that protect production applies — and no workflow executes them.
- **113 of the 158 tests exercise the retired capture lane** — the producer job classes and the shared Kinesis/SQS handlers. Their source is deliberately retained, so the tests remain valid coverage of live library surface; they will be revisited when the handler-cleanup backlog item is picked.
- **Zero tests** on `apps/lambda` (two handlers), on `apps/dabs` (both DLT pipelines and every batch job), and on the DLT expectations themselves (gap).
- **No Terraform policy tooling** anywhere — only `terraform fmt -check` and `terraform validate`, which check syntax, not policy or security posture (gap).
- **Five Bash integration scripts** exist for live-environment validation. Two are DLT-oriented and require a live workspace plus cloud credentials; the HML streaming one was reduced to an unconditional `exit 0` when its capability was retired and is a tombstone to be deleted, not a passing test.
- **Test intent/size is not declared.** No test carries the `Intent: <KIND> — <AC id>` line prescribed by the workspace test-stewardship protocol; by the letter of that rule they are undeclared SCAFFOLD, though in substance they read as durable unit/contract tests. The retrofit is owed (gap).

### Contrato de testes (a pirâmide pretendida)

This is the coverage the post-retirement platform commits to. Each tier names what must exist, not what exists today.

| Tier | Subject | What a test must prove | Cost |
|---|---|---|---|
| unit | shared library modules | every public handler's happy path plus at least one error path, with cloud clients mocked | fast, always in CI |
| unit | Lambda handlers | event parsing, the write contract to its target store, and failure handling on a malformed event | fast, always in CI |
| unit | DABs batch jobs | pure transform and argument-parsing logic isolated from the Spark session | fast, always in CI |
| contract | DLT expectations | each `expect_or_drop` rule accepts a valid record and drops the exact malformed shape it exists to reject, exercised over a stubbed DLT harness | fast, always in CI |
| integration | CI/CD scripts | the deploy gate, destroy acknowledgment, plan-divergence fail-closed path and stack-map integrity, using stub binaries — never real cloud calls | seconds, always in CI |
| static | Terraform | `fmt -check` and `validate` on every stack; a policy/security scanner is the intended addition | seconds, always in CI |
| e2e | live pipeline | one scripted run per release candidate proving raw data reaches a gold table, executed only against a real workspace by an operator | expensive, on demand |

Two rules bind that table. First, **every suite that exists must run in CI** — an unwired test is worth nothing, and the current single-suite wiring is the highest-value gap to close. Second, **an e2e script that can no longer validate anything is deleted, not stubbed** — a script that unconditionally succeeds is worse than no script, because it makes a gate look green.

### Estado runtime tocado

- `utils/tests/unit/`, `apps/docker/onchain-stream-txs/tests/unit/`, `scripts/ci/tests/` — the three pytest suites
- Shell integration scripts under `scripts/` — the live-environment e2e layer
- The CI workflow that invokes pytest (see [[cicd-pipeline]])
- Coverage and cache output, which must be redirected outside the repo tree

### Dependências

- [[cicd-pipeline]] — owns the workflow wiring that decides which suites actually run
- [[medallion-pipelines]] — the DLT expectations that the contract tier must cover
- [[serving-layer]] — the Lambda and export chain that the unit tier must cover
