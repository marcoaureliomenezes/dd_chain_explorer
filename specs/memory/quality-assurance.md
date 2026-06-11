---
slug: quality-assurance
title: Quality Assurance
category: core
tldr: Test pyramid, review gates, and quality discipline currently in force for dd-chain-explorer.
summary: Documents the current test inventory (71 streaming-job unit tests + 35 utils unit tests), how they run, the review-gate cadence (alpha qa-only, rc full trio), anti-slop rules, and the known CI wiring gap for the streaming test suite.
tags:
  - quality-assurance
  - testing
  - anti-slop
agent_tier: self-pull
token_estimate: 420
last_updated: "2026-06-11"
release_origin: audit-remediation-r5
---

## Padrões de qualidade

### Test inventory (current)

| Suite | Location | Count | Runner |
|---|---|---|---|
| Streaming-job unit tests | `apps/docker/onchain-stream-txs/tests/unit/` (6 files) | 71 | `pytest apps/docker/onchain-stream-txs/tests/unit/ -p no:cacheprovider` |
| dm-chain-utils unit tests | `utils/tests/unit/` | 35 | `pytest utils/tests/unit/` |

Each of the 5 streaming job classes is covered for: constructor + logger injection (no
`NameError` on instantiation), happy-path processing loop with mocked boto3/web3 clients,
and at least one error path. Security-driven tests cover the SSRF network allowlist
(`etherscan_multi.py`) and exception logging in the decoder.

### Coverage gaps (known, tracked)

- CI runs **only** the utils suite (`deploy_all_dm_applications.yml` test step); the 71
  streaming-job tests are not wired into any workflow — tracked as WS-F5 of the
  `platform-audit-remediation-20260611` backlog epic.
- DLT pipelines, Lambdas, and dabs batch jobs have zero tests.
- No coverage measurement is configured.

### Review gates

- Per release-governance: end of each `alpha-N` → qa-engineer-only review; end of each
  `rc-N` → full trio (qa-engineer + code-reviewer + security-reviewer) must APPROVE
  before push/PR.
- Security reviews are read-only verdict reports; remediation is implemented by
  software-engineer under its own task.

### Anti-slop discipline

- No fabricated tests or SHAs — every validation cites a command and real evidence.
- Tests run with `-p no:cacheprovider`; no cache/state dirs may land in the repo tree.
- Bug records in `specs/bugs/` close only with `fixed_in:` commit evidence, never
  silently.
