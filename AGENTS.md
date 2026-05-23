# dd-chain-explorer — Repo Context

> This file is loaded by Claude Code, OpenCode, and Codex when working in this repo.
> It complements the workspace-root `AGENTS.md` with repo-domain knowledge.
> Edit this file directly — it is NOT lib-originated and will not be overwritten by `dadaia public install`.

---

## Repo Purpose

DD Chain Explorer is a real-time Ethereum blockchain data platform that captures all mainnet
transactions and blocks, processes them through a Medallion architecture on Databricks Delta Live
Tables, and serves analytics via Lakeview dashboards, a Genie AI/BI space, and S3 exports.
It is built for platform engineers and data analysts monitoring API key consumption, gas usage,
and contract activity on the Ethereum mainnet (AWS sa-east-1, Python 3.12, Databricks DBR 15.x).

---

## Spec Structure

Specs live under `specs/`. Load them in this order before making any change:

1. `specs/memory/constitution.md` — absolute laws of the project (immutable constraints)
2. `specs/releases/ACTIVE.md` — which release is active and in which phase
3. `specs/releases/<release-id>/SPEC.md` — what this release changes
4. `specs/releases/<release-id>/PLAN.md` — how to implement it
5. `specs/releases/<release-id>/TASKS.md` — task checklist with owners and evidence

Legacy reference (read-only until archived in R1 CLOSURE):
- `specs/SPEC.md` — original product spec (do NOT use to authorize implementation)
- `specs/domains/*/SPEC.md` — domain specs (do NOT use to authorize implementation)
- `specs/memory/*.md` — Markdown memory atoms (being migrated to HTML across R1–R4)

Approval marker: `**Status:** Aprovado` in the spec header is required before implementation.
`specs/releases/ACTIVE.md` is the SDD gate. Only tasks in the active release's TASKS.md
with a `[-]` IN_PROGRESS marker authorize edits to production files.

---

## Repo-Specific Stop Conditions

- **Do NOT edit any production file** (apps/, services/, utils/) without an active `[-]` task
  marker in `specs/releases/<active-release-id>/TASKS.md`.
- **Do NOT create or edit `specs/memory/*.html`** outside the CLOSURE phase of a release.
  The workspace-protocol gate enforces this. Only `product-engineer` may write memory atoms.
- **Do NOT edit `specs/releases/ACTIVE.md`** unless you are `product-engineer`.
- **Do NOT apply Terraform to PRD** without the CI/CD `production` approval gate.
- **Do NOT hardcode** API keys, catalog names, or bucket names in any file — use Terraform
  variables (`${var.catalog}`) and SSM Parameter Store for runtime secrets.
- **Do NOT use `path=` in `@dlt.table`** — Unity Catalog forbids explicit paths.
- **Stop and surface to operator** if you encounter two `[-]` tasks simultaneously in TASKS.md.

---

## Key Paths

| Path | Purpose |
|------|---------|
| `specs/releases/ACTIVE.md` | Active release pointer — read this first |
| `specs/releases/<id>/TASKS.md` | Task checklist — the SDD gate reads this |
| `specs/memory/` | Atomic product memory (Markdown until R1 CLOSURE; then HTML) |
| `specs/backlog/candidates.md` | Formal backlog including all 7 open operator questions |
| `apps/dabs/` | Databricks Asset Bundles (DLT pipelines, dashboards, alerts, Genie) |
| `apps/docker/onchain-stream-txs/` | Streaming Docker apps (5 jobs) |
| `apps/lambda/` | Lambda functions (contracts_ingestion, gold_to_dynamodb) |
| `services/modules/` | Shared Terraform modules |
| `services/dev/` | DEV infrastructure (Terraform, local state) |
| `services/prd/` | PRD infrastructure (Terraform, remote state, S3 + DynamoDB lock) |
| `utils/` | dm-chain-utils shared library (PyPI: `dm-chain-utils==0.2.9`) |
| `scripts/ci/` | 16 CI bash scripts |

---

## Key Commands

```bash
# DEV streaming
make deploy_dev_stream       # docker compose up --build (5 streaming jobs)
make stop_dev_stream         # docker compose down

# DEV Databricks (DABs)
make dabs_deploy_dev         # databricks bundle deploy --target dev
make dabs_run_trigger_all    # trigger dm-ethereum + dm-app-logs pipelines

# DEV infrastructure (Terraform)
make tf_apply_dev_peripherals  # Terraform apply DEV/01_peripherals
make tf_apply_dev_lambda       # Terraform apply DEV/02_lambda

# Validation
make dabs_validate_all       # validate all 16 bundles (dry-run)

# PRD observability
make prod_standby            # scale down ECS + pause Databricks
make prod_resume             # scale up ECS + resume Databricks
make prod_ecs_logs           # tail live ECS task logs

# Lint / check
make help                    # list all 60+ make targets
```

---

## Release Lifecycle

This repo follows dadaia-workspace SDD (Spec-Driven Development):

```
specs/releases/
  ACTIVE.md                        <- pointer to active release
  pipeline-restart-r1/             <- ACTIVE -- restore pipeline + security (~22 tasks)
  cost-and-availability-r2/        <- Draft -- cost + availability (~8 tasks)
  data-quality-r3/                 <- Draft -- correctness (~14 tasks)
  analytics-enrichment-r4/         <- Draft -- analytics UX + PRD readiness (~10 tasks)
```

Releases are sequential: R1 must be ARCHIVED before R2 begins. Implementers pick tasks
from TASKS.md using `[ ]` -> `[-]` -> `[x]` markers per `dadaia-task-manager` protocol.

---

## Domain Agent Assignments (from PM mediation)

| Domain | Primary Agent | Write-set |
|--------|-------------|-----------|
| AWS IAM, ECS, Terraform | devops-engineer | `services/` |
| DLT pipelines, schema, DLT tests | data-engineer | `apps/dabs/dlt_ethereum/` |
| Dashboards, Genie, alerts | data-analyst | `apps/dabs/dashboard_*/`, `apps/dabs/genie_*`, `apps/dabs/alert_*` |
| dm-chain-utils library | software-engineer-python | `utils/` |
| Repository hygiene (.gitignore, bundle cleanup) | software-engineer-python | root, `apps/dabs/` |
| Spec / memory atoms | product-engineer | `specs/releases/`, `specs/memory/` |
