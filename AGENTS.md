# dd-chain-explorer — Repo Context

> Loaded by every harness (Claude Code, Codex, Kimi Code) working in this repo.
> Complements the workspace-root `AGENTS.md`/`DADAIA.md` with repo-domain
> knowledge. Edit this file directly — it is not lib-originated.

---

## Repo purpose

`dd-chain-explorer` is the downstream half of an Ethereum data platform: a
separate repository, `dd-chain-capture` (running on a VPS), writes raw
blockchain JSON to this project's S3 raw bucket — the **sole** integration
boundary between the two. Everything in this repo starts from that S3
prefix: Databricks Delta Live Tables (Bronze → Silver → Gold on Unity
Catalog), Lakeview dashboards, two AWS Lambda functions, the Terraform that
provisions all of it (dev/hml/prd), and the GitHub Actions CI/CD pipeline.

**No capture technology lives here** — no Kinesis, no Firehose, no SQS, no
ECS producer service. Do not reintroduce them; the S3 bucket is the boundary
(see `specs/memory/tech-stack.md`).

Databricks runs on the **Free Edition**: serverless compute only, no job
clusters, no instance pools, and no `prod` deployment target exists there
(only `dev` and `hml`).

---

## Spec structure — read before any change

1. `specs/constitution.md` — durable, repo-scoped laws.
2. `specs/releases/ACTIVE.md` — which release is active and in which phase.
3. `specs/releases/<release-id>/SPEC.md` / `PLAN.md` / `TASKS.md` — what/how/
   task-checklist for the active release. Every one must carry
   `**Status:** Aprovado` before it authorizes implementation.
4. `specs/memory/*.md` and `specs/memory/product/*.md` — current product/
   architecture/tech-stack truth (Markdown atoms, `catalog.json` indexes
   `product/`).

Legacy/history: `specs/_archive/**` — read-only, never a source of approval.

---

## Repo-specific stop conditions

- Do not edit any production path (`apps/`, `services/`, `utils/`, `scripts/`,
  `tests/`) without an active `[-]` task marker in the active release's
  `TASKS.md` naming that write set.
- Do not write `specs/memory/**` outside the DEFINITION/CLOSURE phase of a
  release — only `product-engineer` writes memory, and only then.
- Do not apply Terraform to `prd` without going through the CI/CD gate
  (`scripts/ci/plan_env.sh` → the informed environment gate →
  `scripts/ci/deploy_env.sh`) — the one exception is `services/prd/00_bootstrap`,
  which CI can **never** apply (see `docs/runbooks/00-bootstrap-apply.md`).
- Do not hardcode API keys, catalog names, or bucket names — use Terraform
  variables and SSM Parameter Store for runtime secrets. Log the SSM
  *parameter name*, never the value.
- Do not use `path=` in `@dlt.table` — Unity Catalog forbids explicit paths.
- Do not pin `dm-chain-utils` against a public package index — it is a path
  requirement only (`pip install ./utils --no-deps`); the name was never
  published anywhere.
- Stop and surface to the operator if you find two `[-]` tasks simultaneously
  in `TASKS.md` — that is an invariant violation, not something to silently
  resolve.

---

## Key paths

| Path | Purpose |
|------|---------|
| `specs/releases/ACTIVE.md` | Active release pointer — read this first |
| `specs/releases/<id>/TASKS.md` | Task checklist — the human-auditable reservation trace |
| `specs/memory/` | Current product/architecture/tech-stack truth |
| `specs/backlog/BACKLOG.md` | Single-source backlog (ACTIVE + LEDGER) |
| `apps/dabs/` | Databricks Asset Bundles (DLT pipelines, batch jobs, dashboards) |
| `apps/lambda/` | Lambda functions (`contracts_ingestion`, `gold_to_dynamodb`) + `requirements.txt` |
| `utils/` | `dm_chain_utils` shared library (path-installed only) |
| `services/dev/`, `services/hml/`, `services/prd/` | Terraform, one root stack per numbered directory |
| `services/modules/` | Shared Terraform modules |
| `scripts/ci/` | Scripts GitHub Actions runs; `stack_map.json` is the single source for stack names/order |
| `scripts/build_lambda_layer.sh` | The only supported way to build the Lambda layer |
| `tests/` | Repo-level pytest tree — Lambda handlers, kept `dm_chain_utils` modules, DABs pure functions, DLT expectation contracts |
| `docs/runbooks/` | Operator-only, one-time procedures |

---

## Key commands

```bash
make check              # ruff format --check + ruff check + mypy + pytest
make test                # pytest tests/ utils/tests/unit scripts/ci/tests
make build_lambda_layer   # scripts/build_lambda_layer.sh
make dabs_validate_all     # validate every apps/dabs bundle, target=dev
make dev_tf_apply           # DEV Terraform, no CI gate
make tf_plan ENV=hml          # HML/PRD Terraform, same script CI runs
make help                       # every target
```

---

## Release lifecycle

This repo follows the dadaia-workspace SDD flow (see the workspace-root
`DADAIA.md` §1/§5): `specs/releases/<id>/{SPEC,PLAN,TASKS}.md`, reserved with
`[ ]` → `[-]` → `[x]` markers, reviewed at `alpha-N`/`rc-N` boundaries, closed
with `CLOSURE.md` + a memory update + archive to `specs/_archive/`. Live
implementation and its reviews happen on `feature/{M.m.p}`; `develop` is the
only pushable branch.

Five workstreams share this release's write sets: WS-A (CI auth, workflow
purge, governance, the version axis), WS-B (Terraform, live AWS cleanup),
WS-C (Databricks artifacts), WS-D (dead code, supply chain, quality gates,
tests, docs — this file's own domain), WS-E (governance documents, audit
dispositions, memory). See the active release's `TASKS.md` write-set law for
the exact boundaries.
