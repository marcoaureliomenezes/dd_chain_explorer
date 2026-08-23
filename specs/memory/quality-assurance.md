---
slug: quality-assurance
title: Quality Assurance
category: core
tldr: 143 green tests across Lambda handlers, DABs scripts, DLT expectations and CI scripts — every suite runs in CI behind ruff/mypy gates.
summary: Documents the test inventory after the pyramid rebuild (repo-level tests/ covering both Lambda handlers, the DABs job scripts, the DLT expectation contracts and the shared library, plus the scripts/ci hermetic suite), the quality gates now enforced on every pull request (ruff format, ruff check, mypy, pytest, pip-audit, actionlint, terraform fmt/validate), the test-stewardship declarations, the review-gate cadence, and the intended pyramid this platform commits to.
tags:
  - quality-assurance
  - testing
  - test-pyramid
  - anti-slop
last_updated: "2026-08-23"
release_origin: v0.5.0
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

| Suite | Location | Kind | Runs in CI? |
|---|---|---|---|
| Lambda handlers | `tests/lambda/` | unit | yes |
| DABs job scripts + DLT expectations | `tests/dabs/` | unit + contract (stubbed DLT harness) | yes |
| Shared library `dm_chain_utils` | `tests/utils/` | unit | yes |
| CI/CD script logic | `scripts/ci/tests/` | hermetic integration (stub-binary subprocess) | yes |

**143 tests, 143 green**, seconds of runtime, no skips, no xfail, no quarantine markers,
no sleep-based flake patterns. Every suite is executed by the pull-request quality gate —
there is no unwired suite.

Every test declares its intent and size at birth, per the workspace test-stewardship
protocol; the capture-era suites were deleted under a `qa-engineer` verdict, after the
live-surface tests existed, so coverage never dipped to zero in between.

Remaining coverage limits, stated honestly:

- **No Terraform policy tooling** — `terraform fmt -check` and `terraform validate` check
  syntax, not policy or security posture. Least-privilege claims about the CI roles are
  instead asserted by static tests over the bootstrap policy documents.
- **No live e2e**: the raw-to-gold run needs flowing data and a started warehouse, so it
  stays an on-demand operator script rather than a gated tier.
- **Bash integration scripts** for live-environment validation remain in `scripts/`; the
  tombstoned always-succeeding one was deleted rather than kept green.

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

Two rules bind that table. First, **every suite that exists must run in CI** — an unwired test is worth nothing. Second, **an e2e script that can no longer validate anything is deleted, not stubbed** — a script that unconditionally succeeds is worse than no script, because it makes a gate look green.

### Gates enforced on every pull request

`ruff format --check`, `ruff check`, `mypy`, the full pytest set, `pip-audit` over the
pinned lock, `actionlint`, and `terraform fmt -check` + `validate`. A red gate blocks the
merge: `main` requires these checks by branch protection, not by convention.

### Estado runtime tocado

- `tests/` (lambda, dabs, utils) and `scripts/ci/tests/` — the pytest suites
- Shell integration scripts under `scripts/` — the live-environment e2e layer
- The CI quality-gate job that invokes them (see [[cicd-pipeline]])
- Coverage and cache output, which must be redirected outside the repo tree

### Dependências

- [[cicd-pipeline]] — owns the workflow wiring that decides which suites actually run
- [[medallion-pipelines]] — the DLT expectations that the contract tier must cover
- [[serving-layer]] — the Lambda and export chain that the unit tier must cover
