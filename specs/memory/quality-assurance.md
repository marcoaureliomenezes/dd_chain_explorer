---
slug: quality-assurance
title: Quality Assurance
category: core
tldr: Hermetic contract suites in three repos — infra CI/stack/IAM/region/seed contracts, explorer parser + bundle-shape + no-DLT + e2e-verify tests, capture publish contract — every suite in CI; live proof is the chain run (AC-22) and the rebuild drill (AC-29).
summary: The test and gate contract after release v0.7.0. Infra scripts/ci/tests pin the stack map, plan-as-detector lanes, gated waves, service-namespace grant coverage, bootstrap minimality, region single-source, capture runtime, account/workspace/UC/GitHub stacks and the chain; scripts/seed/tests drive the trust seed against stubs. Explorer tests cover the pure parsers on fixtures, the job_market_data contract (exactly one bundle, one job, three ordered serverless tasks, file-arrival, no host literal, no schemas resource), the no-dlt grep and e2e-verify. Capture pins publish-images. Gates — ruff, mypy, pytest, pip-audit, actionlint, zizmor, terraform fmt/validate.
tags:
  - quality
  - testing
  - contract-tests
  - ci
last_updated: "2026-09-23"
release_origin: v0.7.0
---

## Padrões de qualidade

**Status 2026-09-23.** Suites exist on the `feature/0.7.0` branches; the live proofs
(AC-22 chain, AC-29 drill, AC-30 cost) have not run.

### Review gates

- Each repo's `feature/0.7.0 → develop` PR needs CI green and a reviewer APPROVED verdict,
  security lens included; the bootstrap delta needs a security verdict before any apply.

### Anti-slop discipline

- No fabricated evidence: every AC cites a real command and CI run id; no account id,
  host or personal identifier in evidence (public repos).
- Root cause first: bug record + RED test before the fix (e.g. the `scheduler` grant
  family pinned by the namespace-coverage test).
- Tests run with `-p no:cacheprovider`; nothing cached in a repo tree.

## Disciplina de testes

### Inventário atual

| Repo | Suite | Kind |
|---|---|---|
| infra | `scripts/ci/tests/` — stack map, lanes, gated waves, plan gate, deploy path, namespace coverage, bootstrap policy + delta, boundary guards, region move, capture runtime, account/workspace/UC/GitHub stacks, chain, CI governance, no secret defaults | hermetic contract/integration (stub binaries) |
| infra | `scripts/seed/tests/` — trust seed run 1 / run 2 / dry-run, no secret in argv or output | integration against stubs |
| explorer | `tests/market_data/` — parsers on real-format fixtures (COTAHIST `preult` ÷100, 244-char line rejected, Latin-1 round-trip, max VERSAO, YTD differencing), contract helpers | unit, no Spark |
| explorer | `tests/dabs/` — exactly one bundle, job shape, repository shape | contract |
| explorer | `tests/ci/` — workflow contract, `e2e_verify` | contract |
| capture | `tests/ci/` — `publish-images.yml` (region, roles) | contract |

### Contrato de testes

| Tier | Proves | Where |
|---|---|---|
| unit | parsers reject, never coerce | explorer, every PR |
| contract | CI/IaC shape: map, lanes, grants, region, bundle, no DLT | every PR |
| e2e | a landed partition reaches gold, rerun changes nothing | chain run `e2e-verify` (AC-22) |
| resilience | workspace destroy + rebuild keeps every table and count | rebuild drill (AC-29) |

### Gates enforced on every pull request

`ruff format --check`, `ruff check`, `mypy`, `pytest`, `pip-audit`, `actionlint`, `zizmor`;
infra adds `terraform fmt -check` + `validate` and per-stack plans; explorer adds
`bundle validate -t dev`.

### Dependências

- [[cicd-pipeline]] — wires every suite; [[medallion-pipelines]] — the parsers and job
  under test
